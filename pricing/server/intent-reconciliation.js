'use strict';

const { isDiscoveryOrExplanationQuestion } = require('./discovery-classifier');
const {
  buildHeuristicIntentFromText,
  shouldApplyHeuristicIntentOverride,
  applyDiscoveryIntentOverride,
} = require('./lightweight-intent');

function fallbackIntentOnAnalysisFailure(userText) {
  return buildHeuristicIntentFromText(userText);
}

function reconcileIntentWithHeuristics(userText, intent = {}) {
  const nextIntent = {
    ...((intent && typeof intent === 'object' && intent) || {}),
  };
  const heuristicIntent = buildHeuristicIntentFromText(userText);
  if (heuristicIntent && shouldApplyHeuristicIntentOverride(userText, nextIntent)) {
    Object.assign(nextIntent, heuristicIntent);
  }
  if (isDiscoveryOrExplanationQuestion(userText)) {
    Object.assign(nextIntent, applyDiscoveryIntentOverride(nextIntent));
  }
  return nextIntent;
}

module.exports = {
  fallbackIntentOnAnalysisFailure,
  reconcileIntentWithHeuristics,
};
