'use strict';

const {
  inferServiceFamily,
  normalizeServiceAliases,
  buildCanonicalRequest,
  shouldForceQuote,
  getMissingRequiredInputs,
  getServiceFamily,
} = require('./service-families');
const { findVmShapeByText } = require('./vm-shapes');

function normalizeUnits(text) {
  return String(text || '')
    .replace(/\b(\d+(?:\.\d+)?)\s*gbps?\b/ig, '$1 Gbps')
    .replace(/\b(\d+(?:\.\d+)?)\s*gb\b/ig, '$1 GB')
    .replace(/\b(\d+(?:\.\d+)?)\s*mb\b/ig, '$1 MB')
    .replace(/\b(\d+(?:\.\d+)?)\s*vpu'?s?\b/ig, '$1 VPUs')
    .replace(/\b(\d+(?:\.\d+)?)\s*ms\b/ig, '$1 milliseconds');
}

function normalizeIntentResult(intent, originalText) {
  const extractedFromText = extractStructuredInputs(originalText);
  const compositeLike = isCompositeOrComparisonRequest(originalText);
  const detectedFamily = compositeLike ? '' : inferServiceFamily(originalText);
  const normalized = {
    intent: String(intent?.intent || 'quote'),
    route: String(intent?.route || '').trim(),
    shouldQuote: !!intent?.shouldQuote,
    needsClarification: !!intent?.needsClarification,
    clarificationQuestion: String(intent?.clarificationQuestion || '').trim(),
    reformulatedRequest: String(intent?.reformulatedRequest || originalText || '').trim(),
    assumptions: Array.isArray(intent?.assumptions) ? intent.assumptions.filter(Boolean) : [],
    serviceFamily: detectedFamily || (compositeLike ? '' : inferServiceFamily(intent?.reformulatedRequest || originalText, intent?.serviceFamily)),
    serviceName: String(intent?.serviceName || '').trim(),
    extractedInputs: {
      ...(intent?.extractedInputs && typeof intent.extractedInputs === 'object' ? intent.extractedInputs : {}),
      ...extractedFromText,
    },
    confidence: Number.isFinite(Number(intent?.confidence)) ? Number(intent.confidence) : null,
    annualRequested: !!intent?.annualRequested,
    quotePlan: intent?.quotePlan && typeof intent.quotePlan === 'object' ? { ...intent.quotePlan } : {},
  };
  if (normalized.serviceFamily === 'security_waf') {
    const genericInstances = numberLike(normalized.extractedInputs.instanceCount);
    if (genericInstances !== null && numberLike(normalized.extractedInputs.wafInstances) === null) {
      normalized.extractedInputs.wafInstances = genericInstances;
    }
  }
  if (normalized.serviceFamily === 'security_data_safe') {
    const dbCount = numberLike(normalized.extractedInputs.numberOfDatabases);
    if (dbCount !== null && numberLike(normalized.extractedInputs.quantity) === null) {
      normalized.extractedInputs.quantity = dbCount;
    }
  }
  normalized.normalizedRequest = normalizeUnits(buildCanonicalRequest(normalized, originalText) || normalizeServiceAliases(normalized.reformulatedRequest || originalText));
  applyDeterministicRescue(normalized, originalText);
  normalized.route = normalizeRoute(normalized, originalText);
  normalized.quotePlan = normalizeQuotePlan(normalized, originalText);
  return normalized;
}

function normalizeRoute(normalized, originalText) {
  const explicit = String(normalized.route || '').trim().toLowerCase();
  if ([
    'quote_followup',
    'workbook_followup',
    'clarify',
  ].includes(explicit)) return explicit;
  if (normalized.needsClarification) return 'clarify';
  if (isOptionsDiscoveryQuestion(originalText)) {
    return 'product_discovery';
  }
  if (isLicensingDiscoveryQuestion(originalText)) {
    return 'product_discovery';
  }
  if (isPricingDiscoveryQuestion(originalText)) {
    return 'product_discovery';
  }
  if (isCatalogListingQuestion(originalText)) {
    return 'product_discovery';
  }
  if (isShapeDiscoveryQuestion(originalText)) {
    return 'product_discovery';
  }
  if ([
    'general_answer',
    'product_discovery',
    'quote_request',
  ].includes(explicit)) return explicit;
  if (normalized.shouldQuote) return 'quote_request';
  if (String(normalized.intent || '').toLowerCase() === 'discover') return 'product_discovery';
  return 'general_answer';
}

function normalizeQuotePlan(normalized, originalText) {
  const source = String(originalText || '');
  const family = getServiceFamily(normalized.serviceFamily);
  const raw = normalized.quotePlan && typeof normalized.quotePlan === 'object' ? normalized.quotePlan : {};
  const route = normalizeRoute(normalized, originalText);
  const candidateFamilies = Array.from(new Set([
    ...((Array.isArray(raw.candidateFamilies) ? raw.candidateFamilies : []).map((value) => String(value || '').trim()).filter(Boolean)),
    normalized.serviceFamily || '',
  ].filter(Boolean)));
  const missingInputs = Array.from(new Set([
    ...((Array.isArray(raw.missingInputs) ? raw.missingInputs : []).map((value) => String(value || '').trim()).filter(Boolean)),
    ...getMissingRequiredInputs(normalized),
  ]));
  return compactObject({
    action: String(route === 'product_discovery' || route === 'general_answer'
      ? inferPlanAction(route)
      : (raw.action || inferPlanAction(route))),
    targetType: String(raw.targetType || inferTargetType(source, normalized)),
    domain: String(raw.domain || family?.domain || ''),
    candidateFamilies,
    missingInputs,
    useDeterministicEngine: route === 'product_discovery' || route === 'general_answer'
      ? false
      : (raw.useDeterministicEngine !== undefined ? !!raw.useDeterministicEngine : route.startsWith('quote')),
  });
}

function inferPlanAction(route) {
  if (route === 'product_discovery') return 'discover';
  if (route === 'clarify') return 'clarify';
  if (route.startsWith('quote')) return 'quote';
  return 'answer';
}

function inferTargetType(source, normalized) {
  if (/\bworkbook\b|\brvtools\b|\bexcel\b/i.test(source)) return 'workbook';
  if (isCompositeOrComparisonRequest(source)) return 'bundle';
  if (isCatalogListingQuestion(source)) return 'catalog';
  if (isShapeDiscoveryQuestion(source)) return 'shape';
  if ((isOptionsDiscoveryQuestion(source) || isPricingDiscoveryQuestion(source) || isLicensingDiscoveryQuestion(source)) &&
    /\bcompute\b|\bgpu\b|\bhpc\b|\bvirtual machines?\b|\bvm instances?\b/i.test(source)) {
    return 'service';
  }
  if (isLicensingDiscoveryQuestion(source)) return normalized.serviceFamily ? 'service' : 'general';
  if (isPricingDiscoveryQuestion(source)) return normalized.serviceFamily ? 'service' : 'general';
  if (/\bshape?s?\b|\bvirtual machines?\b|\bvm instances?\b/i.test(source)) return 'shape';
  if (normalized.serviceFamily) return 'service';
  return 'general';
}

function numberLike(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function extractStructuredInputs(text) {
  const source = String(text || '');
  const shape = findVmShapeByText(source);
  const capacityGb = extractStorageCapacityGb(source);
  const vpuPerGb = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*vpu'?s?\b/i,
  ]);
  const bandwidthGbps = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*gbps?\b/i,
  ]);
  const bandwidthMbps = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*mbps?\b/i,
  ]);
  const parsedOcpus = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*ocpus?\b/i,
  ]);
  const ocpus = shape?.kind === 'fixed' ? Number(shape.fixedOcpus) : parsedOcpus;
  const ecpus = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*ecpus?\b/i,
  ]);
  const parsedMemoryGb = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*gb\s*(?:ram|memory)\b/i,
    /(?:ram|memory)[^\d]{0,20}(\d[\d,]*(?:\.\d+)?)\s*gb\b/i,
  ]);
  const memoryGb = shape?.kind === 'fixed'
    ? (Number.isFinite(Number(shape.fixedMemoryGb)) ? Number(shape.fixedMemoryGb) : parsedMemoryGb)
    : parsedMemoryGb;
  const invocationsPerDay = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*invocations?\s*(?:per|\/)\s*day/i,
  ]);
  const invocationsPerMonth = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*invocations?\s*(?:per|\/)\s*month/i,
  ]);
  const daysPerMonth = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*days?\s*(?:per|\/)\s*month/i,
  ]);
  const executionMs = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*ms\b/i,
    /(\d[\d,]*(?:\.\d+)?)\s*milliseconds?\b/i,
  ]);
  const memoryMb = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*mb\b/i,
  ]);
  const users = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*(?:users?|named users?)\b/i,
  ]);
  const firewallInstances = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*firewalls?\b/i,
    /(\d[\d,]*(?:\.\d+)?)\s*network firewalls?\b/i,
  ]);
  const wafInstances = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*(?:waf|web application firewall)\s*(?:instances?)?\b/i,
    /(\d[\d,]*(?:\.\d+)?)\s*polic(?:y|ies)\b/i,
  ]);
  const dataProcessedGb = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*gb\b[^\n,.;]*processed per hour/i,
    /(\d[\d,]*(?:\.\d+)?)\s*gb\b[^\n,.;]*data processed/i,
    /data processed[^\d]*(\d[\d,]*(?:\.\d+)?)\s*gb\b/i,
    /processed[^\d]*(\d[\d,]*(?:\.\d+)?)\s*gb\b[^\n,.;]*per hour/i,
    /(\d[\d,]*(?:\.\d+)?)\s*gb\b[^\n,.;]*(?:traffic|throughput)/i,
  ]);
  const requestCount = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*(?:requests?|api calls?|transactions?|queries?|emails?|messages?|sms(?: messages?)?|tokens?|datapoints?|events?|delivery operations?)\b/i,
  ]);
  const gpus = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*gpus?\b/i,
  ]);
  const quantity = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*(?:(?:managed|target)\s+)?(?:databases?|devices?|stations?|jobs?|resources?|nodes?|clusters?|models?|endpoints?|gpus?)\b/i,
  ]);
  const executionHours = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*execution hours?\b/i,
  ]);
  const serviceHours = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*(?:training|transcription|execution|cluster|utilized)\s*hours?\b/i,
  ]);
  const minuteQuantity = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*(?:processed video )?minutes?\b/i,
    /(\d[\d,]*(?:\.\d+)?)\s*minutes?\s+of output media content\b/i,
  ]);
  const workspaceCount = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*workspaces?\b/i,
  ]);
  const provisionedConcurrencyUnits = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*provisioned concurrency/i,
    /provisioned concurrency units?[^\d]*(\d[\d,]*(?:\.\d+)?)/i,
  ]);
  const databaseEdition = matchText(source, [
    /\b(extreme performance)\b/i,
    /\b(high performance)\b/i,
    /\b(enterprise)\b(?: edition)?/i,
    /\b(standard)\b(?: edition)?/i,
    /\b(developer)\b/i,
  ]);
  const databaseStorageModel = matchText(source, [
    /\b(smart database storage)\b/i,
    /\b(filesystem storage)\b/i,
    /\b(vm filesystem storage)\b/i,
  ]);
  const exadataInfraShape = matchText(source, [
    /\b(base system)\b/i,
    /\b(quarter rack)\b/i,
    /\b(half rack)\b/i,
    /\b(full rack)\b/i,
    /\b(database server)\b/i,
    /\b(storage server)\b/i,
    /\b(expansion rack)\b/i,
  ]);
  const exadataInfraGeneration = matchText(source, [
    /\b(x11m)\b/i,
    /\b(x10m)\b/i,
    /\b(x9m)\b/i,
    /\b(x8m)\b/i,
    /\b(x8)\b/i,
    /\b(x7)\b/i,
  ]);
  const shapeSeries = shape?.shapeName || matchText(source, [
    /\b((?:vm|bm)\.[a-z0-9.]+(?:\.flex|\.\d+))\b/i,
    /\b([ea]\d+\.flex)\b/i,
  ], (value) => String(value).toUpperCase());
  const processorVendor = matchText(source, [
    /\b(intel)\b/i,
    /\b(amd)\b/i,
    /\b(arm)\b/i,
    /\b(ampere)\b/i,
  ], (value) => String(value).toLowerCase()) || shape?.vendor || null;
  return compactObject({
    capacityGb,
    vpuPerGb,
    bandwidthGbps,
    bandwidthMbps,
    ocpus,
    ecpus,
    memoryGb,
    invocationsPerDay,
    invocationsPerMonth,
    daysPerMonth,
    executionMs,
    memoryMb,
    users,
    gpus,
    quantity,
    requestCount,
    firewallInstances,
    wafInstances,
    dataProcessedGb,
    executionHours,
    serviceHours,
    minuteQuantity,
    workspaceCount,
    provisionedConcurrencyUnits,
    databaseEdition,
    databaseStorageModel,
    exadataInfraShape,
    exadataInfraGeneration,
    shapeSeries,
    processorVendor,
  });
}

