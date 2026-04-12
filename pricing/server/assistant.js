'use strict';

const { quoteFromPrompt, parsePromptRequest } = require('./quotation-engine');
const { searchProducts, searchPresets, searchServiceRegistry, serviceHasRequiredInputs } = require('./catalog');
const { getServiceFamily, getMissingRequiredInputs, buildCanonicalRequest, getClarificationMessage, getPreQuoteClarification, inferServiceFamily, normalizeExtractedInputsForFamily } = require('./service-families');
const { inferConsumptionPattern, explainConsumptionPattern } = require('./consumption-model');
const { runChat, extractChatText } = require('./genai');
const { analyzeIntent, analyzeImageIntent, buildSessionContextBlock } = require('./intent-extractor');
const { buildAssistantContextPack, buildCatalogListingReply, buildStructuredDiscoveryFallback, buildUncoveredComputeReply, canSafelyQuoteUncoveredComputeVariant, findUncoveredComputeVariant, stringifyContextPack, summarizeContextPack } = require('./context-packs');
const { hasExplicitQuoteLead, isConceptualPricingQuestion, isDiscoveryOrExplanationQuestion } = require('./discovery-classifier');
const { fallbackIntentOnAnalysisFailure, reconcileIntentWithHeuristics } = require('./intent-reconciliation');
const { shouldForceQuoteFollowUpRoute, applyQuoteFollowUpIntentOverride } = require('./quote-followup-intent');
const { reconcilePostIntentFollowUp } = require('./post-intent-followup');
const { buildEarlyAssistantReply } = require('./early-assistant-replies');
const { detectGenericComputeShapeClarification } = require('./compute-shape-clarification');
const { buildQuoteUnresolvedPayload } = require('./quote-unresolved');
const { buildAnswerFallbackPayload } = require('./answer-fallback');
const { reconcileQuoteClarificationState } = require('./quote-clarification-state');
const { buildQuoteRequestShape } = require('./quote-request-shaping');
const { resolveDirectQuoteFastPath } = require('./direct-quote-fast-paths');
const { resolveEarlyAssistantRouting } = require('./early-assistant-routing');
const { buildDiscoveryRoutingState, resolveDiscoveryRoutePayload } = require('./discovery-routing');
const { resolvePostClarificationRouting } = require('./post-clarification-routing');
const { resolveIntentPipeline } = require('./intent-pipeline');
const { prepareQuoteCandidateState } = require('./quote-entry-preparation');
const {
  mergeSessionQuoteFollowUp,
  mergeSessionQuoteFollowUpByRoute,
  preserveCriticalPromptModifiers,
} = require('./session-quote-followup');
const {
  isSessionQuoteFollowUp,
  isShortContextualAnswer,
  mergeClarificationAnswer,
} = require('./clarification-followup');
const {
  hasExplicitByolChoice,
  detectByolAmbiguity,
  filterQuoteByByolChoice,
  shouldAskLicenseChoice,
  buildLicenseChoiceClarificationPayload,
  buildByolAmbiguityClarificationPayload,
} = require('./license-choice');
const {
  resolveEarlyFlexComparisonClarification,
  buildFlexComparisonQuote,
  buildFlexComparisonNarrative,
  buildFlexComparisonReplyPayload,
} = require('./flex-comparison-flow');

const RESPONSE_PROMPT = [
  'You are an OCI pricing specialist speaking to a customer.',
  'Be concise, natural, and practical.',
  'If a deterministic quotation is provided, explain what was matched and mention any assumptions or warnings.',
  'Do not invent prices, SKUs, tiers, or formulas.',
  'If no quotation is available, explain the situation clearly and ask at most one next question when needed.',
  'Do not render tables.',
  'Use plain markdown.',
].join('\n');

const STRUCTURED_DISCOVERY_PROMPT = [
  'You are an OCI pricing discovery specialist.',
  'Answer only using the structured product context provided by the system.',
  'Do not invent OCI services, shapes, pricing rules, modifiers, or availability.',
  'If the context does not contain enough information to answer safely, say the service is not available in the current pricing knowledge base.',
  'Do not generate a quote unless the system explicitly says this is a deterministic quote path.',
  'Use concise natural markdown and prefer short lists when enumerating options.',
].join('\n');

const QUOTE_ENRICHMENT_PROMPT = [
  'You are enriching an OCI pricing response that was already calculated deterministically.',
  'Do not change any numbers, SKUs, totals, assumptions, or warnings.',
  'Do not invent pricing, architecture, licensing, or migration facts.',
  'Do not restate totals, do not rebuild arithmetic, and do not infer discrepancies.',
  'Write short, useful markdown only, with the tone of the requested OCI expert role.',
  'Return at most two short bullet lists:',
  '- OCI considerations for this technology',
  '- Migration notes when the source clearly comes from VMware or RVTools',
  'If a section does not apply, omit it.',
].join('\n');

const FLEX_SHAPE_TOKEN_PATTERN_SOURCE = '(?:(?:vm|bm)\\.)?(?:(?:[a-z][a-z0-9]*)\\.)*(?:[a-z]+\\d+|[a-z]\\d+)\\.flex';
const FLEX_SHAPE_TOKEN_PATTERN = new RegExp(`^${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}$`, 'i');
const FLEX_SHAPE_TOKEN_INLINE_PATTERN = new RegExp(`\\b${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}\\b`, 'i');
const FLEX_SHAPE_TOKEN_GLOBAL_PATTERN = new RegExp(`\\b${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}\\b`, 'ig');

function summarizeMatches(index, text) {
  const products = searchProducts(index, text, 5).map((item) => item.fullDisplayName);
  const presets = searchPresets(index, text, 3).map((item) => item.displayName);
  return { products, presets };
}

function buildServiceUnavailableMessage(userText) {
  const source = String(userText || '').trim();
  return [
    'This OCI pricing guidance service is not available for that request right now.',
    source ? `I could not interpret \`${source}\` safely with the current GenAI controller and structured pricing context.` : 'I could not interpret the request safely with the current GenAI controller and structured pricing context.',
    'I prefer to stop here rather than return an unreliable answer or quote.',
  ].join('\n\n');
}

