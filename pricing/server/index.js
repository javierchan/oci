'use strict';

const express = require('express');
const path    = require('path');
const https   = require('https');
const fs      = require('fs');
const { normalizeCatalog, searchProducts, searchPresets, searchServiceRegistry } = require('./catalog');
const { quoteFromPrompt, buildQuote } = require('./quotation-engine');
const { parseWorkbookBase64, workbookToRequests, analyzeWorkbookForGuidedQuote, buildShapeOptionsForProcessor, parseWorkbookPromptSelections, hasWorkbookSelection } = require('./excel');
const { normalizeProcessorVendor, findVmShapeByText } = require('./vm-shapes');
const { loadGenAISettings, runChat, extractChatText } = require('./genai');
const { resolveGenAIRequestOptions } = require('./genai-profiles');
const { respondToAssistant } = require('./assistant');
const sessionStore = require('./session-store');
const { buildQuoteExportRows, buildQuoteExportCsv, buildQuoteExportWorkbook } = require('./quote-export');
const {
  PricingError,
  GenAIError,
  CatalogError,
  SessionConflictError,
  ValidationError,
  handleError,
  normalizeError,
} = require('./errors');
const { buildRequestLogger, createTrace, logger, summarizeTrace } = require('./logger');

const app  = express();
const PORT = process.env.PORT || 8742;

app.use(express.json({ limit: '25mb' }));

function resolveClientId(req) {
  // Internal/development trust model: the caller supplies x-client-id (or clientId in
  // the body) and the server scopes session access to that value. This is acceptable
  // for local tooling, but production deployment should replace this with an
  // authenticated principal/token lookup before reading or mutating session state.
  return String(req.get('x-client-id') || req.body?.clientId || 'anonymous').trim() || 'anonymous';
}

