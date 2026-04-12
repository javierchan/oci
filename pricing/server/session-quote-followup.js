'use strict';

const { parsePromptRequest } = require('./quotation-engine');
const {
  buildCanonicalRequest,
  getActiveQuoteFollowUpReplacementRules,
  getCompositeFollowUpRemovalRules,
  getFamiliesWithActiveQuoteFollowUpRules,
  getServiceFamily,
  inferServiceFamily,
  supportsFollowUpCapability,
} = require('./service-families');
const { isDiscoveryOrExplanationQuestion } = require('./discovery-classifier');
const {
  extractInlineShapeSelection,
  extractLicenseModeDirective,
  isSessionQuoteFollowUp,
  isShapeSelectionFollowUp,
  replaceShapeInPrompt,
  stripQuotePrefix,
} = require('./clarification-followup');

const FLEX_SHAPE_TOKEN_PATTERN_SOURCE = '(?:(?:vm|bm)\\.)?(?:(?:[a-z][a-z0-9]*)\\.)*(?:[a-z]+\\d+|[a-z]\\d+)\\.flex';
const FLEX_SHAPE_TOKEN_INLINE_PATTERN = new RegExp(`\\b${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}\\b`, 'i');

const SESSION_FOLLOW_UP_REMOVAL_RULES = getCompositeFollowUpRemovalRules();
const SESSION_FOLLOW_UP_REPLACEMENT_RULES = [];

function removeCompositeServiceSegment(basePrompt, pattern) {
  const source = String(basePrompt || '').trim();
  if (!source) return source;
  const prefixMatch = source.match(/^\s*quote\s+/i);
  const prefix = prefixMatch ? prefixMatch[0] : '';
  const body = prefix ? source.slice(prefix.length).trim() : source;
  const separators = /\s+\+\s+|\s+plus\s+/i;
  if (!separators.test(body)) return source;
  const kept = body
    .split(separators)
    .map((segment) => segment.trim())
    .filter(Boolean)
    .filter((segment) => !(new RegExp(pattern, 'i')).test(segment));
  if (!kept.length) return source;
  return `${prefix}${kept.join(' plus ')}`.trim();
}

function appendCompositeServiceSegment(basePrompt, segment) {
  const source = String(basePrompt || '').trim();
  const nextSegment = stripQuotePrefix(segment);
  if (!nextSegment) return source;
  if (!source) return `Quote ${nextSegment}`.trim();
  const prefixMatch = source.match(/^\s*quote\s+/i);
  const prefix = prefixMatch ? prefixMatch[0] : 'Quote ';
  const body = prefixMatch ? source.slice(prefix.length).trim() : source;
  const existingSegments = body
    .split(/\s+\+\s+|\s+plus\s+/i)
    .map((item) => stripQuotePrefix(item).toLowerCase())
    .filter(Boolean);
  if (existingSegments.includes(nextSegment.toLowerCase())) return source;
  return `${prefix}${body} plus ${nextSegment}`.trim();
}

function parseCapacityReservationUtilization(text) {
  const source = String(text || '');
  const match = source.match(/\b(?:capacity reservation(?: utilization)?|reservation utilization)\s*[:=]?\s*(\d+(?:\.\d+)?)\b/i);
  if (!match) return null;
  return Number(match[1]);
}

function parseBurstableBaseline(text) {
  const source = String(text || '');
  const match = source.match(/\bburstable(?: baseline)?\s*[:=]?\s*(\d+(?:\.\d+)?)\b/i) || source.match(/\bbaseline\s*[:=]?\s*(\d+(?:\.\d+)?)\b/i);
  if (!match) return null;
  return Number(match[1]);
}

function extractFollowUpModifierDirective(text) {
  const source = String(text || '').trim();
  if (!source) return '';
  if (/\bpreemptible\b/i.test(source)) return 'preemptible';
  const capacityReservationUtilization = parseCapacityReservationUtilization(source);
  if (capacityReservationUtilization !== null) return `capacity reservation ${capacityReservationUtilization}`;
  const burstableBaseline = parseBurstableBaseline(source);
  if (burstableBaseline !== null) return `burstable baseline ${burstableBaseline}`;
  return '';
}