function extractStorageCapacityGb(source) {
  const capacityTb = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*tb\b(?:\s+(?:block(?:\s+storage)?|block\s+volumes?|file storage|object storage|database storage|log analytics|storage))\b/i,
    /(?:block volumes?|block storage|file storage|object storage|database storage|log analytics|storage)[^\d]{0,20}(\d[\d,]*(?:\.\d+)?)\s*tb\b/i,
  ]);
  if (capacityTb !== null) return capacityTb * 1024;
  return matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*gb\b(?:\s+(?:block(?:\s+storage)?|block\s+volumes?|file storage|object storage|database storage|log analytics|storage))\b/i,
    /(?:block volumes?|block storage|file storage|object storage|database storage|log analytics|storage)[^\d]{0,20}(\d[\d,]*(?:\.\d+)?)\s*gb\b/i,
  ]);
}

function applyDeterministicRescue(normalized, originalText) {
  if (isCompositeOrComparisonRequest(originalText)) return;
  if (isShapeDiscoveryQuestion(originalText)) return;
  if (isOptionsDiscoveryQuestion(originalText)) return;
  if (isLicensingDiscoveryQuestion(originalText)) return;
  if (isPricingDiscoveryQuestion(originalText)) return;
  if (isCatalogListingQuestion(originalText)) return;
  if (!shouldForceQuote(normalized)) return;
  normalized.intent = 'quote';
  normalized.shouldQuote = true;
  normalized.needsClarification = false;
  normalized.clarificationQuestion = '';
  normalized.normalizedRequest = normalizeUnits(buildCanonicalRequest(normalized, originalText) || normalized.normalizedRequest);
}

