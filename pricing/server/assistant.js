'use strict';

const { quoteFromPrompt, parsePromptRequest } = require('./quotation-engine');
const { searchProducts, searchPresets, searchServiceRegistry, serviceHasRequiredInputs } = require('./catalog');
const { getServiceFamily, getMissingRequiredInputs, buildCanonicalRequest } = require('./service-families');
const { inferConsumptionPattern, explainConsumptionPattern } = require('./consumption-model');
const { runChat, extractChatText } = require('./genai');
const { analyzeIntent, analyzeImageIntent } = require('./intent-extractor');

const RESPONSE_PROMPT = [
  'You are an OCI pricing specialist speaking to a customer.',
  'Be concise, natural, and practical.',
  'If a deterministic quotation is provided, explain what was matched and mention any assumptions or warnings.',
  'Do not invent prices, SKUs, tiers, or formulas.',
  'If no quotation is available, explain the situation clearly and ask at most one next question when needed.',
  'Do not render tables.',
  'Use plain markdown.',
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

function summarizeMatches(index, text) {
  const products = searchProducts(index, text, 5).map((item) => item.fullDisplayName);
  const presets = searchPresets(index, text, 3).map((item) => item.displayName);
  return { products, presets };
}

function isCatalogListingRequest(text) {
  const source = String(text || '').trim().toLowerCase();
  if (!source) return false;
  return /\blist all skus?\b/.test(source) ||
    /\bwhat\b.*\boptions\b.*\bcatalog\b/.test(source) ||
    /\bavailable\b.*\bcatalog\b/.test(source) ||
    /\bshow\b.*\bskus?\b/.test(source) ||
    /\blist\b.*\b(hourly prices?|prices?)\b/.test(source);
}

function buildRegistryQuery(text, intent = {}) {
  return String(text || '')
    .replace(/\bquote\b/ig, ' ')
    .replace(/\b\d[\d,]*(?:\.\d+)?\s*(?:requests?|api calls?|transactions?|queries?|emails?|messages?|sms(?: messages?)?|tokens?|gb|tb|mbps|gbps|users?|named users?|ocpus?|ecpus?|hours?|days?)\b/ig, ' ')
    .replace(/[,+]/g, ' ')
    .replace(/\bper month\b|\bper hour\b|\bper day\b|\bmonthly\b|\bhourly\b/ig, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function firstUsdTier(product) {
  const tiers = product?.tiersByCurrency?.USD || [];
  if (!tiers.length) return null;
  return tiers.find((tier) => Number.isFinite(Number(tier.value))) || null;
}

function formatProductCatalogLine(product) {
  const tier = firstUsdTier(product);
  const metric = product.metricDisplayName || product.metricUnitDisplayName || '-';
  const unit = tier ? formatMoney(tier.value, 'USD') : 'USD -';
  return `- \`${product.partNumber}\` | ${product.displayName} | ${metric} | ${unit}`;
}

function findCatalogProducts(index, text, intent) {
  const source = String(text || '');
  const family = String(intent?.serviceFamily || '');
  if (isFastConnectText(source) || family === 'network_fastconnect') {
    return index.products
      .filter((product) => /fastconnect/i.test(`${product.displayName} ${product.serviceCategoryDisplayName}`))
      .filter((product) => ['HOUR', 'HOUR_UTILIZED'].includes(product.priceType))
      .sort((a, b) => a.displayName.localeCompare(b.displayName));
  }

  const registryMatches = searchServiceRegistry(index.serviceRegistry, source, 5);
  const topService = registryMatches[0];
  if (topService?.partNumbers?.length) {
    const products = topService.partNumbers
      .flatMap((partNumber) => index.productsByPartNumber.get(partNumber) || [])
      .filter(Boolean);
    if (products.length) return products;
  }

  return searchProducts(index, source, 20);
}

function buildCatalogListingReply(index, text, intent) {
  const products = findCatalogProducts(index, text, intent);
  const unique = [];
  const seen = new Set();
  for (const product of products) {
    if (!product?.partNumber || seen.has(product.partNumber)) continue;
    seen.add(product.partNumber);
    unique.push(product);
  }
  if (!unique.length) return null;
  const lines = unique.slice(0, 20).map(formatProductCatalogLine);
  return [
    'I checked the OCI pricing catalog already loaded by the agent.',
    'This listing is based on the current global catalog data packaged in the app, so no region input is required for this catalog lookup.',
    '### Catalog matches',
    ...lines,
  ].join('\n\n');
}

function isGreeting(text) {
  return /^(hola|hello|hi|hey|buenas|good morning|good afternoon|good evening)\b[!. ]*$/i.test(String(text || '').trim());
}

function isFastConnectText(text) {
  return /\bfast\s*connect\b|\bfastconnect\b/i.test(String(text || ''));
}

function isDedicatedRerankTransactionPrompt(text) {
  const source = String(text || '');
  if (!/\brerank\b/i.test(source)) return false;
  if (!/\btransactions?\b/i.test(source)) return false;
  if (/\bhours?\b|\bcluster-hours?\b/i.test(source)) return false;
  return true;
}

function conversationMentionsFastConnect(conversation) {
  return (conversation || []).some((item) => isFastConnectText(item.content || ''));
}

function isConfidenceQuestion(text) {
  return /\b(estas seguro|estás seguro|seguro de ese precio|are you sure|is that price correct|is that accurate)\b/i.test(String(text || ''));
}

function parseRegionAnswer(text) {
  const source = String(text || '').trim().toLowerCase();
  if (!source) return null;
  if (/quer[eé]taro/.test(source)) return { code: 'mx-queretaro-1', label: 'Mexico Central (Queretaro)' };
  if (/monterrey/.test(source)) return { code: 'mx-monterrey-1', label: 'Mexico Northeast (Monterrey)' };
  return null;
}

function isShortClarificationAnswer(text) {
  const source = String(text || '').trim();
  if (!source) return false;
  if (source.length > 80) return false;
  return /^(byol|bring your own license|license included|included|con licencia incluida|licencia incluida)$/i.test(source);
}

function isLicenseModeFollowUp(text) {
  const source = String(text || '').trim();
  if (!source || source.length > 160) return false;
  return /\b(byol|bring your own license|license included|included|con licencia incluida|licencia incluida)\b/i.test(source);
}

function isShortContextualAnswer(text) {
  const source = String(text || '').trim();
  if (!source || source.length > 80) return false;
  if (isShortClarificationAnswer(source) || isLicenseModeFollowUp(source)) return true;
  if (/^(on[- ]?demand|reserved|reserve[d]? pricing)$/i.test(source)) return true;
  if (/^\d+(?:\.\d+)?$/.test(source)) return true;
  if (/^(?:(?:vm|bm)\.)?(?:[a-z0-9.]+\.)?[a-z]\d+\.flex$/i.test(source)) return true;
  return false;
}

function isShapeSelectionFollowUp(text) {
  const source = String(text || '').trim();
  return /^(?:(?:vm|bm)\.)?(?:[a-z0-9.]+\.)?[a-z]\d+\.flex$/i.test(source);
}

function lastConversationItems(conversation = []) {
  const items = Array.isArray(conversation) ? conversation : [];
  let lastAssistant = null;
  let lastUser = null;
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (!lastAssistant && item.role === 'assistant') lastAssistant = item;
    if (!lastUser && item.role === 'user') lastUser = item;
    if (lastAssistant && lastUser) break;
  }
  return { lastAssistant, lastUser };
}

function extractProductContextFromAssistant(text) {
  const source = String(text || '').trim();
  if (!source) return '';
  const clarificationMatch = source.match(/do you want\s+(.+?)\s+as byol or license included\??/i);
  if (clarificationMatch) return String(clarificationMatch[1] || '').trim();
  const quoteMatch = source.match(/quotation for\s+`([^`]+)`/i);
  if (quoteMatch) return String(quoteMatch[1] || '').trim();
  return '';
}

function findPriorProductPrompt(conversation = []) {
  const items = Array.isArray(conversation) ? conversation : [];
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (item.role !== 'user') continue;
    const content = String(item.content || '').trim();
    if (!content) continue;
    if (isLicenseModeFollowUp(content)) continue;
    return content;
  }
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (item.role !== 'assistant') continue;
    const extracted = extractProductContextFromAssistant(item.content || '');
    if (extracted) return `Quote ${extracted}`;
  }
  return '';
}

function normalizeLicenseModeText(text) {
  const source = String(text || '').trim();
  if (/\bbyol\b|\bbring your own license\b/i.test(source)) return 'BYOL';
  if (/\blicense included\b|\binclude license\b|\bcon licencia incluida\b|\blicencia incluida\b|\bincluded\b/i.test(source)) return 'License Included';
  return source;
}

function mergeClarificationAnswer(conversation, userText) {
  const isLicenseFollowUp = isLicenseModeFollowUp(userText);
  const isShapeFollowUp = isShapeSelectionFollowUp(userText);
  if (!isLicenseFollowUp && !isShapeFollowUp) return userText;
  const { lastAssistant, lastUser } = lastConversationItems(conversation);
  const assistantText = String(lastAssistant?.content || '');
  const previousPrompt = findPriorProductPrompt(conversation) || String(lastUser?.content || '').trim();
  if (!previousPrompt) return userText;
  const assistantProductContext = extractProductContextFromAssistant(assistantText);
  if (isShapeFollowUp && /which oci vm shape should i use|which .*shape should i use/i.test(assistantText)) {
    return `${previousPrompt} ${String(userText || '').trim()}`.trim();
  }
  if (/\b(BYOL|License Included)\b/i.test(assistantText) || assistantProductContext) {
    return `${previousPrompt} ${normalizeLicenseModeText(userText)}`.trim();
  }
  return userText;
}

function isFlexComparisonRequest(text) {
  const source = String(text || '');
  const matches = source.match(/\b[a-z]\d+\.flex\b/ig) || [];
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
    /\bintegration cloud\b/.test(source),
    /\banalytics cloud\b/.test(source),
    /\bdata integration\b/.test(source),
    /\bmonitoring\b/.test(source),
    /\bnotifications\b/.test(source),
    /\bhttps delivery\b|\bemail delivery\b/.test(source),
    /\biam sms\b|\bsms messages?\b/.test(source),
    /\bthreat intelligence\b/.test(source),
    /\bfleet application management\b/.test(source),
    /\boci batch\b|\bbatch\b/.test(source),
    /\bdata safe\b/.test(source),
    /\blog analytics\b/.test(source),
    /\bfunctions\b/.test(source),
    /\bgenerative ai\b/.test(source),
    /\bvision\b|\bspeech\b|\bmedia flow\b/.test(source),
    /\bfile storage\b/.test(source),
    /\bautonomous(?: ai)? lakehouse\b|\bautonomous data warehouse\b|\bbase database service\b|\bexadata\b|\bdatabase cloud service\b/.test(source),
    /\b(?:vm|bm)\.[a-z0-9.]+\.flex\b/.test(source) || /\b[a-z]\d+\.flex\b/.test(source),
  ].filter(Boolean).length;
  if (/\bcompare\b/.test(source) && /\b[a-z]\d+\.flex\b/.test(source)) return true;
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
  const extractedInputs = {
    ...((intent && typeof intent.extractedInputs === 'object' && intent.extractedInputs) || {}),
  };
  if (intent.serviceFamily === 'security_waf') {
    const genericInstances = Number(extractedInputs.instanceCount);
    if (Number.isFinite(genericInstances) && genericInstances > 0 && !Number.isFinite(Number(extractedInputs.wafInstances))) {
      extractedInputs.wafInstances = genericInstances;
    }
  }
  if (intent.serviceFamily === 'security_data_safe') {
    const dbCount = Number(extractedInputs.numberOfDatabases);
    if (Number.isFinite(dbCount) && dbCount > 0 && !Number.isFinite(Number(extractedInputs.quantity))) {
      extractedInputs.quantity = dbCount;
    }
  }
  return {
    ...intent,
    extractedInputs,
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
  const matches = String(text || '').match(/\b[a-z]\d+\.flex\b/ig) || [];
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

function buildFlexComparisonQuote(index, context) {
  const rows = [];
  const warnings = [];
  for (const shape of context.shapes) {
    const basePrompt = `Quote ${shape} ${context.ocpus} OCPUs ${context.memoryGb} GB RAM ${context.hours}h`;
    const onDemandQuote = quoteFromPrompt(index, basePrompt);
    let variantPrompt = '';
    if (context.modifierKind === 'capacity-reservation') variantPrompt = `${basePrompt} capacity reservation ${context.utilization}`;
    if (context.modifierKind === 'preemptible') variantPrompt = `${basePrompt} preemptible`;
    if (context.modifierKind === 'burstable') variantPrompt = `${basePrompt} burstable baseline ${context.burstableBaseline}`;
    const modifierQuote = quoteFromPrompt(index, variantPrompt);
    if (!onDemandQuote.ok || !modifierQuote.ok) {
      warnings.push(`Could not build a complete comparison for ${shape}.`);
      continue;
    }
    if (Array.isArray(onDemandQuote.warnings) && onDemandQuote.warnings.length) {
      warnings.push(...onDemandQuote.warnings.map((item) => `${shape.toUpperCase()}: ${item}`));
    }
    if (Array.isArray(modifierQuote.warnings) && modifierQuote.warnings.length) {
      warnings.push(...modifierQuote.warnings.map((item) => `${shape.toUpperCase()}: ${item}`));
    }
    rows.push({
      shape: shape.toUpperCase(),
      onDemandMonthly: Number(onDemandQuote.totals?.monthly || 0),
      variantMonthly: Number(modifierQuote.totals?.monthly || 0),
      deltaMonthly: Number(modifierQuote.totals?.monthly || 0) - Number(onDemandQuote.totals?.monthly || 0),
      onDemandAnnual: Number(onDemandQuote.totals?.annual || 0),
      variantAnnual: Number(modifierQuote.totals?.annual || 0),
    });
  }
  if (!rows.length) {
    return { ok: false, warnings: warnings.length ? warnings : ['No Flex shapes could be compared.'] };
  }
  rows.sort((a, b) => a.onDemandMonthly - b.onDemandMonthly);
  const variantLabel = context.modifierKind === 'capacity-reservation'
    ? 'Capacity Reservation'
    : context.modifierKind === 'preemptible'
      ? 'Preemptible'
      : 'Burstable';
  const markdown = [
    `| Shape | On-demand $/Mo | ${variantLabel} $/Mo | Delta $/Mo | On-demand Annual | ${variantLabel} Annual |`,
    '|---|---:|---:|---:|---:|---:|',
    ...rows.map((row) => `| ${row.shape} | ${money(row.onDemandMonthly)} | ${money(row.variantMonthly)} | ${money(row.deltaMonthly)} | ${money(row.onDemandAnnual)} | ${money(row.variantAnnual)} |`),
  ].join('\n');
  return { ok: true, rows, markdown, warnings: Array.from(new Set(warnings)) };
}

function buildFlexComparisonNarrative(context, comparison) {
  const modifierLabel = context.modifierKind === 'capacity-reservation'
    ? 'Capacity Reservation'
    : context.modifierKind === 'preemptible'
      ? 'Preemptible'
      : 'Burstable';
  const assumptions = [
    `- Compared shapes: ${context.shapes.map((shape) => shape.toUpperCase()).join(', ')}.`,
    `- Size used for each shape: ${context.ocpus} OCPUs, ${context.memoryGb} GB RAM, ${context.hours} hours/month.`,
    `- Base side uses on-demand pricing.`,
  ];
  if (context.modifierKind === 'capacity-reservation') {
    assumptions.push(`- Non-capacity-reservation side uses ${context.withoutCrMode}.`);
    assumptions.push(`- Capacity reservation utilization: ${context.utilization}.`);
  }
  if (context.modifierKind === 'burstable') {
    assumptions.push(`- Burstable baseline: ${context.burstableBaseline}.`);
  }
  if (comparison.warnings?.length) {
    assumptions.push(...comparison.warnings.map((item) => `- ${item}`));
  }
  return [
    `I prepared a deterministic OCI Flex shape comparison for \`${context.shapes.map((shape) => shape.toUpperCase()).join(' vs ')}\`.`,
    `The comparison shows the monthly and annual totals with and without ${modifierLabel} for the same sizing.`,
    `Key assumptions:\n${assumptions.join('\n')}`,
    `### OCI comparison\n\n${comparison.markdown}`,
  ].join('\n\n');
}