function createRequestId() {
  return `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function resolveAssistantSessionContext(storedSession, _requestBodySessionContext) {
  if (!storedSession?.sessionContext || typeof storedSession.sessionContext !== 'object') return null;
  return storedSession.sessionContext;
}

function mapStoredConversation(messages) {
  return Array.isArray(messages)
    ? messages.map((item) => ({
        role: item.role === 'agent' ? 'assistant' : item.role,
        content: item.content,
      }))
    : [];
}

// ════════════════════════════════════════════════════════════
//  OCI GenAI — Config from environment
// ════════════════════════════════════════════════════════════
function loadOciConfig(requestLogger = logger) {
  const genai = loadGenAISettings(process.env);
  const user        = process.env.OCI_USER        || '';
  const tenancy     = process.env.OCI_TENANCY      || '';
  const fingerprint = process.env.OCI_FINGERPRINT  || '';
  const region      = genai.region || process.env.OCI_REGION || 'us-chicago-1';
  const compartment = genai.compartmentId || process.env.OCI_COMPARTMENT || tenancy;
  const modelId     = genai.modelId || process.env.OCI_GENAI_MODEL || '';
  const endpoint    = genai.endpoint;
  const profile     = genai.profile;
  const defaultProfile = genai.defaultProfile;

  let privateKeyPem = '';
  const keyContent = process.env.OCI_PRIVATE_KEY || '';
  const keyContentB64 = process.env.OCI_PRIVATE_KEY_B64 || '';
  const keyPath    = process.env.OCI_KEY_FILE    || '';
  if (keyContentB64) {
    try { privateKeyPem = Buffer.from(keyContentB64, 'base64').toString('utf8'); }
    catch(e) {
      requestLogger.warn({ event: 'config.private_key_b64_decode_failed', errorMessage: e.message }, 'OCI_PRIVATE_KEY_B64 decode failed');
    }
  } else if (keyContent) {
    privateKeyPem = keyContent.replace(/\\n/g, '\n');
  }
  else if (keyPath) {
    try { privateKeyPem = fs.readFileSync(keyPath, 'utf8'); }
    catch(e) {
      requestLogger.warn({ event: 'config.private_key_file_unreadable', errorMessage: e.message, keyPath }, 'OCI_KEY_FILE not readable');
    }
  }

  const ok = !!(user && tenancy && fingerprint && privateKeyPem);
  return {
    user,
    tenancy,
    fingerprint,
    region,
    compartment,
    modelId,
    endpoint,
    profile,
    defaultProfile,
    intentModelId: genai.intentModelId,
    narrativeModelId: genai.narrativeModelId,
    discoveryModelId: genai.discoveryModelId,
    imageModelId: genai.imageModelId,
    privateKeyPem,
    ok,
  };
}

function ensureOciConfig(requestLogger = logger) {
  const cfg = loadOciConfig(requestLogger);
  if (!cfg.ok) {
    throw new GenAIError('OCI GenAI is not configured.', {
      code: 'GENAI_NOT_CONFIGURED',
      httpStatus: 503,
    });
  }
  return cfg;
}

function createHttpError(message, { code = 'INTERNAL_ERROR', httpStatus = 500, data = null, expose = true, cause = null } = {}) {
  return new PricingError(message, {
    code,
    httpStatus,
    data,
    expose,
    cause,
  });
}

function logRequestFailure(requestLogger, trace, method, error, message) {
  const normalized = normalizeError(error);
  const logLevel = normalized.httpStatus >= 500 ? 'error' : 'warn';
  requestLogger?.[logLevel]?.({
    event: 'http.request.failure',
    method,
    statusCode: normalized.httpStatus,
    errorCode: normalized.code,
    errorMessage: error?.message || normalized.message,
    ...summarizeTrace(trace),
  }, message);
  return normalized;
}

const WORKBOOK_ENRICHMENT_PROMPT = [
  'You are enriching an OCI workbook estimation response that was already calculated deterministically.',
  'Do not change any totals, numbers, SKUs, warnings, or assumptions.',
  'Do not invent migration facts.',
  'Do not restate counts, totals, or arithmetic from the workbook summary.',
  'Write concise markdown with the tone of an OCI VMware migration specialist.',
  'Only describe the workbook as RVTools or VMware inventory if the provided source type says so.',
  'If the source type is a generic inventory workbook, do not call it RVTools.',
  'Return:',
  '- OCI migration notes if the workbook clearly looks like RVTools or VMware inventory',
  '- OCI next checks if there are warnings that imply follow-up work',
].join('\n');

function sanitizeWorkbookEnrichment(text) {
  const source = String(text || '').trim();
  if (!source) return '';
  const lines = source.split('\n');
  const kept = [];
  let activeSection = '';
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (kept.length && kept[kept.length - 1] !== '') kept.push('');
      continue;
    }
    if (/^#{1,6}\s+/i.test(trimmed)) {
      if (/migration notes/i.test(trimmed)) {
        activeSection = 'migration';
      } else if (/next checks/i.test(trimmed)) {
        activeSection = 'next-checks';
      } else {
        activeSection = '';
      }
      continue;
    }
    if (!activeSection) continue;
    if (/\$|estimated monthly|estimated annual|processed .* into|count|total|the provided rvtools export was successfully processed|the estimation detected the following warnings/i.test(trimmed)) continue;
    kept.push(line);
  }
  return kept.join('\n').trim();
}

function buildWorkbookFallbackSummary({ fileName, requests, warnings, totals }) {
  const currencyCode = totals?.currencyCode || 'USD';
  const requestCount = Array.isArray(requests) ? requests.length : 0;
  const sourceType = Array.isArray(requests) && requests.some((item) => item?.metadata?.inventorySource === 'rvtools')
    ? 'rvtools'
    : Array.isArray(requests) && requests.some((item) => item?.metadata?.inventorySource === 'inventory_workbook')
      ? 'inventory_workbook'
      : 'generic_workbook';
  const isRvTools = sourceType === 'rvtools';
  const isInventoryWorkbook = sourceType === 'inventory_workbook';
  const dominantShapes = Array.isArray(requests)
    ? Array.from(new Set(requests.map((item) => item?.shapeSeries).filter(Boolean))).slice(0, 3)
    : [];
  const hasExplicitSelectedShape = Array.isArray(warnings) && warnings.some((item) => /selected oci target shape/i.test(String(item)));
  const lines = [
    `## OCI Expert Summary`,
    `- Processed \`${fileName}\` into ${requestCount} OCI-native sizing request${requestCount === 1 ? '' : 's'}.`,
    `- Estimated monthly total: ${formatMoney(totals?.monthly || 0, currencyCode)}.`,
    `- Estimated annual total: ${formatMoney(totals?.annual || 0, currencyCode)}.`,
  ];
  if (dominantShapes.length && !hasExplicitSelectedShape) {
    lines.push(`- Dominant OCI compute profiles inferred: ${dominantShapes.map((item) => `\`${item}\``).join(', ')}.`);
  }
  if (isRvTools) {
    lines.push('');
    lines.push('## OCI Migration Notes');
    lines.push('- This workbook was treated as VMware inventory and mapped to OCI compute plus block storage sizing.');
    lines.push('- For x86 VMs, the import uses `2 VMware vCPUs = 1 OCI OCPU`.');
    lines.push('- This is infrastructure sizing guidance; application compatibility, VMware platform services, and OS licensing still need migration review.');
  } else if (isInventoryWorkbook) {
    lines.push('');
    lines.push('## OCI Migration Notes');
    lines.push('- This workbook was treated as a structured infrastructure inventory and mapped heuristically to OCI-native compute plus block storage sizing.');
    lines.push('- Validate the inferred OCI shape family and operating-system-specific licensing before using the estimate as a migration baseline.');
  }
  if (Array.isArray(warnings) && warnings.length) {
    lines.push('');
    lines.push('## OCI Next Checks');
    lines.push(...warnings.slice(0, 3).map((item) => `- ${item}`));
  }
  return lines.join('\n');
}

async function buildWorkbookEnrichment(cfg, { fileName, requests, warnings, totals, lineItems }) {
  const fallback = buildWorkbookFallbackSummary({ fileName, requests, warnings, totals });
  const sourceType = Array.isArray(requests) && requests.some((item) => item?.metadata?.inventorySource === 'rvtools')
    ? 'rvtools'
    : Array.isArray(requests) && requests.some((item) => item?.metadata?.inventorySource === 'inventory_workbook')
      ? 'inventory_workbook'
      : 'generic_workbook';
  if (!cfg?.ok || !Array.isArray(lineItems) || !lineItems.length) return fallback;
  if (sourceType !== 'rvtools') return fallback;
  const currencyCode = totals?.currencyCode || 'USD';
  const requestCount = Array.isArray(requests) ? requests.length : 0;
  const contextBlock = [
    `Workbook: ${fileName}`,
    'Expert role: OCI VMware migration specialist',
    `Source type: ${sourceType}`,
    `Requests detected: ${requestCount}`,
    `Monthly total: ${formatMoney(totals?.monthly || 0, currencyCode)}`,
    `Annual total: ${formatMoney(totals?.annual || 0, currencyCode)}`,
    `Warnings:\n${(warnings || []).slice(0, 6).map((item) => `- ${item}`).join('\n')}`,
    `Representative OCI lines:\n${lineItems.slice(0, 10).map((line) => `- ${line.service || '-'} | ${line.product} | ${line.metric || '-'} | monthly ${formatMoney(line.monthly, currencyCode)}`).join('\n')}`,
  ].filter(Boolean).join('\n\n');
  const requestOptions = resolveGenAIRequestOptions('narrative', cfg);

  try {
    const response = await runChat({
      cfg,
      ...requestOptions,
      systemPrompt: WORKBOOK_ENRICHMENT_PROMPT,
      messages: [{ role: 'user', content: contextBlock }],
    });
    const enrichment = sanitizeWorkbookEnrichment(extractChatText(response?.data || response).trim());
    return enrichment ? `${fallback}\n\n## OCI Expert Notes\n${enrichment}` : fallback;
  } catch (_error) {
    return fallback;
  }
}

function formatMoney(value, currencyCode = 'USD') {
  const num = Number(value);
  if (!Number.isFinite(num)) return `${currencyCode} -`;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currencyCode,
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(num);
}

function buildMarkdownFromLinesForAssistant(lines, totals) {
  if (!Array.isArray(lines) || !lines.length) return '';
  const header = '| # | Environment | Service | Part# | Product | Metric | Qty | Inst | Hours | Rate | Unit | $/Mo | Annual |\n|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|';
  const body = lines.map((line, i) => `| ${i + 1} | ${line.environment || '-'} | ${line.service || '-'} | ${line.partNumber || '-'} | ${line.product || '-'} | ${line.metric || '-'} | ${Number.isFinite(Number(line.quantity)) ? Number(line.quantity) : '-'} | ${Number.isFinite(Number(line.instances)) ? Number(line.instances) : '-'} | ${Number.isFinite(Number(line.hours)) ? Number(line.hours) : '-'} | ${Number.isFinite(Number(line.rate)) ? Number(line.rate) : '-'} | ${formatMoney(line.unitPrice, line.currencyCode || 'USD')} | ${formatMoney(line.monthly, line.currencyCode || 'USD')} | ${formatMoney(line.annual, line.currencyCode || 'USD')} |`).join('\n');
  const total = `| Total | - | - | - | - | - | - | - | - | - | - | ${formatMoney(totals?.monthly, totals?.currencyCode || 'USD')} | ${formatMoney(totals?.annual, totals?.currencyCode || 'USD')} |`;
  return `${header}\n${body}\n${total}`;
}

