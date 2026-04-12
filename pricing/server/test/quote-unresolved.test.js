'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const { buildQuoteUnresolvedPayload } = require(path.join(ROOT, 'quote-unresolved.js'));

test('quote unresolved uses family-specific unavailable message when provided', async () => {
  const payload = await buildQuoteUnresolvedPayload({
    familyMeta: {
      quoteUnavailableMessage: ({ reformulatedRequest }) => `Cannot quote ${reformulatedRequest} deterministically.`,
    },
    userText: 'Quote something',
    reformulatedRequest: 'Quote something',
    quote: { ok: false, error: 'no sku' },
    intent: { intent: 'quote', serviceFamily: 'sample' },
  });

  assert.equal(payload.mode, 'quote_unresolved');
  assert.match(payload.message, /Cannot quote Quote something deterministically/);
});

test('quote unresolved falls back to natural reply when no family message exists', async () => {
  const payload = await buildQuoteUnresolvedPayload({
    familyMeta: null,
    userText: 'Quote something',
    reformulatedRequest: 'Quote something',
    quote: { ok: false, error: 'no sku', warnings: ['warning a'] },
    intent: { intent: 'quote', serviceFamily: 'sample' },
    index: { id: 'stub' },
    conversation: [],
    sessionContext: null,
    assumptions: ['- assume 1 instance'],
    summarizeMatches: () => ({ products: ['Product A'], presets: ['Preset A'] }),
    writeNaturalReply: async (_cfg, _conversation, _userText, context) => {
      assert.match(context.summary, /no sku/i);
      assert.deepEqual(context.warningLines, ['- warning a']);
      assert.deepEqual(context.candidateLines, ['- Product: Product A', '- Preset: Preset A']);
      assert.deepEqual(context.assumptionLines, ['- assume 1 instance']);
      return 'Natural unresolved reply';
    },
    cfg: {},
  });

  assert.equal(payload.mode, 'quote_unresolved');
  assert.equal(payload.message, 'Natural unresolved reply');
});
