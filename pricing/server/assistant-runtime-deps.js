'use strict';

const { quoteFromPrompt, parsePromptRequest } = require('./quotation-engine');
const { searchServiceRegistry, serviceHasRequiredInputs } = require('./catalog');
const { getServiceFamily, getMissingRequiredInputs, getClarificationMessage, getPreQuoteClarification } = require('./service-families');
const { buildAssistantContextPack, buildCatalogListingReply, buildStructuredDiscoveryFallback, buildUncoveredComputeReply, canSafelyQuoteUncoveredComputeVariant, findUncoveredComputeVariant, summarizeContextPack } = require('./context-packs');
const { buildServiceUnavailableMessage } = require('./assistant-response-helpers');
const { buildQuoteNarrative } = require('./assistant-quote-orchestrator');
const { writeNaturalReply, writeStructuredContextReply } = require('./assistant-reply-writers');
const { toMarkdownQuote } = require('./assistant-quote-rendering');
const { buildAssistantSessionContext } = require('./assistant-session-context');
const { buildCompositeQuoteFromSegments, choosePreferredQuote } = require('./composite-quote-builder');
const { detectFlexComparisonModifier, extractFlexComparisonContext, isFlexComparisonRequest, parseBurstableBaseline, parseCapacityReservationUtilization } = require('./flex-comparison-helpers');
const { buildRegistryQuery } = require('./request-query-helpers');
const { hasExplicitQuoteLead, isConceptualPricingQuestion, isDiscoveryOrExplanationQuestion } = require('./discovery-classifier');
const { fallbackIntentOnAnalysisFailure, reconcileIntentWithHeuristics } = require('./intent-reconciliation');
const { shouldForceQuoteFollowUpRoute, applyQuoteFollowUpIntentOverride } = require('./quote-followup-intent');
const { reconcilePostIntentFollowUp } = require('./post-intent-followup');
const { buildEarlyAssistantReply } = require('./early-assistant-replies');
const { detectGenericComputeShapeClarification } = require('./compute-shape-clarification');
const { buildQuoteUnresolvedPayload } = require('./quote-unresolved');
const { buildAnswerFallbackPayload } = require('./answer-fallback');
const { reconcileQuoteClarificationState } = require('./quote-clarification-state');
const { buildQuoteRequestShape } = require('./quote-request-shaping');
const { resolvePostClarificationRouting } = require('./post-clarification-routing');
const {
  buildDiscoveryRoutePayloadDeps,
  buildDiscoveryRoutingStateDeps,
  buildEarlyAssistantRoutingDeps,
  buildIntentPipelineDeps,
} = require('./assistant-orchestration-deps');
const {
  buildAssistantQuoteRoutingDeps,
  buildDirectQuoteFastPathDeps,
} = require('./quote-routing-deps');
const { prepareQuoteCandidateState } = require('./quote-entry-preparation');
const { mergeSessionQuoteFollowUp, mergeSessionQuoteFollowUpByRoute, preserveCriticalPromptModifiers } = require('./session-quote-followup');
const { isSessionQuoteFollowUp, isShortContextualAnswer, mergeClarificationAnswer } = require('./clarification-followup');
const { hasExplicitByolChoice, detectByolAmbiguity, filterQuoteByByolChoice, shouldAskLicenseChoice, buildLicenseChoiceClarificationPayload, buildByolAmbiguityClarificationPayload } = require('./license-choice');
const { formatAssumptions } = require('./quote-assumptions');
const { resolveEarlyFlexComparisonClarification, buildFlexComparisonQuote, buildFlexComparisonNarrative, buildFlexComparisonReplyPayload } = require('./flex-comparison-flow');
const { enrichExtractedInputsForFamily, isCompositeOrComparisonRequest, summarizeMatches } = require('./assistant-request-helpers');
const { analyzeIntent, analyzeImageIntent } = require('./intent-extractor');

function buildAssistantRuntimeDeps() {
  return {
    requestStateDeps: {
      mergeSessionQuoteFollowUp,
      mergeClarificationAnswer,
      isShortContextualAnswer,
      isCompositeOrComparisonRequest,
    },
    responseDeps: {
      buildAssistantSessionContext,
    },
    earlyRoutingDeps: buildEarlyAssistantRoutingDeps({
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
    }),
    directQuoteFastPathDeps: buildDirectQuoteFastPathDeps({
      buildCompositeQuoteFromSegments,
      buildQuoteNarrative,
      formatAssumptions,
      parsePromptRequest,
      quoteFromPrompt,
    }),
    intentPipelineDeps: buildIntentPipelineDeps({
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
    }),
    discoveryRoutingStateDeps: buildDiscoveryRoutingStateDeps({
      buildRegistryQuery,
      searchServiceRegistry,
      serviceHasRequiredInputs,
      buildCatalogListingReply,
    }),
    discoveryRoutePayloadDeps: buildDiscoveryRoutePayloadDeps({
      buildAssistantContextPack,
      writeStructuredContextReply,
      buildStructuredDiscoveryFallback,
      isConceptualPricingQuestion,
      hasExplicitQuoteLead,
      buildServiceUnavailableMessage,
      summarizeContextPack,
    }),
    assistantQuoteRoutingDeps: buildAssistantQuoteRoutingDeps({
      prepareQuoteCandidateState,
      getServiceFamily,
      mergeSessionQuoteFollowUpByRoute,
      findUncoveredComputeVariant,
      canSafelyQuoteUncoveredComputeVariant,
      buildUncoveredComputeReply,
      buildAssistantContextPack,
      summarizeContextPack,
      serviceHasRequiredInputs,
      isDiscoveryOrExplanationQuestion,
      buildQuoteRequestShape,
      preserveCriticalPromptModifiers,
      choosePreferredQuote,
      reconcileQuoteClarificationState,
      getPreQuoteClarification,
      getMissingRequiredInputs,
      getClarificationMessage,
      resolvePostClarificationRouting,
      hasExplicitByolChoice,
      shouldAskLicenseChoice,
      buildLicenseChoiceClarificationPayload,
      quoteFromPrompt,
      parsePromptRequest,
      formatAssumptions,
      detectByolAmbiguity,
      buildByolAmbiguityClarificationPayload,
      filterQuoteByByolChoice,
      toMarkdownQuote,
      buildQuoteNarrative,
      buildQuoteUnresolvedPayload,
      buildAnswerFallbackPayload,
      summarizeMatches,
      writeNaturalReply,
    }),
  };
}

module.exports = {
  buildAssistantRuntimeDeps,
};