function buildRegistryQuery(text, intent = {}) {
  return String(text || '')
    .replace(/\boic\b/ig, ' Oracle Integration Cloud ')
    .replace(/\bquote\b/ig, ' ')
    .replace(/\b\d[\d,]*(?:\.\d+)?\s*(?:requests?|api calls?|transactions?|queries?|emails?|messages?|sms(?: messages?)?|tokens?|gb|tb|mbps|gbps|users?|named users?|ocpus?|ecpus?|hours?|days?)\b/ig, ' ')
    .replace(/[,+]/g, ' ')
    .replace(/\bper month\b|\bper hour\b|\bper day\b|\bmonthly\b|\bhourly\b/ig, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function isFlexComparisonRequest(text) {
  const source = String(text || '');
  const matches = source.match(FLEX_SHAPE_TOKEN_GLOBAL_PATTERN) || [];
  return /\bcompare\b/i.test(source) && matches.length >= 2;
}

function isCompositeOrComparisonRequest(text) {
  const source = String(text || '').toLowerCase();
  const segments = splitCompositeQuoteSegments(source);
  const signaledSegments = segments.filter((segment) => hasCompositeServiceSignal(segment)).length;
  if (segments.length >= 2 && signaledSegments >= 2) return true;
  const serviceHits = [
    /\bload balancer\b/.test(source),
    /\bblock storage\b|\bblock volumes?\b/.test(source),
    /\bobject storage\b/.test(source),
    /\bfastconnect\b|\bfast connect\b/.test(source),
    /\bweb application firewall\b|\bwaf\b/.test(source),
    /\bnetwork firewall\b/.test(source),
    /\bdns\b/.test(source),
    /\bapi gateway\b/.test(source),
    /\bintegration cloud\b/.test(source),
    /\banalytics cloud\b/.test(source),
    /\bdata integration\b/.test(source),
    /\bmonitoring\b/.test(source),
    /\bnotifications\b/.test(source),
    /\bhttps delivery\b|\bemail delivery\b/.test(source),
    /\biam sms\b|\bsms messages?\b/.test(source),
    /\bthreat intelligence\b/.test(source),
    /\bhealth checks?\b/.test(source),
    /\bfleet application management\b/.test(source),
    /\boci batch\b|\bbatch\b/.test(source),
    /\bdata safe\b/.test(source),
    /\blog analytics\b/.test(source),
    /\bfunctions\b/.test(source),
    /\bgenerative ai\b/.test(source),
    /\bvision\b|\bspeech\b|\bmedia flow\b/.test(source),
    /\bfile storage\b/.test(source),
    /\bautonomous(?: ai)? lakehouse\b|\bautonomous data warehouse\b|\bbase database service\b|\bexadata\b|\bdatabase cloud service\b/.test(source),
    FLEX_SHAPE_TOKEN_INLINE_PATTERN.test(source),
  ].filter(Boolean).length;
  if (/\bcompare\b/.test(source) && FLEX_SHAPE_TOKEN_INLINE_PATTERN.test(source)) return true;
  return serviceHits >= 2 || /\b3-tier\b|\bthree-tier\b|\barchitecture\b|\bworkload\b|\bbundle\b|\bstack\b|\bplatform\b/.test(source);
}

function parseCapacityReservationUtilization(text) {
  const source = String(text || '');
  const match = source.match(/\b(?:capacity reservation(?: utilization)?|reservation utilization)\s*[:=]?\s*(\d+(?:\.\d+)?)\b/i);
  if (!match) return null;
  return Number(match[1]);
}

function parseBurstableBaseline(text) {
  const source = String(text || '');
  const match = source.match(/\bburstable(?: baseline)?\s*[:=]?\s*(\d+(?:\.\d+)?)\b/i) || source.match(/\bbaseline\s*[:=]?\s*(\d+(?:\.\d+)?)\b/i);
  if (!match) return null;
  return Number(match[1]);
}

function parseStandaloneNumericAnswer(text) {
  const source = String(text || '').trim();
  if (!/^\d+(?:\.\d+)?$/.test(source)) return null;
  const value = Number(source);
  return Number.isFinite(value) ? value : null;
}

function parseOnDemandMode(text) {
  const source = String(text || '').trim();
  if (/^on[- ]?demand$/i.test(source)) return 'on-demand';
  if (/^reserved(?: pricing)?$/i.test(source)) return 'reserved';
  return '';
}

function enrichExtractedInputsForFamily(intent = {}) {
  return {
    ...intent,
    extractedInputs: normalizeExtractedInputsForFamily(intent.serviceFamily, intent.extractedInputs),
  };
}

function detectFlexComparisonModifier(text) {
  const source = String(text || '');
  if (/\bcapacity reservation\b/i.test(source)) return 'capacity-reservation';
  if (/\bpreemptible\b/i.test(source)) return 'preemptible';
  if (/\bburstable\b/i.test(source)) return 'burstable';
  return '';
}

function extractFlexShapes(text) {
  const matches = String(text || '').match(FLEX_SHAPE_TOKEN_GLOBAL_PATTERN) || [];
  const seen = new Set();
  return matches.filter((item) => {
    const key = item.toUpperCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function findLatestFlexComparisonPrompt(conversation = [], userText = '', fallbackPrompt = '') {
  const current = String(userText || '').trim();
  if (isFlexComparisonRequest(current)) return current;
  const fallback = String(fallbackPrompt || '').trim();
  if (isFlexComparisonRequest(fallback)) return fallback;
  const items = Array.isArray(conversation) ? conversation : [];
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (item.role !== 'user') continue;
    const content = String(item.content || '').trim();
    if (isFlexComparisonRequest(content)) return content;
  }
  return '';
}

function extractFlexComparisonContext(conversation = [], userText = '', fallbackPrompt = '') {
  const basePrompt = findLatestFlexComparisonPrompt(conversation, userText, fallbackPrompt);
  if (!basePrompt) return null;
  const shapes = extractFlexShapes(basePrompt);
  if (shapes.length < 2) return null;

  const parsed = parsePromptRequest(basePrompt);
  const modifierKind = detectFlexComparisonModifier(basePrompt);
  let utilization = parseCapacityReservationUtilization(basePrompt);
  let burstableBaseline = parseBurstableBaseline(basePrompt);
  let withoutCrMode = parseOnDemandMode(basePrompt);

  const items = [...(Array.isArray(conversation) ? conversation : []), { role: 'user', content: userText }];
  for (const item of items) {
    if (item.role !== 'user') continue;
    const content = String(item.content || '');
    if (modifierKind === 'capacity-reservation' && utilization === null) {
      const explicitUtil = parseCapacityReservationUtilization(content);
      const standalone = parseStandaloneNumericAnswer(content);
      if (explicitUtil !== null) utilization = explicitUtil;
      else if (standalone !== null && standalone >= 0 && standalone <= 1) utilization = standalone;
    }
    if (modifierKind === 'burstable' && burstableBaseline === null) {
      const explicitBaseline = parseBurstableBaseline(content);
      const standalone = parseStandaloneNumericAnswer(content);
      if (explicitBaseline !== null) burstableBaseline = explicitBaseline;
      else if (standalone !== null && standalone > 0 && standalone <= 1) burstableBaseline = standalone;
    }
    if (modifierKind === 'capacity-reservation' && !withoutCrMode) {
      withoutCrMode = parseOnDemandMode(content) || withoutCrMode;
    }
  }

  return {
    basePrompt,
    shapes,
    ocpus: parsed.ocpus,
    memoryGb: parsed.memoryQuantity,
    hours: parsed.hours,
    modifierKind,
    utilization,
    burstableBaseline,
    withoutCrMode,
  };
}

function hasCompositeServiceSignal(text) {
  const source = String(text || '');
  return new RegExp(`${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}|\\b(?:vm|bm)\\.[a-z0-9.]+\\.\\d+\\b|\\bload balancer\\b|\\blb\\b|\\bblock storage\\b|\\bblock volumes?\\b|\\bobject storage\\b|\\bfile storage\\b|\\bfastconnect\\b|\\bfast connect\\b|\\bdns\\b|\\bapi gateway\\b|\\bweb application firewall\\b|\\bwaf\\b|\\bnetwork firewall\\b|\\bautonomous(?: ai)? lakehouse\\b|\\bautonomous data warehouse\\b|\\bbase database service\\b|\\bdata integration\\b|\\bintegration cloud\\b|\\boic\\b|\\banalytics cloud\\b|\\boac\\b|\\bdata safe\\b|\\blog analytics\\b|\\bfunctions\\b|\\bgenerative ai\\b|\\bvector store\\b|\\bweb search\\b|\\bagents data ingestion\\b|\\bmemory ingestion\\b|\\bexadata\\b|\\bdatabase cloud service\\b|\\bmonitoring\\b|\\bnotifications\\b|\\bhttps delivery\\b|\\bemail delivery\\b|\\biam sms\\b|\\bsms messages?\\b|\\bthreat intelligence\\b|\\bhealth checks?\\b|\\bfleet application management\\b|\\boci batch\\b|\\bvision\\b|\\bspeech\\b|\\bmedia flow\\b`, 'i').test(source);
}

function splitCompositeQuoteSegments(text) {
  const source = String(text || '').trim();
  const body = source.includes(':') ? source.slice(source.indexOf(':') + 1) : source;
  const rawSegments = body
    .split(/\s*(?:,|\+|\bplus\b)\s*/i)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => !/^\d+(?:\.\d+)?\s*h(?:ours?)?(?:\/month)?$/i.test(item))
    .filter((item) => !/^\d+(?:\.\d+)?\s*days?\/month$/i.test(item));

  const merged = [];
  for (const segment of rawSegments) {
    if (
      merged.length &&
      /^\b(?:active|archiv(?:e|al))\b/i.test(segment) &&
      /\blog analytics\b/i.test(merged[merged.length - 1])
    ) {
      merged.push(`Log Analytics ${segment}`.trim());
      continue;
    }
    if (!merged.length || hasCompositeServiceSignal(segment)) {
      merged.push(segment);
      continue;
    }
    merged[merged.length - 1] = `${merged[merged.length - 1]} ${segment}`.trim();
  }
  return merged;
}

function shouldAppendGlobalHours(segment) {
  const source = String(segment || '');
  return new RegExp(`${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}|\\bfunctions\\b|\\bfastconnect\\b|\\bfast connect\\b|\\bload balancer\\b|\\bfirewall\\b|\\bintegration cloud\\b|\\bworkspace usage\\b|\\bprocessed per hour\\b|\\bautonomous\\b|\\bexadata\\b|\\bdatabase cloud service\\b`, 'i').test(source);
}

function normalizeCompositeSegment(segment, fullText) {
  let out = String(segment || '').trim().replace(/^and\s+/i, '');
  out = out.replace(/^(?:quote\s+)?(?:a|an)\s+.+?\b(?:stack|platform|workload|architecture|bundle|fabric)\s+with\s+/i, '');
  const multipliedInstances = out.match(/^(\d+)\s*x\s+(.*)$/i);
  if (multipliedInstances) {
    out = `${multipliedInstances[2]} ${multipliedInstances[1]} instances`;
  }
  out = out.replace(/\bLB\b/i, 'Flexible Load Balancer');
  out = out.replace(/\bOIC\b\s+enterprise\b/i, 'Oracle Integration Cloud Enterprise');
  out = out.replace(/\bOIC\b\s+standard\b/i, 'Oracle Integration Cloud Standard');
  out = out.replace(/\bOAC\b\s+enterprise\b/i, 'Oracle Analytics Cloud Enterprise');
  out = out.replace(/\bOAC\b\s+professional\b/i, 'Oracle Analytics Cloud Professional');
  out = out.replace(/\bLI\b/i, 'License Included');
  if (/\bvector store retrieval\b/i.test(out) && !/\bgenerative ai\b/i.test(out)) {
    out = `OCI Generative AI ${out}`;
  } else if (/\bweb search\b/i.test(out) && !/\bgenerative ai\b/i.test(out)) {
    out = `OCI Generative AI ${out}`;
  } else if (/\bagents data ingestion\b/i.test(out) && !/\bgenerative ai\b/i.test(out)) {
    out = `OCI Generative AI ${out}`;
  } else if (/\bmemory ingestion\b/i.test(out) && !/\bgenerative ai\b/i.test(out)) {
    out = `OCI Generative AI ${out}`;
  }
  const globalHours = String(fullText || '').match(/(\d+(?:\.\d+)?)\s*h(?:ours?)?(?:\/month)?/i) ||
    String(fullText || '').match(/(\d+(?:\.\d+)?)\s*hours?\s*\/\s*month/i);
  if (globalHours && !/\b\d+(?:\.\d+)?\s*h(?:ours?)?(?:\/month)?\b/i.test(out) && shouldAppendGlobalHours(out)) {
    out = `${out} ${globalHours[1]}h/month`;
  }
  if (!/^quote\b/i.test(out)) out = `Quote ${out}`;
  return out.trim();
}

function buildCompositeQuoteFromSegments(index, text) {
  const segments = splitCompositeQuoteSegments(text);
  if (segments.length < 2) return null;
  const serviceSignalCount = segments.filter((segment) => hasCompositeServiceSignal(segment)).length;
  if (serviceSignalCount < 2) return null;

  const mergedLineItems = [];
  const warnings = [];
  const candidates = [];

  for (const segment of segments) {
    const prompt = normalizeCompositeSegment(segment, text);
    const quote = quoteSegmentWithCanonicalFallback(index, prompt);
    if (!quote.ok || !Array.isArray(quote.lineItems) || !quote.lineItems.length) {
      warnings.push(`Could not deterministically quote segment: ${segment}`);
      continue;
    }
    mergedLineItems.push(...quote.lineItems);
    if (Array.isArray(quote.warnings) && quote.warnings.length) warnings.push(...quote.warnings);
    candidates.push(...((quote.resolution?.candidates) || []));
  }

  if (mergedLineItems.length < 2) return null;

  const totals = mergedLineItems.reduce((acc, line) => {
    acc.monthly += Number(line.monthly || 0);
    acc.annual += Number(line.annual || 0);
    return acc;
  }, { monthly: 0, annual: 0, currencyCode: 'USD' });

  return {
    ok: true,
    request: { source: text },
    resolution: {
      type: 'workload',
      label: 'Composite OCI workload',
      candidates: candidates.filter(Boolean),
    },
    warnings: Array.from(new Set(warnings)),
    lineItems: mergedLineItems,
    totals,
    markdown: toMarkdownQuote(mergedLineItems, totals),
  };
}

function formatAssumptions(assumptions, parsedRequest) {
  const lines = [];
  const sourceAssumptions = Array.isArray(assumptions) ? assumptions.filter(Boolean) : [];
  for (const item of sourceAssumptions) {
    const text = String(item || '').trim();
    if (!text) continue;
    const lower = text.toLowerCase();
    if (!shouldKeepSourceAssumption(lower, parsedRequest)) continue;
    if (/\b(?:usage|hours?\/month|monthly usage|uptime)\b/.test(lower)) {
      const explicitHours = lower.match(/(\d+(?:\.\d+)?)\s*hours?\/month/);
      if (explicitHours && Number(explicitHours[1]) !== Number(parsedRequest.hours)) continue;
    }
    if (/\binstance count\b|\binstances?\b/.test(lower)) {
      const explicitInstances = lower.match(/(\d+(?:\.\d+)?)/);
      if (explicitInstances && Number(explicitInstances[1]) !== Number(parsedRequest.instances)) continue;
    }
    if (/\bcurrency\b/.test(lower) && !lower.includes(String(parsedRequest.currencyCode || '').toLowerCase())) {
      continue;
    }
    lines.push(`- ${text}`);
  }
  const normalizedAssumptions = sourceAssumptions.join(' ').toLowerCase();
  const mentionsUsageDefault = /\b(?:usage|hours?\/month|monthly usage|uptime)\b/.test(normalizedAssumptions);
  const mentionsInstanceDefault = /\binstance count\b|\binstances?\b/.test(normalizedAssumptions);
  const mentionsCurrencyDefault = /\bcurrency\b|\busd\b|\bmxn\b|\beur\b|\bbrl\b|\bgbp\b|\bcad\b|\bjpy\b/.test(normalizedAssumptions);
  if (!mentionsUsageDefault && !/\b\d+(?:\.\d+)?\s*h(?:ours?)?\b/i.test(parsedRequest.source || '')) {
    lines.push(`- Monthly usage defaulted to ${parsedRequest.hours} hours.`);
  }
  if (parsedRequest.annualRequested) {
    lines.push('- Annual total assumes 12 months of the quoted monthly usage.');
  }
  if (!mentionsInstanceDefault && !/\b\d+(?:\.\d+)?\s*(?:instances?|nodes?|vms?)\b/i.test(parsedRequest.source || '')) {
    lines.push(`- Instance count defaulted to ${parsedRequest.instances}.`);
  }
  if (!mentionsCurrencyDefault && !/\b(usd|mxn|eur|brl|gbp|cad|jpy)\b/i.test(parsedRequest.source || '')) {
    lines.push(`- Currency defaulted to ${parsedRequest.currencyCode}.`);
  }
  return Array.from(new Set(lines));
}

function shouldKeepSourceAssumption(lower, parsedRequest) {
  const source = String(parsedRequest?.source || '').toLowerCase();
  if (!lower) return false;
  if (/pasted image|extracted from the pasted image|sizing details were extracted from the pasted image|visible in the image/.test(lower)) {
    return true;
  }
  if (/\b(?:usage|hours?\/month|monthly usage|uptime)\b/.test(lower)) return true;
  if (/\binstance count\b|\binstances?\b/.test(lower)) return true;
  if (/\bcurrency\b/.test(lower)) return true;
  if (/\bbyol\b|\blicense included\b|\blicencia incluida\b/.test(lower)) {
    return /\bbyol\b|\blicense included\b|\blicencia incluida\b/.test(source);
  }
  if (/\bcapacity reservation\b|\bpreemptible\b|\bburstable\b/.test(lower)) {
    return /\bcapacity reservation\b|\bpreemptible\b|\bburstable\b/.test(source);
  }
  return false;
}

async function writeNaturalReply(cfg, conversation, userText, context, sessionContext) {
  const history = Array.isArray(conversation) ? conversation.slice(-6) : [];
  const sessionBlock = buildSessionContextBlock(sessionContext);
  const contextBlock = [
    sessionBlock,
    `User request: ${userText}`,
    `Intent: ${context.intent || 'quote'}`,
    context.summary ? `Summary: ${context.summary}` : '',
    context.quoteMarkdown ? `Quotation markdown:\n${context.quoteMarkdown}` : '',
    context.warningLines?.length ? `Warnings:\n${context.warningLines.join('\n')}` : '',
    context.assumptionLines?.length ? `Assumptions:\n${context.assumptionLines.join('\n')}` : '',
    context.candidateLines?.length ? `Candidates:\n${context.candidateLines.join('\n')}` : '',
  ].filter(Boolean).join('\n\n');

  const messages = [
    ...history.map((item) => ({
      role: item.role === 'assistant' ? 'assistant' : 'user',
      content: String(item.content || ''),
    })),
    { role: 'user', content: contextBlock },
  ];

  const response = await runChat({
    cfg,
    systemPrompt: RESPONSE_PROMPT,
    messages,
    maxTokens: 900,
    temperature: 0.35,
    topP: 0.7,
    topK: -1,
  });
  return extractChatText(response?.data || response).trim();
}

async function writeStructuredContextReply(cfg, conversation, userText, sessionContext, contextPack) {
  if (!cfg?.modelId || !cfg?.compartment) return '';
  const history = Array.isArray(conversation) ? conversation.slice(-6) : [];
  const sessionBlock = buildSessionContextBlock(sessionContext);
  const contextBlock = [
    sessionBlock,
    `User request: ${String(userText || '').trim()}`,
    `Structured product context:\n${stringifyContextPack(contextPack)}`,
  ].filter(Boolean).join('\n\n');

  const messages = [
    ...history.map((item) => ({
      role: item.role === 'assistant' ? 'assistant' : 'user',
      content: String(item.content || ''),
    })),
    { role: 'user', content: contextBlock },
  ];

  try {
    const response = await runChat({
      cfg,
      systemPrompt: STRUCTURED_DISCOVERY_PROMPT,
      messages,
      maxTokens: 700,
      temperature: 0.2,
      topP: 0.5,
      topK: -1,
    });
    return extractChatText(response?.data || response).trim();
  } catch {
    return '';
  }
}

function extractInlinePartNumbers(text = '') {
  return Array.from(new Set((String(text || '').match(/\bB\d{5,6}\b/g) || []).filter(Boolean)));
}

function summarizeQuoteForSession(quote) {
  if (!quote?.ok) return null;
  if (quote.comparison) {
    return {
      type: 'comparison',
      label: 'Flex comparison',
      monthly: Number(quote.comparison.monthlyTotal || 0),
      annual: Number(quote.comparison.annualTotal || 0),
      currencyCode: quote.comparison.currencyCode || 'USD',
      lineItemCount: Array.isArray(quote.comparison.items) ? quote.comparison.items.length : 0,
    };
  }
  const lineItems = Array.isArray(quote.lineItems) ? quote.lineItems : [];
  const request = quote.request || {};
  return {
    type: 'quote',
    label: quote.resolution?.label || request.shape || request.serviceName || request.source || '',
    source: request.source || '',
    monthly: Number(quote.totals?.monthly || 0),
    annual: Number(quote.totals?.annual || 0),
    currencyCode: quote.totals?.currencyCode || 'USD',
    lineItemCount: lineItems.length,
    shapeName: request.shape || request.shapeSeries || '',
    serviceFamily: request.serviceFamily || '',
    processorVendor: request.processorVendor || '',
    vpuPerGb: Number.isFinite(Number(request.vpuPerGb)) ? Number(request.vpuPerGb) : null,
    partNumbers: Array.from(new Set(lineItems.map((line) => line.partNumber).filter(Boolean))).slice(0, 12),
  };
}

function buildQuoteExportPayload(quote) {
  if (!quote?.ok || !Array.isArray(quote.lineItems) || !quote.lineItems.length) return null;
  return {
    formatVersion: 1,
    generatedAt: new Date().toISOString(),
    totals: quote.totals || null,
    lineItems: quote.lineItems.map((line, index) => ({
      rowNumber: index + 1,
      environment: line.environment || '-',
      service: line.service || '-',
      partNumber: line.partNumber || '-',
      product: line.product || '-',
      metric: line.metric || '-',
      quantity: Number.isFinite(Number(line.quantity)) ? Number(line.quantity) : '',
      instances: Number.isFinite(Number(line.instances)) ? Number(line.instances) : '',
      hours: Number.isFinite(Number(line.hours)) ? Number(line.hours) : '',
      rate: Number.isFinite(Number(line.rate)) ? Number(line.rate) : '',
      unitPrice: Number.isFinite(Number(line.unitPrice)) ? Number(line.unitPrice) : '',
      monthly: Number.isFinite(Number(line.monthly)) ? Number(line.monthly) : '',
      annual: Number.isFinite(Number(line.annual)) ? Number(line.annual) : '',
      currencyCode: line.currencyCode || quote.totals?.currencyCode || 'USD',
    })),
  };
}

function buildAssistantSessionSummary(nextContext) {
  if (!nextContext || typeof nextContext !== 'object') return '';
  const lines = [];
  if (nextContext.workbookContext?.fileName) {
    const workbook = nextContext.workbookContext;
    let line = `Active workbook ${workbook.fileName}`;
    if (workbook.shapeName) line += ` using ${workbook.shapeName}`;
    if (Number.isFinite(Number(workbook.vpuPerGb))) line += ` with ${Number(workbook.vpuPerGb)} VPU`;
    lines.push(line);
  }
  if (nextContext.lastQuote?.label) {
    const quote = nextContext.lastQuote;
    let line = `Last quote ${quote.label}`;
    if (Number.isFinite(Number(quote.monthly))) line += ` monthly ${formatMoney(Number(quote.monthly), quote.currencyCode || 'USD')}`;
    if (Number.isFinite(Number(quote.lineItemCount))) line += ` across ${Number(quote.lineItemCount)} lines`;
    lines.push(line);
  }
  if (nextContext.pendingClarification?.question) {
    lines.push(`Pending clarification: ${nextContext.pendingClarification.question}`);
  }
  if (nextContext.lastIntent?.route) {
    lines.push(`Last route ${nextContext.lastIntent.route}`);
  }
  return lines.join('. ');
}

function buildAssistantSessionContext(previous, effectiveUserText, payload) {
  const next = previous && typeof previous === 'object' ? JSON.parse(JSON.stringify(previous)) : {};
  next.lastUserText = String(effectiveUserText || '').trim();
  if (payload?.intent?.intent) next.currentIntent = payload.intent.intent;
  if (payload?.intent && typeof payload.intent === 'object') {
    next.lastIntent = {
      intent: payload.intent.intent || '',
      route: payload.intent.route || '',
      serviceFamily: payload.intent.serviceFamily || '',
      serviceName: payload.intent.serviceName || '',
      confidence: Number.isFinite(Number(payload.intent.confidence)) ? Number(payload.intent.confidence) : null,
      quotePlan: payload.intent.quotePlan && typeof payload.intent.quotePlan === 'object'
        ? JSON.parse(JSON.stringify(payload.intent.quotePlan))
        : null,
    };
  }
  if (payload?.contextPackSummary) {
    next.lastContextPack = JSON.parse(JSON.stringify(payload.contextPackSummary));
  }
  if (payload?.mode === 'clarification' && payload?.message) {
    next.pendingClarification = {
      question: String(payload.message).trim(),
      serviceFamily: payload.intent?.serviceFamily || '',
    };
  } else {
    delete next.pendingClarification;
  }
  if (payload?.quote?.ok) {
    next.lastQuote = summarizeQuoteForSession(payload.quote);
    next.quoteExport = buildQuoteExportPayload(payload.quote);
  }
  next.sessionSummary = buildAssistantSessionSummary(next);
  return next;
}

async function buildGenAIQuoteEnrichment(cfg, userText, quote, assumptions) {
  if (!cfg?.ok || !quote?.ok) return '';
  const lineItems = Array.isArray(quote.lineItems) ? quote.lineItems : [];
  if (!lineItems.length) return '';
  const request = quote.request || {};
  const totals = quote.totals || {};
  const technologyProfile = inferQuoteTechnologyProfile(quote);
  const allowMigrationNotes = request?.metadata?.inventorySource === 'rvtools' || /\bvmware\b|\brvtools\b/i.test(String(userText || ''));
  const contextBlock = [
    `User request: ${String(userText || '').trim()}`,
    `Expert role: ${technologyProfile.role}`,
    `Technology profile: ${technologyProfile.name}`,
    `OCI expert focus: ${technologyProfile.focus}`,
    `Matched label: ${quote.resolution?.label || 'n/a'}`,
    `Monthly total: ${formatMoney(totals.monthly, totals.currencyCode || 'USD')}`,
    `Annual total: ${formatMoney(totals.annual, totals.currencyCode || 'USD')}`,
    assumptions.length ? `Assumptions:\n${assumptions.join('\n')}` : '',
    quote.warnings?.length ? `Warnings:\n${quote.warnings.map((item) => `- ${item}`).join('\n')}` : '',
    `Line items:\n${lineItems.slice(0, 12).map((line) => `- ${line.service || '-'} | ${line.product} | ${line.metric || '-'} | qty ${fmt(line.quantity)} | monthly ${money(line.monthly)}`).join('\n')}`,
    request?.metadata?.inventorySource ? `Inventory source: ${request.metadata.inventorySource}` : '',
    request?.metadata?.vmwareVcpus ? `VMware vCPUs in source request: ${request.metadata.vmwareVcpus}` : '',
  ].filter(Boolean).join('\n\n');

  try {
    const response = await runChat({
      cfg,
      systemPrompt: QUOTE_ENRICHMENT_PROMPT,
      messages: [{ role: 'user', content: contextBlock }],
      maxTokens: 350,
      temperature: 0.2,
      topP: 0.6,
      topK: -1,
    });
    return sanitizeQuoteEnrichment(extractChatText(response?.data || response).trim(), { allowMigrationNotes });
  } catch (_error) {
    return '';
  }
}

function sanitizeQuoteEnrichment(text, options = {}) {
  const source = String(text || '').trim();
  if (!source) return '';
  const allowMigrationNotes = options.allowMigrationNotes !== false;
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
        if (!allowMigrationNotes) {
          activeSection = '';
          continue;
        }
        activeSection = 'migration';
        kept.push('## Migration Notes');
      } else if (/oci considerations/i.test(trimmed)) {
        activeSection = 'considerations';
        kept.push('## OCI Considerations');
      } else {
        activeSection = '';
      }
      continue;
    }
    if (!activeSection) continue;
    if (/\$|monthly total|annual total|breakdown of costs|costs are calculated|potential miscalculation|discrepanc/i.test(trimmed)) continue;
    if (/\b=\b/.test(trimmed) && /\d/.test(trimmed)) continue;
    kept.push(line);
  }
  return kept.join('\n').trim();
}