function buildQuoteExportHttpResponse(clientId, sessionId, format = 'csv') {
  const session = sessionStore.getSession(clientId, sessionId);
  if (!session) {
    return {
      error: createHttpError('Session not found.', {
        code: 'SESSION_NOT_FOUND',
        httpStatus: 404,
      }),
    };
  }
  const quoteExport = session.sessionContext?.quoteExport;
  if (!quoteExport?.lineItems?.length) {
    return {
      error: createHttpError('No exportable quote found in this session.', {
        code: 'QUOTE_EXPORT_NOT_FOUND',
        httpStatus: 404,
      }),
    };
  }
  const normalizedFormat = String(format || 'csv').trim().toLowerCase();
  if (normalizedFormat === 'json') {
    return {
      status: 200,
      json: {
        ok: true,
        quoteExport,
      },
    };
  }
  if (normalizedFormat === 'xlsx') {
    return {
      status: 200,
      headers: {
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'Content-Disposition': `attachment; filename="${sessionId}-quote.xlsx"`,
      },
      body: buildQuoteExportWorkbook(quoteExport.lineItems, quoteExport.totals),
    };
  }
  return {
    status: 200,
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${sessionId}-quote.csv"`,
    },
    body: buildQuoteExportCsv(quoteExport.lineItems, quoteExport.totals),
  };
}

function getEffectiveWorkbookContext(storedSession) {
  const session = storedSession && typeof storedSession === 'object' ? storedSession : null;
  const workbookContext = session?.workbookContext && typeof session.workbookContext === 'object'
    ? session.workbookContext
    : null;
  const sessionWorkbookContext = session?.sessionContext?.workbookContext && typeof session.sessionContext.workbookContext === 'object'
    ? session.sessionContext.workbookContext
    : null;
  const lastQuote = session?.sessionContext?.lastQuote && typeof session.sessionContext.lastQuote === 'object'
    ? session.sessionContext.lastQuote
    : null;
  return {
    ...(sessionWorkbookContext || {}),
    ...(workbookContext || {}),
    sourcePlatform: workbookContext?.sourcePlatform || sessionWorkbookContext?.sourcePlatform || lastQuote?.sourcePlatform || null,
    processorVendor: workbookContext?.processorVendor || sessionWorkbookContext?.processorVendor || lastQuote?.processorVendor || null,
    shapeName: workbookContext?.shapeName || sessionWorkbookContext?.shapeName || lastQuote?.shapeName || null,
    vpuPerGb: Number.isFinite(Number(workbookContext?.vpuPerGb))
      ? Number(workbookContext.vpuPerGb)
      : Number.isFinite(Number(sessionWorkbookContext?.vpuPerGb))
        ? Number(sessionWorkbookContext.vpuPerGb)
        : Number.isFinite(Number(lastQuote?.vpuPerGb))
          ? Number(lastQuote.vpuPerGb)
          : null,
    fileName: workbookContext?.fileName || sessionWorkbookContext?.fileName || null,
    contentBase64: workbookContext?.contentBase64 || sessionWorkbookContext?.contentBase64 || null,
  };
}

