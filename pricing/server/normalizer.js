'use strict';

const {
  inferServiceFamily,
  normalizeServiceAliases,
  buildCanonicalRequest,
  shouldForceQuote,
} = require('./service-families');

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
  return normalized;
}

function numberLike(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function extractStructuredInputs(text) {
  const source = String(text || '');
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
  const ocpus = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*ocpus?\b/i,
  ]);
  const ecpus = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*ecpus?\b/i,
  ]);
  const memoryGb = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*gb\s*(?:ram|memory)\b/i,
    /(?:ram|memory)[^\d]{0,20}(\d[\d,]*(?:\.\d+)?)\s*gb\b/i,
  ]);
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
  const quantity = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*(?:(?:managed|target)\s+)?(?:databases?|devices?|stations?|jobs?|resources?|nodes?|clusters?|models?|endpoints?)\b/i,
  ]);
  const executionHours = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*execution hours?\b/i,
  ]);
  const serviceHours = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*(?:training|transcription)\s*hours?\b/i,
    /(\d[\d,]*(?:\.\d+)?)\s*hours?\b/i,
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
  const shapeSeries = matchText(source, [
    /\b((?:vm|bm)\.[a-z0-9.]+\.flex)\b/i,
    /\b([ea]\d+\.flex)\b/i,
  ], (value) => String(value).toUpperCase());
  const processorVendor = matchText(source, [
    /\b(intel)\b/i,
    /\b(amd)\b/i,
    /\b(arm)\b/i,
    /\b(ampere)\b/i,
  ], (value) => String(value).toLowerCase());
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
  if (!shouldForceQuote(normalized)) return;
  normalized.intent = 'quote';
  normalized.shouldQuote = true;
  normalized.needsClarification = false;
  normalized.clarificationQuestion = '';
  normalized.normalizedRequest = normalizeUnits(buildCanonicalRequest(normalized, originalText) || normalized.normalizedRequest);
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
