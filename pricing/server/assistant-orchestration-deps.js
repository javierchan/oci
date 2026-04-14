'use strict';

function buildEarlyAssistantRoutingDeps(deps = {}) {
  const {
    buildEarlyAssistantReply,
    detectGenericComputeShapeClarification,
    extractFlexComparisonContext,
    resolveEarlyFlexComparisonClarification,
    isFlexComparisonRequest,
    detectFlexComparisonModifier,
    parseCapacityReservationUtilization,
    parseBurstableBaseline,
    buildFlexComparisonReplyPayload,
    buildFlexComparisonQuote,
    buildFlexComparisonNarrative,
  } = deps;

  return {
    buildEarlyAssistantReply,
    detectGenericComputeShapeClarification,
    extractFlexComparisonContext,
    resolveEarlyFlexComparisonClarification,
    isFlexComparisonRequest,
    detectFlexComparisonModifier,
    parseCapacityReservationUtilization,
    parseBurstableBaseline,
    buildFlexComparisonReplyPayload,
    buildFlexComparisonQuote,
    buildFlexComparisonNarrative,
  };
}

function buildIntentPipelineDeps(deps = {}) {
  const {
    analyzeIntent,
    analyzeImageIntent,
    fallbackIntentOnAnalysisFailure,
    buildServiceUnavailableMessage,
    enrichExtractedInputsForFamily,
    reconcileIntentWithHeuristics,
    shouldForceQuoteFollowUpRoute,
    isSessionQuoteFollowUp,
    applyQuoteFollowUpIntentOverride,
    reconcilePostIntentFollowUp,
    extractFlexComparisonContext,
    buildFlexComparisonReplyPayload,
    buildFlexComparisonQuote,
    buildFlexComparisonNarrative,
  } = deps;

  return {
    analyzeIntent,
    analyzeImageIntent,
    fallbackIntentOnAnalysisFailure,
    buildServiceUnavailableMessage,
    enrichExtractedInputsForFamily,
    reconcileIntentWithHeuristics,
    shouldForceQuoteFollowUpRoute,
    isSessionQuoteFollowUp,
    applyQuoteFollowUpIntentOverride,
    reconcilePostIntentFollowUp,
    extractFlexComparisonContext,
    buildFlexComparisonReplyPayload,
    buildFlexComparisonQuote,
    buildFlexComparisonNarrative,
  };
}

function buildDiscoveryRoutingStateDeps(deps = {}) {
  const {
    buildRegistryQuery,
    searchServiceRegistry,
    serviceHasRequiredInputs,
    buildCatalogListingReply,
  } = deps;

  return {
    buildRegistryQuery,
    searchServiceRegistry,
    serviceHasRequiredInputs,
    buildCatalogListingReply,
  };
}

function buildDiscoveryRoutePayloadDeps(deps = {}) {
  const {
    buildAssistantContextPack,
    writeStructuredContextReply,
    buildStructuredDiscoveryFallback,
    isConceptualPricingQuestion,
    hasExplicitQuoteLead,
    buildServiceUnavailableMessage,
    summarizeContextPack,
  } = deps;

  return {
    buildAssistantContextPack,
    writeStructuredContextReply,
    buildStructuredDiscoveryFallback,
    isConceptualPricingQuestion,
    hasExplicitQuoteLead,
    buildServiceUnavailableMessage,
    summarizeContextPack,
  };
}

module.exports = {
  buildDiscoveryRoutePayloadDeps,
  buildDiscoveryRoutingStateDeps,
  buildEarlyAssistantRoutingDeps,
  buildIntentPipelineDeps,
};