async function estimateWorkbookRequest({ cfg, clientId, sessionId, body, persistMessages = false }) {
  const storedSession = sessionId ? sessionStore.getSession(clientId, sessionId) : null;
  const persistedWorkbook = getEffectiveWorkbookContext(storedSession);
  const userLabel = String(body.userLabel || '').trim();
  const fileName = String(body.fileName || persistedWorkbook.fileName || 'workbook.xlsx');
  const contentBase64 = String(body.contentBase64 || persistedWorkbook.contentBase64 || '');
  const requestedShape = findVmShapeByText(body.shapeName || persistedWorkbook.shapeName || '');
  const sourcePlatform = String(body.sourcePlatform || persistedWorkbook.sourcePlatform || '').trim().toLowerCase();
  const processorVendor = normalizeProcessorVendor(body.processorVendor)
    || normalizeProcessorVendor(requestedShape?.vendor)
    || normalizeProcessorVendor(persistedWorkbook.processorVendor);
  const shapeName = requestedShape?.shapeName || String(body.shapeName || persistedWorkbook.shapeName || '').trim().toUpperCase();
  const vpuValue = body.vpuPerGb;
  const vpuPerGb = Number(vpuValue);
  const workbookContextPatch = {
    fileName,
    contentBase64,
    sourcePlatform: sourcePlatform || storedSession?.workbookContext?.sourcePlatform || null,
    processorVendor: processorVendor || storedSession?.workbookContext?.processorVendor || null,
    shapeName: shapeName || storedSession?.workbookContext?.shapeName || null,
    vpuPerGb: Number.isFinite(vpuPerGb) && vpuPerGb > 0
      ? vpuPerGb
      : (Number.isFinite(Number(storedSession?.workbookContext?.vpuPerGb)) ? Number(storedSession.workbookContext.vpuPerGb) : null),
  };
  if (!contentBase64) {
    return {
      error: new ValidationError('Workbook contentBase64 is required.', {
        code: 'WORKBOOK_CONTENT_REQUIRED',
      }),
    };
  }

  try {
    if (persistMessages && storedSession && userLabel) {
      sessionStore.appendMessage(clientId, sessionId, {
        role: 'user',
        content: userLabel,
      });
    }
    const workbook = parseWorkbookBase64(contentBase64);
    const analysis = analyzeWorkbookForGuidedQuote(workbook);
    if (!analysis.quotableRows) {
      return {
        error: new ValidationError('No quotable rows were detected in the workbook.', {
          code: 'WORKBOOK_NO_QUOTABLE_ROWS',
        }),
      };
    }
    if (!sourcePlatform && analysis.sourceType !== 'rvtools') {
      const question = `I analyzed \`${fileName}\` and found ${analysis.quotableRows} quotable workload${analysis.quotableRows === 1 ? '' : 's'}. Do these workbook rows come from VMware, another hypervisor, or bare metal inventory?`;
      if (storedSession) {
        sessionStore.updateSessionState(clientId, sessionId, {
          workbookContext: workbookContextPatch,
          sessionContext: {
            ...(storedSession.sessionContext || {}),
            currentIntent: 'workbook_quote',
            pendingClarification: {
              stage: 'sourcePlatform',
              question,
              options: analysis.sourcePlatformOptions || [],
            },
            workbookContext: workbookContextPatch,
          },
        });
        if (persistMessages) {
          const reply = [question, analysis.warnings?.length ? `\n\nNotes:\n- ${analysis.warnings.slice(0, 3).join('\n- ')}` : ''].join('');
          sessionStore.appendMessage(clientId, sessionId, { role: 'assistant', content: reply });
        }
      }
      return {
        status: 200,
        body: {
          ok: true,
          mode: 'excel_clarification',
          stage: 'sourcePlatform',
          fileName,
          sourceType: analysis.sourceType,
          quotableRows: analysis.quotableRows,
          shapeName: shapeName || null,
          processorVendor: processorVendor || null,
          vpuPerGb: Number.isFinite(vpuPerGb) && vpuPerGb > 0 ? vpuPerGb : null,
          question,
          options: analysis.sourcePlatformOptions || [],
          warnings: analysis.warnings || [],
        },
      };
    }
    const effectiveSourcePlatform = sourcePlatform || (analysis.sourceType === 'rvtools' ? 'vmware' : 'bare_metal');
    if (!processorVendor) {
      const question = `I analyzed \`${fileName}\` and found ${analysis.quotableRows} quotable workload${analysis.quotableRows === 1 ? '' : 's'}. Which OCI processor family should I use for the target compute shapes?`;
      if (storedSession) {
        sessionStore.updateSessionState(clientId, sessionId, {
          workbookContext: { ...workbookContextPatch, sourcePlatform: effectiveSourcePlatform },
          sessionContext: {
            ...(storedSession.sessionContext || {}),
            currentIntent: 'workbook_quote',
            pendingClarification: {
              stage: 'processor',
              question,
              options: analysis.processorOptions || [],
            },
            workbookContext: { ...workbookContextPatch, sourcePlatform: effectiveSourcePlatform },
          },
        });
        if (persistMessages) {
          const reply = [question, analysis.warnings?.length ? `\n\nNotes:\n- ${analysis.warnings.slice(0, 3).join('\n- ')}` : ''].join('');
          sessionStore.appendMessage(clientId, sessionId, { role: 'assistant', content: reply });
        }
      }
      return {
        status: 200,
        body: {
          ok: true,
          mode: 'excel_clarification',
          stage: 'processor',
          fileName,
          sourceType: analysis.sourceType,
          quotableRows: analysis.quotableRows,
          sourcePlatform: effectiveSourcePlatform,
          shapeName: shapeName || null,
          vpuPerGb: Number.isFinite(vpuPerGb) && vpuPerGb > 0 ? vpuPerGb : null,
          question,
          options: analysis.processorOptions,
          warnings: analysis.warnings || [],
        },
      };
    }
    const shapeOptions = buildShapeOptionsForProcessor(processorVendor);
    if (!shapeName) {
      const question = `Use ${processorVendor.toUpperCase()} as the target processor. Which flex shape should I apply to the workbook sizing?`;
      if (storedSession) {
        sessionStore.updateSessionState(clientId, sessionId, {
          workbookContext: { ...workbookContextPatch, sourcePlatform: effectiveSourcePlatform, processorVendor },
          sessionContext: {
            ...(storedSession.sessionContext || {}),
            currentIntent: 'workbook_quote',
            pendingClarification: {
              stage: 'shape',
              question,
              options: shapeOptions,
            },
            workbookContext: { ...workbookContextPatch, sourcePlatform: effectiveSourcePlatform, processorVendor },
          },
        });
        if (persistMessages) {
          const reply = [question, analysis.warnings?.length ? `\n\nNotes:\n- ${analysis.warnings.slice(0, 3).join('\n- ')}` : ''].join('');
          sessionStore.appendMessage(clientId, sessionId, { role: 'assistant', content: reply });
        }
      }
      return {
        status: 200,
        body: {
          ok: true,
          mode: 'excel_clarification',
          stage: 'shape',
          fileName,
          sourceType: analysis.sourceType,
          quotableRows: analysis.quotableRows,
          sourcePlatform: effectiveSourcePlatform,
          processorVendor,
          vpuPerGb: Number.isFinite(vpuPerGb) && vpuPerGb > 0 ? vpuPerGb : null,
          question,
          options: shapeOptions,
          warnings: analysis.warnings || [],
        },
      };
    }
    const selectedShape = shapeOptions.find((option) => option.value === shapeName);
    if (!selectedShape) {
      return {
        error: new ValidationError(`Shape ${shapeName} is not a valid flex shape for ${processorVendor}.`, {
          code: 'INVALID_SHAPE_SELECTION',
        }),
      };
    }
    const { requests, warnings: workbookWarnings } = workbookToRequests(workbook, {
      sourcePlatform: effectiveSourcePlatform,
      processorVendor,
      shapeName,
      vpuPerGb: Number.isFinite(vpuPerGb) && vpuPerGb > 0 ? vpuPerGb : null,
    });
    const results = requests.map((request) => buildQuote(store.normalized, request));
    const lineItems = results.flatMap((result) => result.lineItems || []);
    const warnings = [...(workbookWarnings || []), ...results.flatMap((result) => result.warnings || [])];
    const errors = results.filter((result) => !result.ok).map((result) => result.error);
    const totals = lineItems.reduce((acc, line) => {
      acc.monthly += line.monthly;
      acc.annual += line.annual;
      acc.currencyCode = line.currencyCode;
      return acc;
    }, { monthly: 0, annual: 0, currencyCode: 'USD' });
    const summary = await buildWorkbookEnrichment(cfg, {
      fileName,
      requests,
      warnings,
      totals,
      lineItems,
    });
    if (storedSession) {
      sessionStore.updateSessionState(clientId, sessionId, {
        workbookContext: {
          ...workbookContextPatch,
          sourcePlatform: effectiveSourcePlatform,
          processorVendor,
          shapeName,
          vpuPerGb: Number.isFinite(vpuPerGb) && vpuPerGb > 0 ? vpuPerGb : workbookContextPatch.vpuPerGb,
        },
        sessionContext: {
          ...(storedSession.sessionContext || {}),
          currentIntent: 'workbook_quote',
          pendingClarification: null,
          workbookContext: {
            ...workbookContextPatch,
            sourcePlatform: effectiveSourcePlatform,
            processorVendor,
            shapeName,
            vpuPerGb: Number.isFinite(vpuPerGb) && vpuPerGb > 0 ? vpuPerGb : workbookContextPatch.vpuPerGb,
          },
          lastQuote: {
            type: 'workbook_quote',
            label: shapeName || fileName || 'Workbook quote',
            monthly: Number(totals?.monthly || 0),
            annual: Number(totals?.annual || 0),
            currencyCode: totals?.currencyCode || 'USD',
            lineItemCount: Array.isArray(lineItems) ? lineItems.length : 0,
            shapeName: shapeName || '',
            processorVendor: processorVendor || '',
            sourcePlatform: effectiveSourcePlatform || '',
            vpuPerGb: Number.isFinite(vpuPerGb) && vpuPerGb > 0 ? vpuPerGb : workbookContextPatch.vpuPerGb,
          },
          quoteExport: {
            formatVersion: 1,
            generatedAt: new Date().toISOString(),
            totals,
            lineItems,
          },
          sessionSummary: `Active workbook ${fileName} using ${shapeName || 'workbook sizing'} with ${Number.isFinite(vpuPerGb) && vpuPerGb > 0 ? vpuPerGb : workbookContextPatch.vpuPerGb || 10} VPU. Last workbook quote monthly ${formatMoney(totals?.monthly || 0, totals?.currencyCode || 'USD')}.`,
        },
      });
      if (persistMessages) {
        const message = `### Excel quotation\n\n${summary || ''}\n\n${buildMarkdownFromLinesForAssistant(lineItems, totals)}${warnings.length ? `\n\nWarnings:\n- ${warnings.join('\n- ')}` : ''}${errors.length ? `\n\nUnresolved rows:\n- ${errors.join('\n- ')}` : ''}`;
        sessionStore.appendMessage(clientId, sessionId, { role: 'assistant', content: message });
        sessionStore.appendEvent(clientId, sessionId, {
          type: 'workbook_reply',
          data: {
            mode: 'excel',
            stage: null,
            shapeName,
            processorVendor,
            sourcePlatform: effectiveSourcePlatform,
            vpuPerGb: Number.isFinite(vpuPerGb) && vpuPerGb > 0 ? vpuPerGb : workbookContextPatch.vpuPerGb,
            lineItemCount: Array.isArray(lineItems) ? lineItems.length : 0,
          },
        });
      }
    }

    return {
      status: 200,
      body: {
        ok: !!lineItems.length,
        source: 'excel',
        fileName,
        summary,
        requests,
        results,
        lineItems,
        warnings,
        errors,
        totals,
      },
    };
  } catch (error) {
    return {
      error: new ValidationError(`Could not parse workbook: ${error.message}`, {
        code: 'WORKBOOK_PARSE_ERROR',
      }),
    };
  }
}

