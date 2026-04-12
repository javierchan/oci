'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const { resolvePostClarificationRouting } = require(path.join(ROOT, 'post-clarification-routing.js'));

test('post-clarification routing returns clarification payload from quote clarification state first', async () => {
  const result = await resolvePostClarificationRouting(
    {
      cfg: {},
      index: {},
      conversation: [],
      userText: 'Quote sample',
      effectiveUserText: 'Quote sample',
      sessionContext: {},
      intent: { shouldQuote: true },
      familyMeta: null,
      reformulatedRequest: 'Quote sample',
      preflightQuote: null,
      quoteClarificationState: {
        intent: { needsClarification: true },
        clarificationPayload: { mode: 'clarification', message: 'Need more input' },
      },
    },
    {},
  );

  assert.equal(result.payload.mode, 'clarification');
  assert.match(result.payload.message, /Need more input/);
  assert.equal(result.intent.needsClarification, true);
});

test('post-clarification routing returns license choice payload when the family requires it', async () => {
  const result = await resolvePostClarificationRouting(
    {
      cfg: {},
      index: {},
      conversation: [],
      userText: 'Quote OIC Standard 2 instances',
      effectiveUserText: 'Quote OIC Standard 2 instances',
      sessionContext: {},
      intent: { shouldQuote: true, serviceFamily: 'integration_oic_standard' },
      familyMeta: { canonical: 'Oracle Integration Cloud Standard' },
      reformulatedRequest: 'Quote OIC Standard 2 instances',
      preflightQuote: null,
      quoteClarificationState: { intent: {} },
    },
    {
      hasExplicitByolChoice: () => '',
      shouldAskLicenseChoice: () => true,
      buildLicenseChoiceClarificationPayload: (_familyMeta, intent) => ({ mode: 'clarification', intent, message: 'BYOL or License Included?' }),
    },
  );

  assert.equal(result.payload.mode, 'clarification');
  assert.match(result.payload.message, /BYOL or License Included/i);
});

test('post-clarification routing can return a direct clarification from the intent state', async () => {
  const result = await resolvePostClarificationRouting(
    {
      cfg: {},
      index: {},
      conversation: [],
      userText: 'Quote VM',
      effectiveUserText: 'Quote VM',
      sessionContext: {},
      intent: { shouldQuote: true, needsClarification: true, clarificationQuestion: 'Which shape?' },
      familyMeta: null,
      reformulatedRequest: 'Quote VM',
      preflightQuote: null,
      quoteClarificationState: { intent: {} },
    },
    {
      hasExplicitByolChoice: () => '',
      shouldAskLicenseChoice: () => false,
    },
  );

  assert.equal(result.payload.mode, 'clarification');
  assert.match(result.payload.message, /Which shape/i);
});

test('post-clarification routing returns quote payload when deterministic quote succeeds', async () => {
  const result = await resolvePostClarificationRouting(
    {
      cfg: {},
      index: {},
      conversation: [],
      userText: 'Quote FastConnect 10 Gbps',
      effectiveUserText: 'Quote FastConnect 10 Gbps',
      sessionContext: {},
      intent: { shouldQuote: true, assumptions: [] },
      familyMeta: { canonical: 'OCI FastConnect' },
      reformulatedRequest: 'Quote FastConnect 10 Gbps',
      preflightQuote: { ok: true, lineItems: [{ partNumber: 'B88326' }], totals: { monthly: 100 } },
      quoteClarificationState: { intent: {} },
    },
    {
      hasExplicitByolChoice: () => '',
      shouldAskLicenseChoice: () => false,
      quoteFromPrompt: () => ({ ok: false }),
      parsePromptRequest: () => ({ bandwidthGbps: 10 }),
      formatAssumptions: () => ['10 Gbps'],
      detectByolAmbiguity: () => '',
      buildByolAmbiguityClarificationPayload: () => null,
      filterQuoteByByolChoice: (quote) => quote,
      toMarkdownQuote: () => '',
      buildQuoteNarrative: async (_cfg, userText, quote) => `${userText} :: ${quote.lineItems[0].partNumber}`,
      buildQuoteUnresolvedPayload: async () => ({ mode: 'answer', message: 'unresolved' }),
      buildAnswerFallbackPayload: async () => ({ mode: 'answer', message: 'fallback' }),
      summarizeMatches: () => ({}),
      writeNaturalReply: async () => '',
    },
  );

  assert.equal(result.payload.mode, 'quote');
  assert.match(result.payload.message, /B88326/);
});

test('post-clarification routing returns unresolved payload when quote execution fails', async () => {
  const result = await resolvePostClarificationRouting(
    {
      cfg: {},
      index: {},
      conversation: [],
      userText: 'Quote something',
      effectiveUserText: 'Quote something',
      sessionContext: {},
      intent: { shouldQuote: true, assumptions: [] },
      familyMeta: { canonical: 'Something' },
      reformulatedRequest: 'Quote something',
      preflightQuote: null,
      quoteClarificationState: { intent: {} },
    },
    {
      hasExplicitByolChoice: () => '',
      shouldAskLicenseChoice: () => false,
      quoteFromPrompt: () => ({ ok: false }),
      parsePromptRequest: () => ({}),
      formatAssumptions: () => [],
      detectByolAmbiguity: () => '',
      buildByolAmbiguityClarificationPayload: () => null,
      filterQuoteByByolChoice: (quote) => quote,
      toMarkdownQuote: () => '',
      buildQuoteNarrative: async () => '',
      buildQuoteUnresolvedPayload: async () => ({ mode: 'answer', message: 'unresolved' }),
      buildAnswerFallbackPayload: async () => ({ mode: 'answer', message: 'fallback' }),
      summarizeMatches: () => ({}),
      writeNaturalReply: async () => '',
    },
  );

  assert.equal(result.payload.mode, 'answer');
  assert.match(result.payload.message, /unresolved/);
});

test('post-clarification routing falls back to generic answer payload when the intent does not quote', async () => {
  const result = await resolvePostClarificationRouting(
    {
      cfg: {},
      index: {},
      conversation: [],
      userText: 'How does it work?',
      effectiveUserText: 'How does it work?',
      sessionContext: {},
      intent: { shouldQuote: false },
      familyMeta: null,
      reformulatedRequest: 'How does it work?',
      preflightQuote: null,
      quoteClarificationState: { intent: {} },
    },
    {
      hasExplicitByolChoice: () => '',
      shouldAskLicenseChoice: () => false,
      buildAnswerFallbackPayload: async () => ({ mode: 'answer', message: 'fallback' }),
      summarizeMatches: () => ({}),
      writeNaturalReply: async () => '',
    },
  );

  assert.equal(result.payload.mode, 'answer');
  assert.match(result.payload.message, /fallback/);
});