function replaceOrAppendPattern(basePrompt, regex, replacement) {
  const source = String(basePrompt || '').trim();
  if (!source) return String(replacement || '').trim();
  if (regex.test(source)) return source.replace(regex, replacement);
  return `${source} ${replacement}`.trim();
}

function replaceCurrencyInPrompt(basePrompt, currencyCode) {
  const source = String(basePrompt || '').trim();
  const nextCode = String(currencyCode || '').trim().toUpperCase();
  if (!source || !nextCode) return source;
  if (/\b(?:USD|MXN|EUR|BRL|GBP|CAD|JPY)\b/i.test(source)) {
    return source.replace(/\b(?:USD|MXN|EUR|BRL|GBP|CAD|JPY)\b/i, nextCode);
  }
  return `${source} ${nextCode}`.trim();
}

function applyFollowUpReplacementRule(nextPrompt, source, rule) {
  const sourceMatch = String(source || '').match(rule.sourcePattern)?.[0];
  if (!sourceMatch) return nextPrompt;
  if (typeof rule.apply === 'function') return rule.apply(nextPrompt, sourceMatch, source);
  if (!rule.targetPattern) return nextPrompt;
  return nextPrompt.replace(rule.targetPattern, sourceMatch);
}

function applyActiveQuoteFamilyFollowUpReplacements(nextPrompt, source, familyId) {
  let updatedPrompt = String(nextPrompt || '').trim();
  let matched = false;
  for (const rule of getActiveQuoteFollowUpReplacementRules(familyId)) {
    if (!rule.sourcePattern.test(source)) continue;
    updatedPrompt = applyFollowUpReplacementRule(updatedPrompt, source, rule);
    matched = true;
  }
  return { nextPrompt: updatedPrompt, matched };
}

function resolveCompositeFollowUpReplacementFamily(nextPrompt, source, preferredFamilyIds = []) {
  const prompt = String(nextPrompt || '').trim();
  const followUp = String(source || '').trim();
  if (!prompt || !followUp) return '';
  const seen = new Set();
  const orderedFamilies = [
    ...preferredFamilyIds.filter(Boolean),
    ...getFamiliesWithActiveQuoteFollowUpRules(),
  ].filter((familyId) => {
    if (seen.has(familyId)) return false;
    seen.add(familyId);
    return true;
  });
  const matches = orderedFamilies.filter((familyId) => getActiveQuoteFollowUpReplacementRules(familyId).some((rule) => (
    rule.sourcePattern.test(followUp) && (!rule.targetPattern || rule.targetPattern.test(prompt))
  )));
  return matches.length === 1 ? matches[0] : '';
}

function parseCompositeFollowUpReplacement(followUp) {
  const source = String(followUp || '').trim();
  const match = source.match(/\b(?:replace|swap|switch|cambia(?:r)?|reemplaza|sustituye)\s+(.+?)\s+(?:with|for|por)\s+(.+)/i);
  if (!match) return null;
  const sourceText = String(match[1] || '').trim();
  const targetText = String(match[2] || '').trim();
  const sourceFamilyId = inferServiceFamily(sourceText);
  const targetFamilyId = inferServiceFamily(targetText);
  if (!sourceFamilyId || !targetFamilyId || sourceFamilyId === targetFamilyId) return null;
  return {
    sourceText,
    targetText,
    sourceFamilyId,
    targetFamilyId,
  };
}

function buildCompositeReplacementSegment(targetText, targetFamilyId) {
  const source = String(targetText || '').trim();
  if (!source || !targetFamilyId) return '';
  const parsed = parsePromptRequest(source) || {};
  const canonical = String(buildCanonicalRequest({
    serviceFamily: targetFamilyId,
    extractedInputs: parsed,
    reformulatedRequest: source,
    normalizedRequest: source,
  }, source) || '').trim();
  if (canonical) return stripQuotePrefix(canonical);
  return stripQuotePrefix(source);
}

