'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  buildAssistantQuoteRoutingDeps,
  buildDirectQuoteFastPathDeps,
  buildPostClarificationRoutingDeps,
} = require(path.join(ROOT, 'quote-routing-deps.js'));

test('quote routing deps builds the direct fast-path dependency slice', () => {
  const deps = {
    buildCompositeQuoteFromSegments: () => 'composite',
    buildQuoteNarrative: () => 'narrative',
    formatAssumptions: () => [],
    parsePromptRequest: () => ({}),
    quoteFromPrompt: () => ({}),
    ignored: () => 'ignored',
  };

  const result = buildDirectQuoteFastPathDeps(deps);

  assert.deepEqual(Object.keys(result).sort(), [
    'buildCompositeQuoteFromSegments',
    'buildQuoteNarrative',
    'formatAssumptions',
    'parsePromptRequest',
    'quoteFromPrompt',
  ]);
  assert.equal(result.quoteFromPrompt, deps.quoteFromPrompt);
});

test('quote routing deps builds the post-clarification dependency slice', () => {
  const deps = {
    hasExplicitByolChoice: () => '',
    shouldAskLicenseChoice: () => false,
    buildLicenseChoiceClarificationPayload: () => ({}),
    quoteFromPrompt: () => ({}),
    parsePromptRequest: () => ({}),
    formatAssumptions: () => [],
    detectByolAmbiguity: () => '',
    buildByolAmbiguityClarificationPayload: () => ({}),
    filterQuoteByByolChoice: (quote) => quote,
    toMarkdownQuote: () => '',
    buildQuoteNarrative: async () => '',
    buildQuoteUnresolvedPayload: async () => ({}),
    buildAnswerFallbackPayload: async () => ({}),
    summarizeMatches: () => ({}),
    writeNaturalReply: async () => '',
  };

  const result = buildPostClarificationRoutingDeps(deps);

  assert.deepEqual(Object.keys(result).sort(), [
    'buildAnswerFallbackPayload',
    'buildByolAmbiguityClarificationPayload',
    'buildLicenseChoiceClarificationPayload',
    'buildQuoteNarrative',
    'buildQuoteUnresolvedPayload',
    'detectByolAmbiguity',
    'filterQuoteByByolChoice',
    'formatAssumptions',
    'hasExplicitByolChoice',
    'parsePromptRequest',
    'quoteFromPrompt',
    'shouldAskLicenseChoice',
    'summarizeMatches',
    'toMarkdownQuote',
    'writeNaturalReply',
  ]);
  assert.equal(result.toMarkdownQuote, deps.toMarkdownQuote);
});

test('quote routing deps builds the assistant routing slice on top of post-clarification deps', () => {
  const deps = {
    prepareQuoteCandidateState: () => ({}),
    getServiceFamily: () => null,
    mergeSessionQuoteFollowUpByRoute: () => '',
    findUncoveredComputeVariant: () => '',
    canSafelyQuoteUncoveredComputeVariant: () => false,
    buildUncoveredComputeReply: () => '',
    buildAssistantContextPack: () => ({}),
    summarizeContextPack: () => ({}),
    serviceHasRequiredInputs: () => false,
    isDiscoveryOrExplanationQuestion: () => false,
    buildQuoteRequestShape: () => ({}),
    preserveCriticalPromptModifiers: () => '',
    choosePreferredQuote: () => null,
    reconcileQuoteClarificationState: () => ({}),
    getPreQuoteClarification: () => '',
    getMissingRequiredInputs: () => [],
    getClarificationMessage: () => '',
    resolvePostClarificationRouting: async () => ({}),
    hasExplicitByolChoice: () => '',
    shouldAskLicenseChoice: () => false,
    buildLicenseChoiceClarificationPayload: () => ({}),
    quoteFromPrompt: () => ({}),
    parsePromptRequest: () => ({}),
    formatAssumptions: () => [],
    detectByolAmbiguity: () => '',
    buildByolAmbiguityClarificationPayload: () => ({}),
    filterQuoteByByolChoice: (quote) => quote,
    toMarkdownQuote: () => '',
    buildQuoteNarrative: async () => '',
    buildQuoteUnresolvedPayload: async () => ({}),
    buildAnswerFallbackPayload: async () => ({}),
    summarizeMatches: () => ({}),
    writeNaturalReply: async () => '',
  };

  const result = buildAssistantQuoteRoutingDeps(deps);

  assert.equal(result.prepareQuoteCandidateState, deps.prepareQuoteCandidateState);
  assert.equal(result.resolvePostClarificationRouting, deps.resolvePostClarificationRouting);
  assert.equal(result.buildQuoteNarrative, deps.buildQuoteNarrative);
  assert.equal(result.writeNaturalReply, deps.writeNaturalReply);
});
