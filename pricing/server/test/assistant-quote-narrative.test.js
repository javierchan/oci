'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const {
  buildConsumptionExplanation,
  buildDeterministicConsiderationsFallback,
  buildDeterministicExpertSummary,
  formatMoney,
  inferQuoteTechnologyProfile,
} = require(path.join(__dirname, '..', 'assistant-quote-narrative.js'));

test('formatMoney keeps assistant narrative currency formatting', () => {
  assert.equal(formatMoney(14, 'USD'), '$14.00');
  assert.equal(formatMoney('bad', 'USD'), 'USD -');
});

test('inferQuoteTechnologyProfile detects vmware migration context from quote metadata', () => {
  const profile = inferQuoteTechnologyProfile({
    request: {
      source: 'Quote VM.Standard.E5.Flex',
      metadata: { inventorySource: 'rvtools' },
    },
    lineItems: [],
  });

  assert.equal(profile.key, 'vmware-migration');
});

test('buildDeterministicExpertSummary anchors totals and top cost drivers', () => {
  const summary = buildDeterministicExpertSummary({
    totals: { monthly: 14, annual: 168, currencyCode: 'USD' },
    lineItems: [
      { partNumber: 'B94579', product: 'OCI Web Application Firewall - Instance', monthly: 10 },
      { partNumber: 'B94277', product: 'OCI Web Application Firewall - Requests', monthly: 4 },
    ],
  });

  assert.match(summary, /Monthly total: \$14\.00/);
  assert.match(summary, /B94579/);
});

test('buildDeterministicConsiderationsFallback returns network guidance for network-heavy quotes', () => {
  const text = buildDeterministicConsiderationsFallback({
    request: { source: 'Quote Flexible Load Balancer 50 Mbps plus DNS 1000000 queries per month' },
    lineItems: [
      { service: 'Networking', product: 'Load Balancer Bandwidth' },
      { service: 'Networking', product: 'Networking - DNS' },
    ],
  }, []);

  assert.match(text, /OCI networking\/security review/);
});

test('buildConsumptionExplanation groups large mixed quotes by billing dimension', () => {
  const lines = buildConsumptionExplanation({
    lineItems: [
      { service: 'Compute', product: 'Compute OCPU', metric: 'OCPU Per Hour' },
      { service: 'Storage', product: 'File Storage - Storage', metric: 'Gigabyte Storage Capacity Per Month' },
      { service: 'Network', product: 'API Gateway', metric: 'API Calls' },
      { service: 'Analytics', product: 'Analytics Users', metric: 'Users Per Month' },
      { service: 'Monitoring', product: 'Monitoring Retrieval', metric: '1M Datapoints Retrieved' },
      { service: 'Media', product: 'Media Flow', metric: 'Output Minutes' },
    ],
  });

  assert.ok(Array.isArray(lines));
  assert.ok(lines.some((line) => /Compute-style charges/.test(line)));
  assert.ok(lines.some((line) => /Storage-style charges/.test(line)));
});