function hasCompositeServiceSignal(text) {
  const source = String(text || '');
  return /\b(?:vm|bm)\.[a-z0-9.]+\.flex\b|\b[a-z]\d+\.flex\b|\bload balancer\b|\bblock storage\b|\bblock volumes?\b|\bobject storage\b|\bfile storage\b|\bfastconnect\b|\bfast connect\b|\bdns\b|\bweb application firewall\b|\bwaf\b|\bnetwork firewall\b|\bautonomous(?: ai)? lakehouse\b|\bautonomous data warehouse\b|\bbase database service\b|\bdata integration\b|\bintegration cloud\b|\banalytics cloud\b|\bdata safe\b|\blog analytics\b|\bfunctions\b|\bgenerative ai\b|\bexadata\b|\bdatabase cloud service\b|\bmonitoring\b|\bnotifications\b|\bhttps delivery\b|\bemail delivery\b|\biam sms\b|\bsms messages?\b|\bthreat intelligence\b|\bfleet application management\b|\boci batch\b|\bvision\b|\bspeech\b|\bmedia flow\b/i.test(source);
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
  return /\b(?:vm|bm)\.[a-z0-9.]+\.flex\b|\b[a-z]\d+\.flex\b|\bfunctions\b|\bfastconnect\b|\bfast connect\b|\bload balancer\b|\bfirewall\b|\bintegration cloud\b|\bworkspace usage\b|\bprocessed per hour\b|\bautonomous\b|\bexadata\b|\bdatabase cloud service\b/i.test(source);
}

