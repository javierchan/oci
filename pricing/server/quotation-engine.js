'use strict';

const { getPaygTier, calculatePaygCharge } = require('./catalog');
const { resolveRequestDependencies } = require('./dependency-resolver');
const { inferServiceFamily } = require('./service-families');
const { inferConsumptionPattern } = require('./consumption-model');

const DEFAULT_HOURS = 744;

function hasNumericValue(value) {
  return value !== null && value !== '' && value !== undefined && Number.isFinite(Number(value));
}

function calcRate({ capacityReservationUtilization, preemptible, burstableBaseline }) {
  if (hasNumericValue(capacityReservationUtilization)) {
    const used = Number(capacityReservationUtilization);
    return used + (1 - used) * 0.85;
  }
  if (preemptible) return 0.5;
  if (hasNumericValue(burstableBaseline)) return Number(burstableBaseline);
  return 1;
}

function validateModifiers(index, partNumber, modifiers) {
  const selected = [
    hasNumericValue(modifiers.capacityReservationUtilization),
    !!modifiers.preemptible,
    hasNumericValue(modifiers.burstableBaseline),
  ].filter(Boolean).length;

  if (selected > 1) {
    return 'Capacity reservation, preemptible and burstable are mutually exclusive.';
  }

  if (hasNumericValue(modifiers.capacityReservationUtilization)) {
    const value = Number(modifiers.capacityReservationUtilization);
    if (value < 0 || value > 1) return 'Capacity reservation utilization must be between 0 and 1.';
    if (!index.modifierSets.capacityReservation.has(partNumber)) return `Capacity reservation is not available for ${partNumber}.`;
  }

  if (modifiers.preemptible && !index.modifierSets.preemptible.has(partNumber)) {
    return `Preemptible is not available for ${partNumber}.`;
  }

  if (hasNumericValue(modifiers.burstableBaseline)) {
    const baseline = Number(modifiers.burstableBaseline);
    if (baseline <= 0 || baseline > 1) return 'Burstable baseline must be greater than 0 and at most 1.';
    if (!index.modifierSets.burstable.has(partNumber)) return `Burstable is not available for ${partNumber}.`;
  }

  return null;
}

