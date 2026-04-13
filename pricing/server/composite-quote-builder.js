'use strict';

const { quoteFromPrompt, parsePromptRequest, toMarkdownQuote } = require('./quotation-engine');
const { getServiceFamily, buildCanonicalRequest } = require('./service-families');
const {
  hasCompositeServiceSignal,
  normalizeCompositeSegment,
  splitCompositeQuoteSegments,
} = require('./composite-quote-segmentation');

function choosePreferredQuote(primary, secondary) {
  if (primary?.ok && !secondary?.ok) return primary;
  if (secondary?.ok && !primary?.ok) return secondary;
  if (!primary?.ok && !secondary?.ok) return primary || secondary || null;
  const primaryLines = Array.isArray(primary?.lineItems) ? primary.lineItems.length : 0;
  const secondaryLines = Array.isArray(secondary?.lineItems) ? secondary.lineItems.length : 0;
  if (primaryLines !== secondaryLines) return primaryLines > secondaryLines ? primary : secondary;
  const primaryMonthly = Number(primary?.totals?.monthly || 0);
  const secondaryMonthly = Number(secondary?.totals?.monthly || 0);
  if (primaryMonthly !== secondaryMonthly) return primaryMonthly > secondaryMonthly ? primary : secondary;
  return secondary || primary;
}

function quoteSegmentWithCanonicalFallback(index, prompt) {
  const direct = quoteFromPrompt(index, prompt);
  const parsed = parsePromptRequest(prompt);
  const familyMeta = parsed?.serviceFamily ? getServiceFamily(parsed.serviceFamily) : null;
  if (!familyMeta) return direct;
  const canonical = String(buildCanonicalRequest({
    serviceFamily: parsed.serviceFamily,
    extractedInputs: parsed,
    normalizedRequest: prompt,
    reformulatedRequest: prompt,
  }, prompt) || '').trim();
  if (!canonical || canonical === prompt) return direct;
  const canonicalQuote = quoteFromPrompt(index, canonical);
  return choosePreferredQuote(direct, canonicalQuote);
}

function buildCompositeQuoteFromSegments(index, text) {
  const segments = splitCompositeQuoteSegments(text);
  if (segments.length < 2) return null;
  const serviceSignalCount = segments.filter((segment) => hasCompositeServiceSignal(segment)).length;
  if (serviceSignalCount < 2) return null;

  const mergedLineItems = [];
  const warnings = [];
  const candidates = [];

  for (const segment of segments) {
    const prompt = normalizeCompositeSegment(segment, text);
    const quote = quoteSegmentWithCanonicalFallback(index, prompt);
    if (!quote.ok || !Array.isArray(quote.lineItems) || !quote.lineItems.length) {
      warnings.push(`Could not deterministically quote segment: ${segment}`);
      continue;
    }
    mergedLineItems.push(...quote.lineItems);
    if (Array.isArray(quote.warnings) && quote.warnings.length) warnings.push(...quote.warnings);
    candidates.push(...((quote.resolution?.candidates) || []));
  }

  if (mergedLineItems.length < 2) return null;

  const totals = mergedLineItems.reduce((acc, line) => {
    acc.monthly += Number(line.monthly || 0);
    acc.annual += Number(line.annual || 0);
    return acc;
  }, { monthly: 0, annual: 0, currencyCode: 'USD' });

  return {
    ok: true,
    request: { source: text },
    resolution: {
      type: 'workload',
      label: 'Composite OCI workload',
      candidates: candidates.filter(Boolean),
    },
    warnings: Array.from(new Set(warnings)),
    lineItems: mergedLineItems,
    totals,
    markdown: toMarkdownQuote(mergedLineItems, totals),
  };
}

module.exports = {
  buildCompositeQuoteFromSegments,
  choosePreferredQuote,
  quoteSegmentWithCanonicalFallback,
};
