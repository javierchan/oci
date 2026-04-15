'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  buildAssistantRuntimeDeps,
} = require(path.join(ROOT, 'assistant-runtime-deps.js'));

test('assistant runtime deps assembles the request and response dependency slices', () => {
  const result = buildAssistantRuntimeDeps();

  assert.deepEqual(Object.keys(result.requestStateDeps).sort(), [
    'isCompositeOrComparisonRequest',
    'isShortContextualAnswer',
    'mergeClarificationAnswer',
    'mergeSessionQuoteFollowUp',
  ]);
  assert.deepEqual(Object.keys(result.responseDeps).sort(), [
    'buildAssistantSessionContext',
  ]);
});

test('assistant runtime deps assembles the orchestration dependency slices', () => {
  const result = buildAssistantRuntimeDeps();

  assert.deepEqual(Object.keys(result.earlyRoutingDeps).sort(), [
    'buildEarlyAssistantReply',
    'buildFlexComparisonNarrative',
    'buildFlexComparisonQuote',
    'buildFlexComparisonReplyPayload',
    'detectFlexComparisonModifier',
    'detectGenericComputeShapeClarification',
    'extractFlexComparisonContext',
    'isFlexComparisonRequest',
    'parseBurstableBaseline',
    'parseCapacityReservationUtilization',
    'resolveEarlyFlexComparisonClarification',
  ]);
  assert.deepEqual(Object.keys(result.directQuoteFastPathDeps).sort(), [
    'buildCompositeQuoteFromSegments',
    'buildQuoteNarrative',
    'formatAssumptions',
    'parsePromptRequest',
    'quoteFromPrompt',
  ]);
  assert.deepEqual(Object.keys(result.intentPipelineDeps).sort(), [
    'analyzeImageIntent',
    'analyzeIntent',
    'applyQuoteFollowUpIntentOverride',
    'buildFlexComparisonNarrative',
    'buildFlexComparisonQuote',
    'buildFlexComparisonReplyPayload',
    'buildServiceUnavailableMessage',
    'enrichExtractedInputsForFamily',
    'extractFlexComparisonContext',
    'fallbackIntentOnAnalysisFailure',
    'isSessionQuoteFollowUp',
    'reconcileIntentWithHeuristics',
    'reconcilePostIntentFollowUp',
    'shouldForceQuoteFollowUpRoute',
  ]);
  assert.deepEqual(Object.keys(result.discoveryRoutingStateDeps).sort(), [
    'buildCatalogListingReply',
    'buildRegistryQuery',
    'searchServiceRegistry',
    'serviceHasRequiredInputs',
  ]);
  assert.deepEqual(Object.keys(result.discoveryRoutePayloadDeps).sort(), [
    'buildAssistantContextPack',
    'buildServiceUnavailableMessage',
    'buildStructuredDiscoveryFallback',
    'hasExplicitQuoteLead',
    'isConceptualPricingQuestion',
    'summarizeContextPack',
    'writeStructuredContextReply',
  ]);
});

test('assistant runtime deps assembles the quote-routing dependency slice', () => {
  const result = buildAssistantRuntimeDeps();

  assert.deepEqual(Object.keys(result.assistantQuoteRoutingDeps).sort(), [
    'buildAnswerFallbackPayload',
    'buildAssistantContextPack',
    'buildByolAmbiguityClarificationPayload',
    'buildLicenseChoiceClarificationPayload',
    'buildQuoteNarrative',
    'buildQuoteRequestShape',
    'buildQuoteUnresolvedPayload',
    'buildUncoveredComputeReply',
    'canSafelyQuoteUncoveredComputeVariant',
    'choosePreferredQuote',
    'detectByolAmbiguity',
    'filterQuoteByByolChoice',
    'findUncoveredComputeVariant',
    'formatAssumptions',
    'getClarificationMessage',
    'getMissingRequiredInputs',
    'getPreQuoteClarification',
    'getServiceFamily',
    'hasExplicitByolChoice',
    'isDiscoveryOrExplanationQuestion',
    'mergeSessionQuoteFollowUpByRoute',
    'parsePromptRequest',
    'prepareQuoteCandidateState',
    'preserveCriticalPromptModifiers',
    'quoteFromPrompt',
    'reconcileQuoteClarificationState',
    'resolvePostClarificationRouting',
    'serviceHasRequiredInputs',
    'shouldAskLicenseChoice',
    'summarizeContextPack',
    'summarizeMatches',
    'toMarkdownQuote',
    'writeNaturalReply',
  ]);
});
