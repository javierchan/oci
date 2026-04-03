'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const { normalizeCatalog } = require(path.join(ROOT, 'catalog.js'));
const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));

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
  metricId,
  pricetype = 'HOUR',
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

function buildCalculatorIndex() {
  return normalizeCatalog({
    'metrics.json': {
      items: [
        metric('m-ocpu-hour', 'OCPU Per Hour'),
        metric('m-gb-hour', 'Gigabytes Per Hour'),
        metric('m-capacity-month', 'Gigabyte Storage Capacity Per Month'),
        metric('m-performance-month', 'Performance Units Per Gigabyte Per Month'),
      ],
    },
    'products.json': {
      items: [
        product({
          partNumber: 'B94176',
          displayName: 'Compute - Standard - X9 - OCPU',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.04)],
        }),
        product({
          partNumber: 'B94177',
          displayName: 'Compute - Standard - X9 - Memory',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-gb-hour',
          usdPrices: [payg(0.0015)],
        }),
        product({
          partNumber: 'B91961',
          displayName: 'Storage - Block Volume - Storage',
          serviceCategoryDisplayName: 'Storage - Block Volumes',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0255)],
        }),
        product({
          partNumber: 'B91962',
          displayName: 'Storage - Block Volume - Performance Units',
          serviceCategoryDisplayName: 'Storage - Block Volumes',
          metricId: 'm-performance-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0017)],
        }),
        product({
          partNumber: 'B88513',
          displayName: 'Compute - Bare Metal Standard - X7',
          serviceCategoryDisplayName: 'Compute - Bare Metal',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.06375)],
        }),
        product({
          partNumber: 'B89137',
          displayName: 'Compute - Bare Metal Standard - X7 - Metered',
          serviceCategoryDisplayName: 'Compute - Bare Metal',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.075)],
        }),
      ],
    },
    'productpresets.json': { items: [] },
  });
}

function assertWithin(actual, expected, tolerance = 0.05) {
  assert.ok(Math.abs(Number(actual) - Number(expected)) <= tolerance, `${actual} was not within ${tolerance} of ${expected}`);
}

test('calculator parity: VM.Standard3.Flex 1 OCPU 8 GB plus 200 GB block at 10 VPU stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard3.Flex 1 OCPU 8 GB RAM with 200 GB Block Storage and 10 VPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 47.19);
  assert.match(quote.markdown, /B94176/);
  assert.match(quote.markdown, /B94177/);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
});

test('calculator parity: VM.Standard3.Flex 28 OCPUs 256 GB plus 121 GB block at 30 VPU stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard3.Flex 28 OCPUs 256 GB RAM with 121 GB Block Storage and 30 VPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1128.23);
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B91962');
  assert.ok(performanceLine);
  assertWithin(performanceLine.monthly, 6.171);
});

test('calculator parity: VM.Standard3.Flex 28 OCPUs 512 GB plus 6279 GB block at 30 VPU stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard3.Flex 28 OCPUs 512 GB RAM with 6279 GB Block Storage and 30 VPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1885.01);
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B91962');
  assert.ok(performanceLine);
  assertWithin(performanceLine.monthly, 320.23, 0.1);
});

test('calculator parity: VM.Standard3.Flex 28 OCPUs 512 GB without attached storage stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard3.Flex 28 OCPUs 512 GB RAM 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1404.67, 0.1);
  assert.equal(quote.lineItems.some((line) => line.partNumber === 'B91961'), false);
  assert.equal(quote.lineItems.some((line) => line.partNumber === 'B91962'), false);
});

test('calculator parity: block volume only 6279 GB at 10 VPU stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Block Volume 6279 GB with 10 VPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 266.83, 0.1);
  const storageLine = quote.lineItems.find((line) => line.partNumber === 'B91961');
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B91962');
  assert.ok(storageLine);
  assert.ok(performanceLine);
  assertWithin(storageLine.monthly, 160.11, 0.1);
  assertWithin(performanceLine.monthly, 106.74, 0.1);
});

test('calculator parity: block volume only 6279 GB at 20 VPU stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Block Volume 6279 GB with 20 VPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 373.53, 0.1);
  const storageLine = quote.lineItems.find((line) => line.partNumber === 'B91961');
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B91962');
  assert.ok(storageLine);
  assert.ok(performanceLine);
  assertWithin(storageLine.monthly, 160.11, 0.1);
  assertWithin(performanceLine.monthly, 213.49, 0.1);
});

test('calculator parity: block volume only 6279 GB at 30 VPU stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Block Volume 6279 GB with 30 VPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 480.34, 0.1);
  const storageLine = quote.lineItems.find((line) => line.partNumber === 'B91961');
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B91962');
  assert.ok(storageLine);
  assert.ok(performanceLine);
  assertWithin(storageLine.monthly, 160.11, 0.1);
  assertWithin(performanceLine.monthly, 320.23, 0.1);
});

test('calculator parity: bare metal fixed-shape prompts resolve the bare metal SKU instead of a VM family', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote BM.Standard2.52 744h/month');
  const meteredQuote = quoteFromPrompt(index, 'Quote BM.Standard2.52 metered 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B88513/);
  assert.doesNotMatch(quote.markdown, /B89137/);
  assertWithin(quote.totals.monthly, 2466.36, 0.2);

  assert.equal(meteredQuote.ok, true);
  assert.match(meteredQuote.markdown, /B89137/);
  assert.doesNotMatch(meteredQuote.markdown, /B88513/);
  assertWithin(meteredQuote.totals.monthly, 2901.6, 0.2);
});
