'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const {
  buildDeterministicQuotePayload,
} = require(path.join(__dirname, '..', 'quote-response-payload.js'));

test('deterministic quote payload delegates message building and preserves quote metadata', async () => {
  const quote = { ok: true, resolution: { label: 'OCI WAF' } };
  const intent = { intent: 'quote', shouldQuote: true };
  const payload = await buildDeterministicQuotePayload({
    cfg: { modelId: 'test-model' },
    userText: 'Quote WAF',
    quote,
    assumptions: ['- Usage defaulted to 730 hours.'],
    intent,
  }, {
    buildQuoteNarrative: async (cfg, userText, passedQuote, assumptions) => {
      assert.equal(cfg.modelId, 'test-model');
      assert.equal(userText, 'Quote WAF');
      assert.equal(passedQuote, quote);
      assert.deepEqual(assumptions, ['- Usage defaulted to 730 hours.']);
      return 'Rendered narrative';
    },
  });

  assert.deepEqual(payload, {
    ok: true,
    mode: 'quote',
    message: 'Rendered narrative',
    quote,
    intent,
  });
});
