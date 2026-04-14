'use strict';

const { runChat, extractChatText } = require('./genai');
const {
  buildConsumptionExplanation,
  buildDeterministicConsiderationsFallback,
  buildDeterministicExpertSummary,
  inferQuoteTechnologyProfile,
} = require('./assistant-quote-narrative');
const {
  buildQuoteEnrichmentContextBlock,
  sanitizeQuoteEnrichment,
  shouldAllowMigrationNotes,
} = require('./assistant-quote-enrichment');
const { buildQuoteNarrativeMessage } = require('./assistant-quote-assembly');

const QUOTE_ENRICHMENT_PROMPT = [
  'You are enriching an OCI pricing response that was already calculated deterministically.',
  'Do not change any numbers, SKUs, totals, assumptions, or warnings.',
  'Do not invent pricing, architecture, licensing, or migration facts.',
  'Do not restate totals, do not rebuild arithmetic, and do not infer discrepancies.',
  'Write short, useful markdown only, with the tone of the requested OCI expert role.',
  'Return at most two short bullet lists:',
  '- OCI considerations for this technology',
  '- Migration notes when the source clearly comes from VMware or RVTools',
  'If a section does not apply, omit it.',
].join('\n');

async function buildGenAIQuoteEnrichment(cfg, userText, quote, assumptions) {
  if (!cfg?.ok || !quote?.ok) return '';
  const lineItems = Array.isArray(quote.lineItems) ? quote.lineItems : [];
  if (!lineItems.length) return '';
  const technologyProfile = inferQuoteTechnologyProfile(quote);
  const allowMigrationNotes = shouldAllowMigrationNotes(userText, quote);
  const contextBlock = buildQuoteEnrichmentContextBlock(userText, quote, assumptions, technologyProfile);

  try {
    const response = await runChat({
      cfg,
      systemPrompt: QUOTE_ENRICHMENT_PROMPT,
      messages: [{ role: 'user', content: contextBlock }],
      maxTokens: 350,
      temperature: 0.2,
      topP: 0.6,
      topK: -1,
    });
    return sanitizeQuoteEnrichment(extractChatText(response?.data || response).trim(), { allowMigrationNotes });
  } catch (_error) {
    return '';
  }
}

async function buildQuoteNarrative(cfg, userText, quote, assumptions) {
  const enrichment = await buildGenAIQuoteEnrichment(cfg, userText, quote, assumptions);
  const explanation = buildConsumptionExplanation(quote);
  return buildQuoteNarrativeMessage({
    quote,
    assumptions,
    expertSummary: buildDeterministicExpertSummary(quote),
    enrichment,
    fallbackConsiderations: buildDeterministicConsiderationsFallback(quote, assumptions),
    consumptionExplanation: explanation,
  });
}

module.exports = {
  buildGenAIQuoteEnrichment,
  buildQuoteNarrative,
};