function inferQuoteTechnologyProfile(quote) {
  const request = quote?.request || {};
  const lineItems = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const blob = [
    request?.source || '',
    request?.serviceFamily || '',
    request?.metadata?.inventorySource || '',
    ...lineItems.map((line) => `${line.service || ''} ${line.product || ''} ${line.metric || ''}`),
  ].join('\n').toLowerCase();

  if (request?.metadata?.inventorySource === 'rvtools' || /\bvmware\b|\brvtools\b/.test(blob)) {
    return {
      key: 'vmware-migration',
      role: 'OCI VMware migration specialist',
      name: 'VMware migration to OCI',
      focus: 'right-sizing, VMware vCPU to OCI OCPU normalization, exclusion of platform VMs, and follow-up items such as Windows licensing',
    };
  }
  const storageSignalCount = [
    /\bfile storage\b/.test(blob),
    /\bobject storage\b/.test(blob),
    /\bblock volume\b/.test(blob),
  ].filter(Boolean).length;
  const edgeSignalCount = [
    /\bdns\b/.test(blob),
    /\bload balancer\b/.test(blob),
    /\bfastconnect\b/.test(blob),
    /\bnetwork firewall\b/.test(blob),
    /\bwaf\b|\bweb application firewall\b/.test(blob),
  ].filter(Boolean).length;

  const scoreMonthly = (patterns) => lineItems.reduce((sum, line) => {
    const lineBlob = `${line.service || ''} ${line.product || ''} ${line.metric || ''}`.toLowerCase();
    if (patterns.some((pattern) => pattern.test(lineBlob))) return sum + Number(line.monthly || 0);
    return sum;
  }, 0);

  const networkPatterns = [/\bfastconnect\b/, /\bload balancer\b/, /\bdns\b/, /\bnetwork firewall\b/, /\bwaf\b|\bweb application firewall\b/];
  const databasePatterns = [/\bautonomous\b/, /\bdatabase\b/, /\bexadata\b/, /\bdata safe\b/];
  const serverlessAiPatterns = [/\bfunctions\b/, /\bgenerative ai\b/, /\bvector store\b/, /\bweb search\b/, /\bagents\b/, /\bapi gateway\b/];
  const analyticsPatterns = [/\bintegration cloud\b/, /\banalytics cloud\b/, /\bdata integration\b/];
  const observabilityPatterns = [/\bmonitoring\b/, /\blog analytics\b/, /\bnotifications\b/, /\bhealth checks\b/];
  const operationsPatterns = [/\bfleet application management\b/, /\boci batch\b/, /\bbatch\b/, /\bemail delivery\b/, /\biam sms\b/];
  const computeStoragePatterns = [/\bcompute\b/, /\bflex\b/, /\bocpu\b/, /\bram\b/, /\bblock volume\b/, /\bobject storage\b/, /\bfile storage\b/];

  const databaseMonthly = scoreMonthly(databasePatterns);
  const networkMonthly = scoreMonthly(networkPatterns);
  const serverlessAiMonthly = scoreMonthly(serverlessAiPatterns);
  const analyticsMonthly = scoreMonthly(analyticsPatterns);
  const observabilityMonthly = scoreMonthly(observabilityPatterns);
  const operationsMonthly = scoreMonthly(operationsPatterns);
  const computeStorageMonthly = scoreMonthly(computeStoragePatterns);
  const totalMonthly = lineItems.reduce((sum, line) => sum + Number(line.monthly || 0), 0) || 0;
  const maxDomainShare = totalMonthly > 0
    ? Math.max(
      networkMonthly,
      databaseMonthly,
      serverlessAiMonthly,
      analyticsMonthly,
      observabilityMonthly + operationsMonthly,
      computeStorageMonthly,
    ) / totalMonthly
    : 0;
  const domainScores = [
    networkMonthly,
    databaseMonthly,
    serverlessAiMonthly,
    analyticsMonthly,
    observabilityMonthly + operationsMonthly,
    computeStorageMonthly,
  ];
  const signalDomainCount = [
    networkPatterns.some((pattern) => pattern.test(blob)),
    databasePatterns.some((pattern) => pattern.test(blob)),
    serverlessAiPatterns.some((pattern) => pattern.test(blob)),
    analyticsPatterns.some((pattern) => pattern.test(blob)),
    observabilityPatterns.some((pattern) => pattern.test(blob)),
    operationsPatterns.some((pattern) => pattern.test(blob)),
    computeStoragePatterns.some((pattern) => pattern.test(blob)),
  ].filter(Boolean).length;

  const hasAnalyticsSignals = analyticsPatterns.filter((pattern) => pattern.test(blob)).length >= 2;
  const hasDatabaseSignals = databasePatterns.some((pattern) => pattern.test(blob));
  const hasObservabilitySignals = observabilityPatterns.filter((pattern) => pattern.test(blob)).length >= 2;
  const hasOperationsSignals = operationsPatterns.filter((pattern) => pattern.test(blob)).length >= 2;

  if (signalDomainCount >= 5 && maxDomainShare <= 0.75) {
    return {
      key: 'solutions-architecture',
      role: 'OCI solutions architect',
      name: 'OCI multi-service architecture',
      focus: 'cross-domain cost drivers across compute, storage, networking, database, observability, and platform services, plus which components are foundational versus workload-specific',
    };
  }

  if (hasDatabaseSignals && totalMonthly > 0 && databaseMonthly / totalMonthly >= 0.35) {
    return {
      key: 'database',
      role: 'OCI database architect',
      name: 'OCI database platform',
      focus: 'license model, compute plus storage composition, and prerequisites or infrastructure components that may sit outside the direct metered lines',
    };
  }
  if (hasObservabilitySignals && totalMonthly > 0 && observabilityMonthly / totalMonthly >= 0.2 && operationsMonthly / totalMonthly < 0.15) {
    return {
      key: 'observability',
      role: 'OCI observability architect',
      name: 'OCI observability and notifications',
      focus: 'ingestion, retrieval, storage-unit, and delivery-operation metrics across monitoring, log analytics, and notifications',
    };
  }
  if (hasOperationsSignals && totalMonthly > 0 && (operationsMonthly / totalMonthly >= 0.15 || (observabilityMonthly + operationsMonthly) / totalMonthly >= 0.3)) {
    return {
      key: 'operations-platform',
      role: 'OCI operations and platform services architect',
      name: 'OCI operations and platform services',
      focus: 'counted operational units, observability storage and retrieval metrics, and which lines are free-tier versus usage-bearing',
    };
  }
  if (hasAnalyticsSignals && totalMonthly > 0 && analyticsMonthly / totalMonthly >= 0.25) {
    return {
      key: 'analytics-integration',
      role: 'OCI analytics and integration architect',
      name: 'OCI analytics and integration services',
      focus: 'user, OCPU/ECPU, data processed, and storage-unit metrics, plus BYOL versus License Included where applicable',
    };
  }
  if (storageSignalCount >= 2 && edgeSignalCount <= 2) {
    return {
      key: 'compute-storage',
      role: 'OCI compute and storage architect',
      name: 'OCI compute and storage platform',
      focus: 'shape selection, OCPU and memory sizing, attached storage assumptions, and whether usage is capacity-driven or hourly',
    };
  }
  const profiles = [
    {
      key: 'network-security',
      role: 'OCI networking and security architect',
      name: 'OCI networking and edge security',
      focus: 'port-hour, bandwidth, request, and processed-data dimensions, plus which components are fixed versus usage-driven',
      patterns: [/\bfastconnect\b/, /\bload balancer\b/, /\bdns\b/, /\bnetwork firewall\b/, /\bwaf\b|\bweb application firewall\b/],
    },
    {
      key: 'database',
      role: 'OCI database architect',
      name: 'OCI database platform',
      focus: 'license model, compute plus storage composition, and prerequisites or infrastructure components that may sit outside the direct metered lines',
      patterns: [/\bautonomous\b/, /\bdatabase\b/, /\bexadata\b/, /\bdata safe\b/],
    },
    {
      key: 'serverless-ai',
      role: 'OCI serverless and AI architect',
      name: 'OCI serverless and AI services',
      focus: 'request volume, execution sizing, token or transaction metrics, and when a service is dedicated versus serverless',
      patterns: [/\bfunctions\b/, /\bgenerative ai\b/, /\bvector store\b/, /\bweb search\b/, /\bagents\b/],
    },
    {
      key: 'operations-platform',
      role: 'OCI operations and platform services architect',
      name: 'OCI operations and platform services',
      focus: 'counted operational units such as jobs, managed resources, and delivery volumes, plus which lines are free-tier versus usage-bearing',
      patterns: [/\bfleet application management\b/, /\boci batch\b/, /\bbatch\b/, /\bemail delivery\b/],
    },
    {
      key: 'observability',
      role: 'OCI observability architect',
      name: 'OCI observability and notifications',
      focus: 'ingestion, retrieval, storage-unit, and delivery-operation metrics across monitoring, log analytics, and notifications',
      patterns: [/\bmonitoring\b/, /\blog analytics\b/, /\bnotifications\b/, /\bhealth checks\b/],
    },
    {
      key: 'analytics-integration',
      role: 'OCI analytics and integration architect',
      name: 'OCI analytics and integration services',
      focus: 'user, OCPU/ECPU, data processed, and storage-unit metrics, plus BYOL versus License Included where applicable',
      patterns: [/\bintegration cloud\b/, /\banalytics cloud\b/, /\bdata integration\b/],
    },
    {
      key: 'ai-media',
      role: 'OCI AI and media services architect',
      name: 'OCI AI and media services',
      focus: 'training-hour, transcription-hour, and processed-minute metrics across OCI AI and media pipelines',
      patterns: [/\bvision\b/, /\bspeech\b/, /\bmedia flow\b/, /\bprocessed video\b/],
    },
    {
      key: 'compute-storage',
      role: 'OCI compute and storage architect',
      name: 'OCI compute and storage platform',
      focus: 'shape selection, OCPU and memory sizing, attached storage assumptions, and whether usage is capacity-driven or hourly',
      patterns: [/\bcompute\b/, /\bflex\b/, /\bocpu\b/, /\bram\b/, /\bblock volume\b/, /\bobject storage\b/, /\bfile storage\b/],
    },
  ];
  const scored = profiles
    .map((profile) => ({
      profile,
      score: profile.patterns.reduce((sum, pattern) => sum + (pattern.test(blob) ? 1 : 0), 0),
    }))
    .sort((a, b) => b.score - a.score);
  if (scored[0]?.score > 0) return scored[0].profile;
  return {
    key: 'general',
    role: 'OCI pricing specialist',
    name: 'General OCI pricing',
    focus: 'the main billable dimensions, assumptions, and follow-up checks that a customer should validate before taking the estimate as final',
  };
}

