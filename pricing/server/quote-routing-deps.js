'use strict';

function buildDirectQuoteFastPathDeps(deps = {}) {
  const {
    buildCompositeQuoteFromSegments,
    buildQuoteNarrative,
    formatAssumptions,
    parsePromptRequest,
    quoteFromPrompt,
  } = deps;

  return {
    buildCompositeQuoteFromSegments,
    buildQuoteNarrative,
    formatAssumptions,
    parsePromptRequest,
    quoteFromPrompt,
  };
}

function buildPostClarificationRoutingDeps(deps = {}) {
  const {
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
  } = deps;

  return {
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
  };
}

function buildAssistantQuoteRoutingDeps(deps = {}) {
  const {
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
  } = deps;

  return {
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
    ...buildPostClarificationRoutingDeps(deps),
  };
}

module.exports = {
  buildAssistantQuoteRoutingDeps,
  buildDirectQuoteFastPathDeps,
  buildPostClarificationRoutingDeps,
};
