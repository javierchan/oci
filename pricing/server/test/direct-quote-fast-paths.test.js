'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  isSimpleTransactionalQuoteRequest,
  resolveDirectQuoteFastPath,
} = require(path.join(ROOT, 'direct-quote-fast-paths.js'));

test('direct quote fast paths detect simple transactional requests', () => {
  assert.equal(isSimpleTransactionalQuoteRequest({ requestCount: 5000000 }, false), true);
  assert.equal(isSimpleTransactionalQuoteRequest({ requestCount: 5000000, serviceFamily: 'apigw' }, false), false);
  assert.equal(isSimpleTransactionalQuoteRequest({ requestCount: 5000000, users: 10 }, false), false);
  assert.equal(isSimpleTransactionalQuoteRequest({ requestCount: 5000000 }, true), false);
});

test('direct quote fast paths return an early composite quote payload when composite resolution succeeds', async () => {
  const payload = await resolveDirectQuoteFastPath(
    {
      cfg: {},
      index: {},
      effectiveUserText: 'Quote Functions plus API Gateway plus DNS',
      compositeLike: true,
    },
    {
      buildCompositeQuoteFromSegments: () => ({
        ok: true,
        resolution: { label: 'Composite OCI workload' },
        lineItems: [{ partNumber: 'B90617' }],
      }),
      buildQuoteNarrative: async (_cfg, userText, quote, assumptions) => `${userText} :: ${quote.resolution.label} :: ${assumptions.join(',')}`,
      formatAssumptions: () => ['composite-assumption'],
      parsePromptRequest: () => ({}),
      quoteFromPrompt: () => ({ ok: false }),
    },
  );

  assert.equal(payload.mode, 'quote');
  assert.match(payload.message, /Composite OCI workload/);
  assert.equal(payload.intent.shouldQuote, true);
  assert.equal(payload.intent.needsClarification, false);
});

test('direct quote fast paths return an early simple transactional quote payload when a service-level quote resolves', async () => {
  const payload = await resolveDirectQuoteFastPath(
    {
      cfg: {},
      index: {},
      effectiveUserText: 'Quote API Gateway 5000000 API calls per month',
      compositeLike: false,
    },
    {
      buildCompositeQuoteFromSegments: () => null,
      buildQuoteNarrative: async (_cfg, userText, quote, assumptions) => `${userText} :: ${quote.resolution.type} :: ${assumptions.join(',')}`,
      formatAssumptions: (_assumptions, parsed) => [String(parsed.requestCount)],
      parsePromptRequest: () => ({ requestCount: 5000000 }),
      quoteFromPrompt: () => ({
        ok: true,
        resolution: { type: 'service', label: 'OCI API Gateway' },
        lineItems: [{ partNumber: 'B92072' }],
      }),
    },
  );

  assert.equal(payload.mode, 'quote');
  assert.match(payload.message, /service/);
  assert.match(payload.message, /5000000/);
  assert.equal(payload.quote.lineItems[0].partNumber, 'B92072');
});

test('direct quote fast paths return null when neither early path qualifies', async () => {
  const payload = await resolveDirectQuoteFastPath(
    {
      cfg: {},
      index: {},
      effectiveUserText: 'Quote Oracle Integration Cloud Standard 2 instances',
      compositeLike: false,
    },
    {
      buildCompositeQuoteFromSegments: () => null,
      buildQuoteNarrative: async () => '',
      formatAssumptions: () => [],
      parsePromptRequest: () => ({ instances: 2, serviceFamily: 'integration_oic_standard' }),
      quoteFromPrompt: () => ({ ok: false }),
    },
  );

  assert.equal(payload, null);
});
