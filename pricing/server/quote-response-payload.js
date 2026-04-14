'use strict';

async function buildDeterministicQuotePayload(options = {}, deps = {}) {
  const {
    cfg,
    userText = '',
    quote = null,
    assumptions = [],
    intent = {},
  } = options;
  const { buildQuoteNarrative } = deps;

  return {
    ok: true,
    mode: 'quote',
    message: await buildQuoteNarrative(cfg, userText, quote, assumptions),
    quote,
    intent,
  };
}

module.exports = {
  buildDeterministicQuotePayload,
};
