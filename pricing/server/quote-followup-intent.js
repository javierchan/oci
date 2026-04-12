'use strict';

const { isDiscoveryOrExplanationQuestion } = require('./discovery-classifier');

function shouldForceQuoteFollowUpRoute({ sessionContext, userText, isSessionQuoteFollowUp }) {
  const source = String(userText || '').trim();
  if (!String(sessionContext?.lastQuote?.source || '').trim()) return false;
  if (isDiscoveryOrExplanationQuestion(source)) return false;
  if (typeof isSessionQuoteFollowUp !== 'function' || !isSessionQuoteFollowUp(source)) return false;
  if (/\b(?:how|what|why|which|que|qué|como|cómo|cual|cuál|opciones?|difference|diff|billing|priced|billed|cobra)\b/i.test(source)) {
    return false;
  }
  return true;
}

function applyQuoteFollowUpIntentOverride(intent = {}) {
  return {
    ...intent,
    route: 'quote_followup',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    quotePlan: {
      ...((intent.quotePlan && typeof intent.quotePlan === 'object' && intent.quotePlan) || {}),
      action: 'modify_quote',
      targetType: 'quote',
      useDeterministicEngine: true,
    },
  };
}

module.exports = {
  shouldForceQuoteFollowUpRoute,
  applyQuoteFollowUpIntentOverride,
};
