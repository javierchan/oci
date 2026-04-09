'use strict';

const { searchProducts, searchPresets, searchWorkbookServices, searchServiceRegistry } = require('./catalog');
const { getWorkbookPart, getWorkbookService } = require('./workbook-rules');
const { inferConsumptionPattern, inferQuantityForPattern } = require('./consumption-model');
const { getServiceFamily } = require('./service-families');

const FAMILY_RESOLVERS = {
  network_fastconnect: resolveFastConnectComponents,
  network_load_balancer: resolveLoadBalancerComponents,
  storage_block: resolveBlockVolumeComponents,
  storage_file: resolveFileStorageComponents,
  storage_object_requests: resolveObjectStorageRequestComponents,
  storage_archive: resolveArchiveStorageComponents,
  storage_infrequent_access: resolveInfrequentAccessStorageComponents,
  storage_object: resolveObjectStorageComponents,
  network_firewall: resolveNetworkFirewallComponents,
  security_waf: resolveWafComponents,
  observability_log_analytics: resolveLogAnalyticsComponents,
  database_autonomous_tp: resolveAutonomousTpComponents,
  database_autonomous_dw: resolveAutonomousDwComponents,
  database_base_db: resolveBaseDatabaseComponents,
  database_cloud_service: resolveDatabaseCloudServiceComponents,
  database_exadata_exascale: resolveExadataExascaleComponents,
  database_exadata_dedicated: resolveExadataDedicatedComponents,
  database_exadata_cloud_customer: resolveExadataCloudCustomerComponents,
  analytics_oac_professional: resolveOacProfessionalComponents,
  analytics_oac_enterprise: resolveOacEnterpriseComponents,
  integration_oic_standard: resolveOicStandardComponents,
  integration_oic_enterprise: resolveOicEnterpriseComponents,
  integration_data: resolveDataIntegrationComponents,
  serverless_functions: resolveFunctionsComponents,
  compute_flex: resolveFlexComponents,
  devops_batch: resolveBatchComponents,
  security_data_safe: resolveDataSafeComponents,
  ai_agents_data_ingestion: resolveAiAgentsDataIngestionComponents,
  ai_memory_ingestion: resolveAiMemoryIngestionComponents,
  ai_agents_knowledge_base_storage: resolveAiAgentsKnowledgeBaseStorageComponents,
};

function resolveRequestDependencies(index, request) {
  if (request.explicitPartNumber) {
    const products = index.productsByPartNumber.get(request.explicitPartNumber) || [];
    return finalizeResolution(index, products.map((product) => ({ product })), {
      type: 'product',
      label: request.explicitPartNumber,
      candidates: products.map((item) => item.fullDisplayName),
    }, request);
  }

  if (isCompositeWorkloadRequest(request.source)) {
    const components = resolveCompositeWorkload(index, request);
    if (components.length) {
      return finalizeResolution(index, components, {
        type: 'workload',
        label: 'Composite OCI workload',
        candidates: components.map((item) => item.product.fullDisplayName),
      }, request);
    }
  }

  if (request.shape?.kind === 'flex' || request.shape?.kind === 'fixed') {
    const components = resolveFlexComponents(index, request);
    return finalizeResolution(index, components, {
      type: 'product',
      label: request.shape.shapeName || `${request.shape.family}.${request.shape.series}.shape`,
      candidates: components.map((item) => item.product.fullDisplayName),
    }, request);
  }

  if (request.serviceFamily && FAMILY_RESOLVERS[request.serviceFamily]) {
    const family = getServiceFamily(request.serviceFamily);
    const components = FAMILY_RESOLVERS[request.serviceFamily](index, request);
    return finalizeResolution(index, components, {
      type: 'product',
      label: family?.canonical || request.serviceFamily,
      candidates: components.map((item) => item.product.fullDisplayName),
    }, request);
  }

  if (isFastConnectRequest(request.source)) {
    const components = resolveFastConnectComponents(index, request);
    return finalizeResolution(index, components, {
      type: 'product',
      label: 'FastConnect',
      candidates: components.map((item) => item.product.fullDisplayName),
    }, request);
  }

  if (isBlockVolumeRequest(request.source)) {
    const components = resolveBlockVolumeComponents(index, request);
    return finalizeResolution(index, components, {
      type: 'product',
      label: 'Block Volume',
      candidates: components.map((item) => item.product.fullDisplayName),
    }, request);
  }

  if (isFunctionsRequest(request.source)) {
    const components = resolveFunctionsComponents(index, request);
    return finalizeResolution(index, components, {
      type: 'product',
      label: 'OCI Functions',
      candidates: components.map((item) => item.product.fullDisplayName),
    }, request);
  }

  const registryQuery = buildRegistryQuery(request);
  const preferPreset = shouldPreferPreset(request.productQuery);
  const presetMatches = searchPresets(index, request.productQuery, 3);
  const productMatches = searchRelevantProducts(index, request, 12);
  const workbookServiceMatches = searchWorkbookServices(index, request.productQuery, 6);
  const registryMatches = searchServiceRegistry(index.serviceRegistry, registryQuery || request.productQuery, 8);
  const genericMatch = findFirstResolvableRegistryMatch(index, request, registryMatches);
  const genericService = genericMatch?.service || null;
  const genericComponents = genericMatch?.components || [];

  if (preferPreset && presetMatches.length) {
    const preset = presetMatches[0];
    const components = expandPreset(index, preset);
    return finalizeResolution(index, components, {
      type: 'preset',
      label: preset.displayName,
      candidates: presetMatches.map((item) => item.displayName),
    }, request);
  }

  if (productMatches.length && isDetailedMediaFlowRequest(request.productQuery)) {
    const best = selectDetailedMediaFlowProduct(productMatches, request.productQuery) || productMatches[0];
    return finalizeResolution(index, [{ product: best }], {
      type: 'product',
      label: best.fullDisplayName,
      candidates: productMatches.slice(0, 5).map((item) => item.fullDisplayName),
    }, request);
  }

  if (genericComponents.length) {
    return finalizeResolution(index, genericComponents, {
      type: 'service',
      label: genericService.name,
      candidates: registryMatches.slice(0, 5).map((item) => item.name),
    }, request);
  }

  if (productMatches.length) {
    const best = productMatches[0];
    return finalizeResolution(index, [{ product: best }], {
      type: 'product',
      label: best.fullDisplayName,
      candidates: productMatches.slice(0, 5).map((item) => item.fullDisplayName),
    }, request);
  }

  if (workbookServiceMatches.length) {
    const service = workbookServiceMatches[0];
    const components = expandWorkbookService(index, service);
    return finalizeResolution(index, components, {
      type: 'service',
      label: service.name,
      candidates: workbookServiceMatches.map((item) => item.name),
    }, request);
  }

  if (presetMatches.length) {
    const preset = presetMatches[0];
    const components = expandPreset(index, preset);
    return finalizeResolution(index, components, {
      type: 'preset',
      label: preset.displayName,
      candidates: presetMatches.map((item) => item.displayName),
    }, request);
  }

  return {
    ok: false,
    components: [],
    warnings: [],
    resolution: { type: 'none', candidates: [] },
  };
}

