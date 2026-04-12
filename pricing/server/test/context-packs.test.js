'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const { normalizeCatalog } = require(path.join(ROOT, 'catalog.js'));
const { buildAssistantContextPack, buildCatalogListingReply, buildStructuredDiscoveryFallback, buildUncoveredComputeReply, summarizeContextPack } = require(path.join(ROOT, 'context-packs.js'));

function metric(id, displayName, unitDisplayName = '') {
  return { id, displayName, unitDisplayName };
}

function payg(value) {
  return { model: 'PAY_AS_YOU_GO', value };
}

function product({ partNumber, displayName, serviceCategoryDisplayName, metricId, pricetype = 'HOUR', usdPrices = [payg(1)] }) {
  return {
    partNumber,
    displayName,
    serviceCategoryDisplayName,
    metricId,
    pricetype,
    currencyCodeLocalizations: [{ currencyCode: 'USD', prices: usdPrices }],
  };
}

function buildIndex() {
  return normalizeCatalog({
    'metrics.json': {
      items: [
        metric('m-msg-hour', '5K Messages Per Hour'),
        metric('m-users-month', 'Named User Per Month'),
        metric('m-ocpu-hour', 'OCPU Per Hour'),
        metric('m-capacity-month', 'Gigabyte Storage Capacity Per Month'),
        metric('m-gb-memory-sec', '10,000 GB Memory Seconds'),
        metric('m-invocations-million', '1,000,000 Invocations'),
      ],
    },
    'products.json': {
      items: [
        product({
          partNumber: 'B88326',
          displayName: 'OCI - FastConnect 10 Gbps',
          serviceCategoryDisplayName: 'Networking - FastConnect',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(1.275)],
        }),
        product({
          partNumber: 'B88525',
          displayName: 'Oracle Cloud Infrastructure DNS Traffic Management',
          serviceCategoryDisplayName: 'Networking - DNS',
          metricId: 'm-ocpu-hour',
          pricetype: 'MONTH',
          usdPrices: [payg(0.85)],
        }),
        product({
          partNumber: 'B90325',
          displayName: 'OCI - Health Checks - Premium',
          serviceCategoryDisplayName: 'Edge Services',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(1.3)],
        }),
        product({
          partNumber: 'B92072',
          displayName: 'Oracle Cloud Infrastructure API Gateway - 1,000,000 API Calls',
          serviceCategoryDisplayName: 'Application Development - API Management',
          metricId: 'm-ocpu-hour',
          pricetype: 'MONTH',
          usdPrices: [payg(3)],
        }),
        product({
          partNumber: 'B90925',
          displayName: 'Monitoring - Ingestion',
          serviceCategoryDisplayName: 'Observability - Monitoring',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(1.25)],
        }),
        product({
          partNumber: 'B90926',
          displayName: 'Monitoring - Retrieval',
          serviceCategoryDisplayName: 'Observability - Monitoring',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.75)],
        }),
        product({
          partNumber: 'B90940',
          displayName: 'Notifications - HTTPS Delivery',
          serviceCategoryDisplayName: 'Observability - Notifications',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(4)],
        }),
        product({
          partNumber: 'B90941',
          displayName: 'OCI Notifications - Email Delivery',
          serviceCategoryDisplayName: 'Notifications - Email Delivery',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.01992)],
        }),
        product({
          partNumber: 'B93004',
          displayName: 'OCI Notifications - SMS Outbound - Country Zone 1',
          serviceCategoryDisplayName: 'Notifications - SMS Delivery',
          metricId: 'm-each',
          pricetype: 'MONTH',
          usdPrices: [payg(0.015)],
        }),
        product({
          partNumber: 'B93496',
          displayName: 'OCI IAM SMS',
          serviceCategoryDisplayName: 'Identity and Access Management',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(1.667)],
        }),
        product({
          partNumber: 'B89639',
          displayName: 'Oracle Integration Cloud Service - Standard | 5K Messages Per Hour',
          serviceCategoryDisplayName: 'Application Integration - OIC',
          metricId: 'm-msg-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.6452)],
        }),
        product({
          partNumber: 'B92683',
          displayName: 'Oracle Analytics Cloud - Enterprise - Users',
          serviceCategoryDisplayName: 'Analytics - Analytics Cloud',
          metricId: 'm-users-month',
          pricetype: 'MONTH',
          usdPrices: [payg(80)],
        }),
        product({
          partNumber: 'B90570',
          displayName: 'Oracle Base Database Service - Enterprise',
          serviceCategoryDisplayName: 'Database - Base Database Service - Virtual Machine',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.4301)],
        }),
        product({
          partNumber: 'B111584',
          displayName: 'Oracle Base Database Service - Database Storage',
          serviceCategoryDisplayName: 'Database - Base Database Service - Virtual Machine',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0595)],
        }),
        product({
          partNumber: 'B88592',
          displayName: 'Exadata Dedicated Infrastructure Database - OCPU - License Included',
          serviceCategoryDisplayName: 'Exadata Dedicated Infrastructure Database',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(1.3441)],
        }),
        product({
          partNumber: 'B90617',
          displayName: 'Oracle Functions - Execution Time',
          serviceCategoryDisplayName: 'Application Development - Serverless',
          metricId: 'm-gb-memory-sec',
          pricetype: 'MONTH',
          usdPrices: [payg(0.1417)],
        }),
        product({
          partNumber: 'B90618',
          displayName: 'Oracle Functions - Invocations',
          serviceCategoryDisplayName: 'Application Development - Serverless',
          metricId: 'm-invocations-million',
          pricetype: 'MONTH',
          usdPrices: [payg(0.2)],
        }),
        product({
          partNumber: 'B92598',
          displayName: 'OCI Data Integration - Workspace Workspace',
          serviceCategoryDisplayName: 'Data Integration',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.16)],
        }),
        product({
          partNumber: 'B92599',
          displayName: 'OCI Data Integration - Data Processed',
          serviceCategoryDisplayName: 'Data Integration',
          metricId: 'm-capacity-month',
          pricetype: 'HOUR',
          usdPrices: [payg(0.04)],
        }),
        product({
          partNumber: 'B92733',
          displayName: 'Data Safe for On-Premises Databases & Databases on Compute',
          serviceCategoryDisplayName: 'Security - Data Safe',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(200)],
        }),
        product({
          partNumber: 'B112416',
          displayName: 'OCI Generative AI - Vector Store Retrieval',
          serviceCategoryDisplayName: 'OCI Generative AI - Search and Retrieval',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.5)],
        }),
        product({
          partNumber: 'B111973',
          displayName: 'OCI Generative AI - Web Search',
          serviceCategoryDisplayName: 'OCI Generative AI - Search and Retrieval',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(10)],
        }),
        product({
          partNumber: 'B94173',
          displayName: 'Oracle Threat Intelligence Service',
          serviceCategoryDisplayName: 'Security - Threat Intelligence',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.6)],
        }),
        product({
          partNumber: 'B108077',
          displayName: 'OCI Generative AI - Large Cohere',
          serviceCategoryDisplayName: 'OCI Generative AI - Large Cohere',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(1.5)],
        }),
        product({
          partNumber: 'B108078',
          displayName: 'OCI Generative AI - Small Cohere',
          serviceCategoryDisplayName: 'OCI Generative AI - Small Cohere',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0009)],
        }),
        product({
          partNumber: 'B108079',
          displayName: 'OCI Generative AI - Embed Cohere',
          serviceCategoryDisplayName: 'OCI Generative AI - Embed Cohere',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.001)],
        }),
        product({
          partNumber: 'B108080',
          displayName: 'OCI Generative AI - Large Meta',
          serviceCategoryDisplayName: 'OCI Generative AI - Large Meta',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0018)],
        }),
        product({
          partNumber: 'B110463',
          displayName: 'OCI Generative AI Agents - Data Ingestion',
          serviceCategoryDisplayName: 'OCI Generative AI Agents',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0003)],
        }),
        product({
          partNumber: 'B110462',
          displayName: 'OCI Generative AI Agents - Knowledge Base Storage',
          serviceCategoryDisplayName: 'OCI Generative AI Agents',
          metricId: 'm-storage-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.0084)],
        }),
        product({
          partNumber: 'B91477',
          displayName: 'OCI AI Language - Pre-trained Inferencing',
          serviceCategoryDisplayName: 'OCI AI Services',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0008)],
        }),
        product({
          partNumber: 'B94977',
          displayName: 'Vision - Custom Training',
          serviceCategoryDisplayName: 'Oracle Cloud Infrastructure - Vision - Custom Training',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(1.47)],
        }),
        product({
          partNumber: 'B94896',
          displayName: 'Speech',
          serviceCategoryDisplayName: 'Speech',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.016)],
        }),
        product({
          partNumber: 'B94973',
          displayName: 'Vision - Image Analysis',
          serviceCategoryDisplayName: 'Oracle Cloud Infrastructure - Vision',
          metricId: 'm-transactions-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(0.25)],
        }),
        product({
          partNumber: 'B94974',
          displayName: 'Vision - OCR',
          serviceCategoryDisplayName: 'Oracle Cloud Infrastructure - Vision',
          metricId: 'm-transactions-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(1)],
        }),
        product({
          partNumber: 'B95282',
          displayName: 'Media Services - Media Flow - Standard - H264 - HD - Below 30fps',
          serviceCategoryDisplayName: 'Media Services - Media Flow - Quality - H264 - HD - Below 30fps',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.006)],
        }),
        product({
          partNumber: 'B111539',
          displayName: 'OCI - Vision - Stream Video Analysis',
          serviceCategoryDisplayName: 'OCI - Vision - Stream Video Analysis',
          metricId: 'm-processed-video-minute',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(0.15)],
        }),
        product({
          partNumber: 'B110617',
          displayName: 'OCI - Vision - Stored Video Analysis',
          serviceCategoryDisplayName: 'OCI - Vision - Stored Video Analysis',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.003)],
        }),
        product({
          partNumber: 'B91627',
          displayName: 'Oracle Cloud Infrastructure - Object Storage Requests',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-events-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(0.0034)],
        }),
        product({
          partNumber: 'B91633',
          displayName: 'Archive Storage',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(0.0026)],
        }),
        product({
          partNumber: 'B93000',
          displayName: 'Infrequent Access Storage',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(0.01)],
        }),
        product({
          partNumber: 'B93001',
          displayName: 'Infrequent Access Retrieval',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(0.01)],
        }),
        product({
          partNumber: 'B110475',
          displayName: 'OCI Fleet Application Management Service',
          serviceCategoryDisplayName: 'Fleet Application Management',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(7)],
        }),
      ],
    },
    'productpresets.json': { items: [] },
  });
}

