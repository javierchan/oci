'use strict';

const { formatMoney } = require('./assistant-quote-narrative');

function buildQuoteNarrativeLead(quote) {
  const matched = quote?.resolution?.label || 'the requested OCI product';
  const totals = quote?.totals || {};
  const request = quote?.request || {};
  const lineCount = Array.isArray(quote?.lineItems) ? quote.lineItems.length : 0;
  const currencyCode = totals.currencyCode || 'USD';
  const totalSentence = request.annualRequested
    ? `The estimate includes ${lineCount} priced line${lineCount === 1 ? '' : 's'} and the calculated annual total is **${formatMoney(totals.annual, currencyCode)}**.`
    : `The estimate includes ${lineCount} priced line${lineCount === 1 ? '' : 's'} and the calculated monthly total is **${formatMoney(totals.monthly, currencyCode)}**.`;
  return [
    `I prepared a deterministic OCI quotation for \`${matched}\`.`,
    totalSentence,
  ].join('\n\n');
}

function buildQuoteNarrativeMessage({
  quote,
  assumptions = [],
  expertSummary = '',
  enrichment = '',
  fallbackConsiderations = '',
  consumptionExplanation = [],
}) {
  const parts = [buildQuoteNarrativeLead(quote)];
  if (Array.isArray(assumptions) && assumptions.length) {
    parts.push(`Key assumptions:\n${assumptions.join('\n')}`);
  }
  if (expertSummary) parts.push(expertSummary);
  if (enrichment || fallbackConsiderations) {
    parts.push(enrichment || fallbackConsiderations);
  }
  if (Array.isArray(consumptionExplanation) && consumptionExplanation.length) {
    parts.push(`How OCI measures this:\n${consumptionExplanation.join('\n')}`);
  }
  parts.push(`### OCI quotation\n\n${quote?.markdown || ''}`);
  if (quote?.warnings?.length) {
    parts.push(`Warnings:\n${quote.warnings.map((item) => `- ${item}`).join('\n')}`);
  }
  return parts.join('\n\n');
}

module.exports = {
  buildQuoteNarrativeLead,
  buildQuoteNarrativeMessage,
};
