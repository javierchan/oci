'use strict';

async function resolveIntentPipeline(options = {}, deps = {}) {
  const {
    cfg,
    conversation,
    effectiveUserText = '',
    userText = '',
    imageDataUrl,
    sessionContext,
    contextualFollowUp = false,
    flexComparison = null,
    index,
  } = options;
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

  let analyzedIntent;
  try {
    analyzedIntent = imageDataUrl
      ? await analyzeImageIntent(cfg, effectiveUserText, imageDataUrl)
      : await analyzeIntent(cfg, conversation, effectiveUserText, sessionContext);
  } catch (_error) {
    analyzedIntent = fallbackIntentOnAnalysisFailure(effectiveUserText || userText);
    if (!analyzedIntent) {
      return {
        intent: null,
        postIntentFlexComparison: flexComparison,
        payload: {
          ok: true,
          mode: 'answer',
          message: buildServiceUnavailableMessage(userText),
          intent: {
            intent: 'answer',
            route: 'general_answer',
            shouldQuote: false,
            needsClarification: false,
          },
        },
      };
    }
  }

  const enrichedIntent = reconcileIntentWithHeuristics(
    effectiveUserText,
    enrichExtractedInputsForFamily(analyzedIntent),
  );
  if (shouldForceQuoteFollowUpRoute({
    sessionContext,
    userText,
    isSessionQuoteFollowUp,
  }) && enrichedIntent.route !== 'quote_followup') {
    Object.assign(enrichedIntent, applyQuoteFollowUpIntentOverride(enrichedIntent));
  }

  const postIntentFollowUp = reconcilePostIntentFollowUp({
    intent: enrichedIntent,
    effectiveUserText,
    userText,
    contextualFollowUp,
    conversation,
    initialFlexComparison: flexComparison,
    extractFlexComparisonContext,
  });
  Object.assign(enrichedIntent, postIntentFollowUp.intent);
  const postIntentFlexComparison = postIntentFollowUp.postIntentFlexComparison;
  const postIntentFlexReply = buildFlexComparisonReplyPayload({
    index,
    flexComparison: postIntentFlexComparison,
    buildFlexComparisonQuote,
    buildFlexComparisonNarrative,
  });

  return {
    intent: enrichedIntent,
    postIntentFlexComparison,
    payload: postIntentFlexReply || null,
  };
}

module.exports = {
  resolveIntentPipeline,
};