function isShapeDiscoveryQuestion(text) {
  const source = String(text || '');
  if (!source) return false;
  if (/\bwhat\b.*\bshape|\bque\b.*\bshape|\bqué\b.*\bshape|\bopciones?\b.*\bshape/i.test(source)) return true;
  return /\b(?:compare|comparison|difference|different|diferencia|diferencias|comparar)\b/i.test(source) &&
    /\bshape?s?\b|\bvirtual machines?\b|\bvm instances?\b|\b[a-z]\d+\.flex\b/i.test(source);
}

function isCatalogListingQuestion(text) {
  const source = String(text || '');
  if (!source) return false;
  if (/\blist all skus?\b/i.test(source)) return true;
  if (/\bwhat\b.*\boptions?\b.*\bcatalog\b/i.test(source)) return true;
  if (/\bavailable\b.*\bcatalog\b/i.test(source)) return true;
  if (/\bshow\b.*\bskus?\b/i.test(source)) return true;
  if (/\blist\b.*\b(hourly prices?|prices?)\b/i.test(source)) return true;
  return false;
}

function isOptionsDiscoveryQuestion(text) {
  const source = String(text || '');
  if (!source) return false;
  if (/\b(?:what|which|que|qué)\b.*\boptions?\b/i.test(source)) return true;
  if (/\bopciones?\b.*\b(?:tenemos|hay|disponibles?)\b/i.test(source)) return true;
  if (/\bavailable options?\b/i.test(source)) return true;
  if (/\b(?:what|which|que|qué)\b.*\b(?:available|supported|disponibles?|soportadas?)\b/i.test(source)) return true;
  return false;
}