function buildRegistryQuery(request) {
  return String(request?.productQuery || request?.source || '')
    .replace(/\bquote\b/ig, ' ')
    .replace(/\b\d[\d,]*(?:\.\d+)?\s*(?:requests?|api calls?|transactions?|queries?|emails?|messages?|sms(?: messages?)?|tokens?|gb|tb|mbps|gbps|users?|named users?|ocpus?|ecpus?|hours?|days?)\b/ig, ' ')
    .replace(/[,+]/g, ' ')
    .replace(/\bper month\b|\bper hour\b|\bper day\b|\bmonthly\b|\bhourly\b/ig, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function searchRelevantProducts(index, request, limit = 12) {
  const rawQuery = String(request?.productQuery || request?.source || '').trim();
  const cleanedQuery = buildRegistryQuery(request);
  const merged = [];
  const seen = new Set();
  for (const query of [cleanedQuery, rawQuery]) {
    if (!query) continue;
    for (const product of searchProducts(index, query, limit)) {
      if (seen.has(product.partNumber)) continue;
      seen.add(product.partNumber);
      merged.push(product);
      if (merged.length >= limit) return merged;
    }
  }
  return merged
    .sort((a, b) => scoreProductCompatibility(b, request) - scoreProductCompatibility(a, request))
    .slice(0, limit);
}

function scoreProductCompatibility(product, request) {
  const text = `${product?.displayName || ''} ${product?.metricDisplayName || ''} ${product?.serviceCategoryDisplayName || ''}`.toLowerCase();
  const source = String(request?.source || '').toLowerCase();
  let score = 0;

  const explicitGpus = /(\d[\d,]*(?:\.\d+)?)\s*gpus?\b/i.test(source);
  const explicitOcpus = /(\d[\d,]*(?:\.\d+)?)\s*ocpus?\b/i.test(source);
  const explicitEcpus = /(\d[\d,]*(?:\.\d+)?)\s*ecpus?\b/i.test(source);

  if (explicitGpus) {
    if (text.includes('gpu per hour')) score += 500;
    if (text.includes('ocpu per hour') || text.includes('ecpu per hour')) score -= 200;
  }
  if (explicitOcpus) {
    if (text.includes('ocpu per hour')) score += 500;
    if (text.includes('gpu per hour')) score -= 200;
  }
  if (explicitEcpus) {
    if (text.includes('ecpu per hour')) score += 500;
    if (text.includes('gpu per hour')) score -= 200;
  }
  if (/\bdense i\/o\b/i.test(source) && /dense i\/o/i.test(text)) score += 200;
  if (/\bstandard\b/i.test(source) && /\bstandard\b/i.test(text)) score += 100;
  if (/\bbare metal\b/i.test(source) && /bare metal/i.test(text)) score += 100;
  if (/\bmetered\b/i.test(source) && /\bmetered\b/i.test(text)) score += 100;

  return score;
}

function findFirstResolvableRegistryMatch(index, request, registryMatches) {
  const rankedMatches = [...(registryMatches || [])].sort(
    (a, b) => scoreRegistryMatchCompatibility(index, b, request) - scoreRegistryMatchCompatibility(index, a, request),
  );
  for (const service of rankedMatches) {
    const components = buildGenericServiceComponents(index, request, service);
    if (components.length) return { service, components };
  }
  return null;
}

function isDetailedMediaFlowRequest(text) {
  const source = String(text || '').toLowerCase();
  return /\bmedia flow\b/.test(source) &&
    /\b(sd|hd|4k)\b/.test(source) &&
    /\b(?:below 30fps|above 30fps and below 60fps|above 60fps and below 120fps)\b/.test(source);
}

function selectDetailedMediaFlowProduct(matches, query) {
  const source = String(query || '').toLowerCase();
  const expectedTags = [];
  if (/\b4k\b/.test(source)) expectedTags.push('4k');
  else if (/\bhd\b/.test(source)) expectedTags.push('hd');
  else if (/\bsd\b/.test(source)) expectedTags.push('sd');

  if (/\bbelow 30fps\b/.test(source)) expectedTags.push('below 30fps');
  else if (/\babove 30fps and below 60fps\b/.test(source)) expectedTags.push('above 30fps and below 60fps');
  else if (/\babove 60fps and below 120fps\b/.test(source)) expectedTags.push('above 60fps and below 120fps');

  const ranked = (matches || []).map((product) => {
    const name = String(product?.fullDisplayName || product?.displayName || '').toLowerCase();
    const score = expectedTags.reduce((total, tag) => total + (name.includes(tag) ? 1 : 0), 0);
    return { product, score };
  });

  ranked.sort((a, b) => b.score - a.score);
  return ranked[0]?.product || null;
}

function finalizeResolution(index, components, resolution, request = {}) {
  const filtered = (components || []).filter((item) => item && item.product);
  const expanded = shouldExpandWorkbookPrerequisites(request)
    ? expandWorkbookPrerequisites(index, filtered)
    : { components: filtered, warnings: [] };
  return {
    ok: expanded.components.length > 0,
    components: expanded.components,
    warnings: expanded.warnings,
    resolution,
  };
}

function shouldExpandWorkbookPrerequisites(request = {}) {
  if (request?.applyWorkbookPrerequisites === true) return true;
  if (request?.metadata?.inventorySource) return true;
  if (request?.metadata?.sourceType === 'rvtools' || request?.metadata?.sourceType === 'inventory_workbook') return true;
  return false;
}

function expandPreset(index, preset) {
  return preset.presetItems
    .flatMap((item) => index.productsByPartNumber.get(item.partNumber) || [])
    .filter(Boolean)
    .map((product) => ({ product }));
}

function expandWorkbookService(index, service) {
  const components = [];
  for (const partNumber of service.partNumbers || []) {
    const products = index.productsByPartNumber.get(partNumber) || [];
    for (const product of products) {
      components.push({ product, dependencyKind: 'service-match' });
    }
  }
  return components;
}

function buildGenericServiceComponents(index, request, service) {
  const components = [];
  const source = String(request?.source || '').toLowerCase();
  const explicitGpus = /(\d[\d,]*(?:\.\d+)?)\s*gpus?\b/i.test(source);
  const explicitOcpus = /(\d[\d,]*(?:\.\d+)?)\s*ocpus?\b/i.test(source);
  const explicitEcpus = /(\d[\d,]*(?:\.\d+)?)\s*ecpus?\b/i.test(source);
  for (const partNumber of service.partNumbers || []) {
    const products = index.productsByPartNumber.get(partNumber) || [];
    for (const product of products) {
      const pattern = inferConsumptionPattern(product.metricDisplayName, service.name);
      if (explicitGpus && (pattern === 'ocpu-hour' || pattern === 'ecpu-hour')) continue;
      if (explicitOcpus && pattern === 'gpu-hour') continue;
      if (explicitEcpus && pattern === 'gpu-hour') continue;
      const quantity = inferQuantityForPattern(pattern, product, request);
      if (Number.isFinite(Number(quantity)) && Number(quantity) > 0) {
        components.push({
          product,
          quantity: Number(quantity),
          instances: 1,
          dependencyKind: `pattern:${pattern}`,
        });
        continue;
      }
      if ((service.partNumbers || []).length === 1) {
        components.push({
          product,
          quantity: 1,
          instances: 1,
          dependencyKind: `pattern:${pattern || 'default'}`,
        });
      }
    }
  }
  return dedupeComponents(components);
}

function scoreRegistryMatchCompatibility(index, service, request) {
  if (!service) return 0;
  const serviceText = String(service?.name || '').toLowerCase();
  const source = String(request?.source || '').toLowerCase();
  let score = 0;

  for (const partNumber of service.partNumbers || []) {
    const products = index.productsByPartNumber.get(partNumber) || [];
    for (const product of products) {
      score = Math.max(score, scoreProductCompatibility(product, request));
    }
  }

  const explicitGpus = /(\d[\d,]*(?:\.\d+)?)\s*gpus?\b/i.test(source);
  const explicitOcpus = /(\d[\d,]*(?:\.\d+)?)\s*ocpus?\b/i.test(source);
  const explicitEcpus = /(\d[\d,]*(?:\.\d+)?)\s*ecpus?\b/i.test(source);

  if (explicitGpus && /\bgpu\b/.test(serviceText)) score += 200;
  if (explicitGpus && /\bocpu\b|\becpu\b/.test(serviceText)) score -= 100;
  if (explicitOcpus && /\bocpu\b/.test(serviceText)) score += 200;
  if (explicitOcpus && /\bgpu\b/.test(serviceText)) score -= 200;
  if (explicitEcpus && /\becpu\b/.test(serviceText)) score += 200;
  if (explicitEcpus && /\bgpu\b/.test(serviceText)) score -= 200;

  if (/\bdense i\/o\b/i.test(source) && /dense i\/o/i.test(serviceText)) score += 150;
  if (/\bstandard\b/i.test(source) && /\bstandard\b/i.test(serviceText)) score += 100;
  if (/\bbare metal\b/i.test(source) && /bare metal/i.test(serviceText)) score += 100;
  if (/\bmetered\b/i.test(source) && /\bmetered\b/i.test(serviceText)) score += 100;

  return score;
}

function expandWorkbookPrerequisites(index, baseComponents) {
  const warnings = [];
  const componentsByPart = new Map();
  const pendingServices = [];
  const seenServices = new Set();

  function addComponent(component) {
    if (!component?.product?.partNumber) return;
    const partNumber = component.product.partNumber;
    if (componentsByPart.has(partNumber)) return;
    componentsByPart.set(partNumber, component);
    const workbookPart = getWorkbookPart(index.workbookRules, partNumber);
    if (!workbookPart) return;
    for (const prerequisiteName of workbookPart.prerequisites || []) {
      const service = getWorkbookService(index.workbookRules, prerequisiteName);
      if (!service) {
        warnings.push(`Workbook prerequisite not found in registry: ${prerequisiteName}.`);
        continue;
      }
      if (seenServices.has(service.key)) continue;
      seenServices.add(service.key);
      pendingServices.push(service);
    }
  }

  for (const component of baseComponents || []) addComponent(component);

  while (pendingServices.length) {
    const service = pendingServices.shift();
    const products = resolvePrerequisiteServiceProducts(index, service);
    if (!products.length) {
      warnings.push(`Workbook prerequisite could not be resolved to catalog SKUs: ${service.name}.`);
      continue;
    }
    for (const product of products) {
      addComponent({
        product,
        quantity: 1,
        instances: 1,
        dependencyKind: 'workbook-prerequisite',
      });
    }
  }

  return {
    components: Array.from(componentsByPart.values()),
    warnings: dedupe(warnings),
  };
}

function resolvePrerequisiteServiceProducts(index, service) {
  const partNumbers = Array.isArray(service?.partNumbers) ? service.partNumbers : [];
  const products = partNumbers.flatMap((partNumber) => index.productsByPartNumber.get(partNumber) || []);
  if (products.length > 0) return products;

  if (partNumbers.length > 0) return [];

  const fallbackMatches = searchProducts(index, service?.name || '', 4);
  return fallbackMatches;
}

function shouldPreferPreset(query) {
  const text = String(query || '').toLowerCase();
  if (!text) return false;
  return /\b(architecture|3-tier|three-tier|stack|landing zone|environment|solution|workload|platform)\b/.test(text);
}

function isCompositeWorkloadRequest(text) {
  const source = String(text || '').toLowerCase();
  const hits = [
    /\bload balancer\b/.test(source),
    /\bblock storage\b|\bblock volumes?\b/.test(source),
    /\bobject storage\b/.test(source),
    /\bfastconnect\b|\bfast connect\b/.test(source),
    /\b(?:vm|bm)\.[a-z0-9.]+(?:\.flex|\.\d+)\b/.test(source) ||
      /\b(?:standard|optimized)\d+(?:\.\d+|\.flex)\b/.test(source) ||
      /\bdenseio\.[ea]\d+\.flex\b/.test(source) ||
      /\b[ea]\d+\.flex\b/.test(source),
  ].filter(Boolean).length;
  return hits >= 2 || /\b3-tier\b|\bthree-tier\b|\barchitecture\b/.test(source);
}

function resolveCompositeWorkload(index, request) {
  const components = [];
  components.push(...resolveCompositeCompute(index, request));
  components.push(...resolveCompositeLoadBalancer(index, request));
  components.push(...resolveCompositeBlockStorage(index, request));
  components.push(...resolveCompositeObjectStorage(index, request));
  return components;
}

function resolveCompositeCompute(index, request) {
  const source = String(request.source || '');
  const match = source.match(/(\d+)\s*x\s*(?:vm\.)?(?:standard\.)?(e\d+)\.flex[^\d]*(\d+(?:\.\d+)?)\s*ocpu[^\d]*(\d+(?:\.\d+)?)\s*gb/i);
  if (!match && (request.shape?.kind === 'flex' || request.shape?.kind === 'fixed')) {
    return resolveFlexComponents(index, {
      ...request,
      quantity: Number(request.ocpus || request.quantity || request.shape?.fixedOcpus || 1),
    }).map((item) => ({
      ...item,
      instances: Number(request.instances || 1),
      dependencyKind: item.dependencyKind || classifyComputeMetric(item.product),
    }));
  }
  if (!match) return [];

  const instances = Number(match[1]);
  const series = match[2].toUpperCase();
  const ocpus = Number(match[3]);
  const memory = Number(match[4]);
  const familyLabel = 'Standard';

  return index.products
    .filter((product) => {
      const name = String(product.displayName || '');
      return name.includes(`Compute - ${familyLabel} - ${series}`) &&
        product.serviceCategoryDisplayName === 'Compute - Virtual Machine';
    })
    .map((product) => ({
      product,
      quantity: /memory/i.test(`${product.metricDisplayName} ${product.displayName}`) ? memory : ocpus,
      instances,
      dependencyKind: classifyComputeMetric(product),
    }));
}

function resolveCompositeLoadBalancer(index, request) {
  const source = String(request.source || '');
  if (!/\bload balancer\b/i.test(source)) return [];

  const bandwidthMbps = parseLabeledBandwidthMbps(source, /(flexible load balancer|flex load balancer|load balancer)/i) ||
    parseStandaloneBandwidthMbps(source);
  const components = [];

  const base = index.products.find((product) =>
    product.partNumber === 'B93030' || (
      product.serviceCategoryDisplayName === 'Flexible Load Balancer' &&
      /load balancer base/i.test(product.displayName)
    )
  );
  if (base) components.push({ product: base, quantity: 1, instances: 1, dependencyKind: 'load-balancer-base' });

  const bandwidth = index.products.find((product) =>
    product.partNumber === 'B93031' || (
      product.serviceCategoryDisplayName === 'Flexible Load Balancer' &&
      /load balancer bandwidth/i.test(product.displayName)
    )
  );
  if (bandwidth && bandwidthMbps) {
    components.push({
      product: bandwidth,
      quantity: bandwidthMbps,
      instances: 1,
      dependencyKind: 'load-balancer-bandwidth',
    });
  }

  return components;
}

function resolveCompositeBlockStorage(index, request) {
  const quantityGb = parseLabeledCapacity(request.source, /(block storage|block volumes?)/i);
  if (!quantityGb) return [];

  const components = [];
  const storage = index.products.find((product) => product.partNumber === 'B91961');
  const performance = index.products.find((product) => product.partNumber === 'B91962');
  if (storage) components.push({ product: storage, quantity: quantityGb, instances: 1, dependencyKind: 'block-storage' });
  const vpusPerGb = parseBlockVolumeVpus(request.source) || 10;
  if (performance) components.push({ product: performance, quantity: quantityGb * vpusPerGb, instances: 1, dependencyKind: 'block-performance' });
  return components;
}

function resolveCompositeObjectStorage(index, request) {
  const quantityGb = parseLabeledCapacity(request.source, /(object storage)/i);
  if (!quantityGb) return [];

  const storage = index.products.find((product) => product.partNumber === 'B91628');
  return storage ? [{ product: storage, quantity: quantityGb, instances: 1, dependencyKind: 'object-storage' }] : [];
}

function parseLabeledCapacity(source, labelPattern) {
  const text = String(source || '');
  const segments = splitWorkloadSegments(text).filter((segment) => labelPattern.test(segment));
  for (const segment of segments) {
    const quantity = extractCapacityFromSegment(segment, labelPattern);
    if (quantity !== null) return quantity;
  }
  return extractCapacityFromSegment(text, labelPattern);
}

function parseLabeledBandwidthMbps(source, labelPattern) {
  const text = String(source || '');
  const segments = splitWorkloadSegments(text).filter((segment) => labelPattern.test(segment));
  for (const segment of segments) {
    const value = extractBandwidthFromSegment(segment, labelPattern);
    if (value !== null) return value;
  }
  return extractBandwidthFromSegment(text, labelPattern);
}

function parseStandaloneBandwidthMbps(source) {
  const match = String(source || '').match(/(\d+(?:\.\d+)?)\s*mbps\b/i);
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

function splitWorkloadSegments(text) {
  return String(text || '')
    .split(/\s*(?:\+|,|\band\b)\s*/i)
    .map((item) => item.trim())
    .filter(Boolean);
}

function extractCapacityFromSegment(text, labelPattern) {
  const match = String(text || '').match(new RegExp(`(?:${labelPattern.source})[^\\d]{0,12}(\\d+(?:\\.\\d+)?)\\s*(tb|gb)\\b`, 'i')) ||
    String(text || '').match(new RegExp(`(\\d+(?:\\.\\d+)?)\\s*(tb|gb)\\b(?:\\s+(?:of\\s+)?)?(?:${labelPattern.source})`, 'i'));
  if (!match) return null;
  const value = Number(match[1]);
  const unit = String(match[2] || '').toLowerCase();
  if (!Number.isFinite(value)) return null;
  return unit === 'tb' ? value * 1024 : value;
}

function extractBandwidthFromSegment(text, labelPattern) {
  const match = String(text || '').match(new RegExp(`(?:${labelPattern.source})[^\\d]{0,12}(\\d+(?:\\.\\d+)?)\\s*mbps\\b`, 'i')) ||
    String(text || '').match(new RegExp(`(\\d+(?:\\.\\d+)?)\\s*mbps\\b(?:\\s+(?:of\\s+)?)?(?:${labelPattern.source})`, 'i'));
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

function inferWorkbookPriceType(metricName) {
  const metric = String(metricName || '').toLowerCase();
  if (metric.includes('per hour')) return 'HOUR';
  if (metric.includes('per month')) return 'MONTH';
  return '';
}

function deriveWorkbookCategory(subscriptionService) {
  const displayName = String(subscriptionService || '')
    .replace(/^Oracle Cloud Infrastructure\s*-\s*/i, '')
    .replace(/^Oracle IaaS Public Cloud Services\s*-\s*/i, '')
    .trim();
  const lower = displayName.toLowerCase();
  if (lower.startsWith('compute - bare metal')) return 'Compute - Bare Metal';
  if (lower.startsWith('compute - virtual machine')) return 'Compute - Virtual Machine';
  if (lower.startsWith('storage - block volume')) return 'Storage - Block Volumes';
  return displayName;
}

function buildSyntheticWorkbookProduct(index, partNumber) {
  const workbookPart = getWorkbookPart(index.workbookRules, partNumber);
  if (!workbookPart) return null;
  const paygoPrice = Number(workbookPart.prices?.localizedPaygoPrice ?? workbookPart.prices?.universalCreditsPaygo);
  if (!Number.isFinite(paygoPrice)) return null;
  const metricDisplayName = String(workbookPart.metric || '').trim();
  const category = deriveWorkbookCategory(workbookPart.subscriptionService);
  const displayName = String(workbookPart.description || workbookPart.subscriptionService || '').trim()
    .replace(/^Oracle Cloud Infrastructure\s*-\s*/i, '')
    .replace(/^Oracle IaaS Public Cloud Services\s*-\s*/i, '')
    .trim();
  const metricId = `workbook:${partNumber}:${metricDisplayName.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
  const normalized = {
    partNumber,
    displayName,
    fullDisplayName: `${partNumber} - ${displayName}`,
    priceType: inferWorkbookPriceType(metricDisplayName),
    serviceCategoryDisplayName: category,
    metricId,
    metricDisplayName,
    metricUnitDisplayName: '',
    pricingByCurrency: {
      USD: [{ model: 'PAY_AS_YOU_GO', value: paygoPrice }],
    },
    tiersByCurrency: {
      USD: [{ model: 'PAY_AS_YOU_GO', value: paygoPrice, rangeMin: null, rangeMax: null, rangeUnit: null }],
    },
  };
  return normalized;
}

function resolveFlexComponents(index, request) {
  if (!request?.shape?.family || !request?.shape?.series) return [];
  const familyMap = {
    standard: 'Standard',
    denseio: 'Dense I/O',
    gpu: 'GPU',
    optimized: 'Optimized',
  };
  if (request.shape.kind === 'fixed' && request.shape.productLabel) {
    const wantsMetered = /\bmetered\b/i.test(String(request.source || ''));
    const registryProducts = Array.isArray(request.shape.partNumbers)
      ? request.shape.partNumbers.flatMap((partNumber) => index.productsByPartNumber.get(partNumber) || [])
      : [];
    const registryProduct = registryProducts.find((product) => {
      const displayName = String(product.displayName || '').trim();
      return wantsMetered ? /metered/i.test(displayName) : !/metered/i.test(displayName);
    }) || registryProducts[0];
    if (registryProduct) {
      return [{
        product: registryProduct,
        quantity: Number(request.shape.fixedOcpus || request.ocpus || request.quantity || 1),
        dependencyKind: 'compute',
      }];
    }
    const syntheticRegistryProduct = Array.isArray(request.shape.partNumbers)
      ? request.shape.partNumbers
        .map((partNumber) => buildSyntheticWorkbookProduct(index, partNumber))
        .find((product) => {
          if (!product) return false;
          const displayName = String(product.displayName || '').trim();
          return wantsMetered ? /metered/i.test(displayName) : !/metered/i.test(displayName);
        }) || request.shape.partNumbers
        .map((partNumber) => buildSyntheticWorkbookProduct(index, partNumber))
        .find(Boolean)
      : null;
    if (syntheticRegistryProduct) {
      return [{
        product: syntheticRegistryProduct,
        quantity: Number(request.shape.fixedOcpus || request.ocpus || request.quantity || 1),
        dependencyKind: 'compute',
      }];
    }
    const expectedLabels = [
      request.shape.productLabel,
      `${request.shape.productLabel} - Metered`,
    ].map((item) => String(item || '').trim()).filter(Boolean);
    const categoryPattern = /^Compute - (?:Virtual Machine|Bare Metal)$/i;
    const fixedProduct = index.products.find((product) => {
      const category = String(product.serviceCategoryDisplayName || '').trim();
      const displayName = String(product.displayName || '').trim();
      if (!categoryPattern.test(category)) return false;
      if (!expectedLabels.includes(displayName)) return false;
      return wantsMetered ? /metered/i.test(displayName) : !/metered/i.test(displayName);
    }) || index.products.find((product) => {
      const category = String(product.serviceCategoryDisplayName || '').trim();
      const displayName = String(product.displayName || '').trim();
      return categoryPattern.test(category) && expectedLabels.includes(displayName);
    });
    return fixedProduct ? [{
      product: fixedProduct,
      quantity: Number(request.shape.fixedOcpus || request.ocpus || request.quantity || 1),
      dependencyKind: 'compute',
    }] : [];
  }

  const familyLabel = familyMap[request.shape.family];
  if (!familyLabel) return [];
  const desiredLabel = `Compute - ${familyLabel} - ${request.shape.series}`.toLowerCase();

  return index.products
    .filter((product) => {
      const name = String(product.displayName || '').toLowerCase();
      return product.serviceCategoryDisplayName === 'Compute - Virtual Machine' &&
        name.includes(desiredLabel);
    })
    .map((product) => ({
      product,
      quantity: resolveFlexComponentQuantity(product, request),
      dependencyKind: classifyComputeMetric(product),
    }));
}

function resolveFlexComponentQuantity(product, request) {
  const metric = `${product.metricDisplayName} ${product.displayName}`.toLowerCase();
  if (metric.includes('memory') && hasNumericValue(request.memoryQuantity)) {
    return Number(request.memoryQuantity);
  }
  return Number(request.quantity || 1);
}

function classifyComputeMetric(product) {
  const metric = `${product.metricDisplayName} ${product.displayName}`.toLowerCase();
  if (metric.includes('memory')) return 'memory';
  if (metric.includes('ocpu') || metric.includes('ecpu')) return 'compute';
  return 'compute-component';
}

function isFastConnectRequest(text) {
  return /\bfast\s?connect\b/i.test(String(text || ''));
}

function resolveFastConnectComponents(index, request) {
  const source = String(request.source || '');
  const match = source.match(/(\d+(?:\.\d+)?)\s*g(?:bp?s?)?\b/i);
  const portGbps = match ? Number(match[1]) : 1;
  const mapping = new Map([
    [1, 'B88325'],
    [10, 'B88326'],
    [100, 'B93126'],
    [400, 'B107975'],
  ]);
  const partNumber = mapping.get(portGbps) || 'B88325';
  const product = (index.productsByPartNumber.get(partNumber) || [])[0];
  if (product) {
    return [{ product, quantity: 1, instances: 1, dependencyKind: 'fastconnect-port' }];
  }

  const fallback = index.products.find((item) =>
    item.serviceCategoryDisplayName === 'Networking - FastConnect' &&
    new RegExp(`\\b${portGbps}\\s*g(?:bp?s?)?\\b`, 'i').test(item.displayName)
  );
  return fallback ? [{ product: fallback, quantity: 1, instances: 1, dependencyKind: 'fastconnect-port' }] : [];
}

function isBlockVolumeRequest(text) {
  const source = String(text || '').toLowerCase();
  return /\bblock volumes?\b|\bblock storage\b/.test(source) && /\bvpu'?s?\b|\bperformance\b/.test(source);
}

function isFunctionsRequest(text) {
  const source = String(text || '').toLowerCase();
  return /\b(oracle functions|oci functions|functions|serverless)\b/.test(source) &&
    (/\binvocations?\b/.test(source) || /\bexecution time\b/.test(source) || /\bmemory\b/.test(source));
}

function resolveNetworkFirewallComponents(index, request) {
  const instances = Number(request.firewallInstances || request.quantity || 1);
  const dataGb = Number(request.dataProcessedGb || 0);
  const instance = (index.productsByPartNumber.get('B95403') || [])[0];
  const processing = (index.productsByPartNumber.get('B95404') || [])[0];
  const components = [];
  if (instance) components.push({ product: instance, quantity: instances, instances: 1, dependencyKind: 'network-firewall-instance' });
  if (processing && Number.isFinite(dataGb) && dataGb > 0) {
    components.push({ product: processing, quantity: dataGb, instances: 1, dependencyKind: 'network-firewall-data' });
  }
  return components;
}

function resolveWafComponents(index, request) {
  const instances = Number(request.wafInstances || request.instances || request.quantity || 1);
  const requests = Number(request.requestCount || 0);
  const instance = (index.productsByPartNumber.get('B94579') || [])[0];
  const requestSku = (index.productsByPartNumber.get('B94277') || [])[0];
  const components = [];
  if (instance) components.push({ product: instance, quantity: instances, instances: 1, dependencyKind: 'waf-instance' });
  if (requestSku && Number.isFinite(requests) && requests > 0) {
    components.push({ product: requestSku, quantity: requests / 1000000, instances: 1, dependencyKind: 'waf-requests' });
  }
  return components;
}

function resolveFileStorageComponents(index, request) {
  const capacityGb = Number(request.capacityGb || request.quantity || 0);
  const performanceUnits = Number(request.vpuPerGb || 0);
  const storage = (index.productsByPartNumber.get('B89057') || [])[0];
  const performance = (index.productsByPartNumber.get('B109546') || [])[0];
  const components = [];
  if (storage && capacityGb > 0) components.push({ product: storage, quantity: capacityGb, instances: 1, dependencyKind: 'file-storage' });
  if (performance && capacityGb > 0 && performanceUnits > 0) {
    components.push({ product: performance, quantity: capacityGb * performanceUnits, instances: 1, dependencyKind: 'file-storage-performance' });
  }
  return components;
}

function resolveObjectStorageComponents(index, request) {
  const capacityGb = Number(request.capacityGb || request.quantity || 0);
  const storage = (index.productsByPartNumber.get('B91628') || [])[0];
  if (!storage || !(capacityGb > 0)) return [];
  return [{
    product: storage,
    quantity: capacityGb,
    instances: 1,
    dependencyKind: 'object-storage',
  }];
}

function resolveObjectStorageRequestComponents(index, request) {
  const requestCount = Number(request.requestCount || request.quantity || 0);
  const requests = (index.productsByPartNumber.get('B91627') || [])[0];
  if (!requests || !(requestCount > 0)) return [];
  return [{
    product: requests,
    quantity: requestCount / 10000,
    instances: 1,
    dependencyKind: 'object-storage-requests',
  }];
}

function resolveArchiveStorageComponents(index, request) {
  const capacityGb = Number(request.capacityGb || request.quantity || 0);
  const storage = (index.productsByPartNumber.get('B91633') || [])[0];
  if (!storage || !(capacityGb > 0)) return [];
  return [{
    product: storage,
    quantity: capacityGb,
    instances: 1,
    dependencyKind: 'archive-storage',
  }];
}

function resolveInfrequentAccessStorageComponents(index, request) {
  const source = String(request.source || '');
  const wantsRetrieval = /\bretriev(?:al|ed)?\b/i.test(source);
  const retrievalGb = Number(request.dataProcessedGb || (wantsRetrieval ? request.capacityGb || request.quantity || 0 : 0));
  const capacityGb = Number(request.capacityGb || request.quantity || 0);
  const storage = (index.productsByPartNumber.get('B93000') || [])[0];
  const retrieval = (index.productsByPartNumber.get('B93001') || [])[0];
  if (wantsRetrieval && retrieval && retrievalGb > 0) {
    return [{
      product: retrieval,
      quantity: retrievalGb,
      instances: 1,
      dependencyKind: 'infrequent-access-retrieval',
    }];
  }
  if (storage && capacityGb > 0) {
    return [{
      product: storage,
      quantity: capacityGb,
      instances: 1,
      dependencyKind: 'infrequent-access-storage',
    }];
  }
  return [];
}

function resolveAiAgentsKnowledgeBaseStorageComponents(index, request) {
  const storage = (index.productsByPartNumber.get('B110462') || [])[0];
  const capacityGb = Number(request.capacityGb || request.quantity || 0);
  if (!storage || !(capacityGb > 0)) return [];
  return [{
    product: storage,
    quantity: capacityGb,
    instances: 1,
    dependencyKind: 'ai-agents-knowledge-base-storage',
  }];
}

function resolveLoadBalancerComponents(index, request) {
  const bandwidthMbps = Number(request.quantity || parseLabeledBandwidthMbps(request.source, /(flexible load balancer|flex load balancer|load balancer)/i) || 0);
  const components = [];
  const base = (index.productsByPartNumber.get('B93030') || [])[0];
  const bandwidth = (index.productsByPartNumber.get('B93031') || [])[0];
  if (base) {
    components.push({
      product: base,
      quantity: 1,
      instances: 1,
      dependencyKind: 'load-balancer-base',
    });
  }
  if (bandwidth && bandwidthMbps > 0) {
    components.push({
      product: bandwidth,
      quantity: bandwidthMbps,
      instances: 1,
      dependencyKind: 'load-balancer-bandwidth',
    });
  }
  return components;
}

function resolveLogAnalyticsComponents(index, request) {
  const capacityGb = Number(request.capacityGb || 0);
  const source = String(request.source || '');
  const archivalRequested = /\barchiv(?:e|al)\b/i.test(source);
  const activeRequested = /\bactive\b/i.test(source) || !archivalRequested;
  const active = (index.productsByPartNumber.get('B95634') || [])[0];
  const archival = (index.productsByPartNumber.get('B92809') || [])[0];
  const components = [];
  if (archivalRequested && archival && capacityGb > 0) {
    const storageUnits = Math.max(1, capacityGb / 300);
    components.push({
      product: archival,
      quantity: storageUnits,
      instances: 1,
      dependencyKind: 'log-analytics-archival-storage',
      warning: 'Log Analytics Archival Storage is priced per Logging Analytics Storage Unit Per Hour. This quote infers 1 storage unit = 300 GB, aligned with the Log Analytics Storage Unit definition in the current Oracle price-list references.',
    });
  }
  if (activeRequested && active && capacityGb > 0) {
    const billableGb = Math.max(0, capacityGb - 10);
    const storageUnits = billableGb <= 0 ? 0 : Math.max(1, billableGb / 300);
    const warning = billableGb <= 0
      ? 'Log Analytics Active Storage assumes the first 10 GB per month are free, so this estimate remains at $0.00 within the documented free tier.'
      : 'Log Analytics Active Storage assumes the first 10 GB per month are free, each storage unit represents 300 GB/month, and billable usage has a minimum of 1 storage unit.';
    components.push({
      product: active,
      quantity: storageUnits,
      instances: 1,
      dependencyKind: 'log-analytics-active-storage',
      warning,
    });
  }
  return components;
}

function resolveAutonomousTpComponents(index, request) {
  const source = String(request.source || '');
  const byol = /\bbyol\b|\bbring your own license\b/i.test(source);
  const ecpus = Number(request.ecpus || request.quantity || 0);
  const capacityGb = Number(request.capacityGb || 0);
  const compute = (index.productsByPartNumber.get(byol ? 'B95704' : 'B95702') || [])[0];
  const storage = (index.productsByPartNumber.get('B95706') || [])[0];
  const components = [];
  if (compute && ecpus > 0) {
    components.push({ product: compute, quantity: ecpus, instances: 1, dependencyKind: 'autonomous-ai-tp-compute' });
  }
  if (storage && capacityGb > 0) {
    components.push({ product: storage, quantity: capacityGb, instances: 1, dependencyKind: 'autonomous-ai-tp-storage' });
  }
  return components;
}

function resolveAutonomousDwComponents(index, request) {
  const source = String(request.source || '');
  const byol = /\bbyol\b|\bbring your own license\b/i.test(source);
  const ecpus = Number(request.ecpus || request.quantity || 0);
  const capacityGb = Number(request.capacityGb || 0);
  const compute = (index.productsByPartNumber.get(byol ? 'B95703' : 'B95701') || [])[0];
  const storage = (index.productsByPartNumber.get('B95706') || [])[0];
  const components = [];
  if (compute && ecpus > 0) {
    components.push({
      product: compute,
      quantity: ecpus,
      instances: 1,
      dependencyKind: 'autonomous-ai-lakehouse-compute',
    });
  }
  if (storage && capacityGb > 0) {
    components.push({
      product: storage,
      quantity: capacityGb,
      instances: 1,
      dependencyKind: 'autonomous-ai-lakehouse-storage',
      warning: 'Autonomous AI Lakehouse storage is currently mapped to the shared autonomous database storage SKU exposed in the Oracle pricing references used by this agent.',
    });
  }
  return components;
}

function resolveBaseDatabaseComponents(index, request) {
  const source = String(request.source || '');
  const byol = /\bbyol\b|\bbring your own license\b/i.test(source);
  const edition = String(request.databaseEdition || parseDatabaseEdition(source) || '').toLowerCase();
  const ocpus = Number(request.ocpus || 0);
  const ecpus = Number(request.ecpus || 0);
  const capacityGb = Number(request.capacityGb || 0);
  const components = [];
  const storage = (index.productsByPartNumber.get('B111584') || [])[0];
  const ocpuMap = {
    standard: 'B90569',
    enterprise: 'B90570',
    'high performance': 'B90571',
    'extreme performance': 'B90572',
  };
  const ecpuMap = {
    standard: 'B111585',
    enterprise: 'B111586',
    'high performance': 'B111587',
  };

  let compute = null;
  if (byol) {
    compute = (index.productsByPartNumber.get(ecpus > 0 ? 'B111588' : 'B90573') || [])[0] || null;
  } else if (ecpus > 0 && edition && ecpuMap[edition]) {
    compute = (index.productsByPartNumber.get(ecpuMap[edition]) || [])[0] || null;
  } else if (ocpus > 0 && edition && ocpuMap[edition]) {
    compute = (index.productsByPartNumber.get(ocpuMap[edition]) || [])[0] || null;
  }

  if (compute) {
    components.push({
      product: compute,
      quantity: ecpus > 0 ? ecpus : ocpus,
      instances: 1,
      dependencyKind: 'base-database-compute',
    });
  }
  if (storage && capacityGb > 0) {
    components.push({ product: storage, quantity: capacityGb, instances: 1, dependencyKind: 'base-database-storage' });
  }
  return components;
}

function resolveDatabaseCloudServiceComponents(index, request) {
  const source = String(request.source || '');
  const byol = /\bbyol\b|\bbring your own license\b/i.test(source);
  const edition = String(request.databaseEdition || parseDatabaseEdition(source) || '').toLowerCase();
  const ocpus = Number(request.ocpus || request.quantity || 0);
  const components = [];
  const includedMap = {
    standard: 'B88293',
    enterprise: 'B88290',
    'high performance': 'B88292',
    'extreme performance': 'B88291',
  };
  const byolMap = {
    standard: 'B88404',
    enterprise: 'B88404',
    'high performance': 'B88404',
    'extreme performance': 'B88402',
  };
  const computePart = byol ? byolMap[edition] : includedMap[edition];
  const compute = computePart ? (index.productsByPartNumber.get(computePart) || [])[0] : null;
  if (compute && ocpus > 0) {
    components.push({
      product: compute,
      quantity: ocpus,
      instances: 1,
      dependencyKind: 'database-cloud-service-compute',
    });
  }
  return components;
}

function resolveExadataExascaleComponents(index, request) {
  const source = String(request.source || '');
  const byol = /\bbyol\b|\bbring your own license\b/i.test(source);
  const ecpus = Number(request.ecpus || request.quantity || 0);
  const capacityGb = Number(request.capacityGb || 0);
  const storageModel = String(request.databaseStorageModel || '').toLowerCase();
  const components = [];
  const compute = (index.productsByPartNumber.get(byol ? 'B109357' : 'B109356') || [])[0];
  const storagePart = storageModel.includes('file') ? 'B107951' : storageModel.includes('smart') ? 'B107952' : '';
  const storage = storagePart ? (index.productsByPartNumber.get(storagePart) || [])[0] : null;
  if (compute && ecpus > 0) {
    components.push({
      product: compute,
      quantity: ecpus,
      instances: 1,
      dependencyKind: 'exadata-exascale-compute',
    });
  }
  if (storage && capacityGb > 0) {
    components.push({
      product: storage,
      quantity: capacityGb,
      instances: 1,
      dependencyKind: 'exadata-exascale-storage',
    });
  }
  return components;
}

function resolveExadataDedicatedComponents(index, request) {
  const source = String(request.source || '');
  const byol = /\bbyol\b|\bbring your own license\b/i.test(source);
  const ocpus = Number(request.ocpus || 0);
  const ecpus = Number(request.ecpus || 0);
  const components = [];
  const computePart = ecpus > 0
    ? (byol ? 'B110632' : 'B110631')
    : (byol ? 'B88847' : 'B88592');
  const compute = (index.productsByPartNumber.get(computePart) || [])[0];
  const infra = resolveExadataDedicatedInfra(index, request);
  const infraWarning = infra
    ? null
    : 'Dedicated Exadata infrastructure rack/server pricing is not included in this estimate unless you specify the infrastructure shape separately. The current quote covers the metered database compute line only.';
  if (compute && (ecpus > 0 || ocpus > 0)) {
    components.push({
      product: compute,
      quantity: ecpus > 0 ? ecpus : ocpus,
      instances: 1,
      dependencyKind: 'exadata-dedicated-compute',
      warning: infraWarning || undefined,
    });
  }
  if (infra) {
    components.push({
      product: infra,
      quantity: 1,
      instances: 1,
      dependencyKind: 'exadata-dedicated-infra',
    });
  }
  return components;
}

function resolveExadataCloudCustomerComponents(index, request) {
  const source = String(request.source || '');
  const byol = /\bbyol\b|\bbring your own license\b/i.test(source);
  const ocpus = Number(request.ocpus || 0);
  const ecpus = Number(request.ecpus || 0);
  const components = [];
  const computePart = ecpus > 0
    ? (byol ? 'B110663' : 'B110662')
    : (byol ? 'B91364' : 'B91363');
  const compute = (index.productsByPartNumber.get(computePart) || [])[0];
  const infra = resolveExadataCloudCustomerInfra(index, request);
  const activationNote = buildExadataCloudCustomerActivationNote(index, request);
  const prereqWarning = infra
    ? [
        'Installation/activation service and other non-metered prerequisites may still be required for Exadata Cloud@Customer. The current quote includes the metered database compute plus the selected infrastructure line when available from the live catalog or workbook-backed pricing data.',
        activationNote,
      ].filter(Boolean).join(' ')
    : [
        'Exadata Cloud@Customer infrastructure, installation/activation service, and other non-metered prerequisites are not included in this estimate unless you explicitly size them. The current quote covers the metered database compute line only.',
        activationNote,
      ].filter(Boolean).join(' ');
  if (compute && (ecpus > 0 || ocpus > 0)) {
    components.push({
      product: compute,
      quantity: ecpus > 0 ? ecpus : ocpus,
      instances: 1,
      dependencyKind: 'exadata-cloud-customer-compute',
      warning: prereqWarning,
    });
  }
  if (infra) {
    components.push({
      product: infra,
      quantity: 1,
      instances: 1,
      dependencyKind: 'exadata-cloud-customer-infra',
    });
  }
  return components;
}

function resolveExadataDedicatedInfra(index, request) {
  const shape = String(request.exadataInfraShape || '').toLowerCase();
  const generation = String(request.exadataInfraGeneration || '').toLowerCase();
  if (shape === 'base system') return (index.productsByPartNumber.get('B90777') || [])[0] || null;
  if (shape === 'quarter rack') {
    if (generation === 'x9m') return (index.productsByPartNumber.get('B93380') || [])[0] || null;
    if (generation === 'x8m') return (index.productsByPartNumber.get('B92380') || [])[0] || null;
    if (generation === 'x8') return (index.productsByPartNumber.get('B91535') || [])[0] || null;
    if (generation === 'x7') return (index.productsByPartNumber.get('B89999') || [])[0] || null;
  }
  if (shape === 'half rack') {
    if (generation === 'x8') return (index.productsByPartNumber.get('B91536') || [])[0] || null;
    if (generation === 'x7') return (index.productsByPartNumber.get('B90000') || [])[0] || null;
  }
  if (shape === 'full rack') {
    if (generation === 'x8') return (index.productsByPartNumber.get('B91537') || [])[0] || null;
    if (generation === 'x7') return (index.productsByPartNumber.get('B90001') || [])[0] || null;
  }
  if (shape === 'database server' && generation === 'x11m') return (index.productsByPartNumber.get('B110627') || [])[0] || null;
  if (shape === 'storage server' && generation === 'x11m') return (index.productsByPartNumber.get('B110629') || [])[0] || null;
  return null;
}

function resolveExadataCloudCustomerInfra(index, request) {
  const shape = String(request.exadataInfraShape || '').toLowerCase();
  const generation = String(request.exadataInfraGeneration || '').toLowerCase();
  if (shape === 'base system') {
    if (generation === 'x10m') return createWorkbookRecurringProduct(index, 'B96610');
    return (index.productsByPartNumber.get('B90777') || [])[0] || null;
  }
  if (shape === 'quarter rack') {
    if (generation === 'x9m') return (index.productsByPartNumber.get('B93380') || [])[0] || null;
    if (generation === 'x8m') return (index.productsByPartNumber.get('B92380') || [])[0] || null;
    if (generation === 'x8') return (index.productsByPartNumber.get('B91535') || [])[0] || null;
    if (generation === 'x7') return (index.productsByPartNumber.get('B89999') || [])[0] || null;
  }
  if (shape === 'database server') {
    if (generation === 'x11m') return (index.productsByPartNumber.get('B110627') || [])[0] || null;
    if (generation === 'x10m') return createWorkbookRecurringProduct(index, 'B96611');
  }
  if (shape === 'storage server') {
    if (generation === 'x11m') return (index.productsByPartNumber.get('B110629') || [])[0] || null;
    if (generation === 'x10m') return createWorkbookRecurringProduct(index, 'B96614');
  }
  if (shape === 'expansion rack' && generation === 'x10m') return createWorkbookRecurringProduct(index, 'B96615');
  return null;
}

function buildExadataCloudCustomerActivationNote(index, request) {
  const generation = String(request.exadataInfraGeneration || '').toLowerCase();
  if (generation !== 'x10m') return '';
  const activation = getWorkbookPart(index.workbookRules, 'B91390');
  const amount = Number(activation?.prices?.localizedPaygoPrice ?? activation?.prices?.universalCreditsPaygo);
  if (!Number.isFinite(amount)) return '';
  return `The one-time installation and activation service (${activation.partNumber}) is not included in recurring totals; reference price is USD ${amount.toFixed(2)} per rack.`;
}

function createWorkbookRecurringProduct(index, partNumber) {
  const workbookPart = getWorkbookPart(index.workbookRules, partNumber);
  if (!workbookPart) return null;
  const price = Number(workbookPart.prices?.localizedPaygoPrice ?? workbookPart.prices?.universalCreditsPaygo);
  if (!Number.isFinite(price)) return null;
  const metric = String(workbookPart.metric || '').trim() || 'Hosted Environment Per Month';
  return {
    partNumber: workbookPart.partNumber,
    displayName: workbookPart.subscriptionService,
    fullDisplayName: `${workbookPart.partNumber} - ${workbookPart.subscriptionService}`,
    priceType: 'MONTH',
    serviceCategoryDisplayName: workbookPart.subscriptionService,
    metricId: `workbook:${workbookPart.partNumber}`,
    metricDisplayName: metric,
    metricUnitDisplayName: metric,
    pricingByCurrency: {
      USD: [{
        model: 'PAY_AS_YOU_GO',
        value: price,
        rangeMin: null,
        rangeMax: null,
        rangeUnit: null,
      }],
    },
    tiersByCurrency: {
      USD: [{
        model: 'PAY_AS_YOU_GO',
        value: price,
        rangeMin: null,
        rangeMax: null,
        rangeUnit: null,
      }],
    },
  };
}

function resolveOacProfessionalComponents(index, request) {
  const source = String(request.source || '');
  const byol = /\bbyol\b|\bbring your own license\b/i.test(source);
  const ocpus = Number(request.ocpus || 0);
  const users = Number(request.users || 0);
  const components = [];
  if (users > 0) {
    const usersProduct = (index.productsByPartNumber.get('B92682') || [])[0];
    if (usersProduct) {
      components.push({
        product: usersProduct,
        quantity: users,
        instances: 1,
        dependencyKind: 'oac-professional-users',
      });
    }
    return components;
  }
  if (ocpus > 0) {
    const compute = (index.productsByPartNumber.get(byol ? 'B89636' : 'B89630') || [])[0];
    if (compute) {
      components.push({
        product: compute,
        quantity: ocpus,
        instances: 1,
        dependencyKind: 'oac-professional-ocpu',
      });
    }
  }
  return components;
}

function resolveOacEnterpriseComponents(index, request) {
  const source = String(request.source || '');
  const byol = /\bbyol\b|\bbring your own license\b/i.test(source);
  const ocpus = Number(request.ocpus || 0);
  const users = Number(request.users || 0);
  const components = [];
  if (users > 0) {
    const usersProduct = (index.productsByPartNumber.get('B92683') || [])[0];
    if (usersProduct) {
      components.push({
        product: usersProduct,
        quantity: users,
        instances: 1,
        dependencyKind: 'oac-enterprise-users',
      });
    }
    return components;
  }
  if (ocpus > 0) {
    const compute = (index.productsByPartNumber.get(byol ? 'B89637' : 'B89631') || [])[0];
    if (compute) {
      components.push({
        product: compute,
        quantity: ocpus,
        instances: 1,
        dependencyKind: 'oac-enterprise-ocpu',
      });
    }
  }
  return components;
}

function resolveOicStandardComponents(index, request) {
  const source = String(request.source || '');
  const byol = /\bbyol\b|\bbring your own license\b/i.test(source);
  const instances = Number(request.instances || request.quantity || 1);
  const product = (index.productsByPartNumber.get(byol ? 'B89643' : 'B89639') || [])[0];
  if (!product) return [];
  return [{
    product,
    quantity: instances,
    instances: 1,
    dependencyKind: 'oic-standard-instance',
  }];
}

function resolveOicEnterpriseComponents(index, request) {
  const source = String(request.source || '');
  const byol = /\bbyol\b|\bbring your own license\b/i.test(source);
  const instances = Number(request.instances || request.quantity || 1);
  const product = (index.productsByPartNumber.get(byol ? 'B89644' : 'B89640') || [])[0];
  if (!product) return [];
  return [{
    product,
    quantity: instances,
    instances: 1,
    dependencyKind: 'oic-enterprise-instance',
  }];
}

function resolveDataIntegrationComponents(index, request) {
  const components = [];
  const workspace = (index.productsByPartNumber.get('B92598') || [])[0];
  const processed = (index.productsByPartNumber.get('B92599') || [])[0];
  const execution = (index.productsByPartNumber.get('B93306') || [])[0];
  const source = String(request.source || '').toLowerCase();
  const workspaceCount = Number(request.workspaceCount || 0);
  const dataProcessedGb = Number(request.dataProcessedGb || 0);
  const executionHours = Number(request.executionHours || 0);

  if (workspace && (workspaceCount > 0 || source.includes('workspace'))) {
    components.push({ product: workspace, quantity: workspaceCount > 0 ? workspaceCount : 1, instances: 1, dependencyKind: 'data-integration-workspace' });
    return components;
  }
  if (execution && executionHours > 0) {
    components.push({ product: execution, quantity: executionHours, instances: 1, dependencyKind: 'data-integration-execution' });
    return components;
  }
  if (processed && dataProcessedGb > 0) {
    components.push({ product: processed, quantity: dataProcessedGb, instances: 1, dependencyKind: 'data-integration-processed' });
    return components;
  }
  return components;
}

function parseDatabaseEdition(source) {
  const lower = String(source || '').toLowerCase();
  if (/\bextreme performance\b/.test(lower)) return 'extreme performance';
  if (/\bhigh performance\b/.test(lower)) return 'high performance';
  if (/\benterprise\b/.test(lower)) return 'enterprise';
  if (/\bstandard\b/.test(lower)) return 'standard';
  if (/\bdeveloper\b/.test(lower)) return 'developer';
  return '';
}

function parseFunctionsInputs(text) {
  const source = String(text || '');
  const daysPerMonth = matchNumber(source, [
    /(\d+(?:\.\d+)?)\s*days?\s*\/\s*month/i,
    /(\d+(?:\.\d+)?)\s*days?\s*per\s*month/i,
  ]) ?? 31;
  const invocationsPerMonth = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*invocations?\s*per\s*month/i,
    /(\d[\d,]*(?:\.\d+)?)\s*invocations?\s*\/\s*month/i,
    /(\d[\d,]*(?:\.\d+)?)\s*invocations?\/month/i,
  ]);
  const invocationsPerDay = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*invocations?\s*per\s*day/i,
    /(\d[\d,]*(?:\.\d+)?)\s*invocations?\s*\/\s*day/i,
    /(\d[\d,]*(?:\.\d+)?)\s*invocations?\/day/i,
  ]);
  const executionMs = matchNumber(source, [
    /(\d[\d,]*(?:\.\d+)?)\s*milliseconds?/i,
    /execution time(?: per invocation)?[^\d]*(\d[\d,]*(?:\.\d+)?)/i,
    /(\d[\d,]*(?:\.\d+)?)\s*ms\s*per\s*invocation/i,
    /(\d[\d,]*(?:\.\d+)?)\s*ms\s*\/\s*invocation/i,
    /(\d[\d,]*(?:\.\d+)?)\s*ms\/invocation/i,
  ]);
  const memoryMb = matchNumber(source, [
    /memory(?: used by function)?[^\d]*(\d[\d,]*(?:\.\d+)?)\s*mb/i,
    /(\d[\d,]*(?:\.\d+)?)\s*mb\b/i,
  ]) || matchNumber(source, [
    /memory(?: used by function)?[^\d]*(\d[\d,]*(?:\.\d+)?)/i,
  ]);
  const provisionedConcurrencyUnits = matchNumber(source, [
    /provisioned concurrency units?[^\d]*(\d[\d,]*(?:\.\d+)?)/i,
    /(\d[\d,]*(?:\.\d+)?)\s*provisioned concurrency/i,
    /provisioned concurrency[^\d]*(\d[\d,]*(?:\.\d+)?)/i,
  ]);

  const monthlyInvocations = invocationsPerMonth || (invocationsPerDay ? invocationsPerDay * daysPerMonth : null);
  if (!monthlyInvocations || !executionMs || !memoryMb) return null;

  const executionSeconds = executionMs / 1000;
  const memoryGb = memoryMb / 1024;
  const gbMemorySeconds = monthlyInvocations * executionSeconds * memoryGb;
  const executionQty = gbMemorySeconds / 10000;
  const invocationQty = monthlyInvocations / 1000000;

  return {
    monthlyInvocations,
    executionMs,
    memoryMb,
    provisionedConcurrencyUnits,
    executionQty,
    invocationQty,
  };
}

function resolveFunctionsComponents(index, request) {
  const inputs = parseFunctionsInputs(request.source);
  if (!inputs) return [];
  const execution = (index.productsByPartNumber.get('B90617') || [])[0];
  const invocations = (index.productsByPartNumber.get('B90618') || [])[0];
  const components = [];
  if (execution) {
    components.push({
      product: execution,
      quantity: inputs.executionQty,
      instances: 1,
      dependencyKind: 'functions-execution',
      metadata: inputs,
      warning: inputs.provisionedConcurrencyUnits ? 'Provisioned concurrency units were detected in the request, but no separate billable SKU was found in the OCI catalog or reference price lists used by this agent.' : null,
    });
  }
  if (invocations) {
    components.push({
      product: invocations,
      quantity: inputs.invocationQty,
      instances: 1,
      dependencyKind: 'functions-invocations',
      metadata: inputs,
    });
  }
  return components;
}

function resolveBatchComponents(index, request) {
  const direct = (index.productsByPartNumber.get('B112107') || [])[0];
  if (direct) {
    return [{ product: direct, quantity: Number(request.quantity || 1), instances: 1, dependencyKind: 'batch-each' }];
  }
  const fallback = index.products.find((item) =>
    item.partNumber === 'B112107' ||
    item.serviceCategoryDisplayName === 'OCI Batch' ||
    /\boci batch\b/i.test(item.fullDisplayName || item.displayName || '')
  );
  return fallback ? [{ product: fallback, quantity: Number(request.quantity || 1), instances: 1, dependencyKind: 'batch-each' }] : [];
}

function resolveDataSafeComponents(index, request) {
  const source = String(request.source || '').toLowerCase();
  const onPremises = /\bon-?prem(?:ises)?\b|\bdatabases? on compute\b|\btarget databases?\b/.test(source);
  const preferredPart = onPremises ? 'B92733' : 'B91632';
  const direct = (index.productsByPartNumber.get(preferredPart) || [])[0];
  if (direct) {
    return [{
      product: direct,
      quantity: Number(request.quantity || 1),
      instances: 1,
      dependencyKind: onPremises ? 'data-safe-target-databases' : 'data-safe-databases',
    }];
  }
  const fallback = index.products.find((item) => /data safe/i.test(item.fullDisplayName || item.displayName || ''));
  return fallback ? [{
    product: fallback,
    quantity: Number(request.quantity || 1),
    instances: 1,
    dependencyKind: onPremises ? 'data-safe-target-databases' : 'data-safe-databases',
  }] : [];
}

function resolveAiAgentsDataIngestionComponents(index, request) {
  const direct = (index.productsByPartNumber.get('B110463') || [])[0];
  const quantity = Number(request.requestCount || request.quantity || 1);
  const scaledQuantity = quantity > 0 ? quantity / 10000 : 0;
  if (direct && scaledQuantity > 0) {
    return [{
      product: direct,
      quantity: scaledQuantity,
      instances: 1,
      dependencyKind: 'ai-agents-data-ingestion-transactions',
    }];
  }
  const fallback = index.products.find((item) => /generative ai agents[^\n]*data ingestion/i.test(item.fullDisplayName || item.displayName || ''));
  return fallback && scaledQuantity > 0 ? [{
    product: fallback,
    quantity: scaledQuantity,
    instances: 1,
    dependencyKind: 'ai-agents-data-ingestion-transactions',
  }] : [];
}

function resolveAiMemoryIngestionComponents(index, request) {
  const direct = (index.productsByPartNumber.get('B112383') || [])[0];
  if (direct) {
    return [{
      product: direct,
      quantity: Number(request.requestCount || request.quantity || 1),
      instances: 1,
      dependencyKind: 'ai-memory-ingestion-events',
    }];
  }
  const fallback = index.products.find((item) => /memory ingestion/i.test(item.fullDisplayName || item.displayName || ''));
  return fallback ? [{
    product: fallback,
    quantity: Number(request.requestCount || request.quantity || 1),
    instances: 1,
    dependencyKind: 'ai-memory-ingestion-events',
  }] : [];
}

function parseBlockVolumeVpus(text) {
  const source = String(text || '');
  const direct = source.match(/(\d+(?:\.\d+)?)\s*vpu'?s?\b/i);
  if (direct) return Number(direct[1]);
  const density = source.match(/(\d+(?:\.\d+)?)\s*vpu'?s?\s*(?:\/|per)\s*gb/i);
  return density ? Number(density[1]) : null;
}

function resolveBlockVolumeComponents(index, request) {
  const quantityGb = parseLabeledCapacity(request.source, /(block volumes?|block storage)/i) || Number(request.capacityGb || 0);
  if (!quantityGb) return [];
  const storage = (index.productsByPartNumber.get('B91961') || [])[0];
  const performance = (index.productsByPartNumber.get('B91962') || [])[0];
  const vpus = parseBlockVolumeVpus(request.source) || 10;
  const components = [];
  if (storage) components.push({ product: storage, quantity: quantityGb, instances: 1, dependencyKind: 'block-storage' });
  if (performance) components.push({ product: performance, quantity: quantityGb * vpus, instances: 1, dependencyKind: 'block-performance' });
  return components;
}

function hasNumericValue(value) {
  return value !== null && value !== '' && value !== undefined && Number.isFinite(Number(value));
}

function matchNumber(source, patterns) {
  for (const pattern of patterns) {
    const match = source.match(pattern);
    if (match) return Number(String(match[1]).replace(/,/g, ''));
  }
  return null;
}

function dedupe(items) {
  return Array.from(new Set((items || []).filter(Boolean)));
}

function dedupeComponents(components) {
  const seen = new Set();
  const out = [];
  for (const item of components || []) {
    const key = `${item?.product?.partNumber}:${item?.quantity}:${item?.instances}:${item?.dependencyKind}`;
    if (!item?.product?.partNumber || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

module.exports = {
  resolveRequestDependencies,
};