function buildDeterministicExpertSummary(quote) {
  const profile = inferQuoteTechnologyProfile(quote);
  const totals = quote?.totals || {};
  const currencyCode = totals.currencyCode || 'USD';
  const lineItems = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const topDrivers = [...lineItems]
    .sort((a, b) => Number(b.monthly || 0) - Number(a.monthly || 0))
    .slice(0, 3);
  const sections = [];

  sections.push('## OCI Expert Summary');
  sections.push(`- Perspective: **${profile.role}**.`);
  sections.push(`- This estimate is centered on **${profile.name}** pricing.`);
  sections.push(`- Monthly total: ${formatMoney(totals.monthly, currencyCode)}. Annual total: ${formatMoney(totals.annual, currencyCode)}.`);
  sections.push(`- The quote contains ${lineItems.length} priced line${lineItems.length === 1 ? '' : 's'} derived from the OCI catalog and deterministic pricing rules.`);
  if (topDrivers.length) {
    sections.push(`- Main cost drivers: ${topDrivers.map((line) => `\`${line.partNumber}\` (${line.product}) = ${formatMoney(line.monthly, currencyCode)}/month`).join('; ')}.`);
  }

  return sections.join('\n');
}

function buildDeterministicConsiderationsFallback(quote, assumptions) {
  const profile = inferQuoteTechnologyProfile(quote);
  const lineItems = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const sections = [];

  sections.push('## OCI Considerations');
  if (profile.key === 'vmware-migration') {
    sections.push('- Validate that non-migrated VMware platform VMs stay excluded from the target scope.');
    sections.push('- Review Windows workloads separately because OCI infrastructure pricing does not automatically include Microsoft licensing adjustments in this pass.');
  } else if (profile.key === 'network-security') {
    sections.push('- As an OCI networking/security review, validate throughput assumptions, request volumes, and whether the edge controls shown here align with the intended ingress and egress paths.');
    sections.push('- Review which lines are fixed monthly components versus variable traffic or request-driven charges.');
    sections.push('- Confirm whether the quoted edge/security services match the intended throughput and request profile.');
  } else if (profile.key === 'database') {
    sections.push('- As an OCI database review, validate the service architecture first: Base DB, Autonomous, and Exadata families have materially different operational and licensing behavior.');
    sections.push('- Confirm the intended license model before taking the quote as final if the family supports BYOL and License Included variants.');
    sections.push('- Review whether any deployment or infrastructure prerequisites sit outside the direct metered lines shown here.');
  } else if (profile.key === 'serverless-ai') {
    sections.push('- As an OCI serverless/AI review, validate whether the service is genuinely usage-driven or whether Oracle exposes it as a dedicated hourly construct in the live catalog.');
    sections.push('- Validate request volume and execution sizing because those two dimensions usually dominate the monthly result.');
    sections.push('- For dedicated AI services, confirm whether the catalog exposes the service as usage-based or hour-based before assuming a transactional quote.');
  } else if (profile.key === 'operations-platform') {
    sections.push('- As an OCI operations/platform services review, validate which lines are truly paid units versus free-tier operational counts.');
    sections.push('- Review whether the quoted counts match the intended managed-resource, job, or notification-delivery volumes for the target operating model.');
  } else if (profile.key === 'solutions-architecture') {
    sections.push('- As an OCI solutions-architecture review, validate the service boundaries first: this quote spans multiple OCI domains and should be checked as an integrated platform, not as a single-service estimate.');
    sections.push('- Review which lines are foundational platform components versus workload-specific consumption, because those categories usually drive optimization decisions differently.');
    sections.push('- Confirm the intended commercial model for each major domain, especially where user-based, request-based, and infrastructure-based pricing are mixed together.');
  } else if (profile.key === 'analytics-integration') {
    sections.push('- As an OCI analytics/integration review, verify which commercial unit actually applies: users, OCPUs/ECPUs, processed data, or storage units.');
    sections.push('- Confirm whether the service is billed by users, OCPUs/ECPUs, storage units, or data processed, because different variants in the same family bill differently.');
    sections.push('- Review BYOL versus License Included where the selected product family supports both modes.');
  } else if (profile.key === 'compute-storage') {
    sections.push('- As an OCI compute/storage review, validate shape family, OCPU-to-memory ratio, and whether block or object storage should be sized from provisioned capacity or observed consumption.');
    sections.push('- Review whether attached storage should remain block-based or whether file or object storage would better match the workload pattern.');
  } else {
    sections.push(`- Main OCI expert focus for this estimate: ${profile.focus}.`);
    if (assumptions.length) sections.push('- Validate the sizing assumptions before treating the quote as final.');
  }

  return sections.join('\n');
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

async function buildQuoteNarrative(cfg, userText, quote, assumptions) {
  const matched = quote.resolution?.label || 'the requested OCI product';
  const totals = quote.totals || {};
  const request = quote.request || {};
  const lineCount = Array.isArray(quote.lineItems) ? quote.lineItems.length : 0;
  const currencyCode = totals.currencyCode || 'USD';
  const totalSentence = request.annualRequested
    ? `The estimate includes ${lineCount} priced line${lineCount === 1 ? '' : 's'} and the calculated annual total is **${formatMoney(totals.annual, currencyCode)}**.`
    : `The estimate includes ${lineCount} priced line${lineCount === 1 ? '' : 's'} and the calculated monthly total is **${formatMoney(totals.monthly, currencyCode)}**.`;
  const parts = [
    `I prepared a deterministic OCI quotation for \`${matched}\`.`,
    totalSentence,
  ];
  if (assumptions.length) {
    parts.push(`Key assumptions:\n${assumptions.join('\n')}`);
  }
  parts.push(buildDeterministicExpertSummary(quote));
  const enrichment = await buildGenAIQuoteEnrichment(cfg, userText, quote, assumptions);
  parts.push(enrichment || buildDeterministicConsiderationsFallback(quote, assumptions));
  const explanation = buildConsumptionExplanation(quote);
  if (explanation.length) {
    parts.push(`How OCI measures this:\n${explanation.join('\n')}`);
  }
  parts.push(`### OCI quotation\n\n${quote.markdown}`);
  if (quote.warnings?.length) {
    parts.push(`Warnings:\n${quote.warnings.map((item) => `- ${item}`).join('\n')}`);
  }
  return parts.join('\n\n');
}

