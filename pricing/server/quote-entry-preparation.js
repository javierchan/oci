'use strict';

function resolveEffectiveQuoteText(
  sessionContext,
  intent,
  userText,
  effectiveUserText,
  mergeSessionQuoteFollowUpByRoute,
) {
  const routeMergedFollowUp = mergeSessionQuoteFollowUpByRoute(sessionContext, intent, userText);
  return String(routeMergedFollowUp || effectiveUserText || userText || '').trim() || String(effectiveUserText || '').trim();
}

function shouldPromoteDeterministicTopService({
  effectiveUserText,
  compositeLike = false,
  topService = null,
  intent = {},
  interpretedFamilyMeta = null,
  serviceHasRequiredInputs,
  isDiscoveryOrExplanationQuestion,
}) {
  if (isDiscoveryOrExplanationQuestion(effectiveUserText)) return false;
  if (compositeLike) return false;
  if (!topService || !topService.deterministic) return false;
  if (!serviceHasRequiredInputs(topService, intent.extractedInputs)) return false;
  if (intent.serviceFamily && interpretedFamilyMeta) return false;
  return true;
}

function promoteDeterministicTopService(intent = {}, topService = {}, effectiveQuoteText = '') {
  const nextIntent = { ...intent };
  nextIntent.serviceName = topService.name;
  nextIntent.normalizedRequest = String(effectiveQuoteText || intent.normalizedRequest || '').trim();
  if (!nextIntent.shouldQuote || nextIntent.needsClarification) {
    nextIntent.intent = 'quote';
    nextIntent.shouldQuote = true;
    nextIntent.needsClarification = false;
    nextIntent.clarificationQuestion = '';
  }
  return nextIntent;
}

function resolveUnsupportedComputeVariantState(
  effectiveQuoteText,
  userText,
  interpretedFamilyMeta,
  findUncoveredComputeVariant,
  canSafelyQuoteUncoveredComputeVariant,
) {
  const requestText = String(effectiveQuoteText || userText || '').trim();
  const unsupportedComputeVariant = findUncoveredComputeVariant(requestText);
  const coveredNonComputeFamily = interpretedFamilyMeta && interpretedFamilyMeta.domain !== 'compute';
  return {
    requestText,
    unsupportedComputeVariant,
    shouldFallbackToDiscovery: Boolean(
      !coveredNonComputeFamily &&
      unsupportedComputeVariant &&
      !canSafelyQuoteUncoveredComputeVariant(unsupportedComputeVariant, requestText)
    ),
  };
}

function buildUnsupportedComputeFallbackPayload(
  unsupportedComputeState,
  intent = {},
  index,
  sessionContext,
  buildUncoveredComputeReply,
  buildAssistantContextPack,
  summarizeContextPack,
) {
  const nextIntent = {
    ...intent,
    route: 'product_discovery',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
  };
  return {
    ok: true,
    mode: 'answer',
    message: buildUncoveredComputeReply(unsupportedComputeState.requestText),
    contextPackSummary: summarizeContextPack(buildAssistantContextPack(index, {
      userText: unsupportedComputeState.requestText,
      intent: {
        ...intent,
        route: 'product_discovery',
        shouldQuote: false,
      },
      sessionContext,
    })),
    intent: nextIntent,
  };
}

function prepareQuoteEntry(options = {}, deps = {}) {
  const {
    sessionContext,
    intent = {},
    userText = '',
    effectiveUserText = '',
    compositeLike = false,
    topService = null,
    interpretedFamilyMeta = null,
    index,
  } = options;
  const {
    mergeSessionQuoteFollowUpByRoute,
    findUncoveredComputeVariant,
    canSafelyQuoteUncoveredComputeVariant,
    buildUncoveredComputeReply,
    buildAssistantContextPack,
    summarizeContextPack,
    serviceHasRequiredInputs,
    isDiscoveryOrExplanationQuestion,
  } = deps;

  const effectiveQuoteText = resolveEffectiveQuoteText(
    sessionContext,
    intent,
    userText,
    effectiveUserText,
    mergeSessionQuoteFollowUpByRoute,
  );
  const unsupportedComputeState = resolveUnsupportedComputeVariantState(
    effectiveQuoteText,
    userText,
    interpretedFamilyMeta,
    findUncoveredComputeVariant,
    canSafelyQuoteUncoveredComputeVariant,
  );
  if (intent.shouldQuote && unsupportedComputeState.shouldFallbackToDiscovery) {
    return {
      effectiveQuoteText,
      intent,
      unsupportedComputeState,
      fallbackPayload: buildUnsupportedComputeFallbackPayload(
        unsupportedComputeState,
        intent,
        index,
        sessionContext,
        buildUncoveredComputeReply,
        buildAssistantContextPack,
        summarizeContextPack,
      ),
    };
  }

  const nextIntent = shouldPromoteDeterministicTopService({
    effectiveUserText,
    compositeLike,
    topService,
    intent,
    interpretedFamilyMeta,
    serviceHasRequiredInputs,
    isDiscoveryOrExplanationQuestion,
  })
    ? promoteDeterministicTopService(intent, topService, effectiveQuoteText)
    : intent;

  return {
    effectiveQuoteText,
    intent: nextIntent,
    unsupportedComputeState,
    fallbackPayload: null,
  };
}

function prepareQuoteCandidateState(options = {}, deps = {}) {
  const {
    index,
    sessionContext,
    userText = '',
    effectiveUserText = '',
    intent = {},
    topService = null,
    contextualFollowUp = false,
    compositeLike = false,
  } = options;
  const {
    getServiceFamily,
    buildQuoteRequestShape,
    preserveCriticalPromptModifiers,
    choosePreferredQuote,
  } = deps;

  const interpretedFamilyMeta = getServiceFamily(intent.serviceFamily);
  const quoteEntry = prepareQuoteEntry({
    sessionContext,
    intent,
    userText,
    effectiveUserText,
    compositeLike,
    topService,
    interpretedFamilyMeta,
    index,
  }, deps);
  if (quoteEntry.fallbackPayload) {
    return {
      ...quoteEntry,
      familyMeta: interpretedFamilyMeta,
      reformulatedRequest: '',
      preflightQuote: null,
    };
  }

  const familyMeta = interpretedFamilyMeta;
  const quoteRequestShape = buildQuoteRequestShape({
    index,
    intent: quoteEntry.intent,
    effectiveQuoteText: quoteEntry.effectiveQuoteText,
    contextualFollowUp,
    compositeLike,
    familyMeta,
    preserveCriticalPromptModifiers,
    choosePreferredQuote,
  });

  return {
    ...quoteEntry,
    familyMeta,
    reformulatedRequest: quoteRequestShape.reformulatedRequest,
    preflightQuote: quoteRequestShape.preflightQuote,
  };
}

module.exports = {
  buildUnsupportedComputeFallbackPayload,
  prepareQuoteCandidateState,
  prepareQuoteEntry,
  promoteDeterministicTopService,
  resolveEffectiveQuoteText,
  resolveUnsupportedComputeVariantState,
  shouldPromoteDeterministicTopService,
};
