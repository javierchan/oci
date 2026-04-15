'use strict';

const { searchProducts, searchPresets } = require('./catalog');
const {
  hasCompositeServiceSignal,
  splitCompositeQuoteSegments,
} = require('./composite-quote-segmentation');
const { normalizeExtractedInputsForFamily } = require('./service-families');

const FLEX_SHAPE_TOKEN_PATTERN_SOURCE = '(?:(?:vm|bm)\\.)?(?:(?:[a-z][a-z0-9]*)\\.)*(?:[a-z]+\\d+|[a-z]\\d+)\\.flex';
const FLEX_SHAPE_TOKEN_INLINE_PATTERN = new RegExp(`\\b${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}\\b`, 'i');

function summarizeMatches(index, text, deps = {}) {
  const {
    searchProducts: searchProductsImpl = searchProducts,
    searchPresets: searchPresetsImpl = searchPresets,
  } = deps;
  const products = searchProductsImpl(index, text, 5).map((item) => item.fullDisplayName);
  const presets = searchPresetsImpl(index, text, 3).map((item) => item.displayName);
  return { products, presets };
}

function isCompositeOrComparisonRequest(text) {
  const source = String(text || '').toLowerCase();
  const segments = splitCompositeQuoteSegments(source);
  const signaledSegments = segments.filter((segment) => hasCompositeServiceSignal(segment)).length;
  if (segments.length >= 2 && signaledSegments >= 2) return true;

  const serviceHits = [
    /\bload balancer\b/.test(source),
    /\bblock storage\b|\bblock volumes?\b/.test(source),
    /\bobject storage\b/.test(source),
    /\bfastconnect\b|\bfast connect\b/.test(source),
    /\bweb application firewall\b|\bwaf\b/.test(source),
    /\bnetwork firewall\b/.test(source),
    /\bdns\b/.test(source),
    /\bapi gateway\b/.test(source),
    /\bintegration cloud\b/.test(source),
    /\banalytics cloud\b/.test(source),
    /\bdata integration\b/.test(source),
    /\bmonitoring\b/.test(source),
    /\bnotifications\b/.test(source),
    /\bhttps delivery\b|\bemail delivery\b/.test(source),
    /\biam sms\b|\bsms messages?\b/.test(source),
    /\bthreat intelligence\b/.test(source),
    /\bhealth checks?\b/.test(source),
    /\bfleet application management\b/.test(source),
    /\boci batch\b|\bbatch\b/.test(source),
    /\bdata safe\b/.test(source),
    /\blog analytics\b/.test(source),
    /\bfunctions\b/.test(source),
    /\bgenerative ai\b/.test(source),
    /\bvision\b|\bspeech\b|\bmedia flow\b/.test(source),
    /\bfile storage\b/.test(source),
    /\bautonomous(?: ai)? lakehouse\b|\bautonomous data warehouse\b|\bbase database service\b|\bexadata\b|\bdatabase cloud service\b/.test(source),
    FLEX_SHAPE_TOKEN_INLINE_PATTERN.test(source),
  ].filter(Boolean).length;
  if (/\bcompare\b/.test(source) && FLEX_SHAPE_TOKEN_INLINE_PATTERN.test(source)) return true;
  return serviceHits >= 2 || /\b3-tier\b|\bthree-tier\b|\barchitecture\b|\bworkload\b|\bbundle\b|\bstack\b|\bplatform\b/.test(source);
}

function enrichExtractedInputsForFamily(intent = {}, deps = {}) {
  const {
    normalizeExtractedInputsForFamily: normalizeExtractedInputsForFamilyImpl = normalizeExtractedInputsForFamily,
  } = deps;
  return {
    ...intent,
    extractedInputs: normalizeExtractedInputsForFamilyImpl(intent.serviceFamily, intent.extractedInputs),
  };
}

module.exports = {
  FLEX_SHAPE_TOKEN_INLINE_PATTERN,
  FLEX_SHAPE_TOKEN_PATTERN_SOURCE,
  enrichExtractedInputsForFamily,
  isCompositeOrComparisonRequest,
  summarizeMatches,
};