function normalizeCompositeSegment(segment, fullText) {
  let out = String(segment || '').trim().replace(/^and\s+/i, '');
  out = out.replace(/^(?:quote\s+)?(?:a|an)\s+.+?\b(?:stack|platform|workload|architecture|bundle)\s+with\s+/i, '');
  const multipliedInstances = out.match(/^(\d+)\s*x\s+(.*)$/i);
  if (multipliedInstances) {
    out = `${multipliedInstances[2]} ${multipliedInstances[1]} instances`;
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

async function writeNaturalReply(cfg, conversation, userText, context) {
  const history = Array.isArray(conversation) ? conversation.slice(-6) : [];
  const contextBlock = [
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
  const explanations = [];
  const seen = new Set();
  for (const line of items) {
    const pattern = inferConsumptionPattern(line.metric, `${line.service} ${line.product}`);
    if (!pattern || pattern === 'unknown' || seen.has(pattern)) continue;
    seen.add(pattern);
    const text = explainConsumptionPattern(pattern, {
      displayName: line.product,
      fullDisplayName: line.product,
    });
    if (text) explanations.push(`- ${text}`);
    if (explanations.length >= 3) break;
  }
  return explanations;
}

function buildComputeVmClarificationQuestion(intent = {}) {
  const vendor = String(intent?.extractedInputs?.processorVendor || '').toLowerCase();
  if (vendor === 'amd') {
    return 'Which OCI AMD VM shape should I use for that machine? Common AMD flex options are `E4.Flex` or `E5.Flex`. Once you pick the shape, I can combine it with the attached Block Volume sizing.';
  }
  if (vendor === 'arm' || vendor === 'ampere') {
    return 'Which OCI Arm VM shape should I use for that machine? A common Arm flex option is `A1.Flex`. Once you pick the shape, I can combine it with the attached Block Volume sizing.';
  }
  return 'Which OCI VM shape should I use for that machine? For Intel, common options are `E4.Flex` or `E5.Flex`. Once you pick the shape, I can combine it with the attached Block Volume sizing.';
}

function detectGenericComputeShapeClarification(text) {
  const source = String(text || '');
  const parsed = parsePromptRequest(source);
  const hasVmSignal = /\bvirtual machine\b|\bcompute instance\b|\bvm\b/i.test(source) || !!parsed.processorVendor;
  const hasSizing = Number(parsed.ocpus || 0) > 0 && Number(parsed.memoryQuantity || 0) > 0;
  const missingShape = !parsed.shapeSeries && !parsed.shape;
  if (!hasVmSignal || !hasSizing || !missingShape) return null;
  return {
    serviceFamily: 'compute_vm_generic',
    extractedInputs: {
      ocpus: parsed.ocpus,
      memoryGb: parsed.memoryQuantity,
      capacityGb: parsed.capacityGb,
      processorVendor: parsed.processorVendor,
    },
    question: buildComputeVmClarificationQuestion({ extractedInputs: { processorVendor: parsed.processorVendor } }),
  };
}

function hasExplicitByolChoice(text) {
  const source = String(text || '');
  if (/\bbyol\b|\bbring your own license\b/i.test(source)) return 'byol';
  if (/\blicense included\b|\binclude license\b|\bcon licencia incluida\b|\blicencia incluida\b/i.test(source)) return 'license-included';
  return '';
}

function normalizeByolKey(text) {
  return String(text || '')
    .replace(/^B\d+\s*-\s*/i, '')
    .replace(/\s*-\s*BYOL\b/ig, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function shouldAskLicenseChoice(familyMeta, intent, byolChoice) {
  if (!familyMeta?.requireLicenseChoice || byolChoice) return false;
  const inputs = intent?.extractedInputs || {};
  const skipKeys = Array.isArray(familyMeta.licenseNotRequiredWhenAnyInputs)
    ? familyMeta.licenseNotRequiredWhenAnyInputs
    : [];
  if (skipKeys.some((key) => {
    const value = inputs[key];
    if (typeof value === 'string') return value.trim().length > 0;
    return Number.isFinite(Number(value)) && Number(value) > 0;
  })) {
    return false;
  }
  return true;
}

function detectByolAmbiguity(quote) {
  const lineItems = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const groups = new Map();
  for (const line of lineItems) {
    const product = String(line.product || '');
    const isByol = /\bBYOL\b/i.test(product);
    const key = `${line.service || ''}|${line.metric || ''}|${normalizeByolKey(product)}`;
    if (!groups.has(key)) groups.set(key, { byol: false, included: false, sample: product });
    const entry = groups.get(key);
    if (isByol) entry.byol = true;
    else entry.included = true;
  }
  for (const entry of groups.values()) {
    if (entry.byol && entry.included) return entry.sample;
  }
  return '';
}

function filterQuoteByByolChoice(quote, choice) {
  if (!quote?.ok || !choice) return quote;
  const selected = String(choice).toLowerCase();
  const lineItems = Array.isArray(quote.lineItems) ? quote.lineItems : [];
  const filtered = lineItems.filter((line) => {
    const product = String(line.product || '');
    const isByol = /\bBYOL\b/i.test(product);
    if (!/\bBYOL\b/i.test(product) && !lineItems.some((other) => normalizeByolKey(other.product) === normalizeByolKey(product) && /\bBYOL\b/i.test(other.product))) {
      return true;
    }
    return selected === 'byol' ? isByol : !isByol;
  });
  if (!filtered.length) return quote;
  const totals = filtered.reduce((acc, line) => {
    acc.monthly += Number(line.monthly || 0);
    acc.annual += Number(line.annual || 0);
    return acc;
  }, { monthly: 0, annual: 0, currencyCode: quote.totals?.currencyCode || 'USD' });
  return {
    ...quote,
    lineItems: filtered,
    totals,
    markdown: toMarkdownQuote(filtered, totals),
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

async function respondToAssistant({ cfg, index, conversation, userText, imageDataUrl }) {
  const effectiveUserText = mergeClarificationAnswer(conversation, userText);
  const contextualFollowUp = isShortContextualAnswer(userText);
  const compositeLike = isCompositeOrComparisonRequest(effectiveUserText);
  const flexComparison = extractFlexComparisonContext(conversation, userText);
  const computeShapeClarification = detectGenericComputeShapeClarification(effectiveUserText);
  if (isGreeting(userText)) {
    return {
      ok: true,
      mode: 'answer',
      message: 'Hola. Puedo ayudarte a cotizar servicios de OCI, comparar SKUs, explicar pricing o estimar un Excel. Si quieres una cotización directa, dime el producto y las variables clave como cantidad, horas, OCPU/ECPU, storage o bandwidth.',
      intent: { intent: 'answer', shouldQuote: false, needsClarification: false },
    };
  }

  if (conversationMentionsFastConnect(conversation) && isConfidenceQuestion(userText)) {
    return {
      ok: true,
      mode: 'answer',
      message: 'Sí para el cargo base del puerto. En OCI, el precio de FastConnect para el puerto es uniforme entre regiones, así que la región no cambia esa cotización base. Si quieres, puedo ayudarte a revisar además otros cargos relacionados, como conectividad adicional o tráfico de salida, pero el puerto de 1 Gbps sigue siendo el mismo.',
      intent: { intent: 'answer', shouldQuote: false, needsClarification: false },
    };
  }

  const explicitRegion = parseRegionAnswer(userText);
  if (conversationMentionsFastConnect(conversation) && explicitRegion) {
    return {
      ok: true,
      mode: 'answer',
      message: `${explicitRegion.label} es una región válida de OCI (${explicitRegion.code}). Para FastConnect, el precio base del puerto no cambia por región, así que la cotización del puerto se mantiene. Si quieres, el siguiente paso es revisar si en tu caso hay cargos adicionales asociados al diseño de conectividad.`,
      intent: { intent: 'answer', shouldQuote: false, needsClarification: false },
    };
  }

  if (computeShapeClarification) {
    return {
      ok: true,
      mode: 'clarification',
      message: computeShapeClarification.question,
      intent: {
        intent: 'quote',
        shouldQuote: true,
        needsClarification: true,
        clarificationQuestion: computeShapeClarification.question,
        serviceFamily: computeShapeClarification.serviceFamily,
        extractedInputs: computeShapeClarification.extractedInputs,
      },
    };
  }

  if (isFlexComparisonRequest(effectiveUserText)) {
    const modifierKind = detectFlexComparisonModifier(effectiveUserText);
    if (modifierKind === 'capacity-reservation' && parseCapacityReservationUtilization(effectiveUserText) === null) {
      return {
        ok: true,
        mode: 'clarification',
        message: 'For the Flex shape comparison, what capacity reservation utilization should I use: for example `1.0`, `0.7`, or `0.5`?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'What capacity reservation utilization should I use for the comparison?' },
      };
    }
    if (modifierKind === 'burstable' && parseBurstableBaseline(effectiveUserText) === null) {
      return {
        ok: true,
        mode: 'clarification',
        message: 'For the Flex shape comparison, what burstable baseline should I use: for example `0.5`, `0.25`, or `0.125`?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'What burstable baseline should I use for the comparison?' },
      };
    }
  }

  if (flexComparison) {
    if (flexComparison.modifierKind === 'capacity-reservation' && flexComparison.utilization === null) {
      return {
        ok: true,
        mode: 'clarification',
        message: 'For the Flex shape comparison, what capacity reservation utilization should I use: for example `1.0`, `0.7`, or `0.5`?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'What capacity reservation utilization should I use for the comparison?' },
      };
    }
    if (flexComparison.modifierKind === 'burstable' && flexComparison.burstableBaseline === null) {
      return {
        ok: true,
        mode: 'clarification',
        message: 'For the Flex shape comparison, what burstable baseline should I use: for example `0.5`, `0.25`, or `0.125`?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'What burstable baseline should I use for the comparison?' },
      };
    }
    if (flexComparison.modifierKind === 'capacity-reservation' && !flexComparison.withoutCrMode) {
      return {
        ok: true,
        mode: 'clarification',
        message: 'For the non-capacity-reservation side of the comparison, should I use `On demand` pricing?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'Should I use On demand pricing for the non-capacity-reservation side?' },
      };
    }
    if (flexComparison.modifierKind === 'capacity-reservation' && flexComparison.withoutCrMode !== 'on-demand') {
      return {
        ok: true,
        mode: 'clarification',
        message: 'Reserved pricing for the non-capacity-reservation side is not modeled yet in this comparison flow. If you want, reply with `On demand` and I will generate the deterministic comparison.',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'Reply with On demand to continue the Flex comparison.' },
      };
    }
    const comparison = buildFlexComparisonQuote(index, flexComparison);
    if (comparison.ok) {
      return {
        ok: true,
        mode: 'quote',
        message: buildFlexComparisonNarrative(flexComparison, comparison),
        quote: {
          ok: true,
          request: {
            source: flexComparison.basePrompt,
            comparison: true,
          },
          comparison,
        },
        intent: {
          intent: 'quote',
          shouldQuote: true,
          needsClarification: false,
          clarificationQuestion: '',
        },
      };
    }
  }

  if (compositeLike) {
    const compositeQuote = buildCompositeQuoteFromSegments(index, effectiveUserText);
    if (compositeQuote?.ok) {
      return {
        ok: true,
        mode: 'quote',
        message: await buildQuoteNarrative(cfg, effectiveUserText, compositeQuote, formatAssumptions([], parsePromptRequest(effectiveUserText))),
        quote: compositeQuote,
        intent: {
          intent: 'quote',
          shouldQuote: true,
          needsClarification: false,
          clarificationQuestion: '',
        },
      };
    }
  }

  const rawParsedRequest = parsePromptRequest(effectiveUserText);
  const isSimpleTransactionalQuote = !compositeLike &&
    Number.isFinite(Number(rawParsedRequest.requestCount)) &&
    !Number.isFinite(Number(rawParsedRequest.ocpus)) &&
    !Number.isFinite(Number(rawParsedRequest.ecpus)) &&
    !Number.isFinite(Number(rawParsedRequest.capacityGb)) &&
    !Number.isFinite(Number(rawParsedRequest.users)) &&
    !rawParsedRequest.shape &&
    !rawParsedRequest.serviceFamily;
  if (isSimpleTransactionalQuote) {
    const rawQuote = quoteFromPrompt(index, effectiveUserText);
    if (rawQuote.ok && rawQuote.resolution?.type === 'service') {
      return {
        ok: true,
        mode: 'quote',
        message: await buildQuoteNarrative(cfg, effectiveUserText, rawQuote, formatAssumptions([], rawParsedRequest)),
        quote: rawQuote,
        intent: {
          intent: 'quote',
          shouldQuote: true,
          needsClarification: false,
          clarificationQuestion: '',
        },
      };
    }
  }

  const intent = imageDataUrl
    ? await analyzeImageIntent(cfg, effectiveUserText, imageDataUrl)
    : await analyzeIntent(cfg, conversation, effectiveUserText);
  const enrichedIntent = enrichExtractedInputsForFamily(intent);
  const mergedContextualFollowUp = contextualFollowUp && effectiveUserText !== userText;
  if (mergedContextualFollowUp) {
    enrichedIntent.reformulatedRequest = effectiveUserText;
    enrichedIntent.normalizedRequest = effectiveUserText;
  }
  if (contextualFollowUp && enrichedIntent?.reformulatedRequest) {
    enrichedIntent.normalizedRequest = String(enrichedIntent.reformulatedRequest).trim();
  }
  const postIntentFlexComparison = flexComparison || extractFlexComparisonContext(
    conversation,
    userText,
    enrichedIntent?.reformulatedRequest || enrichedIntent?.normalizedRequest || '',
  );
  if (postIntentFlexComparison) {
    if (postIntentFlexComparison.modifierKind === 'capacity-reservation' && postIntentFlexComparison.utilization === null) {
      return {
        ok: true,
        mode: 'clarification',
        message: 'For the Flex shape comparison, what capacity reservation utilization should I use: for example `1.0`, `0.7`, or `0.5`?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'What capacity reservation utilization should I use for the comparison?' },
      };
    }
    if (postIntentFlexComparison.modifierKind === 'burstable' && postIntentFlexComparison.burstableBaseline === null) {
      return {
        ok: true,
        mode: 'clarification',
        message: 'For the Flex shape comparison, what burstable baseline should I use: for example `0.5`, `0.25`, or `0.125`?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'What burstable baseline should I use for the comparison?' },
      };
    }
    if (postIntentFlexComparison.modifierKind === 'capacity-reservation' && !postIntentFlexComparison.withoutCrMode) {
      return {
        ok: true,
        mode: 'clarification',
        message: 'For the non-capacity-reservation side of the comparison, should I use `On demand` pricing?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'Should I use On demand pricing for the non-capacity-reservation side?' },
      };
    }
    if (postIntentFlexComparison.modifierKind === 'capacity-reservation' && postIntentFlexComparison.withoutCrMode !== 'on-demand') {
      return {
        ok: true,
        mode: 'clarification',
        message: 'Reserved pricing for the non-capacity-reservation side is not modeled yet in this comparison flow. If you want, reply with `On demand` and I will generate the deterministic comparison.',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'Reply with On demand to continue the Flex comparison.' },
      };
    }
    const comparison = buildFlexComparisonQuote(index, postIntentFlexComparison);
    if (comparison.ok) {
      return {
        ok: true,
        mode: 'quote',
        message: buildFlexComparisonNarrative(postIntentFlexComparison, comparison),
        quote: {
          ok: true,
          request: {
            source: postIntentFlexComparison.basePrompt,
            comparison: true,
          },
          comparison,
        },
        intent: {
          intent: 'quote',
          shouldQuote: true,
          needsClarification: false,
          clarificationQuestion: '',
        },
      };
    }
  }
  const registryQuery = buildRegistryQuery(
    String(effectiveUserText || userText || enrichedIntent.normalizedRequest || enrichedIntent.reformulatedRequest || '').trim(),
    enrichedIntent,
  );
  const registryMatches = searchServiceRegistry(index.serviceRegistry, registryQuery, 5);
  const topService = registryMatches.find((item) => item.deterministic && serviceHasRequiredInputs(item, enrichedIntent.extractedInputs)) || registryMatches[0];
  if (isCatalogListingRequest(userText) || (enrichedIntent.intent === 'discover' && !enrichedIntent.shouldQuote)) {
    const catalogReply = buildCatalogListingReply(index, registryQuery || userText, enrichedIntent);
    if (catalogReply) {
      return {
        ok: true,
        mode: 'answer',
        message: catalogReply,
        intent: {
          ...enrichedIntent,
          intent: 'discover',
          shouldQuote: false,
          needsClarification: false,
          clarificationQuestion: '',
        },
      };
    }
  }
  const interpretedFamilyMeta = getServiceFamily(enrichedIntent.serviceFamily);
  if (!compositeLike && topService && topService.deterministic && serviceHasRequiredInputs(topService, enrichedIntent.extractedInputs) && (!enrichedIntent.serviceFamily || !interpretedFamilyMeta)) {
    enrichedIntent.serviceName = topService.name;
    enrichedIntent.normalizedRequest = String(effectiveUserText || userText || enrichedIntent.normalizedRequest || '').trim();
    if (!enrichedIntent.shouldQuote || enrichedIntent.needsClarification) {
      enrichedIntent.intent = 'quote';
      enrichedIntent.shouldQuote = true;
      enrichedIntent.needsClarification = false;
      enrichedIntent.clarificationQuestion = '';
    }
  }
  const familyMeta = interpretedFamilyMeta;
  const canonicalFamilyRequest = !compositeLike && familyMeta
    ? String(buildCanonicalRequest(enrichedIntent, effectiveUserText) || '').trim()
    : '';
  const reformulatedRequest = compositeLike
    ? effectiveUserText
    : familyMeta
      ? (canonicalFamilyRequest || String(
        (contextualFollowUp
          ? (enrichedIntent.reformulatedRequest || enrichedIntent.normalizedRequest)
          : (enrichedIntent.normalizedRequest || enrichedIntent.reformulatedRequest))
        || effectiveUserText,
      ).trim() || effectiveUserText)
      : effectiveUserText;
  const preflightQuote = !compositeLike && familyMeta
    ? choosePreferredQuote(
      quoteFromPrompt(index, effectiveUserText),
      quoteFromPrompt(index, reformulatedRequest),
    )
    : null;
  if (isDedicatedRerankTransactionPrompt(reformulatedRequest || effectiveUserText || userText)) {
    const rerankFamily = getServiceFamily('ai_rerank_dedicated');
    if (rerankFamily?.clarificationQuestion) {
      return {
        ok: true,
        mode: 'clarification',
        message: rerankFamily.clarificationQuestion,
        intent: {
          ...enrichedIntent,
          serviceFamily: 'ai_rerank_dedicated',
          needsClarification: true,
          clarificationQuestion: rerankFamily.clarificationQuestion,
        },
      };
    }
  }
  const missingInputs = getMissingRequiredInputs(enrichedIntent);
  const canQuoteDespiteMissingInputs = !!(familyMeta && missingInputs.length && preflightQuote?.ok);
  if (familyMeta && enrichedIntent.shouldQuote && (!missingInputs.length || canQuoteDespiteMissingInputs)) {
    enrichedIntent.needsClarification = false;
    enrichedIntent.clarificationQuestion = '';
  }
  const byolChoice = hasExplicitByolChoice(`${userText}\n${reformulatedRequest}`);
  if (shouldAskLicenseChoice(familyMeta, enrichedIntent, byolChoice)) {
    return {
      ok: true,
      mode: 'clarification',
      message: familyMeta.licenseClarificationQuestion || `Before I quote ${familyMeta.canonical}, do you want BYOL or License Included?`,
      intent: {
        ...enrichedIntent,
        needsClarification: true,
        clarificationQuestion: familyMeta.licenseClarificationQuestion || 'Do you want BYOL or License Included?',
      },
    };
  }
  if (familyMeta && missingInputs.length && familyMeta.clarificationQuestion && !canQuoteDespiteMissingInputs) {
    const clarificationMessage = familyMeta.id === 'compute_vm_generic'
      ? buildComputeVmClarificationQuestion(intent)
      : familyMeta.clarificationQuestion;
    return {
      ok: true,
      mode: 'clarification',
      message: clarificationMessage,
      intent: {
        ...enrichedIntent,
        needsClarification: true,
        clarificationQuestion: clarificationMessage,
      },
    };
  }

  if (enrichedIntent.needsClarification && enrichedIntent.clarificationQuestion) {
    return {
      ok: true,
      mode: 'clarification',
      message: String(enrichedIntent.clarificationQuestion).trim(),
      intent: enrichedIntent,
    };
  }

  if (enrichedIntent.shouldQuote) {
    let quote = preflightQuote?.ok ? preflightQuote : quoteFromPrompt(index, reformulatedRequest);
    const parsed = parsePromptRequest(reformulatedRequest);
    const assumptions = formatAssumptions(enrichedIntent.assumptions, parsed);

    const byolAmbiguousProduct = quote.ok && !byolChoice ? detectByolAmbiguity(quote) : '';
    if (byolAmbiguousProduct) {
      return {
        ok: true,
        mode: 'clarification',
        message: `Antes de cotizar ${byolAmbiguousProduct}, necesito confirmar la modalidad de licencia: ¿quieres **BYOL** o **License Included**?`,
        intent: {
          ...enrichedIntent,
          needsClarification: true,
          clarificationQuestion: 'Do you want BYOL or License Included?',
        },
      };
    }
    if (quote.ok && byolChoice) {
      quote = filterQuoteByByolChoice(quote, byolChoice);
    }

    if (quote.ok) {
      return {
        ok: true,
        mode: 'quote',
      message: await buildQuoteNarrative(cfg, effectiveUserText, quote, assumptions),
      quote,
      intent: enrichedIntent,
    };
    }

    if (familyMeta?.id === 'ai_memory_ingestion') {
      return {
        ok: true,
        mode: 'quote_unresolved',
        message: [
          'The current OCI catalog loaded by this agent does not expose a direct quotable SKU for `OCI Generative AI - Memory Ingestion`.',
          'I can see related catalog entries such as `B110463` (`OCI Generative AI Agents - Data Ingestion`) and `B112384` (`OCI Generative AI - Memory Retention`), but I should not map your request to either one automatically.',
          'If you want, I can quote one of those related services explicitly or continue once Oracle exposes a direct Memory Ingestion SKU in the live catalog.',
        ].join('\n\n'),
        quote,
        intent: enrichedIntent,
      };
    }

    const matches = summarizeMatches(index, reformulatedRequest);
    const natural = await writeNaturalReply(cfg, conversation, userText, {
      intent: enrichedIntent.intent || 'quote',
      summary: quote.error || 'No deterministic quotation could be produced.',
      warningLines: (quote.warnings || []).map((item) => `- ${item}`),
      candidateLines: [
        ...matches.products.map((item) => `- Product: ${item}`),
        ...matches.presets.map((item) => `- Preset: ${item}`),
      ],
      assumptionLines: assumptions,
    });
    return {
      ok: true,
      mode: 'quote_unresolved',
      message: natural || quote.error || 'No quotation could be generated.',
      quote,
      intent: enrichedIntent,
    };
  }

  const matches = summarizeMatches(index, userText);
  const natural = await writeNaturalReply(cfg, conversation, userText, {
    intent: enrichedIntent.intent || 'explain',
    summary: 'The user is asking for OCI pricing guidance rather than a deterministic quote.',
    candidateLines: [
      ...matches.products.map((item) => `- Product: ${item}`),
      ...matches.presets.map((item) => `- Preset: ${item}`),
    ],
    assumptionLines: Array.isArray(enrichedIntent.assumptions) ? enrichedIntent.assumptions.map((item) => `- ${item}`) : [],
  });

  return {
    ok: true,
    mode: 'answer',
    message: natural || 'I can help with OCI pricing guidance or prepare a deterministic quotation if you share the sizing details.',
    intent: enrichedIntent,
  };
}

module.exports = {
  buildDeterministicExpertSummary,
  respondToAssistant,
  sanitizeQuoteEnrichment,
};