function buildConsumptionExplanation(quote) {
  const items = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const patternEntries = [];
  const seenPatterns = new Set();
  for (const line of items) {
    const pattern = inferConsumptionPattern(line.metric, `${line.service} ${line.product}`);
    if (!pattern || pattern === 'unknown' || seenPatterns.has(pattern)) continue;
    seenPatterns.add(pattern);
    patternEntries.push({ pattern, line });
  }

  if (patternEntries.length <= 3 && items.length <= 6) {
    return patternEntries.map(({ pattern, line }) => {
      const text = explainConsumptionPattern(pattern, {
        displayName: line.product,
        fullDisplayName: line.product,
      });
      return text ? `- ${text}` : null;
    }).filter(Boolean);
  }

  const grouped = new Map();
  for (const line of items) {
    const pattern = inferConsumptionPattern(line.metric, `${line.service} ${line.product}`);
    const group = classifyConsumptionGroup(pattern, line);
    if (!grouped.has(group.key)) grouped.set(group.key, { ...group, examples: [], patterns: new Set() });
    const bucket = grouped.get(group.key);
    bucket.patterns.add(pattern);
    if (bucket.examples.length < 3) bucket.examples.push(line.product);
  }

  const priority = ['compute', 'storage', 'requests', 'users', 'platform', 'media', 'network', 'other'];
  return Array.from(grouped.values())
    .sort((a, b) => priority.indexOf(a.key) - priority.indexOf(b.key))
    .slice(0, 5)
    .map((group) => {
      const examples = Array.from(new Set(group.examples)).slice(0, 2).map((item) => `\`${item}\``).join(', ');
      return `- ${group.description}${examples ? ` Example lines: ${examples}.` : ''}`;
    });
}

