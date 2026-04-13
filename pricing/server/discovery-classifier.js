'use strict';

const EXPLICIT_QUOTE_LEAD_PATTERN = /^(?:quote|cotiza(?:r|me)?|cotización|dame\s+(?:un\s+)?quote|estimate|estim(?:a|ar)|need\s+(?:an?|a consolidated)\s+oci\s+estimate|quiero\s+cotizar|necesito\s+cotizar|ay[uú]dame\s+a\s+cotizar|me\s+cotizas?)\b/i;

const CONCEPTUAL_PRICING_PATTERNS = [
  /\b(?:what|which|que|qué|cuales?|cu[aá]les)\b[\s\S]*\b(?:skus?|sku'?s|componentes?|components?)\b[\s\S]*\b(?:need|needed|required|require|requier(?:e|o|en)?|requerid[oa]s?|necesari[oa]s?)\b[\s\S]*\b(?:quote|quoting|pricing|cotizar|cotización)\b/i,
  /\b(?:skus?|sku'?s|componentes?|components?)\b[\s\S]*\b(?:required|requireds?|requerid[oa]s?|necesari[oa]s?)\b[\s\S]*\b(?:en|in|for|para|de)\b[\s\S]*\b(?:quote|cotiz(?:ar|ación))\b/i,
  /\b(?:what|which|que|qué|cuales?|cu[aá]les)\b[\s\S]*\b(?:inputs?|information|datos|variables|componentes?|components?|skus?)\b[\s\S]*\b(?:need|needed|required|require|necesito|requiero|required)\b[\s\S]*\b(?:before|for|to|para)\b[\s\S]*\b(?:quote|quoting|pricing|price|cotizar|cotización)\b/i,
  /\b(?:what|which|que|qué)\b[\s\S]*\b(?:do i need|need before|is required|required before|necesito|se requiere|requiero)\b[\s\S]*\b(?:quote|pricing|cotizar|cotización)\b/i,
  /\b(?:what|which|que|qué)\b[\s\S]*\b(?:me pides|datos necesitas|informaci[oó]n necesitas?|need from me|need from us|faltan|falta)\b[\s\S]*\b(?:quote|pricing|cotizar|cotización)\b/i,
  /\b(?:before|antes de)\b[\s\S]*\b(?:quote|quoting|cotizar|cotización)\b[\s\S]*\b(?:what|which|que|qué)\b[\s\S]*\b(?:inputs?|information|datos|need|needed|necesito|necesitas|required)\b/i,
  /\b(?:how|como|cómo)\b[\s\S]*\b(?:build|structure|compose|prepare|arma|armar|construye|construir|compone|componer|preparo|preparar)\b[\s\S]*\b(?:quote|cotiz(?:ar|ación))\b/i,
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

const HYBRID_QUOTE_DISCOVERY_PATTERNS = [
  /\b(?:quote|cotiza(?:r|me)?|cotización|estimate|estim(?:a|ar)|quiero\s+cotizar|necesito\s+cotizar|ay[uú]dame\s+a\s+cotizar|me\s+cotizas?)\b[\s\S]*\b(?:but|pero|first|primero|and|y)\b[\s\S]*\b(?:tell me|dime|what inputs?|what information|need from me|need from us|missing|faltan|falta|datos?|informaci[oó]n|si\s+falta\s+algo|que\s+te\s+falta|que\s+me\s+falta)\b/i,
  /\b(?:quote|cotiza(?:r|me)?|cotización|quiero\s+cotizar|necesito\s+cotizar|ay[uú]dame\s+a\s+cotizar)\b[\s\S]*\b(?:what inputs?|what information|need from me|need from us|missing|faltan|falta|datos?|informaci[oó]n|que\s+te\s+falta|que\s+me\s+falta|si\s+falta\s+algo)\b/i,
  /\b(?:what|which|que|qué)\b[\s\S]*\b(?:faltan|falta|need|needed|required|inputs?|information|datos?|informaci[oó]n)\b[\s\S]*\b(?:quote|cotizar|cotización)\b/i,
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
  if (hasExplicitQuoteLead(source)) {
    return HYBRID_QUOTE_DISCOVERY_PATTERNS.some((pattern) => pattern.test(source));
  }
  if (isConceptualPricingQuestion(source)) return true;
  return DISCOVERY_OR_EXPLANATION_PATTERNS.some((pattern) => pattern.test(source));
}

module.exports = {
  CONCEPTUAL_PRICING_PATTERNS,
  DISCOVERY_OR_EXPLANATION_PATTERNS,
  HYBRID_QUOTE_DISCOVERY_PATTERNS,
  hasExplicitQuoteLead,
  isConceptualPricingQuestion,
  isDiscoveryOrExplanationQuestion,
};