function isPricingDiscoveryQuestion(text) {
  const source = String(text || '');
  if (!source) return false;
  if (isSkuCompositionDiscoveryQuestion(source)) return true;
  if (/\b(?:how|como|cómo)\b.*\b(?:build|structure|compose|arma|armar|construye|construir|compone|componer)\b.*\b(?:quote|cotiz(?:ar|ación))\b/i.test(source)) return true;
  if (/\b(how|como|cómo)\b.*\b(?:billed|charged|priced|cobra|cobran|costea|pricing)\b/i.test(source)) return true;
  if (/\b(?:pricing model|billing model|cost model|modelo de cobro|modelo de pricing)\b/i.test(source)) return true;
  if (/\b(?:pricing dimensions?|billing dimensions?)\b/i.test(source)) return true;
  if (/\b(?:explain|explica)\b.*\b(?:pricing|billing|billed|charged|priced|dimensions?|metrics?|units?)\b/i.test(source)) return true;
  if (/\b(?:what|which|que|qué)\b.*\b(?:dimensions?|metrics?|units?|inputs?)\b.*\b(?:bill|charge|price|pricing|cobra)\b/i.test(source)) return true;
  if (/\b(?:what|which|que|qué)\b.*\b(?:is|es)\b.*\b(?:charged|billed|priced)\b/i.test(source)) return true;
  return false;
}