test('context pack exposes license modes and required inputs for Base Database discovery', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'What information do I need to quote Base Database Service?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'database_base_db',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'database' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'database_base_db');
  assert.deepEqual(pack.serviceContext.family.licenseModes, ['BYOL', 'License Included']);
  assert.ok(pack.serviceContext.family.requiredInputGuidance.some((item) => item.key === 'databaseEdition'));
  assert.ok(pack.serviceContext.family.requiredInputGuidance.some((item) => item.key === 'capacityGb'));
  assert.ok(pack.serviceContext.family.requiredInputGuidance.some((item) => item.key === 'ocpus'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B90570'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B111584'));
  assert.ok(pack.serviceContext.family.options.editions.includes('Enterprise'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('storage capacity (GB)'));
});

test('context pack exposes optional license guidance for OAC Enterprise user-based pricing', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is Oracle Analytics Cloud Enterprise billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'analytics_oac_enterprise',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'analytics' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'analytics_oac_enterprise');
  assert.ok(pack.serviceContext.family.licenseModes.includes('BYOL'));
  assert.ok(pack.serviceContext.family.licenseModes.includes('License Included'));
  assert.ok(pack.serviceContext.family.licenseModes.includes('No explicit license choice required for some pricing paths'));
  assert.ok(pack.serviceContext.family.requiredInputGuidance.some((item) => item.key === 'users'));
  assert.ok(pack.serviceContext.family.requiredInputGuidance.some((item) => item.key === 'ocpus'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('named users'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('OCPUs'));
});