function classifyConsumptionGroup(pattern, line) {
  const serviceBlob = `${line?.service || ''} ${line?.product || ''}`.toLowerCase();
  if (['ocpu-hour', 'ecpu-hour', 'memory-gb-hour', 'functions-gb-memory-seconds', 'functions-invocations-million'].includes(pattern)) {
    return {
      key: 'compute',
      description: 'Compute-style charges are driven by provisioned CPU, memory, or execution usage over time. For hourly SKUs the requested size is multiplied by monthly hours; for serverless functions OCI separately charges execution memory-seconds and invocation volume.',
    };
  }
  if (['capacity-gb-month', 'performance-units-per-gb-month', 'log-analytics-storage-unit-month'].includes(pattern)) {
    return {
      key: 'storage',
      description: 'Storage-style charges are driven by provisioned or retained capacity. OCI bills GB-month, performance density, or storage-unit constructs depending on the storage service.',
    };
  }
  if (['requests', 'count-each', 'data-processed-gb-month', 'data-processed-gb-hour'].includes(pattern)) {
    return {
      key: 'requests',
      description: 'Transaction and request charges are volume-based. The agent converts API calls, requests, processed traffic, deliveries, or counted items into the billing unit defined by each SKU.',
    };
  }
  if (pattern === 'users-per-month') {
    return {
      key: 'users',
      description: 'User-based charges are billed directly from the active user count per month rather than from hourly uptime.',
    };
  }
  if (['workspace-hour', 'execution-hour-utilized', 'generic-hourly', 'generic-monthly', 'utilized-hour'].includes(pattern)) {
    return {
      key: 'platform',
      description: 'Platform-service charges use service-specific hourly or monthly units such as workspaces, execution hours, or dedicated service hours, depending on the SKU metric.',
    };
  }
  if (pattern === 'media-output-minute') {
    return {
      key: 'media',
      description: 'Media and AI pipeline charges are billed from directly consumed training hours, transcription hours, or processed/output media minutes.',
    };
  }
  if (['port-hour', 'load-balancer-hour', 'bandwidth-mbps-hour'].includes(pattern) || /\bfastconnect\b|\bload balancer\b|\bdns\b|\bhealth checks?\b/.test(serviceBlob)) {
    return {
      key: 'network',
      description: 'Network charges are driven by provisioned connectivity, bandwidth configuration, or request/query volume depending on the service.',
    };
  }
  return {
    key: 'other',
    description: 'Some lines use OCI service-specific billing units that are quoted directly from the catalog metric attached to the SKU.',
  };
}

