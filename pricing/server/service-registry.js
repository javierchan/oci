'use strict';

const { normalizeServiceName } = require('./workbook-rules');
const { inferConsumptionPattern } = require('./consumption-model');
const { classifyDomain: classifyFamilyDomain } = require('./service-families');

function slugify(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'unknown';
}

function unique(items) {
  return Array.from(new Set((items || []).filter(Boolean)));
}

function classifyDomain(name) {
  const familyDomain = classifyFamilyDomain(name);
  if (familyDomain) return familyDomain;
  const text = String(name || '').toLowerCase();
  if (/\b(fastconnect|load balancer|network|dns|email delivery|vcn|traffic|gateway|waf)\b/.test(text)) return 'network';
  if (/\b(block volume|object storage|file storage|archive|storage)\b/.test(text)) return 'storage';
  if (/\b(compute|ocpu|ecpu|gpu|vm|bare metal|capacity reservation)\b/.test(text)) return 'compute';
  if (/\b(database|autonomous|mysql|postgresql|heatwave|data guard|exadata)\b/.test(text)) return 'database';
  if (/\b(functions|serverless|api gateway|events|streaming)\b/.test(text)) return 'serverless';
  if (/\b(integration|oic|goldengate|data integration)\b/.test(text)) return 'integration';
  if (/\b(logging|monitoring|apm|operations insights|observability|notifications)\b/.test(text)) return 'observability';
  if (/\b(identity|vault|security|cloud guard|bastion|kms|certificate|waf)\b/.test(text)) return 'security';
  if (/\b(analytics|data science|ai|vision|language|speech|document understanding)\b/.test(text)) return 'analytics';
  if (/\b(devops|container|oke|registry|artifacts)\b/.test(text)) return 'devops';
  return 'other';
}

function hasDeterministicSupport(patterns, prerequisites) {
  const set = new Set(patterns || []);
  if (set.has('port-hour')) return true;
  if (set.has('load-balancer-hour')) return true;
  if (set.has('bandwidth-mbps-hour')) return true;
  if (set.has('capacity-gb-month')) return true;
  if (set.has('performance-units-per-gb-month')) return true;
  if (set.has('functions-gb-memory-seconds')) return true;
  if (set.has('functions-invocations-million')) return true;
  if (set.has('ocpu-hour')) return true;
  if (set.has('ecpu-hour')) return true;
  if (set.has('memory-gb-hour')) return true;
  if (set.has('users-per-month')) return true;
  if (set.has('requests')) return true;
  if (set.has('generic-hourly')) return true;
  if (set.has('generic-monthly')) return true;
  if (prerequisites?.length) return true;
  return false;
}

function hasConsumptionExplanation(patterns) {
  return (patterns || []).some((pattern) => pattern !== 'unknown');
}

function determineCoverageLevel(entry) {
  if (entry.deterministic && entry.explainable && entry.prerequisitesResolved) return 'L4';
  if (entry.deterministic && entry.explainable) return 'L3';
  if (entry.deterministic) return 'L2';
  if (entry.partNumbers.length) return 'L1';
  return 'L0';
}

function inferRequiredInputs(entry) {
  const patterns = new Set(entry.patterns || []);
  const required = new Set();
  if (patterns.has('capacity-gb-month')) required.add('capacityGb');
  if (patterns.has('data-processed-gb-month')) required.add('dataProcessedGb');
  if (patterns.has('log-analytics-storage-unit-month')) required.add('capacityGb');
  if (patterns.has('workspace-hour')) required.add('workspaceCount');
  if (patterns.has('data-processed-gb-hour')) required.add('dataProcessedGb');
  if (patterns.has('execution-hour-utilized')) required.add('executionHours');
  if (patterns.has('performance-units-per-gb-month')) {
    required.add('capacityGb');
    required.add('vpuPerGb');
  }
  if (patterns.has('port-hour') && /\bfastconnect\b/i.test(entry.name)) required.add('bandwidthGbps');
  if (patterns.has('bandwidth-mbps-hour')) required.add('bandwidthMbps');
  if (patterns.has('ocpu-hour')) required.add('ocpus');
  if (patterns.has('ecpu-hour')) required.add('ecpus');
  if (patterns.has('memory-gb-hour')) required.add('memoryGb');
  if (patterns.has('users-per-month')) required.add('users');
  if (patterns.has('requests')) required.add('requestCount');
  if (patterns.has('functions-gb-memory-seconds')) {
    required.add('executionMs');
    required.add('memoryMb');
    required.add('invocationsPerMonth|invocationsPerDay');
  }
  if (patterns.has('functions-invocations-million')) required.add('invocationsPerMonth|invocationsPerDay');
  return Array.from(required).sort();
}

