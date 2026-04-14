'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const {
  buildQuoteEnrichmentContextBlock,
  sanitizeQuoteEnrichment,
  shouldAllowMigrationNotes,
} = require(path.join(__dirname, '..', 'assistant-quote-enrichment.js'));

test('quote enrichment sanitizer drops numeric breakdowns and keeps technical considerations', () => {
  const sanitized = sanitizeQuoteEnrichment([
    '## OCI Considerations for Web Application Firewall',
    '* WAF pricing has fixed instance and variable request dimensions.',
    '',
    '## Breakdown of Costs',
    '* 2 instances at $5 = $10',
    '* 25 million requests = $9',
    '',
    '## Migration Notes',
    '* Not applicable.',
  ].join('\n'));

  assert.match(sanitized, /## OCI Considerations/);
  assert.match(sanitized, /fixed instance and variable request dimensions/);
  assert.match(sanitized, /## Migration Notes/);
  assert.doesNotMatch(sanitized, /\$10|\$9|Breakdown of Costs/);
});

test('quote enrichment context block includes formatted totals and line items', () => {
  const contextBlock = buildQuoteEnrichmentContextBlock(
    'Quote WAF',
    {
      resolution: { label: 'OCI WAF' },
      totals: { monthly: 14, annual: 168, currencyCode: 'USD' },
      lineItems: [
        { service: 'Security', product: 'OCI WAF Instance', metric: 'Instance Per Hour', quantity: 2, monthly: 10 },
        { service: 'Security', product: 'OCI WAF Requests', metric: '1M Requests', quantity: 25, monthly: 4 },
      ],
      warnings: ['Requests are estimated from monthly traffic volume.'],
      request: { metadata: { inventorySource: 'rvtools', vmwareVcpus: 24 } },
    },
    ['- Monthly usage defaulted to 730 hours.'],
    {
      role: 'OCI networking and security architect',
      name: 'OCI networking and edge security',
      focus: 'port-hour, bandwidth, request, and processed-data dimensions',
    },
  );

  assert.match(contextBlock, /Expert role: OCI networking and security architect/);
  assert.match(contextBlock, /Monthly total: \$14\.00/);
  assert.match(contextBlock, /OCI WAF Instance/);
  assert.match(contextBlock, /Inventory source: rvtools/);
  assert.match(contextBlock, /VMware vCPUs in source request: 24/);
});

test('quote enrichment migration-note guard follows quote metadata and user text', () => {
  assert.equal(shouldAllowMigrationNotes('Quote Monitoring', { request: {} }), false);
  assert.equal(shouldAllowMigrationNotes('Quote VMware migration', { request: {} }), true);
  assert.equal(shouldAllowMigrationNotes('Quote Monitoring', { request: { metadata: { inventorySource: 'rvtools' } } }), true);
});