function toMarkdownQuote(lineItems, totals) {
  const header = '| # | Environment | Service | Part# | Product | Metric | Qty | Inst | Hours | Rate | Unit | $/Mo | Annual |\n|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|';
  const body = (lineItems || []).map((line, index) => `| ${[
    index + 1,
    line.environment,
    line.service || '-',
    line.partNumber,
    line.product,
    line.metric || '-',
    fmt(line.quantity),
    fmt(line.instances),
    fmt(line.hours),
    fmt(line.rate),
    money(line.unitPrice),
    money(line.monthly),
    money(line.annual),
  ].join(' | ')} |`).join('\n');
  const total = `| Total | - | - | - | - | - | - | - | - | - | - | ${money(totals.monthly)} | ${money(totals.annual)} |`;
  return `${header}\n${body}\n${total}`;
}

function fmt(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value ?? '-');
  return Number.isInteger(num) ? String(num) : String(Number(num.toFixed(4)));
}

function money(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '$-';
  return `$${Number(num.toFixed(4))}`;
}

function choosePreferredQuote(primary, secondary) {
  if (primary?.ok && !secondary?.ok) return primary;
  if (secondary?.ok && !primary?.ok) return secondary;
  if (!primary?.ok && !secondary?.ok) return primary || secondary || null;
  const primaryLines = Array.isArray(primary?.lineItems) ? primary.lineItems.length : 0;
  const secondaryLines = Array.isArray(secondary?.lineItems) ? secondary.lineItems.length : 0;
  if (primaryLines !== secondaryLines) return primaryLines > secondaryLines ? primary : secondary;
  const primaryMonthly = Number(primary?.totals?.monthly || 0);
  const secondaryMonthly = Number(secondary?.totals?.monthly || 0);
  if (primaryMonthly !== secondaryMonthly) return primaryMonthly > secondaryMonthly ? primary : secondary;
  return secondary || primary;
}