function createEntry(serviceName) {
  return {
    id: slugify(serviceName),
    name: serviceName,
    domain: classifyDomain(serviceName),
    partNumbers: [],
    metrics: [],
    patterns: [],
    prerequisites: [],
    sources: [],
    exampleProducts: [],
    deterministic: false,
    explainable: false,
    prerequisitesResolved: false,
    requiredInputs: [],
    coverageLevel: 'L0',
  };
}

function buildServiceRegistry(index) {
  const workbookServices = Array.isArray(index?.workbookRules?.services) ? index.workbookRules.services : [];
  const byName = new Map();

  function ensure(name) {
    const normalized = normalizeServiceName(name);
    if (!normalized) return null;
    if (!byName.has(normalized)) byName.set(normalized, createEntry(name));
    return byName.get(normalized);
  }

  for (const service of workbookServices) {
    const entry = ensure(service.name);
    if (!entry) continue;
    entry.partNumbers.push(...(service.partNumbers || []));
    entry.metrics.push(...(service.metrics || []));
    entry.prerequisites.push(...(service.prerequisites || []));
    entry.sources.push(...(service.sources || []));
  }

  for (const product of index?.products || []) {
    const serviceName = product.displayName || product.serviceCategoryDisplayName || product.fullDisplayName;
    const entry = ensure(serviceName);
    if (!entry) continue;
    entry.partNumbers.push(product.partNumber);
    entry.metrics.push(product.metricDisplayName);
    entry.sources.push('catalog');
    entry.exampleProducts.push(product.fullDisplayName);
    if (product.serviceCategoryDisplayName && product.serviceCategoryDisplayName !== product.displayName) {
      entry.exampleProducts.push(product.serviceCategoryDisplayName);
    }
  }

  const services = Array.from(byName.values()).map((entry) => {
    entry.partNumbers = unique(entry.partNumbers).sort();
    entry.metrics = unique(entry.metrics).sort();
    entry.prerequisites = unique(entry.prerequisites).sort();
    entry.sources = unique(entry.sources).sort();
    entry.exampleProducts = unique(entry.exampleProducts).slice(0, 5);
    entry.patterns = unique(entry.metrics.map((metric) => inferConsumptionPattern(metric, entry.name)));
    entry.deterministic = hasDeterministicSupport(entry.patterns, entry.prerequisites);
    entry.explainable = hasConsumptionExplanation(entry.patterns);
    entry.prerequisitesResolved = entry.prerequisites.every((item) => byName.has(normalizeServiceName(item)));
    entry.requiredInputs = inferRequiredInputs(entry);
    entry.coverageLevel = determineCoverageLevel(entry);
    return entry;
  }).sort((a, b) => a.name.localeCompare(b.name));

  const summary = {
    serviceCount: services.length,
    byCoverageLevel: countBy(services, (item) => item.coverageLevel),
    byDomain: countBy(services, (item) => item.domain),
    explainableCount: services.filter((item) => item.explainable).length,
    deterministicCount: services.filter((item) => item.deterministic).length,
  };

  return { services, summary };
}

function countBy(items, selector) {
  return items.reduce((acc, item) => {
    const key = selector(item);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function searchServiceRegistry(registry, query, limit = 12) {
  const q = String(query || '').trim().toLowerCase();
  if (!q) return [];
  const stopwords = new Set(['oci', 'oracle', 'cloud', 'infrastructure', 'service', 'services']);
  const rawTokens = q.split(/\s+/).filter(Boolean);
  const tokens = rawTokens.filter((token) => !stopwords.has(token));
  const effectiveTokens = tokens.length ? tokens : rawTokens;
  const scored = [];
  for (const service of registry?.services || []) {
    const haystack = `${service.name} ${service.metrics.join(' ')} ${service.patterns.join(' ')} ${service.partNumbers.join(' ')}`.toLowerCase();
    const tokenSet = new Set(
      haystack
        .replace(/[^a-z0-9.+#-]+/g, ' ')
        .split(/\s+/)
        .filter(Boolean),
    );
    let score = 0;
    if (haystack.includes(q)) score += 80;
    let matchedTokens = 0;
    for (const token of effectiveTokens) {
      if (tokenSet.has(token)) score += token.length <= 4 ? 30 : 18;
      else if (haystack.includes(token)) score += 10;
      if (tokenSet.has(token) || haystack.includes(token)) matchedTokens += 1;
    }
    score += matchedTokens * 5;
    if (score > 0) scored.push({ score, service });
  }
  scored.sort((a, b) => b.score - a.score || a.service.name.localeCompare(b.service.name));
  return scored.slice(0, limit).map((item) => item.service);
}

function serviceHasRequiredInputs(service, extractedInputs = {}) {
  const inputs = extractedInputs || {};
  return (service?.requiredInputs || []).every((key) => {
    if (key.includes('|')) {
      return key.split('|').some((alt) => hasInput(inputs[alt]));
    }
    return hasInput(inputs[key]);
  });
}

function hasInput(value) {
  return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
}

module.exports = {
  buildServiceRegistry,
  searchServiceRegistry,
  serviceHasRequiredInputs,
};