test('context pack exposes OIC Standard instance guidance and pricing dimensions', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'What information do I need to quote Oracle Integration Cloud Standard?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'integration_oic_standard',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'integration' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'integration_oic_standard');
  assert.deepEqual(pack.serviceContext.family.licenseModes, ['BYOL', 'License Included']);
  assert.ok(pack.serviceContext.family.requiredInputGuidance.some((item) => item.key === 'instances'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B89639'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('instance count'));
});

test('context pack exposes Exadata Dedicated infrastructure options from family guidance', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'What options do we have for Exadata Dedicated Infrastructure?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'database_exadata_dedicated',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'database' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'database_exadata_dedicated');
  assert.deepEqual(pack.serviceContext.family.licenseModes, ['BYOL', 'License Included']);
  assert.ok(pack.serviceContext.family.options.infrastructureShapes.includes('Base System'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('OCPUs'));
});

test('context pack exposes OCI Functions measurement options from explicit family metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is OCI Functions billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'serverless_functions',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'serverless' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'serverless_functions');
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('monthly invocations'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('execution time per invocation (ms)'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('memory (MB)'));
  assert.ok(pack.serviceContext.family.options.variants.includes('provisioned concurrency'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B90617'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B90618'));
});

test('context pack exposes Data Integration variants and measurement options from explicit family metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'What information do I need to quote OCI Data Integration?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'integration_data',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'integration' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'integration_data');
  assert.ok(pack.serviceContext.family.options.variants.includes('workspace usage'));
  assert.ok(pack.serviceContext.family.options.variants.includes('data processed'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('workspace count'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('data processed per hour (GB)'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B92598'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B92599'));
});

test('context pack exposes Data Safe family variants from explicit family metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is Data Safe for On-Premises Databases billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'security_data_safe',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'security' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'security_data_safe');
  assert.ok(pack.serviceContext.family.options.variants.includes('On-Premises Databases'));
  assert.ok(pack.serviceContext.family.options.variants.includes('Database Cloud Service'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('target databases'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B92733'));
});

test('context pack exposes residual compute coverage context for GPU and HPC discovery', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'What GPU and HPC options do we have in OCI Compute?',
    intent: {
      route: 'product_discovery',
      serviceFamily: '',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'compute' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.topic, 'vm_shapes');
  assert.ok(pack.computeCoverage);
  assert.ok(pack.computeCoverage.uncoveredVariantCount > 0);
  assert.ok(pack.computeCoverage.uncoveredCategories.some((item) => item.category === 'gpu'));
  assert.ok(pack.computeCoverage.uncoveredCategories.some((item) => item.category === 'hpc'));
});

test('context pack exposes supported alternatives for matched uncovered GPU variants', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'Can you quote OCI Compute GPU - A10?',
    intent: {
      route: 'quote_request',
      serviceFamily: '',
      quotePlan: { action: 'quote', targetType: 'service', domain: 'compute' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.ok(pack.computeCoverage);
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.category, 'gpu');
  assert.ok(pack.computeCoverage.matchedUncoveredVariant?.suggestedAlternatives.includes('VM.Standard.E4.Flex'));
});

test('context pack matches legacy fixed VM aliases from uncovered compute variants', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'Can you quote VM.Standard1.4?',
    intent: {
      route: 'quote_request',
      serviceFamily: '',
      quotePlan: { action: 'quote', targetType: 'service', domain: 'compute' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.ok(pack.computeCoverage);
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.category, 'legacy_fixed');
  assert.ok(pack.computeCoverage.matchedUncoveredVariant?.aliases.includes('VM.Standard1'));
  assert.ok(pack.computeCoverage.matchedUncoveredVariant?.suggestedAlternatives.includes('VM.Standard3.Flex'));
});

test('context pack matches E2 micro aliases from uncovered compute variants', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'Can you quote VM.Standard.E2.1.Micro?',
    intent: {
      route: 'quote_request',
      serviceFamily: '',
      quotePlan: { action: 'quote', targetType: 'service', domain: 'compute' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.ok(pack.computeCoverage);
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.category, 'free_tier');
  assert.ok(pack.computeCoverage.matchedUncoveredVariant?.aliases.includes('VM.Standard.E2.1.Micro'));
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.guidance?.reason, 'free_tier_discovery_only');
  assert.ok(pack.computeCoverage.matchedUncoveredVariant?.suggestedAlternatives.includes('VM.Standard.A1.Flex'));
});

test('context pack derives a family from the service registry for DNS discovery', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'Como se cobra DNS en OCI?',
    intent: {
      route: 'product_discovery',
      serviceFamily: '',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'network' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.ok(pack.serviceContext.family);
  assert.equal(pack.serviceContext.family.id, 'network_dns');
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B88525'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('queries per month'));
});

test('context pack derives a family from the service registry for API Gateway discovery', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is API Gateway billed in OCI?',
    intent: {
      route: 'product_discovery',
      serviceFamily: '',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'application' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.ok(pack.serviceContext.family);
  assert.equal(pack.serviceContext.family.id, 'apigw');
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B92072'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('API calls per month'));
});

test('context pack exposes Health Checks family measurement options from explicit metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is Health Checks billed in OCI?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'edge_health_checks',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'network' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'edge_health_checks');
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('endpoint count'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B90325'));
});

test('context pack exposes Block Volume and File Storage input guidance from explicit metadata', () => {
  const index = buildIndex();
  const cases = [
    ['storage_block', 'How is OCI Block Volume billed?', 'capacityGb', 'vpuPerGb', 'storage capacity (GB)'],
    ['storage_file', 'How is OCI File Storage billed?', 'capacityGb', 'vpuPerGb', 'performance units per GB'],
  ];

  for (const [familyId, userText, keyA, keyB, mode] of cases) {
    const pack = buildAssistantContextPack(index, {
      userText,
      intent: {
        route: 'product_discovery',
        serviceFamily: familyId,
        quotePlan: { action: 'discover', targetType: 'service', domain: 'storage' },
        extractedInputs: {},
      },
      sessionContext: {},
    });

    assert.equal(pack.serviceContext.family.id, familyId);
    assert.ok(pack.serviceContext.family.requiredInputGuidance.some((item) => item.key === keyA));
    assert.ok(pack.serviceContext.family.requiredInputGuidance.some((item) => item.key === keyB));
    assert.ok(pack.serviceContext.family.options.measurementModes.some((item) => item.includes(mode)));
  }
});

test('context pack exposes FastConnect, WAF, Load Balancer, and Object Storage options from explicit metadata', () => {
  const index = buildIndex();
  const cases = [
    ['network_fastconnect', 'What FastConnect options do we have?', 'bandwidthGbps', 'bandwidth (Gbps)'],
    ['security_waf', 'How is Web Application Firewall billed?', 'wafInstances', 'requests per month'],
    ['network_load_balancer', 'How is Load Balancer billed in OCI?', 'bandwidthMbps', 'bandwidth (Mbps)'],
    ['storage_object', 'What options do we have in Object Storage?', 'capacityGb', 'storage capacity (TB)'],
  ];

  for (const [familyId, userText, requiredKey, mode] of cases) {
    const pack = buildAssistantContextPack(index, {
      userText,
      intent: {
        route: 'product_discovery',
        serviceFamily: familyId,
        quotePlan: { action: 'discover', targetType: 'service', domain: 'network' },
        extractedInputs: {},
      },
      sessionContext: {},
    });

    assert.equal(pack.serviceContext.family.id, familyId);
    assert.ok(pack.serviceContext.family.requiredInputGuidance.some((item) => item.key === requiredKey));
    assert.ok(pack.serviceContext.family.options.measurementModes.some((item) => item.includes(mode)));
  }
});

test('context pack exposes Archive, Infrequent Access, and Object Storage Requests options from explicit metadata', () => {
  const index = buildIndex();
  const cases = [
    ['storage_archive', 'How is Archive Storage billed?', 'capacityGb', 'storage capacity (GB)'],
    ['storage_infrequent_access', 'How is Infrequent Access Storage billed?', 'capacityGb', 'storage capacity (GB)'],
    ['storage_object_requests', 'How are Object Storage requests billed?', 'requestCount', 'requests per month'],
  ];

  for (const [familyId, userText, requiredKey, mode] of cases) {
    const pack = buildAssistantContextPack(index, {
      userText,
      intent: {
        route: 'product_discovery',
        serviceFamily: familyId,
        quotePlan: { action: 'discover', targetType: 'service', domain: 'storage' },
        extractedInputs: {},
      },
      sessionContext: {},
    });

    assert.equal(pack.serviceContext.family.id, familyId);
    assert.ok(pack.serviceContext.family.requiredInputGuidance.some((item) => item.key === requiredKey));
    assert.ok(pack.serviceContext.family.options.measurementModes.some((item) => item.includes(mode)));
  }
});

test('context pack exposes Monitoring variants and measurement options from explicit family metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is OCI Monitoring billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'observability_monitoring',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'observability' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'observability_monitoring');
  assert.ok(pack.serviceContext.family.options.variants.includes('ingestion'));
  assert.ok(pack.serviceContext.family.options.variants.includes('retrieval'));
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('million datapoints'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B90925'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B90926'));
});