function applySessionFollowUpDirective(basePrompt, followUp, options = {}) {
  const source = String(followUp || '').trim();
  let nextPrompt = String(basePrompt || '').trim();
  let suppressFallbackAppend = false;
  let matchedCompositeReplacement = false;
  let matchedCompositeRemoval = false;
  const activeFamilyId = String(options.activeFamily?.familyId || '').trim();
  const activeFamilyInputs = (options.activeFamily && typeof options.activeFamily.parsed === 'object' && options.activeFamily.parsed) || {};
  const followUpFamilyId = String(options.followUpFamilyId || '').trim();
  if (!source) return nextPrompt;

  if (isShapeSelectionFollowUp(source) && FLEX_SHAPE_TOKEN_INLINE_PATTERN.test(nextPrompt)) {
    nextPrompt = replaceShapeInPrompt(nextPrompt, source);
    suppressFallbackAppend = true;
  }

  const inlineShapeSelection = extractInlineShapeSelection(source);
  if (!isShapeSelectionFollowUp(source) && inlineShapeSelection && FLEX_SHAPE_TOKEN_INLINE_PATTERN.test(nextPrompt)) {
    nextPrompt = replaceShapeInPrompt(nextPrompt, inlineShapeSelection);
    suppressFallbackAppend = true;
  }

  const compositeReplacement = parseCompositeFollowUpReplacement(source);
  if (compositeReplacement) {
    const sourceFamily = getServiceFamily(compositeReplacement.sourceFamilyId);
    const removeDirective = sourceFamily?.followUpDirectives?.removeFromComposite;
    const sourceAllowed = supportsFollowUpCapability(compositeReplacement.sourceFamilyId, 'compositeReplaceSource');
    const targetAllowed = supportsFollowUpCapability(compositeReplacement.targetFamilyId, 'compositeReplaceTarget');
    const targetSegment = sourceAllowed && targetAllowed
      ? buildCompositeReplacementSegment(
        compositeReplacement.targetText,
        compositeReplacement.targetFamilyId,
      )
      : '';
    suppressFallbackAppend = true;
    if (removeDirective && targetSegment) {
      matchedCompositeReplacement = true;
      nextPrompt = appendCompositeServiceSegment(
        removeCompositeServiceSegment(nextPrompt, removeDirective.segmentPattern),
        targetSegment,
      );
    }
  }

  for (const rule of SESSION_FOLLOW_UP_REMOVAL_RULES) {
    if (rule.detect.test(source)) {
      nextPrompt = removeCompositeServiceSegment(nextPrompt, rule.segmentPattern);
      matchedCompositeRemoval = true;
      suppressFallbackAppend = true;
    }
  }

  if (/\b(?:mxn|usd|eur|brl|gbp|cad|jpy)\b/i.test(source)) {
    const code = source.match(/\b(mxn|usd|eur|brl|gbp|cad|jpy)\b/i)?.[1]?.toUpperCase();
    if (code) nextPrompt = replaceCurrencyInPrompt(nextPrompt, code);
  }

  const licenseMode = extractLicenseModeDirective(source);
  if (licenseMode) {
    suppressFallbackAppend = true;
    if (supportsFollowUpCapability(activeFamilyId, 'licenseMode', activeFamilyInputs)) {
      nextPrompt = replaceOrAppendPattern(nextPrompt, /\b(?:BYOL|License Included)\b/i, licenseMode);
    }
  }

  const familyReplacement = (matchedCompositeRemoval || matchedCompositeReplacement)
    ? { nextPrompt, matched: false }
    : applyActiveQuoteFamilyFollowUpReplacements(nextPrompt, source, activeFamilyId);
  nextPrompt = familyReplacement.nextPrompt;
  let matchedFamilyReplacement = familyReplacement.matched;

  if (!matchedCompositeRemoval && !matchedCompositeReplacement && !matchedFamilyReplacement && followUpFamilyId && followUpFamilyId !== activeFamilyId) {
    const followUpFamilyReplacement = applyActiveQuoteFamilyFollowUpReplacements(nextPrompt, source, followUpFamilyId);
    nextPrompt = followUpFamilyReplacement.nextPrompt;
    matchedFamilyReplacement = followUpFamilyReplacement.matched;
  }

  if (!matchedCompositeRemoval && !matchedCompositeReplacement && !matchedFamilyReplacement) {
    const compositeFamilyId = resolveCompositeFollowUpReplacementFamily(nextPrompt, source, [
      followUpFamilyId,
      activeFamilyId,
    ]);
    if (compositeFamilyId) {
      const compositeFamilyReplacement = applyActiveQuoteFamilyFollowUpReplacements(nextPrompt, source, compositeFamilyId);
      nextPrompt = compositeFamilyReplacement.nextPrompt;
      matchedFamilyReplacement = compositeFamilyReplacement.matched;
    }
  }

  if (matchedFamilyReplacement) suppressFallbackAppend = true;

  if (!matchedFamilyReplacement) {
    for (const rule of SESSION_FOLLOW_UP_REPLACEMENT_RULES) {
      if (!rule.sourcePattern.test(source)) continue;
      nextPrompt = applyFollowUpReplacementRule(nextPrompt, source, rule);
      if (/\bsms messages?\b/i.test(String(source.match(rule.sourcePattern)?.[0] || ''))) break;
    }
  }

  const modifierDirective = extractFollowUpModifierDirective(source);
  if (modifierDirective) {
    nextPrompt = replaceOrAppendPattern(
      nextPrompt,
      /\b(?:preemptible|capacity reservation(?: utilization)?\s*[:=]?\s*\d+(?:\.\d+)?|burstable(?: baseline)?\s*[:=]?\s*\d+(?:\.\d+)?)\b/i,
      modifierDirective,
    );
    suppressFallbackAppend = true;
  }

  if (nextPrompt !== String(basePrompt || '').trim()) return nextPrompt.trim();
  if (suppressFallbackAppend) return nextPrompt.trim();
  return `${String(basePrompt || '').trim()} ${source}`.trim();
}

