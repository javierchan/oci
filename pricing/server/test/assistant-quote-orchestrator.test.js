'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const orchestratorPath = path.join(ROOT, 'assistant-quote-orchestrator.js');
const genaiPath = path.join(ROOT, 'genai.js');

function loadOrchestrator(options = {}) {
  delete require.cache[orchestratorPath];
  delete require.cache[genaiPath];

  require.cache[genaiPath] = {
    id: genaiPath,
    filename: genaiPath,
    loaded: true,
    exports: {
      runChat: async () => {
        if (options.throwGenAI) throw new Error('genai unavailable');
        return { data: { text: options.genaiText || '' } };
      },
      extractChatText: (payload) => String(payload?.text || ''),
    },
  };

  return require(orchestratorPath);
}

function buildQuote() {
  return {
    ok: true,
    resolution: { label: 'Flexible Load Balancer' },
    totals: { monthly: 14, annual: 168, currencyCode: 'USD' },
    lineItems: [
      { partNumber: 'B93030', service: 'Networking', product: 'Load Balancer Base', metric: 'Load Balancer', quantity: 1, monthly: 10 },
      { partNumber: 'B93031', service: 'Networking', product: 'Load Balancer Bandwidth', metric: 'Mbps Per Hour', quantity: 50, monthly: 4 },
    ],
    markdown: '| quote |',
    warnings: ['Validate bandwidth assumptions.'],
    request: {},
  };
}

test('quote orchestrator falls back to deterministic considerations when GenAI is unavailable', async () => {
  const { buildQuoteNarrative } = loadOrchestrator({ throwGenAI: true });
  const message = await buildQuoteNarrative(
    {},
    'Quote Flexible Load Balancer 50 Mbps',
    buildQuote(),
    ['- Monthly usage defaulted to 730 hours.'],
  );

  assert.match(message, /## OCI Expert Summary/);
  assert.match(message, /## OCI Considerations/);
  assert.match(message, /How OCI measures this:/);
  assert.match(message, /### OCI quotation/);
});

test('quote orchestrator keeps sanitized GenAI considerations and strips numeric breakdowns', async () => {
  const { buildQuoteNarrative } = loadOrchestrator({
    genaiText: [
      '## OCI Considerations',
      '- Validate throughput assumptions and request profile.',
      '',
      '## Breakdown of Costs',
      '- 1 instance = $10',
    ].join('\n'),
  });
  const message = await buildQuoteNarrative(
    { ok: true },
    'Quote Flexible Load Balancer 50 Mbps',
    buildQuote(),
    [],
  );

  assert.match(message, /## OCI Considerations/);
  assert.match(message, /Validate throughput assumptions/);
  assert.doesNotMatch(message, /Breakdown of Costs/);
  assert.doesNotMatch(message, /1 instance = \$10/);
});