test('context pack exposes Notifications HTTPS Delivery measurement options from explicit metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is Notifications HTTPS Delivery billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'observability_notifications_https',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'observability' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'observability_notifications_https');
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('delivery operations'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B90940'));
});

test('context pack exposes Email Delivery measurement options from explicit metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is Email Delivery billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'operations_email_delivery',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'operations' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'operations_email_delivery');
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('emails per month'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B90941'));
});

test('context pack exposes IAM SMS measurement options from explicit metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is IAM SMS billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'operations_iam_sms',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'operations' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'operations_iam_sms');
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('messages'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B93496'));
});

test('context pack exposes Threat Intelligence measurement options from explicit metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is Oracle Threat Intelligence Service billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'security_threat_intelligence',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'security' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'security_threat_intelligence');
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('API calls'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B94173'));
});

test('context pack exposes Vector Store Retrieval measurement options from explicit metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is OCI Generative AI Vector Store Retrieval billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'ai_vector_store_retrieval',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'analytics' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'ai_vector_store_retrieval');
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('requests'));
  assert.ok(pack.serviceContext.family.options.variants.includes('vector store retrieval'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B112416'));
});

test('context pack exposes Web Search measurement options from explicit metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is OCI Generative AI Web Search billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'ai_web_search',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'analytics' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'ai_web_search');
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('requests'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B111973'));
});