function isLicensingDiscoveryQuestion(text) {
  const source = String(text || '');
  if (!source) return false;
  if (isSkuCompositionDiscoveryQuestion(source)) return true;
  if (/\b(?:difference|diferencia|compare|comparar)\b.*\b(?:byol|license included|licencia incluida)\b/i.test(source)) return true;
  if (/\b(?:when|cuando|cuándo|do i need|necesito)\b.*\b(?:byol|license included|licencia incluida)\b/i.test(source)) return true;
  if (/\b(?:what|which|que|qué)\b.*\b(?:license|licensing|licencia)\b/i.test(source)) return true;
  if (/\b(?:prerequisite|prerequisites|prerrequisito|prerrequisitos|required inputs?|required information)\b/i.test(source)) return true;
  if (/\b(?:what|which|que|qué|how|como|cómo)\b.*\b(?:need|needed|required|require|information|inputs?|datos?)\b.*\b(?:quote|price|pricing|cotizar|cotización|costo)\b/i.test(source)) return true;
  if (/\b(?:what|which|que|qué)\b.*\b(?:need|necesito|requiere|requiero)\b.*\b(?:for|para)\b.*\b(?:oracle integration cloud|base database service|autonomous|analytics cloud|database cloud service)\b/i.test(source)) return true;
  return false;
}

function isSkuCompositionDiscoveryQuestion(text) {
  const source = String(text || '');
  if (!source) return false;
  if (/\b(?:what|which|que|qué|cuales?|cu[aá]les)\b[\s\S]*\b(?:skus?|sku'?s|componentes?|components?)\b[\s\S]*\b(?:need|needed|required|require|requier(?:e|o|en)?|requerid[oa]s?|necesari[oa]s?)\b[\s\S]*\b(?:quote|quoting|pricing|cotizar|cotización)\b/i.test(source)) return true;
  if (/\b(?:skus?|sku'?s|componentes?|components?)\b[\s\S]*\b(?:required|requireds?|requerid[oa]s?|necesari[oa]s?)\b[\s\S]*\b(?:en|in|for|para|de)\b[\s\S]*\b(?:quote|cotiz(?:ar|ación))\b/i.test(source)) return true;
  return false;
}

function isCompositeOrComparisonRequest(text) {
  const source = String(text || '').toLowerCase();
  const serviceHits = [
    /\bload balancer\b/.test(source),
    /\bblock storage\b|\bblock volumes?\b/.test(source),
    /\bobject storage\b/.test(source),
    /\bfastconnect\b|\bfast connect\b/.test(source),
    /\bweb application firewall\b|\bwaf\b/.test(source),
    /\bnetwork firewall\b/.test(source),
    /\bintegration cloud\b/.test(source),
    /\banalytics cloud\b/.test(source),
    /\bdata integration\b/.test(source),
    /\bdata safe\b/.test(source),
    /\blog analytics\b/.test(source),
    /\bfunctions\b/.test(source),
    /\bgenerative ai\b/.test(source),
    /\bautonomous(?: ai)? lakehouse\b|\bautonomous data warehouse\b|\bbase database service\b/.test(source),
    /\b(?:vm|bm)\.[a-z0-9.]+\.flex\b/.test(source) || /\b[a-z]\d+\.flex\b/.test(source),
  ].filter(Boolean).length;
  if (/\bcompare\b/.test(source) && /\b[a-z]\d+\.flex\b/.test(source)) return true;
  return serviceHits >= 2 || /\b3-tier\b|\bthree-tier\b|\barchitecture\b|\bworkload\b|\bbundle\b|\bstack\b|\bplatform\b/.test(source);
}

function matchNumber(source, patterns) {
  for (const pattern of patterns) {
    const match = String(source || '').match(pattern);
    if (match) return Number(String(match[1]).replace(/,/g, ''));
  }
  return null;
}

function matchText(source, patterns, transform = (value) => value) {
  for (const pattern of patterns) {
    const match = String(source || '').match(pattern);
    if (match) return transform(String(match[1]).trim());
  }
  return null;
}

function compactObject(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, value]) => value !== null && value !== undefined && value !== ''));
}

module.exports = {
  normalizeIntentResult,
  normalizeServiceAliases,
  inferServiceFamily,
};