function getActiveQuoteFamilyContext(sessionContext = {}) {
  const lastQuote = sessionContext?.lastQuote || {};
  const source = String(lastQuote.source || '').trim();
  const parsed = source ? (parsePromptRequest(source) || {}) : {};
  const declaredFamilyId = String(lastQuote.serviceFamily || parsed.serviceFamily || '').trim();
  const inferredFamilyId = String(
    FLEX_SHAPE_TOKEN_INLINE_PATTERN.test(source)
      ? 'compute_flex'
      : (inferServiceFamily(source) || '')
  ).trim();
  const preferInferredFamily = declaredFamilyId === 'compute_vm_generic' && inferredFamilyId && inferredFamilyId !== declaredFamilyId;
  const familyId = String(
    preferInferredFamily
      ? inferredFamilyId
      : getServiceFamily(declaredFamilyId)
      ? declaredFamilyId
      : (inferredFamilyId || declaredFamilyId)
  ).trim();
  return {
    familyId,
    familyMeta: familyId ? getServiceFamily(familyId) : null,
    parsed,
  };
}

function mergeSessionQuoteFollowUpByRoute(sessionContext, intent, userText) {
  const route = String(intent?.route || '').trim().toLowerCase();
  const lastQuoteSource = String(sessionContext?.lastQuote?.source || '').trim();
  const source = String(userText || '').trim();
  if (route !== 'quote_followup' || !lastQuoteSource || !source) return '';
  return applySessionFollowUpDirective(lastQuoteSource, source, {
    activeFamily: getActiveQuoteFamilyContext(sessionContext),
    followUpFamilyId: intent?.serviceFamily,
  });
}

function preserveCriticalPromptModifiers(basePrompt, referencePrompt) {
  let nextPrompt = String(basePrompt || '').trim();
  const reference = String(referencePrompt || '').trim();
  if (!nextPrompt || !reference) return nextPrompt;
  if (/\bmetered\b/i.test(reference) && !/\bmetered\b/i.test(nextPrompt)) {
    nextPrompt = `${nextPrompt} metered`.trim();
  }
  return nextPrompt;
}

function mergeSessionQuoteFollowUp(sessionContext, userText) {
  const source = String(userText || '').trim();
  if (isDiscoveryOrExplanationQuestion(source)) return source;
  if (!isSessionQuoteFollowUp(source)) return source;
  const lastQuoteSource = String(sessionContext?.lastQuote?.source || '').trim();
  if (!lastQuoteSource) return source;
  const normalized = source
    .replace(/^(?:y|and|ahora|now)\s+/i, '')
    .trim();
  if (!normalized) return lastQuoteSource;
  return applySessionFollowUpDirective(lastQuoteSource, normalized, {
    activeFamily: getActiveQuoteFamilyContext(sessionContext),
    followUpFamilyId: inferServiceFamily(normalized),
  });
}

module.exports = {
  applySessionFollowUpDirective,
  getActiveQuoteFamilyContext,
  mergeSessionQuoteFollowUp,
  mergeSessionQuoteFollowUpByRoute,
  preserveCriticalPromptModifiers,
};