test('context pack exposes Large Cohere measurement options from explicit metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is OCI Generative AI Large Cohere billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'ai_large_cohere',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'analytics' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'ai_large_cohere');
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('transactions'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B108077'));
});

test('context pack exposes Small Cohere, Embed Cohere, Large Meta, and Knowledge Base Storage from explicit metadata', () => {
  const index = buildIndex();
  const families = [
    ['ai_small_cohere', 'How is OCI Generative AI Small Cohere billed?', 'transactions', 'B108078'],
    ['ai_embed_cohere', 'How is OCI Generative AI Embed Cohere billed?', 'transactions', 'B108079'],
    ['ai_large_meta', 'How is OCI Generative AI Large Meta billed?', 'transactions', 'B108080'],
    ['ai_agents_knowledge_base_storage', 'How is OCI Generative AI knowledge base storage billed?', 'storage per hour (GB)', 'B110462'],
  ];

  for (const [familyId, userText, mode, partNumber] of families) {
    const pack = buildAssistantContextPack(index, {
      userText,
      intent: {
        route: 'product_discovery',
        serviceFamily: familyId,
        quotePlan: { action: 'discover', targetType: 'service', domain: 'analytics' },
        extractedInputs: {},
      },
      sessionContext: {},
    });

    assert.equal(pack.serviceContext.family.id, familyId);
    assert.ok(pack.serviceContext.family.options.measurementModes.includes(mode));
    assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === partNumber));
  }
});

