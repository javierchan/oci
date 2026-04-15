'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const { resolveRequestDependencies } = require(path.join(__dirname, '..', 'dependency-resolver.js'));
const { normalizeCatalog } = require(path.join(__dirname, '..', 'catalog.js'));
const { normalizeIntentResult } = require(path.join(__dirname, '..', 'normalizer.js'));

function metric(id, displayName, unitDisplayName = '') {
  return { id, displayName, unitDisplayName };
}

function payg(value, rangeMin, rangeMax) {
  const tier = { model: 'PAY_AS_YOU_GO', value };
  if (rangeMin !== undefined) tier.rangeMin = rangeMin;
  if (rangeMax !== undefined) tier.rangeMax = rangeMax;
  return tier;
}

function product({
  partNumber,
  displayName,
  serviceCategoryDisplayName,
  metricId = 'm-count',
  pricetype = 'MONTH',
  usdPrices = [payg(1)],
}) {
  return {
    partNumber,
    displayName,
    serviceCategoryDisplayName,
    metricId,
    pricetype,
    currencyCodeLocalizations: [
      {
        currencyCode: 'USD',
        prices: usdPrices,
      },
    ],
  };
}

function buildIndex() {
  return normalizeCatalog({
    'metrics.json': {
      items: [
        metric('m-count', 'Count'),
        metric('m-port-hour', 'Port Hour'),
        metric('m-storage-month', 'Gigabyte Storage Capacity Per Month'),
        metric('m-performance-month', 'Performance Units Per Gigabyte Per Month'),
        metric('m-ocpu-hour', 'OCPU Per Hour'),
      ],
    },
    'products.json': {
      items: [
        product({
          partNumber: 'B88325',
          displayName: 'FastConnect 1 Gbps Port',
          serviceCategoryDisplayName: 'Networking - FastConnect',
          metricId: 'm-port-hour',
          pricetype: 'HOUR',
        }),
        product({
          partNumber: 'B88326',
          displayName: 'FastConnect 10 Gbps Port',
          serviceCategoryDisplayName: 'Networking - FastConnect',
          metricId: 'm-port-hour',
          pricetype: 'HOUR',
        }),
        product({
          partNumber: 'B91961',
          displayName: 'Block Volume Storage',
          serviceCategoryDisplayName: 'Block Volume',
          metricId: 'm-storage-month',
        }),
        product({
          partNumber: 'B91962',
          displayName: 'Block Volume Performance',
          serviceCategoryDisplayName: 'Block Volume',
          metricId: 'm-performance-month',
        }),
        product({
          partNumber: 'BFLEXFIXED',
          displayName: 'VM.Standard2.2',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
        }),
        product({
          partNumber: 'MFHD30',
          displayName: 'Media Flow HD below 30fps',
          serviceCategoryDisplayName: 'Media Services',
          metricId: 'm-count',
        }),
        product({
          partNumber: 'MF4K30',
          displayName: 'Media Flow 4K below 30fps',
          serviceCategoryDisplayName: 'Media Services',
          metricId: 'm-count',
        }),
      ],
    },
    'productpresets.json': { items: [] },
    'products-apex.json': { items: [] },
  });
}

test('dependency resolver uses metadata fallback for FastConnect when serviceFamily is missing', () => {
  const resolution = resolveRequestDependencies(buildIndex(), {
    source: 'Quote OCI FastConnect 10 Gbps',
    productQuery: 'Quote OCI FastConnect 10 Gbps',
    serviceFamily: '',
    quantity: 10,
  });

  assert.equal(resolution.ok, true);
  assert.deepEqual(resolution.components.map((item) => item.product.partNumber), ['B88326']);
  assert.equal(resolution.resolution.label, 'OCI FastConnect');
});

test('dependency resolver routes fixed compute shapes through compute_flex metadata dispatch', () => {
  const resolution = resolveRequestDependencies(buildIndex(), {
    source: 'Quote VM.Standard2.2',
    productQuery: 'Quote VM.Standard2.2',
    serviceFamily: '',
    quantity: 2,
    ocpus: 2,
    shape: {
      kind: 'fixed',
      family: 'standard',
      series: 'X9',
      shapeName: 'VM.Standard2.2',
      productLabel: 'VM.Standard2.2',
      fixedOcpus: 2,
      partNumbers: ['BFLEXFIXED'],
    },
  });

  assert.equal(resolution.ok, true);
  assert.deepEqual(resolution.components.map((item) => item.product.partNumber), ['BFLEXFIXED']);
  assert.equal(resolution.resolution.label, 'OCI Compute Flex');
});

test('dependency resolver uses metadata composite detection before generic matching', () => {
  const resolution = resolveRequestDependencies(buildIndex(), {
    source: 'Quote a 3-tier architecture with FastConnect 10 Gbps and Block Storage 100 GB 20 VPUs',
    productQuery: 'Quote a 3-tier architecture with FastConnect 10 Gbps and Block Storage 100 GB 20 VPUs',
    serviceFamily: '',
    quantity: 10,
    capacityGb: 100,
    vpuPerGb: 20,
  });

  assert.equal(resolution.ok, true);
  assert.deepEqual(
    resolution.components.map((item) => item.product.partNumber).sort(),
    ['B88326', 'B91961', 'B91962'],
  );
  assert.equal(resolution.resolution.type, 'workload');
});

test('dependency resolver uses family metadata for detailed Media Flow product selection', () => {
  const resolution = resolveRequestDependencies(buildIndex(), {
    source: 'Quote Media Flow HD below 30fps',
    productQuery: 'Quote Media Flow HD below 30fps',
    serviceFamily: '',
  });

  assert.equal(resolution.ok, true);
  assert.equal(resolution.components[0].product.partNumber, 'MFHD30');
});

test('intent normalization always returns a string serviceFamily field', () => {
  const intent = normalizeIntentResult({
    intent: 'quote',
    route: 'quote_request',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Quote OCI FastConnect 10 Gbps',
    assumptions: [],
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    quotePlan: {},
  }, 'Quote OCI FastConnect 10 Gbps');

  assert.equal(typeof intent.serviceFamily, 'string');
  assert.equal(intent.serviceFamily, 'network_fastconnect');
});
