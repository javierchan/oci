'use strict';

const EXPLICIT_QUOTE_LEAD_PATTERN = /^(?:quote|cotiza(?:r)?|cotización|dame\s+(?:un\s+)?quote|estimate|estim(?:a|ar)|need\s+(?:an?|a consolidated)\s+oci\s+estimate)\b/i;

const CONCEPTUAL_PRICING_PATTERNS = [
  /\b(?:what|which|que|qué|cuales?|cu[aá]les)\b[\s\S]*\b(?:skus?|sku'?s|componentes?|components?)\b[\s\S]*\b(?:need|needed|required|require|requier(?:e|o|en)?|requerid[oa]s?|necesari[oa]s?)\b[\s\S]*\b(?:quote|quoting|pricing|cotizar|cotización)\b/i,
  /\b(?:skus?|sku'?s|componentes?|components?)\b[\s\S]*\b(?:required|requireds?|requerid[oa]s?|necesari[oa]s?)\b[\s\S]*\b(?:en|in|for|para|de)\b[\s\S]*\b(?:quote|cotiz(?:ar|ación))\b/i,
  /\b(?:what|which|que|qué|cuales?|cu[aá]les)\b[\s\S]*\b(?:inputs?|information|datos|variables|componentes?|components?|skus?)\b[\s\S]*\b(?:need|needed|required|require|necesito|requiero|required)\b[\s\S]*\b(?:before|for|to|para)\b[\s\S]*\b(?:quote|quoting|pricing|price|cotizar|cotización)\b/i,
  /\b(?:what|which|que|qué)\b[\s\S]*\b(?:do i need|need before|is required|required before|necesito|se requiere|requiero)\b[\s\S]*\b(?:quote|pricing|cotizar|cotización)\b/i,
  /\b(?:how|como|cómo)\b[\s\S]*\b(?:build|structure|compose|arma|armar|construye|construir|compone|componer)\b[\s\S]*\b(?:quote|cotiz(?:ar|ación))\b/i,
  /\b(?:only|solo)\b[\s\S]*\bocpu\b[\s\S]*\b(?:no|without|sin)\b[\s\S]*\b(?:disk|storage|memory|disco|almacenamiento|memoria)\b/i,
];

const DISCOVERY_OR_EXPLANATION_PATTERNS = [
  /\b(?:how|what|which|why|que|qué|como|cómo|cual|cuál)\b.*\b(?:billed|charged|priced|price|pricing|billing|cobra|cobran|costea)\b/i,
  /\b(?:pricing model|billing model|cost model|modelo de cobro|modelo de pricing|pricing dimensions?|billing dimensions?)\b/i,
  /\b(?:explain|explica)\b.*\b(?:pricing|billing|billed|charged|priced|dimensions?|metrics?|units?|components?|skus?)\b/i,
  /\b(?:what|which|que|qué)\b.*\b(?:dimensions?|metrics?|units?|components?|skus?|inputs?|information)\b.*\b(?:bill|charge|price|pricing|quote|cotizar|cotización|cobra)\b/i,
  /\b(?:what|which|que|qué)\b.*\b(?:options?|available|supported|disponibles?|soportadas?)\b/i,
  /\b(?:difference|diferencia|compare|comparar)\b.*\b(?:byol|license included|licencia incluida)\b/i,
];

function hasExplicitQuoteLead(text = '') {
  const source = String(text || '').trim();
  if (!source) return false;
  return EXPLICIT_QUOTE_LEAD_PATTERN.test(source);
}

function isConceptualPricingQuestion(text = '') {
  const source = String(text || '').trim();
  if (!source) return false;
  return CONCEPTUAL_PRICING_PATTERNS.some((pattern) => pattern.test(source));
}

function isDiscoveryOrExplanationQuestion(text = '') {
  const source = String(text || '').trim();
  if (!source) return false;
  if (hasExplicitQuoteLead(source)) return false;
  if (isConceptualPricingQuestion(source)) return true;
  return DISCOVERY_OR_EXPLANATION_PATTERNS.some((pattern) => pattern.test(source));
}

module.exports = {
  CONCEPTUAL_PRICING_PATTERNS,
  DISCOVERY_OR_EXPLANATION_PATTERNS,
  hasExplicitQuoteLead,
  isConceptualPricingQuestion,
  isDiscoveryOrExplanationQuestion,
};
