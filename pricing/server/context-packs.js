'use strict';

const { searchProducts, searchServiceRegistry } = require('./catalog');
const { getServiceFamily, getMissingRequiredInputs, inferServiceFamily } = require('./service-families');
const { VM_SHAPES, listFlexShapesByVendor, findVmShapeByText } = require('./vm-shapes');
const { computeVariantAudit = {} } = require('../data/rule-registry/coverage_matrix.json');

const UNCOVERED_COMPUTE_SERVICES = Array.isArray(computeVariantAudit.uncoveredServices)
  ? computeVariantAudit.uncoveredServices
  : [];
const COVERED_COMPUTE_SERVICES = Array.isArray(computeVariantAudit.coveredServices)
  ? computeVariantAudit.coveredServices
  : [];
const RESIDUAL_COMPUTE_SERVICES = [
  ...UNCOVERED_COMPUTE_SERVICES.map((service) => ({ ...service, auditState: 'uncovered' })),
  ...COVERED_COMPUTE_SERVICES.map((service) => ({ ...service, auditState: 'covered' })),
].filter((service, index, items) =>
  items.findIndex((candidate) => String(candidate.name || '').toLowerCase() === String(service.name || '').toLowerCase()) === index
);

function formatUsd(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return 'USD -';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: num < 1 ? 4 : 2,
  }).format(num);
}

function isCatalogListingText(text) {
  const source = String(text || '');
  if (!source) return false;
  if (/\blist all skus?\b/i.test(source)) return true;
  if (/\bwhat\b.*\boptions?\b.*\bcatalog\b/i.test(source)) return true;
  if (/\bavailable\b.*\bcatalog\b/i.test(source)) return true;
  if (/\bshow\b.*\bskus?\b/i.test(source)) return true;
  if (/\blist\b.*\b(hourly prices?|prices?)\b/i.test(source)) return true;
  return false;
}

function summarizeSessionContext(sessionContext) {
  if (!sessionContext || typeof sessionContext !== 'object') return null;
  const workbook = sessionContext.workbookContext && typeof sessionContext.workbookContext === 'object'
    ? sessionContext.workbookContext
    : null;
  const lastQuote = sessionContext.lastQuote && typeof sessionContext.lastQuote === 'object'
    ? sessionContext.lastQuote
    : null;
  return {
    currentIntent: sessionContext.currentIntent || '',
    sessionSummary: sessionContext.sessionSummary || '',
    workbook: workbook ? {
      fileName: workbook.fileName || '',
      sourcePlatform: workbook.sourcePlatform || '',
      processorVendor: workbook.processorVendor || '',
      shapeName: workbook.shapeName || '',
      vpuPerGb: Number.isFinite(Number(workbook.vpuPerGb)) ? Number(workbook.vpuPerGb) : null,
    } : null,
    lastQuote: lastQuote ? {
      label: lastQuote.label || '',
      serviceFamily: lastQuote.serviceFamily || '',
      shapeName: lastQuote.shapeName || '',
      monthly: Number.isFinite(Number(lastQuote.monthly)) ? Number(lastQuote.monthly) : null,
      currencyCode: lastQuote.currencyCode || 'USD',
      lineItemCount: Number.isFinite(Number(lastQuote.lineItemCount)) ? Number(lastQuote.lineItemCount) : null,
      partNumbers: Array.isArray(lastQuote.partNumbers) ? lastQuote.partNumbers.slice(0, 12) : [],
    } : null,
  };
}

function buildVmShapeContext() {
  const intelFixed = (VM_SHAPES || [])
    .filter((shape) => shape.kind === 'fixed' && String(shape.vendor || '').toLowerCase() === 'intel' && /^VM\./i.test(String(shape.shapeName || '')))
    .map((shape) => ({
      shapeName: shape.shapeName,
      kind: shape.kind,
      fixedOcpus: Number(shape.fixedOcpus),
      fixedMemoryGb: Number(shape.fixedMemoryGb),
    }));

  return {
    topic: 'vm_shapes',
    coreRules: {
      x86OcpuToVcpuRatio: '1 OCPU = 2 vCPUs',
      ampereOcpuToVcpuRatio: '1 OCPU = 1 vCPU',
      fixedVsFlex: 'Fixed shapes have predefined CPU and memory. Flex shapes accept user-defined OCPU and memory.',
    },
    families: {
      intel: {
        flex: listFlexShapesByVendor('intel').map((shape) => shape.shapeName),
        fixed: intelFixed,
      },
      amd: {
        flex: listFlexShapesByVendor('amd').map((shape) => shape.shapeName),
      },
      ampere: {
        flex: listFlexShapesByVendor('ampere').map((shape) => shape.shapeName),
      },
    },
  };
}