// ════════════════════════════════════════════════════════════
//  POST /api/chat  — OCI GenAI only
// ════════════════════════════════════════════════════════════
app.post('/api/chat', async (req, res) => {
  const clientId = resolveClientId(req);
  const sessionId = String(req.body?.sessionId || '').trim();
  const requestLogger = buildRequestLogger({
    routeName: '/api/chat',
    requestId: createRequestId(),
    clientId,
    sessionId,
    profile: String(req.body?.profile || '').trim(),
  });
  const trace = createTrace();
  requestLogger.info({
    event: 'http.request.start',
    method: 'POST',
    hasSystemPrompt: Boolean(req.body?.system),
    messageCount: Array.isArray(req.body?.messages) ? req.body.messages.length : 0,
  }, 'Received /api/chat request');

  try {
    const cfg = ensureOciConfig(requestLogger);
    const requestOptions = resolveGenAIRequestOptions(req.body.profile || cfg.defaultProfile || 'narrative', cfg, {
      maxTokens: req.body.max_tokens,
      temperature: req.body.temperature,
      topP: req.body.top_p,
      topK: req.body.top_k,
      modelId: req.body.model,
    });
    const response = await runChat({
      cfg,
      ...requestOptions,
      systemPrompt: req.body.system || '',
      messages: req.body.messages || [],
      logger: requestLogger,
      trace,
    });
    const payload = response && response.data ? response.data : response;
    const text = extractChatText(payload);
    requestLogger.info({
      event: 'http.request.complete',
      method: 'POST',
      statusCode: 200,
      modelId: requestOptions.modelId || cfg.modelId,
      ...summarizeTrace(trace),
    }, 'Completed /api/chat request');
    return res.json({
      id: 'oci-' + Date.now(),
      type: 'message',
      role: 'assistant',
      content: [{ type: 'text', text: text || '' }],
      model: requestOptions.modelId || cfg.modelId,
      stop_reason: 'end_turn',
      raw: text ? undefined : payload,
    });
  } catch (err) {
    logRequestFailure(requestLogger, trace, 'POST', err, 'Failed /api/chat request');
    return handleError(res, err);
  }
});

