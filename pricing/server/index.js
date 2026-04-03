'use strict';

const express = require('express');
const path    = require('path');
const https   = require('https');
const fs      = require('fs');
const XLSX    = require('xlsx');
const { normalizeCatalog, searchProducts, searchPresets, searchServiceRegistry } = require('./catalog');
const { quoteFromPrompt, buildQuote } = require('./quotation-engine');
const { parseWorkbookBase64, workbookToRequests, analyzeWorkbookForGuidedQuote, buildShapeOptionsForProcessor, parseWorkbookPromptSelections, hasWorkbookSelection } = require('./excel');
const { normalizeProcessorVendor, findVmShapeByText } = require('./vm-shapes');
const { loadGenAISettings, runChat, extractChatText } = require('./genai');
const { respondToAssistant } = require('./assistant');
const sessionStore = require('./session-store');

const app  = express();
const PORT = process.env.PORT || 8742;

app.use(express.json({ limit: '25mb' }));

function resolveClientId(req) {
  return String(req.get('x-client-id') || req.body?.clientId || 'anonymous').trim() || 'anonymous';
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
function loadOciConfig() {
  const genai = loadGenAISettings(process.env);
  const user        = process.env.OCI_USER        || '';
  const tenancy     = process.env.OCI_TENANCY      || '';
  const fingerprint = process.env.OCI_FINGERPRINT  || '';
  const region      = genai.region || process.env.OCI_REGION || 'us-chicago-1';
  const compartment = genai.compartmentId || process.env.OCI_COMPARTMENT || tenancy;
  const modelId     = genai.modelId || process.env.OCI_GENAI_MODEL ||
    'ocid1.generativeaimodel.oc1.us-chicago-1.amaaaaaask7dceyafjcwpf75fmqoismvwlmzjbprdzzljhfcrirozftbrjoq';
  const endpoint    = genai.endpoint;
  const profile     = genai.profile;

  let privateKeyPem = '';
  const keyContent = process.env.OCI_PRIVATE_KEY || '';
  const keyContentB64 = process.env.OCI_PRIVATE_KEY_B64 || '';
  const keyPath    = process.env.OCI_KEY_FILE    || '';
  if (keyContentB64) {
    try { privateKeyPem = Buffer.from(keyContentB64, 'base64').toString('utf8'); }
    catch(e) { console.warn('OCI_PRIVATE_KEY_B64 decode failed:', e.message); }
  } else if (keyContent) {
    privateKeyPem = keyContent.replace(/\\n/g, '\n');
  }
  else if (keyPath) {
    try { privateKeyPem = fs.readFileSync(keyPath, 'utf8'); }
    catch(e) { console.warn('OCI_KEY_FILE not readable:', e.message); }
  }

  const ok = !!(user && tenancy && fingerprint && privateKeyPem);
  return { user, tenancy, fingerprint, region, compartment, modelId, endpoint, profile, privateKeyPem, ok };
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

  try {
    const response = await runChat({
      cfg,
      systemPrompt: WORKBOOK_ENRICHMENT_PROMPT,
      messages: [{ role: 'user', content: contextBlock }],
      maxTokens: 450,
      temperature: 0.2,
      topP: 0.6,
      topK: -1,
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

function buildQuoteExportRows(lineItems = [], totals = null) {
  const rows = (Array.isArray(lineItems) ? lineItems : []).map((line, index) => ({
    '#': index + 1,
    Environment: line.environment || '-',
    Service: line.service || '-',
    'Part#': line.partNumber || '-',
    Product: line.product || '-',
    Metric: line.metric || '-',
    Qty: Number.isFinite(Number(line.quantity)) ? Number(line.quantity) : '',
    Inst: Number.isFinite(Number(line.instances)) ? Number(line.instances) : '',
    Hours: Number.isFinite(Number(line.hours)) ? Number(line.hours) : '',
    Rate: Number.isFinite(Number(line.rate)) ? Number(line.rate) : '',
    Unit: Number.isFinite(Number(line.unitPrice)) ? Number(line.unitPrice) : '',
    '$/Mo': Number.isFinite(Number(line.monthly)) ? Number(line.monthly) : '',
    Annual: Number.isFinite(Number(line.annual)) ? Number(line.annual) : '',
    Currency: line.currencyCode || totals?.currencyCode || 'USD',
  }));
  if (totals) {
    rows.push({
      '#': 'Total',
      Environment: '',
      Service: '',
      'Part#': '',
      Product: '',
      Metric: '',
      Qty: '',
      Inst: '',
      Hours: '',
      Rate: '',
      Unit: '',
      '$/Mo': Number.isFinite(Number(totals.monthly)) ? Number(totals.monthly) : '',
      Annual: Number.isFinite(Number(totals.annual)) ? Number(totals.annual) : '',
      Currency: totals.currencyCode || 'USD',
    });
  }
  return rows;
}

function buildQuoteExportCsv(lineItems = [], totals = null) {
  const rows = buildQuoteExportRows(lineItems, totals);
  if (!rows.length) return '';
  const headers = Object.keys(rows[0]);
  const escapeCell = (value) => {
    const text = String(value ?? '');
    if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
    return text;
  };
  return [
    headers.map(escapeCell).join(','),
    ...rows.map((row) => headers.map((key) => escapeCell(row[key])).join(',')),
  ].join('\n');
}

function buildQuoteExportWorkbook(lineItems = [], totals = null) {
  const workbook = XLSX.utils.book_new();
  const sheet = XLSX.utils.json_to_sheet(buildQuoteExportRows(lineItems, totals));
  XLSX.utils.book_append_sheet(workbook, sheet, 'Quote');
  return XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' });
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
    return { status: 400, body: { ok: false, error: 'Workbook contentBase64 is required.' } };
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
      return { status: 400, body: { ok: false, error: 'No quotable rows were detected in the workbook.' } };
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
      return { status: 400, body: { ok: false, error: `Shape ${shapeName} is not a valid flex shape for ${processorVendor}.` } };
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
    return { status: 400, body: { ok: false, error: `Could not parse workbook: ${error.message}` } };
  }
}

// ════════════════════════════════════════════════════════════
//  POST /api/chat  — OCI GenAI only
// ════════════════════════════════════════════════════════════
app.post('/api/chat', async (req, res) => {
  const cfg = loadOciConfig();
  if (!cfg.ok) {
    return res.status(500).json({
      type: 'error',
      error: {
        type: 'configuration_error',
        message: 'OCI GenAI is not configured. Set OCI_USER, OCI_TENANCY, OCI_FINGERPRINT and OCI_PRIVATE_KEY in your .env file.',
      }
    });
  }
  try {
    const response = await runChat({
      cfg,
      systemPrompt: req.body.system || '',
      messages: req.body.messages || [],
      maxTokens: req.body.max_tokens || 2000,
    });
    const payload = response && response.data ? response.data : response;
    const text = extractChatText(payload);
    return res.json({
      id: 'oci-' + Date.now(),
      type: 'message',
      role: 'assistant',
      content: [{ type: 'text', text: text || '' }],
      model: cfg.modelId,
      stop_reason: 'end_turn',
      raw: text ? undefined : payload,
    });
  } catch (err) {
    const status = Number(err?.status || err?.statusCode || 502);
    return res.status(Number.isFinite(status) ? status : 502).json({
      type: 'error',
      error: {
        type: 'oci_genai_error',
        message: err?.message || 'OCI GenAI request failed.',
        status: Number.isFinite(status) ? status : undefined,
        details: err.message,
      }
    });
  }
});

app.post('/api/assistant', async (req, res) => {
  if (!ensureCatalogReady(res)) return;
  const cfg = loadOciConfig();
  if (!cfg.ok) {
    return res.status(500).json({
      ok: false,
      error: 'OCI GenAI is not configured.',
    });
  }
  const text = String(req.body.text || '').trim();
  const sessionId = String(req.body.sessionId || '').trim();
  const clientId = resolveClientId(req);
  const storedSession = sessionId ? sessionStore.getSession(clientId, sessionId) : null;
  const effectiveWorkbookContext = getEffectiveWorkbookContext(storedSession);
  const conversation = storedSession
    ? mapStoredConversation(storedSession.messages)
    : Array.isArray(req.body.conversation) ? req.body.conversation : [];
  const imageDataUrl = String(req.body.imageDataUrl || '').trim();
  const userLabel = String(req.body.userLabel || '').trim();
  const persistedUserContent = userLabel || text || (imageDataUrl ? '[Image attached]' : '');
  const sessionContext = storedSession?.sessionContext || (req.body.sessionContext && typeof req.body.sessionContext === 'object'
    ? req.body.sessionContext
    : null);
  if (!text && !imageDataUrl) return res.status(400).json({ ok: false, error: 'Provide text or imageDataUrl.' });

  try {
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
    return res.json({
      ...reply,
      session: sessionId ? sessionStore.getSession(clientId, sessionId) : null,
    });
  } catch (error) {
    return res.status(502).json({
      ok: false,
      error: error.message || 'Assistant request failed.',
    });
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
};

const FRONTEND_DIR = path.join(__dirname, '..', 'app');
const CACHE_TTL_MS = 6 * 60 * 60 * 1000;
const store = { data: {}, loadedAt: {}, errors: {}, busy: false, normalized: null };

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

async function fetchOne(name) {
  console.log(`  ↓ ${name}…`);
  try {
    const data = await fetchJSON(OCI_URLS[name]);
    store.data[name] = data; store.loadedAt[name] = new Date(); delete store.errors[name];
    store.normalized = normalizeCatalog(store.data);
    const n = data?.items?.length ?? (Array.isArray(data) ? data.length : '?');
    console.log(`  ✓ ${name} (${n} entries)`);
  } catch(e) { store.errors[name] = e.message; console.warn(`  ✗ ${name} — ${e.message}`); }
}

async function fetchAll() {
  if (store.busy) return;
  store.busy = true;
  console.log('\n━━ Downloading OCI catalogs from oracle.com ━━');
  await Promise.all(Object.keys(OCI_URLS).map(fetchOne));
  store.busy = false;
  console.log(`\n${Object.keys(store.data).length}/${Object.keys(OCI_URLS).length} catalogs ready.\n`);
}

setInterval(() => {
  const now = Date.now();
  const stale = Object.keys(OCI_URLS).filter(n => { const t = store.loadedAt[n]; return !t || now - t.getTime() > CACHE_TTL_MS; });
  if (stale.length) { console.log(`↺ Auto-refresh: ${stale.join(', ')}`); Promise.all(stale.map(fetchOne)); }
}, 60 * 60 * 1000);

app.get('/api/health', (_req, res) => {
  const catalogs = {};
  for (const n of Object.keys(OCI_URLS)) catalogs[n] = { loaded: !!store.data[n], loadedAt: store.loadedAt[n] ?? null, error: store.errors[n] ?? null };
  const cfg = loadOciConfig();
  res.json({ ok: Object.keys(store.data).length > 0, catalogsLoaded: Object.keys(store.data).length, loading: store.busy, catalogs, ociConfigured: cfg.ok });
});

function ensureCatalogReady(res) {
  if (!store.normalized || !store.normalized.products.length) {
    res.status(503).json({ ok: false, error: 'OCI catalog is not ready yet.' });
    return false;
  }
  return true;
}

app.get('/api/catalog/search', (req, res) => {
  if (!ensureCatalogReady(res)) return;
  const q = String(req.query.q || '');
  res.json({
    ok: true,
    products: searchProducts(store.normalized, q, 15),
    presets: searchPresets(store.normalized, q, 10),
    services: searchServiceRegistry(store.normalized.serviceRegistry, q, 12),
  });
});

app.get('/api/coverage', (req, res) => {
  if (!ensureCatalogReady(res)) return;
  const q = String(req.query.q || '').trim();
  const registry = store.normalized.serviceRegistry || { services: [], summary: {} };
  const services = q ? searchServiceRegistry(registry, q, 50) : registry.services;
  res.json({
    ok: true,
    summary: registry.summary,
    services,
  });
});

app.get('/api/catalog/:file', (req, res) => {
  const { file } = req.params;
  if (!OCI_URLS[file]) return res.status(404).json({ error: 'Unknown catalog' });
  if (store.busy && !store.data[file]) return res.status(202).json({ error: 'Still loading', loading: true });
  if (!store.data[file]) return res.status(503).json({ error: store.errors[file] || 'Not available' });
  res.setHeader('Cache-Control', 'public, max-age=1800').json(store.data[file]);
});

app.post('/api/catalog/reload', (_req, res) => {
  Object.keys(store.data).forEach(k => { delete store.data[k]; delete store.loadedAt[k]; });
  store.normalized = null;
  fetchAll();
  res.json({ ok: true });
});

app.post('/api/quote', (req, res) => {
  if (!ensureCatalogReady(res)) return;
  const text = String(req.body.text || '');
  const lines = Array.isArray(req.body.lines) ? req.body.lines : [];

  if (!text && !lines.length) {
    return res.status(400).json({ ok: false, error: 'Provide text or structured lines.' });
  }

  if (text) return res.json(quoteFromPrompt(store.normalized, text));

  const results = lines.map((line) => buildQuote(store.normalized, line));
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
});

app.post('/api/excel/estimate', async (req, res) => {
  if (!ensureCatalogReady(res)) return;
  const cfg = loadOciConfig();
  const clientId = resolveClientId(req);
  const sessionId = String(req.body.sessionId || '').trim();
  const result = await estimateWorkbookRequest({ cfg, clientId, sessionId, body: req.body, persistMessages: true });
  return res.status(result.status).json({
    ...result.body,
    session: sessionId ? sessionStore.getSession(clientId, sessionId) : null,
  });
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
  if (!session) return res.status(404).json({ ok: false, error: 'Session not found.' });
  return res.json({ ok: true, session });
});

app.get('/api/sessions/:id/quote-export', (req, res) => {
  const clientId = resolveClientId(req);
  const session = sessionStore.getSession(clientId, req.params.id);
  if (!session) return res.status(404).json({ ok: false, error: 'Session not found.' });
  const quoteExport = session.sessionContext?.quoteExport;
  if (!quoteExport?.lineItems?.length) {
    return res.status(404).json({ ok: false, error: 'No exportable quote found in this session.' });
  }
  const format = String(req.query.format || 'csv').trim().toLowerCase();
  if (format === 'json') {
    return res.json({
      ok: true,
      quoteExport,
    });
  }
  if (format === 'xlsx') {
    const workbook = buildQuoteExportWorkbook(quoteExport.lineItems, quoteExport.totals);
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${req.params.id}-quote.xlsx"`);
    return res.send(workbook);
  }
  const csv = buildQuoteExportCsv(quoteExport.lineItems, quoteExport.totals);
  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', `attachment; filename="${req.params.id}-quote.csv"`);
  return res.send(csv);
});

app.post('/api/sessions/:id/messages', (req, res) => {
  const clientId = resolveClientId(req);
  const session = sessionStore.appendMessage(clientId, req.params.id, {
    role: req.body?.role,
    content: req.body?.content,
  }, {
    expectedVersion: req.body?.expectedVersion,
  });
  if (!session) return res.status(404).json({ ok: false, error: 'Session not found.' });
  if (session.conflict) return res.status(409).json({ ok: false, error: 'Session version conflict.', session: session.session });
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
  if (!session) return res.status(404).json({ ok: false, error: 'Session not found.' });
  if (session.conflict) return res.status(409).json({ ok: false, error: 'Session version conflict.', session: session.session });
  return res.json({ ok: true, session });
});

app.delete('/api/sessions/:id', (req, res) => {
  const clientId = resolveClientId(req);
  const ok = sessionStore.deleteSession(clientId, req.params.id);
  if (!ok) return res.status(404).json({ ok: false, error: 'Session not found.' });
  return res.json({ ok: true });
});

app.delete('/api/sessions', (req, res) => {
  const clientId = resolveClientId(req);
  sessionStore.clearSessions(clientId);
  return res.json({ ok: true });
});

app.use(express.static(FRONTEND_DIR));
app.get('*', (_req, res) => res.sendFile(path.join(FRONTEND_DIR, 'index.html')));

// ── Boot ───────────────────────────────────────────────────
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('  OCI Pricing Agent v2.1 — OCI GenAI Edition');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
const _cfg = loadOciConfig();
console.log(`  OCI GenAI : ${_cfg.ok ? `✓ configured (${_cfg.region})` : '✗ not configured — set OCI_* vars in .env'}`);
app.listen(PORT, '0.0.0.0', () => console.log(`\n🚀  http://localhost:${PORT}\n`));
fetchAll();
