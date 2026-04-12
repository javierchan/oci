'use strict';

const { quoteFromPrompt, parsePromptRequest } = require('./quotation-engine');
const {
  buildCanonicalRequest,
  getActiveQuoteFollowUpReplacementRules,
  normalizeExtractedInputsForFamily,
} = require('./service-families');

function normalizeFamilyIntent(intent = {}, normalizeInputs = normalizeExtractedInputsForFamily) {
  return {
    ...intent,
    extractedInputs: normalizeInputs(intent.serviceFamily, intent.extractedInputs),
  };
}

function preservesFamilyReplacementSignals(
  source,
  candidate,
  familyId,
  getRules = getActiveQuoteFollowUpReplacementRules,
) {
  const base = String(source || '').trim();
  const next = String(candidate || '').trim();
  if (!base || !next || !familyId) return true;
  for (const rule of getRules(familyId)) {
    if (!rule.sourcePattern.test(base)) continue;
    if (rule.targetPattern && !rule.targetPattern.test(next)) return false;
  }
  return true;
}

function buildQuoteRequestShape(options = {}, deps = {}) {
  const {
    index,
    intent = {},
    effectiveQuoteText = '',
    contextualFollowUp = false,
    compositeLike = false,
    familyMeta = null,
    preserveCriticalPromptModifiers = (prompt) => String(prompt || '').trim(),
    choosePreferredQuote = (primary, secondary) => secondary || primary || null,
  } = options;
  const {
    buildCanonicalRequest: buildCanonicalRequestImpl = buildCanonicalRequest,
    getActiveQuoteFollowUpReplacementRules: getActiveQuoteFollowUpReplacementRulesImpl = getActiveQuoteFollowUpReplacementRules,
    normalizeExtractedInputsForFamily: normalizeExtractedInputsForFamilyImpl = normalizeExtractedInputsForFamily,
    parsePromptRequest: parsePromptRequestImpl = parsePromptRequest,
    quoteFromPrompt: quoteFromPromptImpl = quoteFromPrompt,
  } = deps;

  const parsedEffectiveQuoteRequest = familyMeta
    ? (parsePromptRequestImpl(effectiveQuoteText) || {})
    : {};
  const canonicalFamilyInputs = familyMeta
    ? {
      ...parsedEffectiveQuoteRequest,
      ...((intent && typeof intent.extractedInputs === 'object' && intent.extractedInputs) || {}),
    }
    : {};
  const canonicalFamilyIntent = familyMeta
    ? normalizeFamilyIntent({
      ...intent,
      extractedInputs: canonicalFamilyInputs,
    }, normalizeExtractedInputsForFamilyImpl)
    : intent;
  const canonicalFamilyRequest = !compositeLike && familyMeta
    ? String(buildCanonicalRequestImpl(canonicalFamilyIntent, effectiveQuoteText) || '').trim()
    : '';
  const preferredCanonicalFamilyRequest = preservesFamilyReplacementSignals(
    effectiveQuoteText,
    canonicalFamilyRequest,
    intent.serviceFamily,
    getActiveQuoteFollowUpReplacementRulesImpl,
  )
    ? canonicalFamilyRequest
    : '';
  const fallbackFamilyRequest = String(
    (contextualFollowUp
      ? (intent.reformulatedRequest || intent.normalizedRequest)
      : (intent.normalizedRequest || intent.reformulatedRequest))
      || effectiveQuoteText,
  ).trim() || effectiveQuoteText;
  const reformulatedRequest = preserveCriticalPromptModifiers(
    compositeLike
      ? effectiveQuoteText
      : familyMeta
        ? (preferredCanonicalFamilyRequest || fallbackFamilyRequest)
        : effectiveQuoteText,
    effectiveQuoteText,
  );
  const preflightQuote = !compositeLike && familyMeta
    ? choosePreferredQuote(
      quoteFromPromptImpl(index, effectiveQuoteText),
      quoteFromPromptImpl(index, reformulatedRequest),
    )
    : null;

  return {
    canonicalFamilyInputs,
    canonicalFamilyIntent,
    canonicalFamilyRequest,
    preferredCanonicalFamilyRequest,
    reformulatedRequest,
    preflightQuote,
  };
}

module.exports = {
  buildQuoteRequestShape,
  normalizeFamilyIntent,
  preservesFamilyReplacementSignals,
};
