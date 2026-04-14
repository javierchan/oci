'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  buildDiscoveryRoutePayloadDeps,
  buildDiscoveryRoutingStateDeps,
  buildEarlyAssistantRoutingDeps,
  buildIntentPipelineDeps,
} = require(path.join(ROOT, 'assistant-orchestration-deps.js'));

test('assistant orchestration deps builds the early-routing dependency slice', () => {
  const deps = {
    buildEarlyAssistantReply: () => ({}),
    detectGenericComputeShapeClarification: () => null,
    extractFlexComparisonContext: () => null,
    resolveEarlyFlexComparisonClarification: () => null,
    isFlexComparisonRequest: () => false,
    detectFlexComparisonModifier: () => '',
    parseCapacityReservationUtilization: () => null,
    parseBurstableBaseline: () => null,
    buildFlexComparisonReplyPayload: () => null,
    buildFlexComparisonQuote: () => null,
    buildFlexComparisonNarrative: () => '',
    ignored: () => null,
  };

  const result = buildEarlyAssistantRoutingDeps(deps);

  assert.deepEqual(Object.keys(result).sort(), [
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
});

test('assistant orchestration deps builds the intent-pipeline dependency slice', () => {
  const deps = {
    analyzeIntent: async () => ({}),
    analyzeImageIntent: async () => ({}),
    fallbackIntentOnAnalysisFailure: () => ({}),
    buildServiceUnavailableMessage: () => '',
    enrichExtractedInputsForFamily: (intent) => intent,
    reconcileIntentWithHeuristics: (_text, intent) => intent,
    shouldForceQuoteFollowUpRoute: () => false,
    isSessionQuoteFollowUp: () => false,
    applyQuoteFollowUpIntentOverride: (intent) => intent,
    reconcilePostIntentFollowUp: () => ({ intent: {}, postIntentFlexComparison: null }),
    extractFlexComparisonContext: () => null,
    buildFlexComparisonReplyPayload: () => null,
    buildFlexComparisonQuote: () => null,
    buildFlexComparisonNarrative: () => '',
  };

  const result = buildIntentPipelineDeps(deps);

  assert.deepEqual(Object.keys(result).sort(), [
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
});

test('assistant orchestration deps builds both discovery dependency slices', () => {
  const deps = {
    buildRegistryQuery: () => '',
    searchServiceRegistry: () => [],
    serviceHasRequiredInputs: () => false,
    buildCatalogListingReply: () => '',
    buildAssistantContextPack: () => ({}),
    writeStructuredContextReply: async () => '',
    buildStructuredDiscoveryFallback: () => '',
    isConceptualPricingQuestion: () => false,
    hasExplicitQuoteLead: () => false,
    buildServiceUnavailableMessage: () => '',
    summarizeContextPack: () => ({}),
  };

  const stateDeps = buildDiscoveryRoutingStateDeps(deps);
  const payloadDeps = buildDiscoveryRoutePayloadDeps(deps);

  assert.deepEqual(Object.keys(stateDeps).sort(), [
    'buildCatalogListingReply',
    'buildRegistryQuery',
    'searchServiceRegistry',
    'serviceHasRequiredInputs',
  ]);
  assert.deepEqual(Object.keys(payloadDeps).sort(), [
    'buildAssistantContextPack',
    'buildServiceUnavailableMessage',
    'buildStructuredDiscoveryFallback',
    'hasExplicitQuoteLead',
    'isConceptualPricingQuestion',
    'summarizeContextPack',
    'writeStructuredContextReply',
  ]);
});
