'use strict';

async function buildQuoteUnresolvedPayload({
  familyMeta,
  userText,
  reformulatedRequest,
  quote,
  intent,
  index,
  conversation,
  sessionContext,
  assumptions,
  summarizeMatches,
  writeNaturalReply,
  cfg,
} = {}) {
  if (typeof familyMeta?.quoteUnavailableMessage === 'function') {
    return {
      ok: true,
      mode: 'quote_unresolved',
      message: familyMeta.quoteUnavailableMessage({
        userText,
        reformulatedRequest,
        quote,
        intent,
      }),
      quote,
      intent,
    };
  }

  const matches = typeof summarizeMatches === 'function'
    ? summarizeMatches(index, reformulatedRequest)
    : { products: [], presets: [] };
  const natural = typeof writeNaturalReply === 'function'
    ? await writeNaturalReply(cfg, conversation, userText, {
      intent: intent?.intent || 'quote',
      summary: quote?.error || 'No deterministic quotation could be produced.',
      warningLines: (quote?.warnings || []).map((item) => `- ${item}`),
      candidateLines: [
        ...(matches.products || []).map((item) => `- Product: ${item}`),
        ...(matches.presets || []).map((item) => `- Preset: ${item}`),
      ],
      assumptionLines: assumptions,
    }, sessionContext)
    : '';

  return {
    ok: true,
    mode: 'quote_unresolved',
    message: natural || quote?.error || 'No quotation could be generated.',
    quote,
    intent,
  };
}

module.exports = {
  buildQuoteUnresolvedPayload,
};
