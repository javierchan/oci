'use strict';

const { inferServiceFamily, getServiceFamily } = require('./service-families');
const { normalizeIntentResult } = require('./normalizer');
const { hasExplicitQuoteLead, isConceptualPricingQuestion, isDiscoveryOrExplanationQuestion } = require('./discovery-classifier');

function buildHeuristicIntentFromText(userText) {
  const source = String(userText || '').trim();
  if (!source) return null;
  if (!hasExplicitQuoteLead(source) && !isConceptualPricingQuestion(source)) return null;
  const inferredFamily = inferServiceFamily(source);
  const family = getServiceFamily(inferredFamily);
  if (!family && !hasExplicitQuoteLead(source)) return null;
  const baseIntent = {
    intent: hasExplicitQuoteLead(source) ? 'quote' : 'discover',
    route: hasExplicitQuoteLead(source) ? 'quote_request' : 'product_discovery',
    shouldQuote: hasExplicitQuoteLead(source),
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: source,
    assumptions: [],
    serviceFamily: inferredFamily || '',
    serviceName: family?.canonical || '',
    extractedInputs: {},
    confidence: 0.35,
    annualRequested: /\bannual(?:ly)?\b/i.test(source),
    quotePlan: {},
  };
  return normalizeIntentResult(baseIntent, source);
}

function shouldApplyHeuristicIntentOverride(userText, intent = {}) {
  const source = String(userText || '').trim();
  if (!source) return false;
  return (
    (hasExplicitQuoteLead(source) && (!intent.shouldQuote || intent.route === 'general_answer')) ||
    (isDiscoveryOrExplanationQuestion(source) && intent.route === 'general_answer')
  );
}

function applyDiscoveryIntentOverride(intent = {}) {
  return {
    ...intent,
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    quotePlan: {
      ...((intent.quotePlan && typeof intent.quotePlan === 'object' && intent.quotePlan) || {}),
      action: 'discover',
      targetType: 'service',
      useDeterministicEngine: false,
    },
  };
}

module.exports = {
  buildHeuristicIntentFromText,
  shouldApplyHeuristicIntentOverride,
  applyDiscoveryIntentOverride,
};
