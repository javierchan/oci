'use strict';

async function buildAnswerFallbackPayload({
  cfg,
  index,
  conversation,
  userText,
  sessionContext,
  intent,
  summarizeMatches,
  writeNaturalReply,
} = {}) {
  const matches = typeof summarizeMatches === 'function'
    ? summarizeMatches(index, userText)
    : { products: [], presets: [] };
  const natural = typeof writeNaturalReply === 'function'
    ? await writeNaturalReply(cfg, conversation, userText, {
      intent: intent?.intent || 'explain',
      summary: 'The user is asking for OCI pricing guidance rather than a deterministic quote.',
      candidateLines: [
        ...(matches.products || []).map((item) => `- Product: ${item}`),
        ...(matches.presets || []).map((item) => `- Preset: ${item}`),
      ],
      assumptionLines: Array.isArray(intent?.assumptions) ? intent.assumptions.map((item) => `- ${item}`) : [],
    }, sessionContext)
    : '';

  return {
    ok: true,
    mode: 'answer',
    message: natural || 'I can help with OCI pricing guidance or prepare a deterministic quotation if you share the sizing details.',
    intent,
  };
}

module.exports = {
  buildAnswerFallbackPayload,
};
