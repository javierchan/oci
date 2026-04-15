'use strict';

async function resolveAssistantQuoteRouting(options = {}, deps = {}) {
  const {
    cfg,
    index,
    conversation,
    userText = '',
    effectiveUserText = '',
    sessionContext,
    intent = {},
    topService = null,
    contextualFollowUp = false,
    compositeLike = false,
  } = options;
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

  const quoteCandidateState = prepareQuoteCandidateState({
    index,
    sessionContext,
    userText,
    effectiveUserText,
    intent,
    topService,
    contextualFollowUp,
    compositeLike,
  }, {
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
  });
  if (quoteCandidateState.fallbackPayload) {
    return {
      intent: {
        ...intent,
        ...(quoteCandidateState.intent || {}),
      },
      payload: quoteCandidateState.fallbackPayload,
    };
  }

  const nextIntent = {
    ...intent,
    ...(quoteCandidateState.intent || {}),
  };
  const familyMeta = quoteCandidateState.familyMeta;
  const reformulatedRequest = quoteCandidateState.reformulatedRequest;
  const preflightQuote = quoteCandidateState.preflightQuote;

  const quoteClarificationState = reconcileQuoteClarificationState({
    intent: nextIntent,
    reformulatedRequest,
    effectiveUserText,
    userText,
    familyMeta,
    preflightQuote,
    getPreQuoteClarification,
    getMissingRequiredInputs,
    getClarificationMessage,
  });

  return resolvePostClarificationRouting({
    cfg,
    index,
    conversation,
    userText,
    effectiveUserText,
    sessionContext,
    intent: nextIntent,
    familyMeta,
    reformulatedRequest,
    preflightQuote,
    quoteClarificationState,
  }, {
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
  });
}

module.exports = {
  resolveAssistantQuoteRouting,
};