test('context pack exposes AI Language measurement options from explicit metadata', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is OCI AI Language billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'ai_language',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'analytics' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.equal(pack.serviceContext.family.id, 'ai_language');
  assert.ok(pack.serviceContext.family.options.measurementModes.includes('transactions'));
  assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === 'B91477'));
});

test('context pack exposes Vision, Speech, Media Flow, and Fleet measurement options from explicit metadata', () => {
  const index = buildIndex();
  const families = [
    ['ai_vision_custom_training', 'How is Vision Custom Training billed?', 'training hours', 'B94977'],
    ['ai_speech', 'How is OCI Speech billed?', 'transcription hours', 'B94896'],
    ['media_flow', 'How is OCI Media Flow billed?', 'output media minutes', 'B95282'],
    ['ai_vision_stored_video_analysis', 'How is OCI Vision Stored Video Analysis billed?', 'processed video minutes', 'B110617'],
    ['ops_fleet_application_management', 'How is OCI Fleet Application Management billed?', 'managed resources per month', 'B110475'],
  ];

  for (const [familyId, userText, mode, partNumber] of families) {
    const pack = buildAssistantContextPack(index, {
      userText,
      intent: {
        route: 'product_discovery',
        serviceFamily: familyId,
        quotePlan: { action: 'discover', targetType: 'service', domain: 'analytics' },
        extractedInputs: {},
      },
      sessionContext: {},
    });

    assert.equal(pack.serviceContext.family.id, familyId);
    assert.ok(pack.serviceContext.family.options.measurementModes.includes(mode));
    assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === partNumber));
  }
});

test('context pack exposes Vision OCR, Image Analysis, Stream Video Analysis, and Notifications SMS from explicit metadata', () => {
  const index = buildIndex();
  const families = [
    ['ai_vision_image_analysis', 'How is OCI Vision Image Analysis billed?', 'transactions', 'B94973'],
    ['ai_vision_ocr', 'How is OCI Vision OCR billed?', 'transactions', 'B94974'],
    ['ai_vision_stream_video_analysis', 'How is OCI Vision Stream Video Analysis billed?', 'processed video minutes', 'B111539'],
    ['operations_notifications_sms', 'How is OCI Notifications SMS billed?', 'SMS messages', 'B93004'],
  ];

  for (const [familyId, userText, mode, partNumber] of families) {
    const pack = buildAssistantContextPack(index, {
      userText,
      intent: {
        route: 'product_discovery',
        serviceFamily: familyId,
        quotePlan: { action: 'discover', targetType: 'service', domain: 'analytics' },
        extractedInputs: {},
      },
      sessionContext: {},
    });

    assert.equal(pack.serviceContext.family.id, familyId);
    assert.ok(pack.serviceContext.family.options.measurementModes.includes(mode));
    assert.ok(pack.serviceContext.pricingDimensions.some((item) => item.partNumber === partNumber));
  }
});

