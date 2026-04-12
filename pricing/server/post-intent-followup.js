'use strict';

function reconcilePostIntentFollowUp({
  intent,
  effectiveUserText,
  userText,
  contextualFollowUp,
  conversation,
  initialFlexComparison,
  extractFlexComparisonContext,
}) {
  const nextIntent = {
    ...((intent && typeof intent === 'object' && intent) || {}),
  };
  const mergedContextualFollowUp = !!contextualFollowUp && String(effectiveUserText || '') !== String(userText || '');

  if (mergedContextualFollowUp) {
    nextIntent.reformulatedRequest = String(effectiveUserText || '').trim();
    nextIntent.normalizedRequest = String(effectiveUserText || '').trim();
  }
  if (contextualFollowUp && nextIntent?.reformulatedRequest) {
    nextIntent.normalizedRequest = String(nextIntent.reformulatedRequest).trim();
  }

  const postIntentFlexComparison = initialFlexComparison || (
    typeof extractFlexComparisonContext === 'function'
      ? extractFlexComparisonContext(
        conversation,
        userText,
        nextIntent?.reformulatedRequest || nextIntent?.normalizedRequest || '',
      )
      : null
  );

  return {
    intent: nextIntent,
    mergedContextualFollowUp,
    postIntentFlexComparison,
  };
}

module.exports = {
  reconcilePostIntentFollowUp,
};