function toTitleCase(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function categorizeComputeVariant(service = {}) {
  const name = String(service.name || '');
  if (/cloud@customer/i.test(name)) return 'cloud_at_customer';
  if (/gpu/i.test(name)) return 'gpu';
  if (/\bhpc\b/i.test(name)) return 'hpc';
  if (/windows os/i.test(name)) return 'guest_os';
  if (/microsoft sql/i.test(name)) return 'marketplace_os';
  if (/dense i\/o/i.test(name)) return 'denseio_legacy';
  if (/e2 micro/i.test(name)) return 'free_tier';
  if (/\bstandard - e2\b/i.test(name)) return 'legacy_fixed';
  if (/virtual machine standard/i.test(name) || /bare metal standard/i.test(name)) return 'legacy_fixed';
  return 'other';
}

function normalizeComputeVariantLabel(name) {
  return String(name || '')
    .replace(/^Oracle (Cloud Infrastructure|Big Data Service|Compute Cloud@Customer)\s*-\s*Compute\s*-\s*/i, '')
    .replace(/\s+-\s+Metered$/i, ' (Metered)')
    .trim();
}

function buildComputeVariantAliases(service = {}) {
  const name = String(service.name || '');
  const aliases = [];
  if (/virtual machine standard - x5/i.test(name)) aliases.push('VM.Standard1');
  if (/virtual machine standard - x7/i.test(name)) aliases.push('VM.Standard2');
  if (/virtual machine dense i\/o - x5/i.test(name)) aliases.push('VM.DenseIO1');
  if (/virtual machine dense i\/o - x7/i.test(name)) aliases.push('VM.DenseIO2');
  if (/virtual machine standard - e2 micro - free/i.test(name) || /\be2 micro\b/i.test(name)) {
    aliases.push('VM.Standard.E2.1.Micro', 'E2 Micro');
  } else if (/\bstandard - e2\b/i.test(name)) {
    aliases.push('VM.Standard.E2');
  }
  if (/virtual machine standard - b1/i.test(name) || /bare metal standard - b1/i.test(name)) aliases.push('VM.Standard.B1', 'Standard.B1');
  if (/gpu - a10/i.test(name)) aliases.push('GPU.A10', 'BM.GPU.A10');
  if (/gpu - a100/i.test(name)) aliases.push('GPU.A100');
  if (/gpu - b200/i.test(name)) aliases.push('GPU.B200');
  if (/gpu - gb200/i.test(name)) aliases.push('GPU.GB200');
  if (/gpu - h100/i.test(name)) aliases.push('GPU.H100');
  if (/gpu - h200/i.test(name)) aliases.push('GPU.H200');
  if (/gpu - l40s/i.test(name) || /gpu\.l40s/i.test(name)) aliases.push('GPU.L40S');
  if (/gpu - mi300x/i.test(name)) aliases.push('GPU.MI300X');
  if (/gpu standard - v2/i.test(name)) aliases.push('GPU.V100', 'VM.GPU3', 'BM.GPU3');
  if (/\bhpc - x7\b/i.test(name)) aliases.push('HPC.X7');
  if (/\bhpc - e5\b/i.test(name)) aliases.push('HPC.E5');
  if (/microsoft sql enterprise/i.test(name)) aliases.push('Microsoft SQL Enterprise', 'SQL Enterprise');
  if (/microsoft sql standard/i.test(name)) aliases.push('Microsoft SQL Standard', 'SQL Standard');
  if (/cloud@customer/i.test(name)) aliases.push('Compute Cloud@Customer', 'Cloud@Customer');
  return aliases;
}

function buildComputeAlternatives(category) {
  switch (category) {
    case 'gpu':
      return [
        'VM.Standard3.Flex',
        'VM.Standard.E4.Flex',
        'VM.Standard.E5.Flex',
        'BM.Standard2.52',
      ];
    case 'hpc':
      return [
        'BM.Standard2.52',
        'VM.Standard.E4.Flex',
        'VM.Standard.E5.Flex',
      ];
    case 'guest_os':
    case 'marketplace_os':
      return [
        'Quote the underlying OCI compute shape separately',
        'Quote Block Volume separately',
        'Handle guest OS or marketplace licensing as a separate line item',
      ];
    case 'cloud_at_customer':
      return [
        'OCI Dedicated Region or standard OCI public-region compute pricing',
        'VM.Standard.E5.Flex',
        'BM.Standard2.52',
      ];
    case 'free_tier':
      return [
        'Always Free E2 Micro discovery guidance',
        'VM.Standard.A1.Flex',
        'VM.Standard3.Flex',
      ];
    case 'denseio_legacy':
      return [
        'VM.DenseIO.E4.Flex',
        'VM.DenseIO.E5.Flex',
        'BM.DenseIO2.52',
      ];
    case 'legacy_fixed':
      return [
        'VM.Standard3.Flex',
        'VM.Standard.E4.Flex',
        'BM.Standard2.52',
      ];
    default:
      return [
        'VM.Standard3.Flex',
        'VM.Standard.E4.Flex',
        'VM.Standard.A1.Flex',
      ];
  }
}

function detectComputeCommercialModel(variant = {}, requestedText = '') {
  const source = [
    String(variant.name || ''),
    String(variant.label || ''),
    String(requestedText || ''),
  ].join('\n');
  if (/resource commit/i.test(source)) return 'resource_commit';
  if (/\bmetered\b/i.test(source)) return 'metered';
  if (/free/i.test(String(variant.label || variant.name || ''))) return 'free';
  return 'standard';
}

function buildComputeGuidance(category, variant = {}, requestedText = '') {
  const label = String(variant.label || variant.name || '').trim();
  const commercialModel = detectComputeCommercialModel(variant, requestedText);
  switch (category) {
    case 'gpu':
      return {
        coverageState: 'unsupported_safe_block',
        reason: 'gpu_shape_metadata_incomplete',
        categoryNote: commercialModel === 'resource_commit'
          ? 'GPU Cloud@Customer or resource-commit pricing paths need more shape-level and commercial-model metadata than the current deterministic model exposes.'
          : commercialModel === 'metered'
            ? 'Metered GPU pricing paths need more shape-level metadata than the current deterministic model exposes.'
            : 'GPU pricing paths need more shape-level metadata than the current deterministic model exposes.',
        nextStep: 'I can still help with available VM and bare metal CPU shapes, but GPU deterministic quoting is not enabled yet.',
        commercialModel,
      };
    case 'hpc':
      return {
        coverageState: 'unsupported_safe_block',
        reason: 'hpc_shape_metadata_incomplete',
        categoryNote: commercialModel === 'metered'
          ? 'Metered HPC pricing paths need additional shape, node, and capacity metadata before they can be quoted safely.'
          : 'HPC pricing paths need additional shape and capacity metadata before they can be quoted safely.',
        nextStep: 'I can still guide shape options and supported standard compute alternatives, but I should not price this HPC family yet.',
        commercialModel,
      };
    case 'guest_os':
      return {
        coverageState: 'unsupported_safe_block',
        reason: 'guest_os_pricing_separate',
        requiresSeparateLicensing: true,
        categoryNote: commercialModel === 'metered'
          ? 'Metered guest OS licensing lines need explicit modeling before I can quote them safely.'
          : 'Guest OS licensing lines need explicit modeling before I can quote them safely.',
        nextStep: 'I can still quote the underlying OCI compute and storage path separately, but not the guest OS licensing line.',
        commercialModel,
      };
    case 'marketplace_os':
      return {
        coverageState: 'unsupported_safe_block',
        reason: 'marketplace_licensing_separate',
        requiresSeparateLicensing: true,
        categoryNote: commercialModel === 'metered'
          ? 'Metered marketplace licensing lines need explicit modeling before I can quote them safely.'
          : 'Marketplace licensing lines need explicit modeling before I can quote them safely.',
        nextStep: 'I can still quote the underlying OCI compute and storage path separately, but not the marketplace licensing line.',
        commercialModel,
      };
    case 'cloud_at_customer':
      return {
        coverageState: 'unsupported_safe_block',
        reason: 'cloud_at_customer_commercial_terms_incomplete',
        categoryNote: 'Cloud@Customer pricing paths include hardware deployment, resource commitments, and commercial terms that are not fully modeled in the current deterministic engine.',
        nextStep: 'I can still guide a comparable public-region compute path or a standard OCI baseline, but I should not quote this Cloud@Customer family as if it were standard public OCI compute.',
        commercialModel,
      };
    case 'free_tier':
      return {
        coverageState: 'unsupported_safe_block',
        reason: 'free_tier_discovery_only',
        categoryNote: 'Always Free and promotional zero-cost compute paths are handled as discovery guidance, not as deterministic PAYG quote lines.',
        nextStep: 'I can still help identify a free-tier-friendly baseline or quote an equivalent paid OCI VM shape when you need a deterministic pricing result.',
        commercialModel,
      };
    case 'denseio_legacy':
      return {
        coverageState: 'unsupported_safe_block',
        reason: 'legacy_denseio_needs_nvme_mapping',
        categoryNote: commercialModel === 'metered'
          ? 'Legacy metered Dense I/O X5/X7 families need explicit NVMe, local-storage, and commercial-model mapping before they can be quoted safely.'
          : 'Legacy Dense I/O X5/X7 families need explicit NVMe and local-storage mapping before they can be quoted safely.',
        nextStep: 'I can still guide modern DenseIO Flex alternatives with local NVMe behavior, but I should not quote this legacy Dense I/O family directly.',
        commercialModel,
      };
    case 'legacy_fixed':
      return {
        coverageState: 'unsupported_safe_block',
        reason: 'legacy_fixed_needs_modern_mapping',
        categoryNote: commercialModel === 'metered'
          ? 'Legacy metered X5/X7 families need explicit mapping to modern Flex or bare metal families before they can be quoted safely.'
          : 'Legacy fixed X5/X7 families need explicit mapping to modern Flex or bare metal families before they can be quoted safely.',
        nextStep: `I can still guide the closest modern OCI shapes for ${label || 'this family'}, but I should not price the legacy fixed shape directly.`,
        commercialModel,
      };
    default:
      return {
        coverageState: 'unsupported_safe_block',
        reason: 'compute_family_metadata_incomplete',
        categoryNote: 'This compute family still needs more explicit pricing metadata before I can quote it safely.',
        nextStep: 'I can still help identify supported OCI compute families or answer discovery questions about available options.',
        commercialModel,
      };
  }
}

function buildComputeCoverageContext(userText = '') {
  const source = String(userText || '').trim();
  const normalized = source.toLowerCase();
  const prefersMicro = /\bmicro\b/i.test(source);
  const prefersCloudAtCustomer = /cloud@customer/i.test(source);
  const prefersMetered = /\bmetered\b/i.test(source);
  const prefersResourceCommit = /resource commit/i.test(source);
  const residual = RESIDUAL_COMPUTE_SERVICES.map((service) => ({
    name: service.name,
    label: normalizeComputeVariantLabel(service.name),
    category: categorizeComputeVariant(service),
    aliases: buildComputeVariantAliases(service),
    metrics: Array.isArray(service.metrics) ? service.metrics.slice(0, 4) : [],
    partNumbers: Array.isArray(service.partNumbers) ? service.partNumbers.slice(0, 4) : [],
    auditState: service.auditState || 'covered',
    matchedDeterministicCoverage: service.matchedDeterministicCoverage !== false,
    coverageMode: service.coverageMode || '',
  }));
  const byCategory = new Map();
  for (const item of residual) {
    if (!byCategory.has(item.category)) byCategory.set(item.category, []);
    byCategory.get(item.category).push(item);
  }
  const categorySummary = Array.from(byCategory.entries())
    .map(([category, items]) => ({
      category,
      label: toTitleCase(category.replace(/_/g, ' ')),
      count: items.length,
      examples: items.slice(0, 6).map((item) => item.label),
    }))
    .sort((a, b) => b.count - a.count);

  const matched = residual
    .map((item) => {
      const tokens = [
        ...((Array.isArray(item.aliases) ? item.aliases : []).map((value) => ({ value, weight: 3000 }))),
        ...item.partNumbers.map((value) => ({ value, weight: 2000 })),
        { value: item.label, weight: 1000 },
        { value: item.name, weight: 500 },
      ].filter((entry) => entry.value);
      const score = tokens.reduce((best, entry) => {
        const token = String(entry.value).toLowerCase();
        if (!token || !normalized.includes(token)) return best;
        return Math.max(best, entry.weight + token.length);
      }, 0);
      const itemCommercialModel = detectComputeCommercialModel(item);
      const contextualBias =
        (item.category === 'free_tier' && prefersMicro ? 5000 : 0) +
        (item.category === 'cloud_at_customer' && prefersCloudAtCustomer ? 5000 : 0) +
        (prefersMetered && itemCommercialModel === 'metered' ? 4000 : 0) +
        (prefersResourceCommit && itemCommercialModel === 'resource_commit' ? 4000 : 0);
      return score > 0 ? { item, score: score + contextualBias } : null;
    })
    .filter(Boolean)
    .sort((a, b) => b.score - a.score)[0]?.item || null;

  return {
    coveredShapeCount: Array.isArray(VM_SHAPES) ? VM_SHAPES.length : 0,
    uncoveredVariantCount: residual.length,
    uncoveredCategories: categorySummary,
    matchedUncoveredVariant: matched ? {
      ...matched,
      suggestedAlternatives: buildComputeAlternatives(matched.category),
      guidance: buildComputeGuidance(matched.category, matched, userText),
    } : null,
  };
}

function findUncoveredComputeVariant(text = '') {
  return buildComputeCoverageContext(text).matchedUncoveredVariant || null;
}

function buildUncoveredComputeReply(userText = '') {
  const variant = findUncoveredComputeVariant(userText);
  if (!variant) return '';
  const requested = String(userText || '').trim();
  const label = String(variant.label || variant.name || 'that OCI compute family').trim();
  const category = String(variant.category || '').trim();
  const alternatives = Array.isArray(variant.suggestedAlternatives) ? variant.suggestedAlternatives.filter(Boolean) : [];
  const guidance = buildComputeGuidance(category, variant, userText);
  const categoryNote = guidance.categoryNote;
  const nextStep = guidance.nextStep;
  return [
    `This OCI pricing service is not available yet for \`${label}\`.`,
    requested ? `I recognized the request \`${requested}\`, but I cannot quote that compute family safely with the current deterministic model.` : 'I recognized the compute family, but I cannot quote it safely with the current deterministic model.',
    categoryNote,
    nextStep,
    alternatives.length ? `Supported alternatives right now: ${alternatives.join(', ')}.` : '',
  ].join('\n\n');
}

function canSafelyQuoteUncoveredComputeVariant(variant, userText = '') {
  const category = String(variant?.category || '').trim();
  const source = String(userText || '');
  switch (category) {
    case 'gpu':
      return /(\d[\d,]*(?:\.\d+)?)\s*gpus?\b/i.test(source);
    case 'hpc':
      return /(\d[\d,]*(?:\.\d+)?)\s*ocpus?\b/i.test(source);
    case 'cloud_at_customer':
      return /(\d[\d,]*(?:\.\d+)?)\s*gpus?\b/i.test(source);
    case 'free_tier':
    case 'guest_os':
    case 'marketplace_os':
    case 'denseio_legacy':
    case 'legacy_fixed':
      return /(\d[\d,]*(?:\.\d+)?)\s*ocpus?\b/i.test(source);
    default:
      return false;
  }
}

function firstUsdTier(product) {
  const tiers = product?.tiersByCurrency?.USD;
  return Array.isArray(tiers) && tiers.length ? tiers[0] : null;
}

function formatProductCatalogLine(product) {
  const tier = firstUsdTier(product);
  const metric = product.metricDisplayName || product.metricUnitDisplayName || '-';
  const unit = tier ? formatUsd(tier.value) : 'USD -';
  return `- \`${product.partNumber}\` | ${product.displayName} | ${metric} | ${unit}`;
}

function findCatalogProducts(index, text, intent) {
  const source = String(text || '');
  const family = String(intent?.serviceFamily || '');
  if (/\bfast\s*connect\b|\bfastconnect\b/i.test(source) || family === 'network_fastconnect') {
    return index.products
      .filter((product) => /fastconnect/i.test(`${product.displayName} ${product.serviceCategoryDisplayName}`))
      .filter((product) => ['HOUR', 'HOUR_UTILIZED'].includes(product.priceType))
      .sort((a, b) => String(a.displayName || '').localeCompare(String(b.displayName || '')));
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
  if (!(intent?.quotePlan?.targetType === 'catalog' || isCatalogListingText(text))) return '';
  const products = findCatalogProducts(index, text, intent);
  const unique = [];
  const seen = new Set();
  for (const product of products) {
    if (!product?.partNumber || seen.has(product.partNumber)) continue;
    seen.add(product.partNumber);
    unique.push(product);
  }
  if (!unique.length) return '';
  const lines = unique.slice(0, 20).map(formatProductCatalogLine);
  return [
    'I checked the OCI pricing catalog already loaded by the agent.',
    'This listing is based on the current global catalog data packaged in the app, so no region input is required for this catalog lookup.',
    '### Catalog matches',
    ...lines,
  ].join('\n\n');
}

function buildPricingDimensions(products) {
  return (Array.isArray(products) ? products : [])
    .slice(0, 8)
    .map((product) => {
      const tier = firstUsdTier(product);
      return {
        partNumber: product.partNumber,
        serviceCategory: product.serviceCategoryDisplayName || '',
        displayName: product.displayName || '',
        metric: product.metricDisplayName || '',
        priceType: product.priceType || '',
        usdRate: Number.isFinite(Number(tier?.value)) ? Number(tier.value) : null,
      };
    });
}

function labelInputKey(key) {
  const source = String(key || '').trim();
  if (!source) return '';
  const labels = {
    capacityGb: 'storage capacity (GB)',
    vpuPerGb: 'block volume performance level (VPU per GB)',
    bandwidthGbps: 'bandwidth (Gbps)',
    firewallInstances: 'firewall instances',
    dataProcessedGb: 'data processed per month (GB)',
    wafInstances: 'WAF instances or policies',
    requestCount: 'monthly requests or transactions',
    quantity: 'resource count',
    serviceHours: 'service hours',
    ecpus: 'ECPUs',
    ocpus: 'OCPUs',
    databaseEdition: 'database edition',
    databaseStorageModel: 'database storage model',
    exadataInfraShape: 'Exadata infrastructure shape',
    exadataInfraGeneration: 'Exadata generation',
    users: 'named users',
    instances: 'instance count',
    workspaceCount: 'workspace count',
    dataProcessedGb: 'data processed per hour (GB)',
    executionHours: 'execution hours per month',
    executionMs: 'execution time per invocation (ms)',
    memoryMb: 'memory (MB)',
    invocationsPerMonth: 'monthly invocations',
    invocationsPerDay: 'daily invocations',
    daysPerMonth: 'days per month',
    processorVendor: 'processor family',
    shapeSeries: 'shape family',
    shapeName: 'shape name',
  };
  return labels[source] || source.replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase();
}

function summarizeRequiredInputs(family) {
  if (!family) return [];
  const ordered = [
    ...(Array.isArray(family.clarifyRequired) ? family.clarifyRequired : []),
    ...(Array.isArray(family.clarifyAnyInputs) ? family.clarifyAnyInputs : []),
    ...(Array.isArray(family.rescueInputs) ? family.rescueInputs : []),
    ...(Array.isArray(family.rescueAnyInputs) ? family.rescueAnyInputs : []),
    ...(Array.isArray(family.licenseNotRequiredWhenAnyInputs) ? family.licenseNotRequiredWhenAnyInputs : []),
  ];
  return Array.from(new Set(ordered.filter(Boolean))).map((key) => ({
    key,
    label: labelInputKey(key),
  }));
}

function inferLicenseModes(family) {
  if (!family?.requireLicenseChoice) return [];
  const modes = ['BYOL', 'License Included'];
  if (Array.isArray(family.licenseNotRequiredWhenAnyInputs) && family.licenseNotRequiredWhenAnyInputs.length) {
    modes.push('No explicit license choice required for some pricing paths');
  }
  return modes;
}

function inferGuidanceFromClarificationQuestion(family) {
  const source = String(family?.clarificationQuestion || '');
  if (!source) return [];
  const inferred = [];
  if (/\binstances?\b/i.test(source)) inferred.push('instances');
  if (/\busers?\b|\bnamed users?\b/i.test(source)) inferred.push('users');
  if (/\bocpus?\b/i.test(source)) inferred.push('ocpus');
  if (/\becpus?\b/i.test(source)) inferred.push('ecpus');
  if (/\bstorage\b|\bgb\b/i.test(source)) inferred.push('capacityGb');
  if (/\bbandwidth\b|\bgbps\b/i.test(source)) inferred.push('bandwidthGbps');
  if (/\brequests?\b|\btransactions?\b|\bqueries?\b/i.test(source)) inferred.push('requestCount');
  if (/\bshape\b/i.test(source)) inferred.push('shapeSeries');
  return inferred;
}

function extractKeywordOptions(source, patterns) {
  const text = String(source || '');
  const found = [];
  for (const pattern of patterns) {
    const matcher = pattern.global ? text.matchAll(pattern) : [text.match(pattern)];
    for (const match of matcher) {
      if (!match) continue;
      const value = String(match[1] || match[0] || '').trim();
      if (value) found.push(value);
    }
  }
  return Array.from(new Set(found));
}

function inferFamilyOptions(family, products = []) {
  if (!family) return null;
  const productText = (Array.isArray(products) ? products : [])
    .map((product) => `${product.displayName || ''} ${product.serviceCategoryDisplayName || ''}`)
    .join('\n');
  const clarificationText = String(family.clarificationQuestion || '');
  const source = `${productText}\n${clarificationText}`;

  const editions = extractKeywordOptions(source, [
    /\b(extreme performance)\b/ig,
    /\b(high performance)\b/ig,
    /\b(enterprise)\b(?: edition)?/ig,
    /\b(standard)\b(?: edition)?/ig,
    /\b(developer)\b/ig,
    /\b(professional)\b/ig,
  ]).map((value) => value.replace(/\b\w/g, (char) => char.toUpperCase()));

  const storageModels = extractKeywordOptions(source, [
    /\b(smart database storage)\b/ig,
    /\b(filesystem storage)\b/ig,
    /\b(vm filesystem storage)\b/ig,
  ]).map((value) => value.replace(/\b\w/g, (char) => char.toUpperCase()));

  const infrastructureShapes = extractKeywordOptions(source, [
    /\b(base system)\b/ig,
    /\b(quarter rack)\b/ig,
    /\b(half rack)\b/ig,
    /\b(full rack)\b/ig,
    /\b(database server)\b/ig,
    /\b(storage server)\b/ig,
    /\b(expansion rack)\b/ig,
  ]).map((value) => value.replace(/\b\w/g, (char) => char.toUpperCase()));

  const infrastructureGenerations = extractKeywordOptions(source, [
    /\b(x11m)\b/ig,
    /\b(x10m)\b/ig,
    /\b(x9m)\b/ig,
    /\b(x8m)\b/ig,
    /\b(x8)\b/ig,
    /\b(x7)\b/ig,
  ]).map((value) => value.toUpperCase());

  const measurementModes = [];
  const guidance = [
    ...(Array.isArray(family.clarifyRequired) ? family.clarifyRequired : []),
    ...(Array.isArray(family.clarifyAnyInputs) ? family.clarifyAnyInputs : []),
    ...inferGuidanceFromClarificationQuestion(family),
  ];
  const uniqueGuidance = Array.from(new Set(guidance.filter(Boolean)));
  for (const key of uniqueGuidance) {
    measurementModes.push(labelInputKey(key));
  }

  const variants = [];
  if (editions.length) variants.push(...editions.map((value) => `${value} edition`));
  if (Array.isArray(family.licenseNotRequiredWhenAnyInputs) && family.licenseNotRequiredWhenAnyInputs.length) {
    variants.push(...family.licenseNotRequiredWhenAnyInputs.map((key) => `${labelInputKey(key)} pricing path`));
  }
  if (storageModels.length) variants.push(...storageModels);
  if (infrastructureShapes.length) variants.push(...infrastructureShapes);
  if (infrastructureGenerations.length) variants.push(...infrastructureGenerations);

  const result = {
    variants: Array.from(new Set([
      ...(Array.isArray(family.options?.variants) ? family.options.variants : []),
      ...variants,
    ])).slice(0, 12),
    measurementModes: Array.from(new Set([
      ...(Array.isArray(family.options?.measurementModes) ? family.options.measurementModes : []),
      ...measurementModes,
    ])).slice(0, 12),
    editions: Array.from(new Set([
      ...(Array.isArray(family.options?.editions) ? family.options.editions : []),
      ...editions,
    ])).slice(0, 12),
    storageModels: Array.from(new Set([
      ...(Array.isArray(family.options?.storageModels) ? family.options.storageModels : []),
      ...storageModels,
    ])).slice(0, 12),
    infrastructureShapes: Array.from(new Set([
      ...(Array.isArray(family.options?.infrastructureShapes) ? family.options.infrastructureShapes : []),
      ...infrastructureShapes,
    ])).slice(0, 12),
    infrastructureGenerations: Array.from(new Set([
      ...(Array.isArray(family.options?.infrastructureGenerations) ? family.options.infrastructureGenerations : []),
      ...infrastructureGenerations,
    ])).slice(0, 12),
  };
  return Object.values(result).some((items) => Array.isArray(items) && items.length) ? result : null;
}

function extractVmShapeMentions(text) {
  const source = String(text || '');
  if (!source) return [];
  const mentions = [];
  const normalizedSource = source.toUpperCase();
  for (const shape of VM_SHAPES || []) {
    const candidates = Array.isArray(shape.aliases) && shape.aliases.length
      ? shape.aliases
      : [shape.shapeName];
    const matched = candidates.some((candidate) => {
      const raw = String(candidate || '').toUpperCase();
      return raw && normalizedSource.includes(raw);
    });
    if (matched) {
      mentions.push(String(shape.shapeName || '').toUpperCase());
    }
  }
  const shorthand = findVmShapeByText(source);
  if (shorthand?.shapeName) mentions.push(String(shorthand.shapeName).toUpperCase());
  return Array.from(new Set(mentions)).slice(0, 6);
}

function pickRelevantServices(index, userText, intent) {
  const inferredFamilyId = intent?.serviceFamily || inferServiceFamily(userText || '', '');
  const family = getServiceFamily(inferredFamilyId || '');
  const searchQueries = Array.from(new Set([
    String(userText || '').trim(),
    String(intent?.serviceName || '').trim(),
    String(intent?.normalizedRequest || '').trim(),
    String(family?.canonical || '').trim(),
  ].filter(Boolean)));
  const registryMatches = searchQueries
    .flatMap((query) => searchServiceRegistry(index.serviceRegistry, query, 5))
    .filter((service, index, items) =>
      items.findIndex((candidate) => String(candidate.id || candidate.name || '').toLowerCase() === String(service.id || service.name || '').toLowerCase()) === index
    )
    .slice(0, 5);
  const topService = registryMatches[0];
  const derivedFamily = !family && topService ? {
    id: topService.id || '',
    canonical: topService.name || '',
    domain: topService.domain || '',
    resolver: '',
    aliases: [],
    clarifyRequired: topService.requiredInputs || [],
    clarifyAnyInputs: [],
    clarificationQuestion: '',
    requireLicenseChoice: false,
    licenseNotRequiredWhenAnyInputs: [],
    licenseClarificationQuestion: '',
    missingInputs: [],
    requiredInputGuidance: summarizeRequiredInputs({
      clarifyRequired: topService.requiredInputs || [],
      clarifyAnyInputs: [],
      rescueInputs: [],
      rescueAnyInputs: [],
      licenseNotRequiredWhenAnyInputs: [],
    }),
    licenseModes: [],
    options: null,
  } : null;
  const effectiveFamily = family || derivedFamily;
  const familyProducts = Array.isArray(family?.partNumbers)
    ? family.partNumbers.flatMap((partNumber) => index.productsByPartNumber.get(partNumber) || [])
    : [];
  const discoveredProducts = searchQueries
    .flatMap((query) => searchProducts(index, query, 8))
    .filter((product, index, items) =>
      items.findIndex((candidate) => String(candidate.partNumber || candidate.displayName || '').toLowerCase() === String(product.partNumber || product.displayName || '').toLowerCase()) === index
    )
    .slice(0, 8);
  const products = familyProducts.length
    ? Array.from(new Map([...familyProducts, ...discoveredProducts].map((product) => [String(product.partNumber || product.displayName || ''), product])).values())
    : discoveredProducts;
  const missingInputs = effectiveFamily ? getMissingRequiredInputs(intent) : [];
  const requiredInputGuidance = effectiveFamily ? summarizeRequiredInputs(effectiveFamily) : [];
  const enrichedRequiredInputGuidance = requiredInputGuidance.length
    ? requiredInputGuidance
    : inferGuidanceFromClarificationQuestion(effectiveFamily).map((key) => ({
      key,
      label: labelInputKey(key),
    }));
  const familyOptions = family ? inferFamilyOptions(family, products) : null;
  return {
    registryMatches: registryMatches.map((service) => ({
      name: service.name,
      domain: service.domain,
      coverageLevel: service.coverageLevel,
      requiredInputs: service.requiredInputs || [],
      patterns: service.patterns || [],
      partNumbers: (service.partNumbers || []).slice(0, 8),
    })),
    products: products.map((product) => ({
      partNumber: product.partNumber,
      displayName: product.displayName,
      serviceCategoryDisplayName: product.serviceCategoryDisplayName,
      metricDisplayName: product.metricDisplayName,
      priceType: product.priceType,
    })),
    pricingDimensions: buildPricingDimensions(products),
    family: effectiveFamily ? {
      id: effectiveFamily.id,
      canonical: effectiveFamily.canonical,
      domain: effectiveFamily.domain,
      resolver: effectiveFamily.resolver || '',
      aliases: Array.isArray(effectiveFamily.aliases) ? effectiveFamily.aliases.map((pattern) => String(pattern)).slice(0, 8) : [],
      clarifyRequired: effectiveFamily.clarifyRequired || effectiveFamily.rescueInputs || [],
      clarifyAnyInputs: effectiveFamily.clarifyAnyInputs || effectiveFamily.rescueAnyInputs || [],
      clarificationQuestion: effectiveFamily.clarificationQuestion || '',
      requireLicenseChoice: !!effectiveFamily.requireLicenseChoice,
      licenseNotRequiredWhenAnyInputs: effectiveFamily.licenseNotRequiredWhenAnyInputs || [],
      licenseClarificationQuestion: effectiveFamily.licenseClarificationQuestion || '',
      missingInputs,
      requiredInputGuidance: enrichedRequiredInputGuidance,
      licenseModes: inferLicenseModes(effectiveFamily),
      options: familyOptions,
    } : null,
  };
}

function inferPackTopic(userText, intent) {
  const source = String(userText || '').toLowerCase();
  if (/\bshape?s?\b|\bvirtual machines?\b|\bvm instances?\b|\bcompute\b|\bvm\.[a-z0-9.]+\b|\bbm\.[a-z0-9.]+\b|\bgpu\b|\bhpc\b|\bdenseio\b|\bwindows os\b/.test(source)) return 'vm_shapes';
  if (extractVmShapeMentions(userText).length) return 'vm_shapes';
  if (intent?.serviceFamily) return intent.serviceFamily;
  return 'general_pricing';
}

function buildAssistantContextPack(index, { userText, intent, sessionContext }) {
  const pack = {
    route: intent?.route || '',
    topic: inferPackTopic(userText, intent),
    userQuestion: String(userText || '').trim(),
    quotePlan: intent?.quotePlan || null,
    extractedInputs: intent?.extractedInputs || {},
    session: summarizeSessionContext(sessionContext),
    serviceContext: pickRelevantServices(index, userText, intent),
  };
  if (pack.topic === 'vm_shapes' || pack.serviceContext.family?.domain === 'compute') {
    pack.vmShapes = buildVmShapeContext();
    pack.computeCoverage = buildComputeCoverageContext(userText);
    const mentions = extractVmShapeMentions(userText);
    if (mentions.length >= 2) {
      pack.shapeComparison = mentions.map((shapeName) => {
        const shape = (VM_SHAPES || []).find((item) => String(item.shapeName || '').toUpperCase() === shapeName);
        return shape ? {
          shapeName,
          vendor: shape.vendor || '',
          kind: shape.kind || '',
          family: shape.family || '',
          series: shape.series || '',
          fixedOcpus: Number.isFinite(Number(shape.fixedOcpus)) ? Number(shape.fixedOcpus) : null,
          fixedMemoryGb: Number.isFinite(Number(shape.fixedMemoryGb)) ? Number(shape.fixedMemoryGb) : null,
          ocpuToVcpuRatio: Number.isFinite(Number(shape.ocpuToVcpuRatio)) ? Number(shape.ocpuToVcpuRatio) : null,
        } : { shapeName };
      });
    }
  }
  return pack;
}

function stringifyContextPack(pack) {
  return JSON.stringify(pack, null, 2);
}

function summarizeContextPack(pack) {
  if (!pack || typeof pack !== 'object') return null;
  return {
    topic: pack.topic || '',
    route: pack.route || '',
    quotePlan: pack.quotePlan ? {
      action: pack.quotePlan.action || '',
      targetType: pack.quotePlan.targetType || '',
      domain: pack.quotePlan.domain || '',
      candidateFamilies: Array.isArray(pack.quotePlan.candidateFamilies) ? pack.quotePlan.candidateFamilies.slice(0, 8) : [],
      missingInputs: Array.isArray(pack.quotePlan.missingInputs) ? pack.quotePlan.missingInputs.slice(0, 8) : [],
    } : null,
    family: pack.serviceContext?.family ? {
      id: pack.serviceContext.family.id,
      canonical: pack.serviceContext.family.canonical,
      domain: pack.serviceContext.family.domain,
      requiredInputGuidance: Array.isArray(pack.serviceContext.family.requiredInputGuidance)
        ? pack.serviceContext.family.requiredInputGuidance.slice(0, 8).map((item) => item.label || item.key || '')
        : [],
      licenseModes: Array.isArray(pack.serviceContext.family.licenseModes)
        ? pack.serviceContext.family.licenseModes.slice(0, 6)
        : [],
      options: pack.serviceContext.family.options || null,
    } : null,
    registryMatchNames: Array.isArray(pack.serviceContext?.registryMatches)
      ? pack.serviceContext.registryMatches.slice(0, 5).map((item) => item.name)
      : [],
    computeCoverage: pack.computeCoverage ? {
      coveredShapeCount: pack.computeCoverage.coveredShapeCount,
      uncoveredVariantCount: pack.computeCoverage.uncoveredVariantCount,
      uncoveredCategories: Array.isArray(pack.computeCoverage.uncoveredCategories)
        ? pack.computeCoverage.uncoveredCategories.slice(0, 6).map((item) => item.label)
        : [],
      matchedUncoveredVariant: pack.computeCoverage.matchedUncoveredVariant?.label || '',
      matchedUncoveredCategory: pack.computeCoverage.matchedUncoveredVariant?.category || '',
      matchedUncoveredReason: pack.computeCoverage.matchedUncoveredVariant?.guidance?.reason || '',
      matchedUncoveredCommercialModel: pack.computeCoverage.matchedUncoveredVariant?.guidance?.commercialModel || '',
      requiresSeparateLicensing: !!pack.computeCoverage.matchedUncoveredVariant?.guidance?.requiresSeparateLicensing,
      matchedUncoveredAlternatives: Array.isArray(pack.computeCoverage.matchedUncoveredVariant?.suggestedAlternatives)
        ? pack.computeCoverage.matchedUncoveredVariant.suggestedAlternatives.slice(0, 6)
        : [],
    } : null,
    shapeComparison: Array.isArray(pack.shapeComparison)
      ? pack.shapeComparison.slice(0, 6).map((item) => item.shapeName)
      : [],
  };
}

module.exports = {
  buildAssistantContextPack,
  buildCatalogListingReply,
  canSafelyQuoteUncoveredComputeVariant,
  buildUncoveredComputeReply,
  findUncoveredComputeVariant,
  stringifyContextPack,
  summarizeContextPack,
};