test('context packs can build a safe unsupported compute reply for HPC variants', () => {
  const message = buildUncoveredComputeReply('Quote OCI Compute HPC - X7 with 2 nodes for 744 hours');

  assert.match(message, /not available yet/i);
  assert.match(message, /HPC - X7/i);
  assert.match(message, /HPC pricing paths/i);
  assert.match(message, /BM\.Standard2\.52/i);
});

test('context packs can build a safe unsupported compute reply for legacy fixed VM aliases', () => {
  const message = buildUncoveredComputeReply('Quote VM.Standard1.4 for 744h/month');

  assert.match(message, /not available yet/i);
  assert.match(message, /Virtual Machine Standard - X5/i);
  assert.match(message, /Legacy fixed X5\/X7/i);
  assert.match(message, /VM\.Standard3\.Flex/i);
});

test('context pack matches legacy denseio aliases and suggests modern denseio flex alternatives', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'Can you quote VM.DenseIO2.8 for 744 hours?',
    intent: {
      route: 'quote_request',
      serviceFamily: '',
      quotePlan: { action: 'quote', targetType: 'service', domain: 'compute' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.ok(pack.computeCoverage);
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.category, 'denseio_legacy');
  assert.ok(pack.computeCoverage.matchedUncoveredVariant?.aliases.includes('VM.DenseIO2'));
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.guidance?.reason, 'legacy_denseio_needs_nvme_mapping');
  assert.ok(pack.computeCoverage.matchedUncoveredVariant?.suggestedAlternatives.includes('VM.DenseIO.E4.Flex'));
  assert.ok(pack.computeCoverage.matchedUncoveredVariant?.suggestedAlternatives.includes('VM.DenseIO.E5.Flex'));
});

test('context pack matches Cloud@Customer GPU aliases as cloud_at_customer guidance', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'Can you quote GPU.L40S on Compute Cloud@Customer?',
    intent: {
      route: 'quote_request',
      serviceFamily: '',
      quotePlan: { action: 'quote', targetType: 'service', domain: 'compute' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.ok(pack.computeCoverage);
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.category, 'cloud_at_customer');
  assert.ok(pack.computeCoverage.matchedUncoveredVariant?.aliases.includes('GPU.L40S'));
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.guidance?.reason, 'cloud_at_customer_commercial_terms_incomplete');
  assert.ok(pack.computeCoverage.matchedUncoveredVariant?.suggestedAlternatives.includes('VM.Standard.E5.Flex'));
});

test('context pack keeps resource commit commercial model for Cloud@Customer GPU variants', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'Can you quote GPU.L40S on Compute Cloud@Customer resource commit?',
    intent: {
      route: 'quote_request',
      serviceFamily: '',
      quotePlan: { action: 'quote', targetType: 'service', domain: 'compute' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.ok(pack.computeCoverage);
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.category, 'cloud_at_customer');
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.guidance?.commercialModel, 'resource_commit');
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.guidance?.reason, 'cloud_at_customer_commercial_terms_incomplete');
});

test('context pack matches standard E2 aliases as legacy fixed guidance', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'Can you quote VM.Standard.E2?',
    intent: {
      route: 'quote_request',
      serviceFamily: '',
      quotePlan: { action: 'quote', targetType: 'service', domain: 'compute' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  assert.ok(pack.computeCoverage);
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.category, 'legacy_fixed');
  assert.ok(pack.computeCoverage.matchedUncoveredVariant?.aliases.includes('VM.Standard.E2'));
  assert.equal(pack.computeCoverage.matchedUncoveredVariant?.guidance?.reason, 'legacy_fixed_needs_modern_mapping');
});

test('context packs can build a safe unsupported compute reply for Microsoft SQL marketplace licensing', () => {
  const message = buildUncoveredComputeReply('Quote Microsoft SQL Enterprise on OCI Compute for 744h/month');

  assert.match(message, /not available yet/i);
  assert.match(message, /Microsoft SQL Enterprise/i);
  assert.match(message, /marketplace licensing line/i);
  assert.match(message, /Quote the underlying OCI compute shape separately/i);
});

test('context packs can build a safe unsupported compute reply for E2 micro free-tier discovery', () => {
  const message = buildUncoveredComputeReply('Quote VM.Standard.E2.1.Micro for 744 hours');

  assert.match(message, /Virtual Machine Standard - E2 Micro - Free/i);
  assert.match(message, /Always Free and promotional zero-cost compute paths/i);
  assert.match(message, /free-tier-friendly baseline/i);
});

