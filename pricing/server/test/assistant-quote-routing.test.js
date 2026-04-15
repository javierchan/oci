'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const {
  resolveAssistantQuoteRouting,
} = require(path.join(__dirname, '..', 'assistant-quote-routing.js'));

test('assistant quote routing returns fallback payload from candidate preparation when present', async () => {
  const result = await resolveAssistantQuoteRouting(
    {
      cfg: {},
      index: {},
      conversation: [],
      userText: 'Quote unsupported VM',
      effectiveUserText: 'Quote unsupported VM',
      sessionContext: {},
      intent: { route: 'quote_request' },
      topService: null,
      contextualFollowUp: false,
      compositeLike: false,
    },
    {
      prepareQuoteCandidateState: () => ({
        fallbackPayload: { mode: 'answer', message: 'unsupported' },
        intent: { route: 'product_discovery' },
      }),
    },
  );

  assert.equal(result.payload.mode, 'answer');
  assert.match(result.payload.message, /unsupported/);
  assert.equal(result.intent.route, 'product_discovery');
});

test('assistant quote routing forwards prepared quote state into post-clarification routing', async () => {
  const result = await resolveAssistantQuoteRouting(
    {
      cfg: { ok: true },
      index: {},
      conversation: [],
      userText: 'Quote FastConnect 10 Gbps',
      effectiveUserText: 'Quote FastConnect 10 Gbps',
      sessionContext: {},
      intent: { shouldQuote: true, assumptions: [] },
      topService: { canonicalName: 'OCI FastConnect' },
      contextualFollowUp: false,
      compositeLike: false,
    },
    {
      prepareQuoteCandidateState: () => ({
        fallbackPayload: null,
        intent: { shouldQuote: true, serviceFamily: 'network_fastconnect' },
        familyMeta: { canonical: 'OCI FastConnect' },
        reformulatedRequest: 'Quote FastConnect 10 Gbps',
        preflightQuote: { ok: true, lineItems: [{ partNumber: 'B88326' }] },
      }),
      reconcileQuoteClarificationState: ({ reformulatedRequest }) => ({
        intent: { route: 'quote_request' },
        clarificationPayload: null,
        reformulatedRequest,
      }),
      resolvePostClarificationRouting: async (options) => ({
        intent: options.intent,
        payload: {
          mode: 'quote',
          message: `${options.reformulatedRequest} :: ${options.preflightQuote.lineItems[0].partNumber}`,
        },
      }),
    },
  );

  assert.equal(result.payload.mode, 'quote');
  assert.match(result.payload.message, /B88326/);
  assert.equal(result.intent.serviceFamily, 'network_fastconnect');
});
