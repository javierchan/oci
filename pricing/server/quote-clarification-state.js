'use strict';

function reconcileQuoteClarificationState({
  intent,
  reformulatedRequest,
  effectiveUserText,
  userText,
  familyMeta,
  preflightQuote,
  getPreQuoteClarification,
  getMissingRequiredInputs,
  getClarificationMessage,
} = {}) {
  const nextIntent = {
    ...((intent && typeof intent === 'object' && intent) || {}),
  };

  const preQuoteClarification = typeof getPreQuoteClarification === 'function'
    ? getPreQuoteClarification({
      ...nextIntent,
      extractedInputs: nextIntent.extractedInputs || {},
      reformulatedRequest,
    }, effectiveUserText || userText)
    : '';
  if (nextIntent.shouldQuote && preQuoteClarification) {
    return {
      intent: {
        ...nextIntent,
        needsClarification: true,
        clarificationQuestion: preQuoteClarification,
      },
      missingInputs: [],
      canQuoteDespiteMissingInputs: false,
      clarificationPayload: {
        ok: true,
        mode: 'clarification',
        message: preQuoteClarification,
        intent: {
          ...nextIntent,
          needsClarification: true,
          clarificationQuestion: preQuoteClarification,
        },
      },
    };
  }

  const missingInputs = typeof getMissingRequiredInputs === 'function'
    ? getMissingRequiredInputs(nextIntent)
    : [];
  const canQuoteDespiteMissingInputs = !!(familyMeta && missingInputs.length && preflightQuote?.ok);
  if (familyMeta && nextIntent.shouldQuote && (!missingInputs.length || canQuoteDespiteMissingInputs)) {
    nextIntent.needsClarification = false;
    nextIntent.clarificationQuestion = '';
  }

  if (familyMeta && missingInputs.length && familyMeta.clarificationQuestion && !canQuoteDespiteMissingInputs) {
    const clarificationMessage = (
      typeof getClarificationMessage === 'function'
        ? getClarificationMessage(nextIntent, effectiveUserText || userText)
        : ''
    ) || familyMeta.clarificationQuestion;
    return {
      intent: {
        ...nextIntent,
        needsClarification: true,
        clarificationQuestion: clarificationMessage,
      },
      missingInputs,
      canQuoteDespiteMissingInputs,
      clarificationPayload: {
        ok: true,
        mode: 'clarification',
        message: clarificationMessage,
        intent: {
          ...nextIntent,
          needsClarification: true,
          clarificationQuestion: clarificationMessage,
        },
      },
    };
  }

  return {
    intent: nextIntent,
    missingInputs,
    canQuoteDespiteMissingInputs,
    clarificationPayload: null,
  };
}

module.exports = {
  reconcileQuoteClarificationState,
};