function parsePromptRequest(text) {
  const source = sanitizeQuotePromptText(text);
  const annualRequested = /\b(1[\s-]*year|one year|yearly|annual|annually|per year|por un a[nñ]o|anual)\b/i.test(source);
  const hours = matchNumber(source, [
    /(\d+(?:\.\d+)?)\s*h(?:ours?)?(?:\s*\/?\s*month)?/i,
    /monthly\s+uptime\s+(\d+(?:\.\d+)?)/i,
  ]) ?? DEFAULT_HOURS;
  const instances = matchNumber(source, [/(?:^|\s)(\d+(?:\.\d+)?)\s*(?:instances?|nodes?|vms?)\b/i]) ?? 1;
  const quantity = matchNumber(source, [
    /(\d+(?:\.\d+)?)\s*(?:ocpus?|ecpus?|gb|tb|mbps|gbps|users?|transactions?|requests?|queries?|emails?|messages?|sms(?: messages?)?|tokens?|minutes?|hours?|ports?|endpoints?|api calls?|databases?|devices?|stations?|jobs?|resources?|nodes?|clusters?|models?)\b/i,
    /(\d+(?:\.\d+)?)\s*(?:(?:managed|target)\s+)(?:resources?|databases?)\b/i,
    /\bqty(?:uantity)?\s*[:=]?\s*(\d+(?:\.\d+)?)/i,
  ]) ?? 1;
  const ocpus = matchNumber(source, [/(\d+(?:\.\d+)?)\s*ocpus?\b/i]);
  const ecpus = matchNumber(source, [/(\d+(?:\.\d+)?)\s*ecpus?\b/i]);
  const capacityReservationUtilization = matchNumber(source, [
    /capacity reservation(?: utilization)?\s*[:=]?\s*(\d+(?:\.\d+)?)/i,
    /reservation(?: utilization)?\s*[:=]?\s*(\d+(?:\.\d+)?)/i,
  ]);
  const burstableBaseline = matchNumber(source, [
    /burstable(?: baseline)?\s*[:=]?\s*(\d+(?:\.\d+)?)/i,
    /baseline\s*[:=]?\s*(\d+(?:\.\d+)?)/i,
  ]);
  const memoryQuantity = matchNumber(source, [
    /(\d+(?:\.\d+)?)\s*gb\s*(?:ram|memory)\b/i,
    /memory\s*[:=]?\s*(\d+(?:\.\d+)?)\s*gb\b/i,
    /ram\s*[:=]?\s*(\d+(?:\.\d+)?)\s*gb\b/i,
  ]);
  const preemptible = /\bpreemptible\b/i.test(source);
  const environment = matchText(source, [/\b(prod|production|qa|uat|dev|test|dr)\b/i]) || 'default';
  const currencyCode = matchText(source, [/\b(usd|mxn|eur|brl|gbp|cad|jpy)\b/i], (value) => value.toUpperCase()) || 'USD';
  const partNumber = matchText(source, [/\b(B\d{5,})\b/i], (value) => value.toUpperCase()) || null;
  const shape = parseShape(source);
  const firewallInstances = matchNumber(source, [/(?:^|\s)(\d+(?:\.\d+)?)\s*firewalls?\b/i, /(\d+(?:\.\d+)?)\s*network firewalls?\b/i]);
  const wafInstances = matchNumber(source, [/(?:^|\s)(\d+(?:\.\d+)?)\s*(?:waf|web application firewall)\s*(?:instances?)?\b/i, /(\d+(?:\.\d+)?)\s*polic(?:y|ies)\b/i]);
  const dataProcessedGb = matchNumber(source, [
    /(\d+(?:\.\d+)?)\s*gb\b[^\n,.;]*processed per hour/i,
    /(\d+(?:\.\d+)?)\s*gb\b[^\n,.;]*data processed/i,
    /data processed[^\d]*(\d+(?:\.\d+)?)\s*gb\b/i,
    /processed[^\d]*(\d+(?:\.\d+)?)\s*gb\b[^\n,.;]*per hour/i,
  ]);
  const requestCount = matchNumber(source, [/(\d+(?:\.\d+)?)\s*(?:requests?|api calls?|transactions?|queries?|emails?|messages?|sms(?: messages?)?|tokens?|datapoints?|events?|delivery operations?)\b/i]);
  const capacityGb = extractStorageCapacityGb(source);
  const vpuPerGb = matchNumber(source, [/(\d+(?:\.\d+)?)\s*vpu'?s?\b/i, /(\d+(?:\.\d+)?)\s*performance units per gb\b/i]);
  const executionHours = matchNumber(source, [/(\d+(?:\.\d+)?)\s*execution hours?\b/i]);
  const serviceHours = matchNumber(source, [/(\d+(?:\.\d+)?)\s*(?:training|transcription)\s*hours?\b/i, /(\d+(?:\.\d+)?)\s*hours?\b/i]);
  const minuteQuantity = matchNumber(source, [/(\d+(?:\.\d+)?)\s*(?:processed video )?minutes?\b/i, /(\d+(?:\.\d+)?)\s*minutes?\s+of output media content\b/i]);
  const normalizedQuantity = minuteQuantity ?? serviceHours ?? quantity;
  const workspaceCount = matchNumber(source, [/(\d+(?:\.\d+)?)\s*workspaces?\b/i]);
  const users = matchNumber(source, [/(\d+(?:\.\d+)?)\s*(?:users?|named users?)\b/i]);
  const shapeSeries = matchText(source, [/\b((?:vm|bm)\.[a-z0-9.]+\.flex)\b/i, /\b([ea]\d+\.flex)\b/i], (value) => String(value).toUpperCase());
  const processorVendor = matchText(source, [/\b(intel)\b/i, /\b(amd)\b/i, /\b(arm)\b/i, /\b(ampere)\b/i], (value) => String(value).toLowerCase());
  const databaseEdition = matchText(source, [/\b(extreme performance)\b/i, /\b(high performance)\b/i, /\b(enterprise)\b(?: edition)?/i, /\b(standard)\b(?: edition)?/i, /\b(developer)\b/i]);
  const databaseStorageModel = matchText(source, [/\b(smart database storage)\b/i, /\b(filesystem storage)\b/i, /\b(vm filesystem storage)\b/i]);
  const exadataInfraShape = matchText(source, [/\b(base system)\b/i, /\b(quarter rack)\b/i, /\b(half rack)\b/i, /\b(full rack)\b/i, /\b(database server)\b/i, /\b(storage server)\b/i, /\b(expansion rack)\b/i]);
  const exadataInfraGeneration = matchText(source, [/\b(x11m)\b/i, /\b(x10m)\b/i, /\b(x9m)\b/i, /\b(x8m)\b/i, /\b(x8)\b/i, /\b(x7)\b/i]);

  return {
    source,
    productQuery: source,
    serviceFamily: inferServiceFamily(source),
    quantity: normalizedQuantity,
    ocpus,
    ecpus,
    memoryQuantity,
    instances,
    hours,
    environment,
    currencyCode,
    annualRequested,
    firewallInstances,
    wafInstances,
    dataProcessedGb,
    requestCount,
    capacityGb,
    vpuPerGb,
    executionHours,
    serviceHours,
    minuteQuantity,
    workspaceCount,
    users,
    shapeSeries,
    processorVendor,
    databaseEdition,
    databaseStorageModel,
    exadataInfraShape,
    exadataInfraGeneration,
    shape,
    modifiers: {
      capacityReservationUtilization,
      preemptible,
      burstableBaseline,
    },
    explicitPartNumber: partNumber,
  };
}

function sanitizeQuotePromptText(text) {
  return String(text || '')
    .trim()
    .replace(/[,. ]+(?:and\s+)?explain\b[\s\S]*$/i, '')
    .replace(/[,. ]+(?:and\s+)?show\b[\s\S]*$/i, '')
    .trim();
}

function extractStorageCapacityGb(source) {
  const tb = matchNumber(source, [
    /(\d+(?:\.\d+)?)\s*tb\b(?:\s+(?:block(?:\s+storage)?|block\s+volumes?|file storage|object storage|database storage|smart database storage|filesystem storage|vm filesystem storage|log analytics|storage))\b/i,
    /(?:block volumes?|block storage|file storage|object storage|database storage|smart database storage|filesystem storage|vm filesystem storage|log analytics|storage)[^\d]{0,20}(\d+(?:\.\d+)?)\s*tb\b/i,
  ]);
  if (tb !== null) return tb * 1024;
  return matchNumber(source, [
    /(\d+(?:\.\d+)?)\s*gb\b(?:\s+(?:block(?:\s+storage)?|block\s+volumes?|file storage|object storage|database storage|smart database storage|filesystem storage|vm filesystem storage|log analytics|storage))\b/i,
    /(?:block volumes?|block storage|file storage|object storage|database storage|smart database storage|filesystem storage|vm filesystem storage|log analytics|storage)[^\d]{0,20}(\d+(?:\.\d+)?)\s*gb\b/i,
  ]);
}

function matchNumber(source, patterns) {
  for (const pattern of patterns) {
    const match = source.match(pattern);
    if (match) return Number(match[1]);
  }
  return null;
}

function matchText(source, patterns, transform = (value) => value) {
  for (const pattern of patterns) {
    const match = source.match(pattern);
    if (match) return transform(match[1]);
  }
  return null;
}

function parseShape(source) {
  const match = String(source || '').match(/\b(?:(vm|bm)\.)?(?:(standard|denseio|dense\.?io|gpu)\.)?([a-z]\d+)\.flex\b/i);
  if (!match) return null;
  const familyRaw = String(match[2] || 'standard').replace('.', '').toLowerCase();
  return {
    kind: 'flex',
    family: familyRaw === 'denseio' ? 'denseio' : familyRaw,
    series: match[3].toUpperCase(),
  };
}

function quoteFromPrompt(index, text) {
  return buildQuote(index, parsePromptRequest(text));
}

function buildQuote(index, request) {
  const dependencyResolution = resolveRequestDependencies(index, request);
  if (!dependencyResolution.ok) {
    return {
      ok: false,
      error: 'No matching OCI product or preset was found.',
      request,
      resolution: dependencyResolution.resolution,
    };
  }

  const lineItems = [];
  const warnings = Array.isArray(dependencyResolution.warnings) ? [...dependencyResolution.warnings] : [];

  for (const component of dependencyResolution.components) {
    const product = component.product;
    const modifierError = validateModifiers(index, product.partNumber, request.modifiers);
    if (modifierError) {
      warnings.push(modifierError);
      continue;
    }

    const usageQuantity = resolveLineQuantity(product, request, component);
    const instances = Number(component.instances || request.instances || 1);
    const hours = Number(request.hours || DEFAULT_HOURS);
    const chargeQuantity = resolveChargeQuantity(product, usageQuantity, instances, hours);
    const charge = calculatePaygCharge(product, chargeQuantity, request.currencyCode);
    const tier = charge.tier || getPaygTier(product, chargeQuantity, request.currencyCode);
    if (!charge.ok || !tier || !Number.isFinite(Number(charge.totalCharge))) {
      warnings.push(`PAYG price not found for ${product.partNumber} in ${request.currencyCode}.`);
      continue;
    }

    const rate = calcRate(request.modifiers);
    const unitPrice = Number(charge.effectiveUnitPrice);
    const qty = usageQuantity;
    const isHourly = ['HOUR'].includes(product.priceType);
    const isHourlyUtilized = ['HOUR', 'HOUR_UTILIZED'].includes(product.priceType);
    const monthlyBase = isHourlyUtilized
      ? charge.totalCharge
      : charge.totalCharge * instances;
    const monthly = monthlyBase * rate;
    const annual = monthly * 12;

    if (component.warning) warnings.push(component.warning);

    lineItems.push({
      environment: request.environment,
      service: product.serviceCategoryDisplayName,
      partNumber: product.partNumber,
      product: product.fullDisplayName,
      metric: product.metricDisplayName,
      priceType: product.priceType,
      quantity: qty,
      instances,
      hours,
      rate,
      currencyCode: request.currencyCode,
      unitPrice,
      billedQuantity: charge.billedQuantity,
      monthly,
      annual,
      tier,
      modifiers: request.modifiers,
      dependencyKind: component.dependencyKind || 'standalone',
    });
  }

  if (!lineItems.length) {
    return {
      ok: false,
      error: warnings[0] || 'No quotable OCI lines were produced.',
    request,
    resolution: dependencyResolution.resolution,
    warnings,
  };
  }

  const totals = lineItems.reduce((acc, line) => {
    acc.monthly += line.monthly;
    acc.annual += line.annual;
    return acc;
  }, { monthly: 0, annual: 0, currencyCode: request.currencyCode });

  return {
    ok: true,
    request,
    resolution: dependencyResolution.resolution,
    warnings,
    lineItems,
    totals,
    markdown: toMarkdownQuote(lineItems, totals),
  };
}

function resolveLineQuantity(product, request, component = {}) {
  if (hasNumericValue(component.quantity)) return Number(component.quantity);
  const metric = `${product.metricDisplayName} ${product.displayName}`.toLowerCase();
  if (metric.includes('memory') && hasNumericValue(request.memoryQuantity)) {
    return Number(request.memoryQuantity);
  }
  return Number(request.quantity || 1);
}

function resolveChargeQuantity(product, usageQuantity, instances, hours) {
  const pattern = inferConsumptionPattern(product?.metricDisplayName, `${product?.serviceCategoryDisplayName || ''} ${product?.displayName || ''}`);
  if (['execution-hour-utilized', 'utilized-hour', 'media-output-minute', 'count-each'].includes(pattern)) {
    return Number(usageQuantity || 0) * Number(instances || 1);
  }
  if (['HOUR', 'HOUR_UTILIZED'].includes(product.priceType)) {
    return Number(usageQuantity || 0) * Number(instances || 1) * Number(hours || DEFAULT_HOURS);
  }
  return Number(usageQuantity || 0);
}

function toMarkdownQuote(lineItems, totals) {
  const header = '| # | Environment | Service | Part# | Product | Metric | Qty | Inst | Hours | Rate | Unit | $/Mo | Annual |\n|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|';
  const rows = lineItems.map((line, index) => [
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
  ]);

  const body = rows.map((row) => `| ${row.join(' | ')} |`).join('\n');
  const total = `| Total | - | - | - | - | - | - | - | - | - | - | ${money(totals.monthly)} | ${money(totals.annual)} |`;
  return `${header}\n${body}\n${total}`;
}

function fmt(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value ?? '-');
  return Number.isInteger(num) ? String(num) : num.toFixed(3).replace(/\.?0+$/, '');
}

function money(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  return `$${num.toFixed(4).replace(/\.?0+$/, '')}`;
}

module.exports = {
  DEFAULT_HOURS,
  buildQuote,
  quoteFromPrompt,
  parsePromptRequest,
  calcRate,
  toMarkdownQuote,
};