function quoteSegmentWithCanonicalFallback(index, prompt) {
  const direct = quoteFromPrompt(index, prompt);
  const parsed = parsePromptRequest(prompt);
  const familyMeta = parsed?.serviceFamily ? getServiceFamily(parsed.serviceFamily) : null;
  if (!familyMeta) return direct;
  const canonical = String(buildCanonicalRequest({
    serviceFamily: parsed.serviceFamily,
    extractedInputs: parsed,
    normalizedRequest: prompt,
    reformulatedRequest: prompt,
  }, prompt) || '').trim();
  if (!canonical || canonical === prompt) return direct;
  const canonicalQuote = quoteFromPrompt(index, canonical);
  return choosePreferredQuote(direct, canonicalQuote);
}

async function respondToAssistant({ cfg, index, conversation, userText, imageDataUrl, sessionContext }) {
  const effectiveUserText = mergeSessionQuoteFollowUp(
    sessionContext,
    mergeClarificationAnswer(conversation, userText),
  );
  const respond = (payload) => ({
    ...payload,
    sessionContext: buildAssistantSessionContext(sessionContext, effectiveUserText, payload),
  });
  const contextualFollowUp = isShortContextualAnswer(userText);
  const compositeLike = isCompositeOrComparisonRequest(effectiveUserText);
  const {
    payload: earlyRoutingPayload,
    flexComparison,
  } = resolveEarlyAssistantRouting({
    conversation,
    userText,
    effectiveUserText,
    index,
  }, {
    buildEarlyAssistantReply,
    detectGenericComputeShapeClarification,
    extractFlexComparisonContext,
    resolveEarlyFlexComparisonClarification,
    isFlexComparisonRequest,
    detectFlexComparisonModifier,
    parseCapacityReservationUtilization,
    parseBurstableBaseline,
    buildFlexComparisonReplyPayload,
    buildFlexComparisonQuote,
    buildFlexComparisonNarrative,
  });
  if (earlyRoutingPayload) return respond(earlyRoutingPayload);

  const directQuoteFastPath = await resolveDirectQuoteFastPath({
    cfg,
    index,
    effectiveUserText,
    compositeLike,
  }, {
    buildCompositeQuoteFromSegments,
    buildQuoteNarrative,
    formatAssumptions,
    parsePromptRequest,
    quoteFromPrompt,
  });
  if (directQuoteFastPath) return respond(directQuoteFastPath);

  const intentPipeline = await resolveIntentPipeline({
    cfg,
    conversation,
    effectiveUserText,
    userText,
    imageDataUrl,
    sessionContext,
    contextualFollowUp,
    flexComparison,
    index,
  }, {
    analyzeIntent,
    analyzeImageIntent,
    fallbackIntentOnAnalysisFailure,
    buildServiceUnavailableMessage,
    enrichExtractedInputsForFamily,
    reconcileIntentWithHeuristics,
    shouldForceQuoteFollowUpRoute,
    isSessionQuoteFollowUp,
    applyQuoteFollowUpIntentOverride,
    reconcilePostIntentFollowUp,
    extractFlexComparisonContext,
    buildFlexComparisonReplyPayload,
    buildFlexComparisonQuote,
    buildFlexComparisonNarrative,
  });
  if (intentPipeline.payload) return respond(intentPipeline.payload);
  const enrichedIntent = intentPipeline.intent;
  const {
    topService,
    catalogReply,
    isDiscoveryIntent,
  } = buildDiscoveryRoutingState({
    index,
    effectiveUserText,
    userText,
    intent: enrichedIntent,
  }, {
    buildRegistryQuery,
    searchServiceRegistry,
    serviceHasRequiredInputs,
    buildCatalogListingReply,
  });
  const discoveryRoutePayload = await resolveDiscoveryRoutePayload({
    cfg,
    index,
    conversation,
    userText,
    effectiveUserText,
    sessionContext,
    intent: enrichedIntent,
    catalogReply,
    isDiscoveryIntent,
  }, {
    buildAssistantContextPack,
    writeStructuredContextReply,
    buildStructuredDiscoveryFallback,
    isConceptualPricingQuestion,
    hasExplicitQuoteLead,
    buildServiceUnavailableMessage,
    summarizeContextPack,
  });
  if (discoveryRoutePayload) return respond(discoveryRoutePayload);
  const quoteCandidateState = prepareQuoteCandidateState({
    index,
    sessionContext,
    userText,
    effectiveUserText,
    intent: enrichedIntent,
    topService,
    contextualFollowUp,
    compositeLike,
  }, {
    getServiceFamily,
    mergeSessionQuoteFollowUpByRoute,
    findUncoveredComputeVariant,
    canSafelyQuoteUncoveredComputeVariant,
    buildUncoveredComputeReply,
    buildAssistantContextPack,
    summarizeContextPack,
    serviceHasRequiredInputs,
    isDiscoveryOrExplanationQuestion,
    buildQuoteRequestShape,
    preserveCriticalPromptModifiers,
    choosePreferredQuote,
  });
  if (quoteCandidateState.fallbackPayload) return respond(quoteCandidateState.fallbackPayload);
  const effectiveQuoteText = quoteCandidateState.effectiveQuoteText;
  Object.assign(enrichedIntent, quoteCandidateState.intent);
  const familyMeta = quoteCandidateState.familyMeta;
  const reformulatedRequest = quoteCandidateState.reformulatedRequest;
  const preflightQuote = quoteCandidateState.preflightQuote;
  const quoteClarificationState = reconcileQuoteClarificationState({
    intent: enrichedIntent,
    reformulatedRequest,
    effectiveUserText,
    userText,
    familyMeta,
    preflightQuote,
    getPreQuoteClarification,
    getMissingRequiredInputs,
    getClarificationMessage,
  });
  const postClarification = await resolvePostClarificationRouting({
    cfg,
    index,
    conversation,
    userText,
    effectiveUserText,
    sessionContext,
    intent: enrichedIntent,
    familyMeta,
    reformulatedRequest,
    preflightQuote,
    quoteClarificationState,
  }, {
    hasExplicitByolChoice,
    shouldAskLicenseChoice,
    buildLicenseChoiceClarificationPayload,
    quoteFromPrompt,
    parsePromptRequest,
    formatAssumptions,
    detectByolAmbiguity,
    buildByolAmbiguityClarificationPayload,
    filterQuoteByByolChoice,
    toMarkdownQuote,
    buildQuoteNarrative,
    buildQuoteUnresolvedPayload,
    buildAnswerFallbackPayload,
    summarizeMatches,
    writeNaturalReply,
  });
  Object.assign(enrichedIntent, postClarification.intent);
  return respond(postClarification.payload);
}

module.exports = {
  buildDeterministicExpertSummary,
  respondToAssistant,
  sanitizeQuoteEnrichment,
};
