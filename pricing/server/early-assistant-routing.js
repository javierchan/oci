'use strict';

function buildComputeShapeClarificationPayload(computeShapeClarification = null) {
  if (!computeShapeClarification) return null;
  return {
    ok: true,
    mode: 'clarification',
    message: computeShapeClarification.question,
    intent: {
      intent: 'quote',
      shouldQuote: true,
      needsClarification: true,
      clarificationQuestion: computeShapeClarification.question,
      serviceFamily: computeShapeClarification.serviceFamily,
      extractedInputs: computeShapeClarification.extractedInputs,
    },
  };
}

function buildDirectFlexReply(index, flexComparison, deps = {}) {
  const {
    buildFlexComparisonReplyPayload,
    buildFlexComparisonQuote,
    buildFlexComparisonNarrative,
  } = deps;
  return buildFlexComparisonReplyPayload({
    index,
    flexComparison,
    buildFlexComparisonQuote,
    buildFlexComparisonNarrative,
  });
}

function resolveEarlyFlexClarification(effectiveUserText, deps = {}) {
  const {
    resolveEarlyFlexComparisonClarification,
    isFlexComparisonRequest,
    detectFlexComparisonModifier,
    parseCapacityReservationUtilization,
    parseBurstableBaseline,
  } = deps;
  return resolveEarlyFlexComparisonClarification({
    effectiveUserText,
    isFlexComparisonRequest,
    detectFlexComparisonModifier,
    parseCapacityReservationUtilization,
    parseBurstableBaseline,
  });
}

function resolveEarlyAssistantRouting(options = {}, deps = {}) {
  const {
    conversation = [],
    userText = '',
    effectiveUserText = '',
    index,
  } = options;
  const {
    buildEarlyAssistantReply,
    detectGenericComputeShapeClarification,
    extractFlexComparisonContext,
  } = deps;

  const earlyAssistantReply = buildEarlyAssistantReply({ conversation, userText });
  if (earlyAssistantReply) {
    return {
      payload: earlyAssistantReply,
      flexComparison: extractFlexComparisonContext(conversation, userText),
    };
  }

  const computeShapeClarification = detectGenericComputeShapeClarification(effectiveUserText);
  if (computeShapeClarification) {
    return {
      payload: buildComputeShapeClarificationPayload(computeShapeClarification),
      flexComparison: extractFlexComparisonContext(conversation, userText),
    };
  }

  const flexComparison = extractFlexComparisonContext(conversation, userText);
  const earlyFlexClarification = resolveEarlyFlexClarification(effectiveUserText, deps);
  if (earlyFlexClarification) {
    return {
      payload: earlyFlexClarification,
      flexComparison,
    };
  }

  const directFlexReply = buildDirectFlexReply(index, flexComparison, deps);
  if (directFlexReply) {
    return {
      payload: directFlexReply,
      flexComparison,
    };
  }

  return {
    payload: null,
    flexComparison,
  };
}

module.exports = {
  buildComputeShapeClarificationPayload,
  buildDirectFlexReply,
  resolveEarlyAssistantRouting,
  resolveEarlyFlexClarification,
};