test('context packs can build a safe unsupported compute reply for Cloud@Customer GPU variants', () => {
  const message = buildUncoveredComputeReply('Quote GPU.L40S on Compute Cloud@Customer for 744 hours');

  assert.match(message, /Cloud@Customer/i);
  assert.match(message, /resource commitments/i);
  assert.match(message, /standard public OCI compute/i);
});

test('context packs can build a safe unsupported compute reply for Cloud@Customer GPU resource commit variants', () => {
  const message = buildUncoveredComputeReply('Quote GPU.L40S on Compute Cloud@Customer resource commit for 744 hours');

  assert.match(message, /Cloud@Customer/i);
  assert.match(message, /resource commitments/i);
  assert.match(message, /standard public OCI compute/i);
});

test('context packs can build a safe unsupported compute reply for standard E2 variants', () => {
  const message = buildUncoveredComputeReply('Quote VM.Standard.E2 for 744 hours');

  assert.match(message, /Standard - E2/i);
  assert.match(message, /Legacy fixed X5\/X7 families need explicit mapping/i);
  assert.match(message, /VM\.Standard3\.Flex/i);
});

test('context packs can build a safe unsupported compute reply for metered legacy denseio variants', () => {
  const message = buildUncoveredComputeReply('Quote VM.DenseIO2.8 metered for 744 hours');

  assert.match(message, /Virtual Machine Dense I\/O - X7 \(Metered\)/i);
  assert.match(message, /Legacy metered Dense I\/O X5\/X7/i);
  assert.match(message, /VM\.DenseIO\.E4\.Flex/i);
});

test('context packs can build a safe unsupported compute reply for metered Windows guest os variants', () => {
  const message = buildUncoveredComputeReply('Quote Windows OS - Metered for 744 hours');

  assert.match(message, /Windows OS - Metered/i);
  assert.match(message, /Metered guest OS licensing lines/i);
  assert.match(message, /underlying OCI compute and storage path separately/i);
});

test('context packs can build catalog listing replies for FastConnect SKUs', () => {
  const index = buildIndex();
  const message = buildCatalogListingReply(index, 'list all skus for FastConnect', {
    serviceFamily: 'network_fastconnect',
  });

  assert.match(message, /catalog already loaded/i);
  assert.match(message, /Catalog matches/i);
  assert.match(message, /FastConnect/i);
});

test('context pack summary keeps required inputs, license modes, and unsupported compute alternatives', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'Quote Windows OS - Metered for 744 hours',
    intent: {
      route: 'quote_request',
      serviceFamily: 'database_base_db',
      quotePlan: { action: 'quote', targetType: 'service', domain: 'compute' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  const summary = summarizeContextPack(pack);
  assert.ok(summary.family);
  assert.ok(summary.family.requiredInputGuidance.includes('database edition'));
  assert.ok(summary.family.licenseModes.includes('BYOL'));
  assert.ok(summary.computeCoverage);
  assert.equal(summary.computeCoverage.matchedUncoveredCommercialModel, 'metered');
  assert.equal(summary.computeCoverage.requiresSeparateLicensing, true);
  assert.ok(summary.computeCoverage.matchedUncoveredAlternatives.includes('Quote the underlying OCI compute shape separately'));
});

test('context packs can build a structured discovery fallback with SKU lines for catalog-backed families', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: 'How is Data Safe for On-Premises Databases billed?',
    intent: {
      route: 'product_discovery',
      serviceFamily: 'security_data_safe',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'security' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  const message = buildStructuredDiscoveryFallback(pack);
  assert.match(message, /main quote SKUs/i);
  assert.match(message, /B92733/i);
  assert.match(message, /Data Safe for On-Premises Databases/i);
  assert.match(message, /Relevant variants: Database Cloud Service, On-Premises Databases/i);
});

test('context packs can build a structured discovery fallback for compute families without universal SKU claims', () => {
  const index = buildIndex();
  const pack = buildAssistantContextPack(index, {
    userText: "Cuales son los SKU's requeridos en una quote de Virtual Machines \\(Instances\\)?",
    intent: {
      route: 'product_discovery',
      serviceFamily: 'compute_vm_generic',
      quotePlan: { action: 'discover', targetType: 'service', domain: 'compute' },
      extractedInputs: {},
    },
    sessionContext: {},
  });

  const message = buildStructuredDiscoveryFallback(pack);
  assert.match(message, /consistent quote is usually built from OCPU, memory, and attached Block Storage assumptions/i);
  assert.match(message, /To build a reliable quote, I still need:/i);
  assert.match(message, /shape family/i);
});
