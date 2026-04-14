'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const {
  buildQuoteNarrativeLead,
  buildQuoteNarrativeMessage,
} = require(path.join(__dirname, '..', 'assistant-quote-assembly.js'));

test('quote narrative lead uses monthly totals by default', () => {
  const text = buildQuoteNarrativeLead({
    resolution: { label: 'Flexible Load Balancer' },
    totals: { monthly: 14, annual: 168, currencyCode: 'USD' },
    lineItems: [{}, {}],
    request: {},
  });

  assert.match(text, /I prepared a deterministic OCI quotation for `Flexible Load Balancer`\./);
  assert.match(text, /calculated monthly total is \*\*\$14\.00\*\*/);
  assert.match(text, /2 priced lines/);
});

test('quote narrative lead uses annual totals when annualRequested is set', () => {
  const text = buildQuoteNarrativeLead({
    resolution: { label: 'Base Database Service' },
    totals: { monthly: 100, annual: 1200, currencyCode: 'USD' },
    lineItems: [{}],
    request: { annualRequested: true },
  });

  assert.match(text, /calculated annual total is \*\*\$1,200\.00\*\*/);
  assert.match(text, /1 priced line/);
});

test('quote narrative message assembles deterministic sections in stable order', () => {
  const text = buildQuoteNarrativeMessage({
    quote: {
      resolution: { label: 'OCI WAF' },
      totals: { monthly: 14, annual: 168, currencyCode: 'USD' },
      lineItems: [{}, {}],
      markdown: '| quote |',
      warnings: ['Validate request volume.'],
      request: {},
    },
    assumptions: ['- Monthly usage defaulted to 730 hours.'],
    expertSummary: '## OCI Expert Summary\n- Perspective: **OCI networking and security architect**.',
    fallbackConsiderations: '## OCI Considerations\n- Validate throughput assumptions.',
    consumptionExplanation: ['- Network charges are driven by provisioned connectivity.'],
  });

  assert.match(text, /Key assumptions:/);
  assert.match(text, /## OCI Expert Summary/);
  assert.match(text, /## OCI Considerations/);
  assert.match(text, /How OCI measures this:/);
  assert.match(text, /### OCI quotation/);
  assert.match(text, /Warnings:\n- Validate request volume\./);
});
