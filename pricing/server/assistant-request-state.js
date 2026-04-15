'use strict';

function buildAssistantRequestState(options = {}, deps = {}) {
  const {
    conversation,
    userText = '',
    sessionContext,
  } = options;
  const {
    mergeSessionQuoteFollowUp,
    mergeClarificationAnswer,
    isShortContextualAnswer,
    isCompositeOrComparisonRequest,
  } = deps;

  const effectiveUserText = mergeSessionQuoteFollowUp(
    sessionContext,
    mergeClarificationAnswer(conversation, userText),
  );

  return {
    effectiveUserText,
    contextualFollowUp: isShortContextualAnswer(userText),
    compositeLike: isCompositeOrComparisonRequest(effectiveUserText),
  };
}

function buildAssistantResponse(payload = {}, sessionContext, effectiveUserText = '', deps = {}) {
  const {
    buildAssistantSessionContext,
  } = deps;

  return {
    ...payload,
    sessionContext: buildAssistantSessionContext(sessionContext, effectiveUserText, payload),
  };
}

module.exports = {
  buildAssistantRequestState,
  buildAssistantResponse,
};
