'use strict';

const fs = require('fs');
const path = require('path');

let cachedRules = null;

function readJsonl(filePath) {
  if (!fs.existsSync(filePath)) return [];
  return fs.readFileSync(filePath, 'utf8')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function normalizeServiceName(value) {
  return String(value || '')
    .replace(/\s+/g, ' ')
    .replace(/\s*-\s*/g, ' - ')
    .trim()
    .toLowerCase();
}

function tokenize(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9.+#-]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean);
}

function createEmptyRules() {
  return {
    partsByPartNumber: new Map(),
    servicesByName: new Map(),
    services: [],
  };
}

function ensureService(servicesByName, rawName) {
  const name = String(rawName || '').trim();
  if (!name) return null;
  const key = normalizeServiceName(name);
  if (!key) return null;
  if (!servicesByName.has(key)) {
    servicesByName.set(key, {
      name,
      key,
      partNumbers: new Set(),
      metrics: new Set(),
      prerequisites: new Set(),
      sources: new Set(),
    });
  }
  return servicesByName.get(key);
}

function ensurePart(partsByPartNumber, partNumber) {
  const key = String(partNumber || '').trim().toUpperCase();
  if (!key) return null;
  if (!partsByPartNumber.has(key)) {
    partsByPartNumber.set(key, {
      partNumber: key,
      subscriptionService: '',
      metric: '',
      notes: '',
      additionalInformation: '',
      prerequisites: [],
      prices: {},
    });
  }
  return partsByPartNumber.get(key);
}

function loadWorkbookRules() {
  if (cachedRules) return cachedRules;

  const baseDir = path.join(__dirname, '..', 'data', 'xls-extract');
  const priceRows = readJsonl(path.join(baseDir, 'price_list_rows.jsonl'));
  const supplementRows = readJsonl(path.join(baseDir, 'supplement_rows.jsonl'));

  const rules = createEmptyRules();

  for (const row of priceRows) {
    const part = ensurePart(rules.partsByPartNumber, row.part_number);
    if (!part) continue;
    part.subscriptionService = row.subscription_service || part.subscriptionService;
    part.metric = row.metric || part.metric;
    part.notes = row.notes || part.notes;
    part.additionalInformation = row.additional_information || part.additionalInformation;
    part.prices = {
      universalCreditsPaygo: row.universal_credits_paygo,
      annualFlex: row.annual_flex,
      localizedPaygoPrice: row.localized_paygo_price,
      localizedAnnualFlexPrice: row.localized_annual_flex_price,
    };

    const service = ensureService(rules.servicesByName, row.subscription_service);
    if (service) {
      service.partNumbers.add(part.partNumber);
      if (row.metric) service.metrics.add(row.metric);
      service.sources.add('price_list');
    }
  }

  for (const row of supplementRows) {
    const part = ensurePart(rules.partsByPartNumber, row.part_number);
    if (!part) continue;
    part.subscriptionService = row.subscription_service || part.subscriptionService;
    part.metric = row.metric || part.metric;
    part.prerequisites = Array.isArray(row.prerequisites) ? row.prerequisites.filter(Boolean) : [];

    const service = ensureService(rules.servicesByName, row.subscription_service);
    if (service) {
      service.partNumbers.add(part.partNumber);
      if (row.metric) service.metrics.add(row.metric);
      for (const item of part.prerequisites) {
        const clean = String(item || '').trim();
        if (clean) service.prerequisites.add(clean);
      }
      service.sources.add('supplement');
    }
  }

  rules.services = Array.from(rules.servicesByName.values())
    .map((service) => ({
      name: service.name,
      key: service.key,
      partNumbers: Array.from(service.partNumbers).sort(),
      metrics: Array.from(service.metrics).sort(),
      prerequisites: Array.from(service.prerequisites).sort(),
      sources: Array.from(service.sources).sort(),
    }))
    .sort((a, b) => a.name.localeCompare(b.name));

  cachedRules = rules;
  return rules;
}

function searchWorkbookServices(workbookRules, query, limit = 8) {
  const q = String(query || '').trim().toLowerCase();
  if (!q || !workbookRules?.services?.length) return [];
  const tokens = tokenize(q);
  const scored = [];

  for (const service of workbookRules.services) {
    const haystack = `${service.name} ${service.metrics.join(' ')} ${service.prerequisites.join(' ')}`.toLowerCase();
    let score = 0;
    if (haystack.includes(q)) score += 80;
    for (const token of tokens) {
      if (haystack.includes(token)) score += 10;
    }
    if (score > 0) scored.push({ score, service });
  }

  scored.sort((a, b) => b.score - a.score || a.service.name.localeCompare(b.service.name));
  return scored.slice(0, limit).map((item) => item.service);
}

function getWorkbookPart(workbookRules, partNumber) {
  return workbookRules?.partsByPartNumber?.get(String(partNumber || '').toUpperCase()) || null;
}

function getWorkbookService(workbookRules, serviceName) {
  const service = workbookRules?.servicesByName?.get(normalizeServiceName(serviceName)) || null;
  if (!service) return null;
  return {
    name: service.name,
    key: service.key,
    partNumbers: Array.from(service.partNumbers || []).sort(),
    metrics: Array.from(service.metrics || []).sort(),
    prerequisites: Array.from(service.prerequisites || []).sort(),
    sources: Array.from(service.sources || []).sort(),
  };
}

module.exports = {
  loadWorkbookRules,
  searchWorkbookServices,
  getWorkbookPart,
  getWorkbookService,
  normalizeServiceName,
};