app.post('/api/assistant', async (req, res) => {
  const clientId = resolveClientId(req);
  const sessionId = String(req.body?.sessionId || '').trim();
  const requestLogger = buildRequestLogger({
    routeName: '/api/assistant',
    requestId: createRequestId(),
    clientId,
    sessionId,
  });
  const trace = createTrace();
  requestLogger.info({
    event: 'http.request.start',
    method: 'POST',
    hasText: Boolean(String(req.body?.text || '').trim()),
    hasImage: Boolean(String(req.body?.imageDataUrl || '').trim()),
  }, 'Received /api/assistant request');

  try {
    ensureCatalogReady();
    const cfg = ensureOciConfig(requestLogger);
    const text = String(req.body.text || '').trim();
    const storedSession = sessionId ? sessionStore.getSession(clientId, sessionId) : null;
    const effectiveWorkbookContext = getEffectiveWorkbookContext(storedSession);
    const conversation = storedSession
      ? mapStoredConversation(storedSession.messages)
      : Array.isArray(req.body.conversation) ? req.body.conversation : [];
    const imageDataUrl = String(req.body.imageDataUrl || '').trim();
    const userLabel = String(req.body.userLabel || '').trim();
    const persistedUserContent = userLabel || text || (imageDataUrl ? '[Image attached]' : '');
    const sessionContext = resolveAssistantSessionContext(storedSession, req.body.sessionContext);
    if (!text && !imageDataUrl) {
      throw new ValidationError('Provide text or imageDataUrl.', {
        code: 'ASSISTANT_INPUT_REQUIRED',
      });
    }

    const workbookFollowup = parseWorkbookPromptSelections(text);
    const hasActiveWorkbook = !!effectiveWorkbookContext?.contentBase64;
    const hasWorkbookQuote = storedSession?.sessionContext?.lastQuote?.type === 'workbook_quote';
    if ((hasActiveWorkbook || hasWorkbookQuote) && hasWorkbookSelection(workbookFollowup) && !imageDataUrl) {
      if (persistedUserContent) {
        sessionStore.appendMessage(clientId, sessionId, {
          role: 'user',
          content: persistedUserContent,
        });
      }
      const workbookReply = await estimateWorkbookRequest({
        cfg,
        clientId,
        sessionId,
        body: {
          ...workbookFollowup,
          userLabel: persistedUserContent,
        },
        persistMessages: true,
      });
      if (workbookReply.error) throw workbookReply.error;
      requestLogger.info({
        event: 'http.request.complete',
        method: 'POST',
        statusCode: workbookReply.status,
        routingPath: 'workbook_shortcut',
        outcome: workbookReply.body?.ok ? 'quote' : 'clarification',
        ...summarizeTrace(trace),
      }, 'Completed /api/assistant request');
      return res.status(workbookReply.status).json({
        ...workbookReply.body,
        session: sessionId ? sessionStore.getSession(clientId, sessionId) : null,
        message: workbookReply.body?.ok && Array.isArray(workbookReply.body?.lineItems)
          ? `### Excel quotation\n\n${workbookReply.body.summary || ''}\n\n${buildMarkdownFromLinesForAssistant(workbookReply.body.lineItems, workbookReply.body.totals)}${Array.isArray(workbookReply.body.warnings) && workbookReply.body.warnings.length ? `\n\nWarnings:\n- ${workbookReply.body.warnings.join('\n- ')}` : ''}`
          : String(workbookReply.body?.question || workbookReply.body?.error || ''),
      });
    }
    if (storedSession && persistedUserContent) {
      sessionStore.appendMessage(clientId, sessionId, {
        role: 'user',
        content: persistedUserContent,
      });
    }
    const reply = await respondToAssistant({
      cfg,
      index: store.normalized,
      conversation,
      userText: text,
      imageDataUrl,
      sessionContext,
      logger: requestLogger,
      trace,
    });
    if (storedSession) {
      sessionStore.appendMessage(clientId, sessionId, {
        role: 'assistant',
        content: String(reply?.message || ''),
      });
      sessionStore.appendEvent(clientId, sessionId, {
        type: 'assistant_reply',
        data: {
          mode: reply?.mode || '',
          route: reply?.intent?.route || '',
          intent: reply?.intent?.intent || '',
          serviceFamily: reply?.intent?.serviceFamily || '',
          quotePlan: reply?.intent?.quotePlan || null,
          contextPack: reply?.contextPackSummary || null,
        },
      });
      sessionStore.updateSessionState(clientId, sessionId, {
        sessionContext: reply?.sessionContext || null,
        workbookContext: reply?.sessionContext?.workbookContext || storedSession.workbookContext || null,
      });
    }
    requestLogger.info({
      event: 'http.request.complete',
      method: 'POST',
      statusCode: 200,
      routingPath: reply?.mode || '',
      route: reply?.intent?.route || '',
      serviceFamily: reply?.intent?.serviceFamily || '',
      shouldQuote: Boolean(reply?.intent?.shouldQuote),
      outcome: reply?.needsClarification || reply?.question ? 'clarification' : (reply?.quote || reply?.quoteMarkdown || reply?.totals ? 'quote' : 'answer'),
      ...summarizeTrace(trace),
    }, 'Completed /api/assistant request');
    
    return res.json({
      ...reply,
      session: sessionId ? sessionStore.getSession(clientId, sessionId) : null,
    });
  } catch (error) {
    logRequestFailure(requestLogger, trace, 'POST', error, 'Failed /api/assistant request');
    return handleError(res, error);
  }
});

// ── Config status ──────────────────────────────────────────
app.get('/api/providers', (_req, res) => {
  const cfg = loadOciConfig();
  res.json({ oci: { configured: cfg.ok, region: cfg.region, endpoint: cfg.endpoint, compartment: cfg.compartment, modelId: cfg.modelId, profile: cfg.profile } });
});

// ════════════════════════════════════════════════════════════
//  OCI Catalog download
// ════════════════════════════════════════════════════════════
const OCI_URLS = {
  'products.json':       'https://www.oracle.com/a/ocom/docs/cloudestimator2/data/products.json',
  'productpresets.json': 'https://www.oracle.com/a/ocom/docs/cloudestimator2/data/productpresets.json',
  'metrics.json':        'https://www.oracle.com/a/ocom/docs/cloudestimator2/data/metrics.json',
  'products-apex.json':  'https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/',
};

const FRONTEND_DIR = path.join(__dirname, '..', 'app');
const CATALOG_CACHE_DIR = path.join(__dirname, '..', 'data', 'catalog-cache', 'current');
const CACHE_TTL_MS = 6 * 60 * 60 * 1000;
const MAX_FETCH_ATTEMPTS = 4;
const store = { data: {}, loadedAt: {}, errors: {}, busy: false, normalized: null, attempts: {} };

