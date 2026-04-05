'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const { normalizeCatalog } = require(path.join(__dirname, '..', 'catalog.js'));

test('normalizeCatalog merges apex products as complementary source without duplicating normalized matches', () => {
  const index = normalizeCatalog({
    'metrics.json': {
      items: [
        { id: 'm1', displayName: 'OCPU Per Hour', unitDisplayName: 'OCPU' },
      ],
    },
    'products.json': {
      items: [
        {
          partNumber: 'B100',
          displayName: 'OCI Generative AI - xAI - Grok 4 Code Cached Input Tokens',
          serviceCategoryDisplayName: 'Generative AI',
          metricId: 'm1',
          pricetype: 'HOUR',
          currencyCodeLocalizations: [{ currencyCode: 'USD', prices: [{ model: 'PAY_AS_YOU_GO', value: 1 }] }],
        },
      ],
    },
    'products-apex.json': {
      items: [
        {
          partNumber: 'B100',
          displayName: 'OCI Generative AI - xAI - Grok 4 Code Cached Input Tokens',
          metricName: 'OCPU Per Hour',
          serviceCategory: 'Generative AI',
          currencyCodeLocalizations: [{ currencyCode: 'USD', prices: [{ model: 'PAY_AS_YOU_GO', value: 1 }] }],
        },
        {
          partNumber: 'B200',
          displayName: 'OCI - Compute - GPU - H100T',
          metricName: 'OCPU Per Hour',
          serviceCategory: 'Compute - GPU',
          currencyCodeLocalizations: [{ currencyCode: 'USD', prices: [{ model: 'PAY_AS_YOU_GO', value: 2 }] }],
        },
      ],
    },
    'productpresets.json': { items: [] },
  });

  const b100 = index.products.filter((item) => item.partNumber === 'B100');
  const b200 = index.products.find((item) => item.partNumber === 'B200');

  assert.equal(b100.length, 1);
  assert.ok(b200);
  assert.equal(b200.metricDisplayName, 'OCPU Per Hour');
  assert.equal(b200.serviceCategoryDisplayName, 'Compute - GPU');
});