function fetchJSON(url, hops = 5) {
  return new Promise((resolve, reject) => {
    if (hops < 0) return reject(new Error('Too many redirects'));
    const req = https.get(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; OCI-Pricing-Agent/2.1)', 'Accept': 'application/json, */*' },
      timeout: 30000,
    }, (r) => {
      if (r.statusCode >= 300 && r.statusCode < 400 && r.headers.location) {
        r.resume(); return fetchJSON(r.headers.location, hops - 1).then(resolve).catch(reject);
      }
      if (r.statusCode !== 200) { r.resume(); return reject(new Error(`HTTP ${r.statusCode}`)); }
      const c = [];
      r.on('data', d => c.push(d));
      r.on('end', () => { try { resolve(JSON.parse(Buffer.concat(c).toString('utf8'))); } catch(e) { reject(e); } });
      r.on('error', reject);
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Timeout')); });
  });
}

function cloneJson(value) {
  return value && typeof value === 'object' ? JSON.parse(JSON.stringify(value)) : value;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function mergePaginatedPayload(firstPage, pages) {
  if (!firstPage || typeof firstPage !== 'object' || !Array.isArray(firstPage.items)) {
    return cloneJson(firstPage);
  }
  const merged = cloneJson(firstPage);
  merged.items = pages.flatMap((page) => Array.isArray(page?.items) ? page.items : []);
  merged.hasMore = false;
  merged.offset = 0;
  merged.limit = merged.items.length;
  return merged;
}

function buildNextPageUrl(baseUrl, page) {
  if (!page || typeof page !== 'object') return null;
  if (typeof page.next === 'string' && page.next.trim()) return page.next.trim();
  if (!Array.isArray(page.items) || !page.items.length) return null;
  if (page.hasMore !== true) return null;
  const limit = Number(page.limit);
  const offset = Number(page.offset);
  if (!Number.isFinite(limit) || limit <= 0) return null;
  const nextOffset = Number.isFinite(offset) ? offset + limit : limit;
  const url = new URL(baseUrl);
  url.searchParams.set('offset', String(nextOffset));
  if (!url.searchParams.get('limit')) url.searchParams.set('limit', String(limit));
  return url.toString();
}

async function fetchAllPages(name, baseUrl) {
  const pages = [];
  const seen = new Set();
  let nextUrl = baseUrl;
  while (nextUrl) {
    if (seen.has(nextUrl)) throw new Error(`Pagination loop detected for ${name}`);
    seen.add(nextUrl);
    const page = await fetchJSON(nextUrl);
    pages.push(page);
    nextUrl = buildNextPageUrl(baseUrl, page);
  }
  return mergePaginatedPayload(pages[0], pages);
}

function writeCatalogSnapshot(name, data) {
  fs.mkdirSync(CATALOG_CACHE_DIR, { recursive: true });
  fs.writeFileSync(path.join(CATALOG_CACHE_DIR, name), JSON.stringify(data, null, 2));
}

async function fetchCatalogWithRetries(name, baseUrl, maxAttempts = MAX_FETCH_ATTEMPTS) {
  let lastError = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    store.attempts[name] = attempt;
    try {
      if (attempt > 1) {
        console.log(`  ↺ ${name} retry ${attempt}/${maxAttempts}…`);
      }
      return await fetchAllPages(name, baseUrl);
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) {
        const delayMs = Math.min(4000, 500 * (2 ** (attempt - 1)));
        logger.warn({
          event: 'catalog.fetch.retry',
          catalogName: name,
          attempt,
          maxAttempts,
          delayMs,
          errorMessage: error.message,
        }, `  ! ${name} attempt ${attempt}/${maxAttempts} failed — ${error.message}; retrying in ${delayMs}ms`);
        await sleep(delayMs);
      }
    }
  }
  throw new Error(`${lastError?.message || 'Unknown error'} (after ${maxAttempts} attempts)`);
}

async function fetchOne(name) {
  console.log(`  ↓ ${name}…`);
  try {
    const data = await fetchCatalogWithRetries(name, OCI_URLS[name]);
    store.data[name] = data; store.loadedAt[name] = new Date(); delete store.errors[name];
    store.normalized = normalizeCatalog(store.data);
    writeCatalogSnapshot(name, data);
    const n = data?.items?.length ?? (Array.isArray(data) ? data.length : '?');
    console.log(`  ✓ ${name} (${n} entries, attempt ${store.attempts[name]}/${MAX_FETCH_ATTEMPTS})`);
  } catch(e) {
    store.errors[name] = e.message;
    logger.warn({
      event: 'catalog.fetch.failure',
      catalogName: name,
      errorMessage: e.message,
    }, `  ✗ ${name} — ${e.message}`);
  }
}

async function fetchAll() {
  if (store.busy) return;
  store.busy = true;
  console.log('\n━━ Downloading OCI catalogs from Oracle sources ━━');
  await Promise.all(Object.keys(OCI_URLS).map(fetchOne));
  store.busy = false;
  console.log(`\n${Object.keys(store.data).length}/${Object.keys(OCI_URLS).length} catalogs ready.\n`);
}

let refreshTimer = null;

function startCatalogRefreshTimer() {
  if (refreshTimer) return refreshTimer;
  refreshTimer = setInterval(() => {
    const now = Date.now();
    const stale = Object.keys(OCI_URLS).filter((n) => {
      const t = store.loadedAt[n];
      return !t || now - t.getTime() > CACHE_TTL_MS;
    });
    if (stale.length) {
      console.log(`↺ Auto-refresh: ${stale.join(', ')}`);
      Promise.all(stale.map(fetchOne)).catch((error) => {
        logger.warn({
          event: 'catalog.auto_refresh.failure',
          errorMessage: error.message,
        }, `Auto-refresh failed: ${error.message}`);
      });
    }
  }, 60 * 60 * 1000);
  if (typeof refreshTimer.unref === 'function') refreshTimer.unref();
  return refreshTimer;
}

app.get('/api/health', (_req, res) => {
  const catalogs = {};
  for (const n of Object.keys(OCI_URLS)) catalogs[n] = {
    loaded: !!store.data[n],
    loadedAt: store.loadedAt[n] ?? null,
    error: store.errors[n] ?? null,
    attempts: store.attempts[n] ?? 0,
    maxAttempts: MAX_FETCH_ATTEMPTS,
  };
  const cfg = loadOciConfig();
  res.json({ ok: Object.keys(store.data).length > 0, catalogsLoaded: Object.keys(store.data).length, loading: store.busy, catalogs, ociConfigured: cfg.ok });
});

function ensureCatalogReady() {
  if (!store.normalized || !store.normalized.products.length) {
    throw new CatalogError('OCI catalog is not ready yet.', {
      code: 'CATALOG_NOT_READY',
      httpStatus: 503,
    });
  }
  return store.normalized;
}

app.get('/api/catalog/search', (req, res) => {
  try {
    const index = ensureCatalogReady();
    const q = String(req.query.q || '');
    res.json({
      ok: true,
      products: searchProducts(index, q, 15),
      presets: searchPresets(index, q, 10),
      services: searchServiceRegistry(index.serviceRegistry, q, 12),
    });
  } catch (error) {
    return handleError(res, error);
  }
});

app.get('/api/coverage', (req, res) => {
  try {
    const index = ensureCatalogReady();
    const q = String(req.query.q || '').trim();
    const registry = index.serviceRegistry || { services: [], summary: {} };
    const services = q ? searchServiceRegistry(registry, q, 50) : registry.services;
    res.json({
      ok: true,
      summary: registry.summary,
      services,
    });
  } catch (error) {
    return handleError(res, error);
  }
});

app.get('/api/catalog/:file', (req, res) => {
  try {
    const { file } = req.params;
    if (!OCI_URLS[file]) {
      throw new CatalogError('Unknown catalog.', {
        code: 'CATALOG_NOT_FOUND',
        httpStatus: 404,
      });
    }
    if (store.busy && !store.data[file]) {
      throw new CatalogError('Still loading.', {
        code: 'CATALOG_LOADING',
        httpStatus: 202,
        data: { loading: true },
      });
    }
    if (!store.data[file]) {
      throw new CatalogError(store.errors[file] || 'Not available.', {
        code: 'CATALOG_UNAVAILABLE',
        httpStatus: 503,
      });
    }
    res.setHeader('Cache-Control', 'public, max-age=1800').json(store.data[file]);
  } catch (error) {
    return handleError(res, error);
  }
});

app.post('/api/catalog/reload', (_req, res) => {
  Object.keys(store.data).forEach(k => { delete store.data[k]; delete store.loadedAt[k]; });
  store.normalized = null;
  fetchAll();
  res.json({ ok: true });
});

app.post('/api/quote', (req, res) => {
  try {
    const index = ensureCatalogReady();
    const text = String(req.body.text || '');
    const lines = Array.isArray(req.body.lines) ? req.body.lines : [];

    if (!text && !lines.length) {
      throw new ValidationError('Provide text or structured lines.', {
        code: 'QUOTE_INPUT_REQUIRED',
      });
    }

    if (text) return res.json(quoteFromPrompt(index, text));

    const results = lines.map((line) => buildQuote(index, line));
    const lineItems = results.flatMap((result) => result.lineItems || []);
    const warnings = results.flatMap((result) => result.warnings || []);
    const errors = results.filter((result) => !result.ok).map((result) => result.error);
    const totals = lineItems.reduce((acc, line) => {
      acc.monthly += line.monthly;
      acc.annual += line.annual;
      acc.currencyCode = line.currencyCode;
      return acc;
    }, { monthly: 0, annual: 0, currencyCode: 'USD' });

    return res.json({
      ok: !!lineItems.length,
      source: 'structured-lines',
      results,
      lineItems,
      warnings,
      errors,
      totals,
    });
  } catch (error) {
    return handleError(res, error);
  }
});

app.post('/api/excel/estimate', async (req, res) => {
  try {
    ensureCatalogReady();
    const cfg = loadOciConfig();
    const clientId = resolveClientId(req);
    const sessionId = String(req.body.sessionId || '').trim();
    const result = await estimateWorkbookRequest({ cfg, clientId, sessionId, body: req.body, persistMessages: true });
    if (result.error) return handleError(res, result.error);
    return res.status(result.status).json({
      ...result.body,
      session: sessionId ? sessionStore.getSession(clientId, sessionId) : null,
    });
  } catch (error) {
    return handleError(res, error);
  }
});

app.get('/api/sessions', (req, res) => {
  const clientId = resolveClientId(req);
  return res.json({ ok: true, sessions: sessionStore.listSessions(clientId) });
});

app.post('/api/sessions', (req, res) => {
  const clientId = resolveClientId(req);
  const session = sessionStore.createSession(clientId, req.body?.title || 'New session');
  return res.json({ ok: true, session });
});

app.get('/api/sessions/:id', (req, res) => {
  const clientId = resolveClientId(req);
  const session = sessionStore.getSession(clientId, req.params.id);
  if (!session) {
    return handleError(res, createHttpError('Session not found.', {
      code: 'SESSION_NOT_FOUND',
      httpStatus: 404,
    }));
  }
  return res.json({ ok: true, session });
});

app.get('/api/sessions/:id/quote-export', (req, res) => {
  const clientId = resolveClientId(req);
  const result = buildQuoteExportHttpResponse(clientId, req.params.id, req.query.format);
  if (result.headers) {
    for (const [key, value] of Object.entries(result.headers)) {
      res.setHeader(key, value);
    }
  }
  if (result.error) return handleError(res, result.error);
  if (result.json) return res.status(result.status).json(result.json);
  return res.status(result.status).send(result.body);
});

app.post('/api/sessions/:id/messages', (req, res) => {
  const clientId = resolveClientId(req);
  const session = sessionStore.appendMessage(clientId, req.params.id, {
    role: req.body?.role,
    content: req.body?.content,
  }, {
    expectedVersion: req.body?.expectedVersion,
  });
  if (!session) {
    return handleError(res, createHttpError('Session not found.', {
      code: 'SESSION_NOT_FOUND',
      httpStatus: 404,
    }));
  }
  if (session.conflict) {
    return handleError(res, new SessionConflictError('Session version conflict.', {
      data: { session: session.session },
    }));
  }
  return res.json({ ok: true, session });
});

app.post('/api/sessions/:id/state', (req, res) => {
  const clientId = resolveClientId(req);
  const session = sessionStore.updateSessionState(clientId, req.params.id, {
    sessionContext: req.body?.sessionContext,
    workbookContext: req.body?.workbookContext,
    title: req.body?.title,
  }, {
    expectedVersion: req.body?.expectedVersion,
  });
  if (!session) {
    return handleError(res, createHttpError('Session not found.', {
      code: 'SESSION_NOT_FOUND',
      httpStatus: 404,
    }));
  }
  if (session.conflict) {
    return handleError(res, new SessionConflictError('Session version conflict.', {
      data: { session: session.session },
    }));
  }
  return res.json({ ok: true, session });
});

app.delete('/api/sessions/:id', (req, res) => {
  const clientId = resolveClientId(req);
  const ok = sessionStore.deleteSession(clientId, req.params.id);
  if (!ok) {
    return handleError(res, createHttpError('Session not found.', {
      code: 'SESSION_NOT_FOUND',
      httpStatus: 404,
    }));
  }
  return res.json({ ok: true });
});

app.delete('/api/sessions', (req, res) => {
  const clientId = resolveClientId(req);
  sessionStore.clearSessions(clientId);
  return res.json({ ok: true });
});

app.use(express.static(FRONTEND_DIR));
app.get('*', (_req, res) => res.sendFile(path.join(FRONTEND_DIR, 'index.html')));

function boot() {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('  OCI Pricing Agent v2.1 — OCI GenAI Edition');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  const _cfg = loadOciConfig();
  console.log(`  OCI GenAI : ${_cfg.ok ? `✓ configured (${_cfg.region})` : '✗ not configured — set OCI_* vars in .env'}`);
  const server = app.listen(PORT, '0.0.0.0', () => console.log(`\n🚀  http://localhost:${PORT}\n`));
  startCatalogRefreshTimer();
  fetchAll();
  return server;
}

if (require.main === module) {
  boot();
}

module.exports = {
  app,
  boot,
  startCatalogRefreshTimer,
  buildQuoteExportRows,
  buildQuoteExportCsv,
  buildQuoteExportWorkbook,
  buildQuoteExportHttpResponse,
  resolveAssistantSessionContext,
  fetchAll,
};
