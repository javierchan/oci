'use strict';

async function resolvePostClarificationRouting(options = {}, deps = {}) {
  const {
    cfg,
    index,
    conversation,
    userText = '',
    effectiveUserText = '',
    sessionContext,
    intent = {},
    familyMeta = null,
    reformulatedRequest = '',
    preflightQuote = null,
    quoteClarificationState = {},
  } = options;
  const {
    hasExplicitByolChoice,
    shouldAskLicenseChoice,
    buildLicenseChoiceClarificationPayload,
    quoteFromPrompt,
    parsePromptRequest,
    formatAssumptions,
    detectByolAmbiguity,
    buildByolAmbiguityClarificationPayload,
    filterQuoteByByolChoice,
    toMarkdownQuote,
    buildQuoteNarrative,
    buildQuoteUnresolvedPayload,
    buildAnswerFallbackPayload,
    summarizeMatches,
    writeNaturalReply,
  } = deps;

  const nextIntent = {
    ...intent,
    ...((quoteClarificationState && quoteClarificationState.intent) || {}),
  };
  if (quoteClarificationState?.clarificationPayload) {
    return {
      intent: nextIntent,
      payload: quoteClarificationState.clarificationPayload,
    };
  }

  const byolChoice = hasExplicitByolChoice(`${userText}\n${reformulatedRequest}`);
  if (shouldAskLicenseChoice(familyMeta, nextIntent, byolChoice)) {
    return {
      intent: nextIntent,
      payload: buildLicenseChoiceClarificationPayload(familyMeta, nextIntent),
    };
  }

  if (nextIntent.needsClarification && nextIntent.clarificationQuestion) {
    return {
      intent: nextIntent,
      payload: {
        ok: true,
        mode: 'clarification',
        message: String(nextIntent.clarificationQuestion).trim(),
        intent: nextIntent,
      },
    };
  }

  if (nextIntent.shouldQuote) {
    let quote = preflightQuote?.ok ? preflightQuote : quoteFromPrompt(index, reformulatedRequest);
    const parsed = parsePromptRequest(reformulatedRequest);
    const assumptions = formatAssumptions(nextIntent.assumptions, parsed);

    const byolAmbiguousProduct = quote.ok && !byolChoice ? detectByolAmbiguity(quote) : '';
    if (byolAmbiguousProduct) {
      return {
        intent: nextIntent,
        payload: buildByolAmbiguityClarificationPayload(byolAmbiguousProduct, nextIntent),
      };
    }
    if (quote.ok && byolChoice) {
      quote = filterQuoteByByolChoice(quote, byolChoice, toMarkdownQuote);
    }

    if (quote.ok) {
      return {
        intent: nextIntent,
        payload: {
          ok: true,
          mode: 'quote',
          message: await buildQuoteNarrative(cfg, effectiveUserText, quote, assumptions),
          quote,
          intent: nextIntent,
        },
      };
    }

    return {
      intent: nextIntent,
      payload: await buildQuoteUnresolvedPayload({
        familyMeta,
        userText,
        reformulatedRequest,
        quote,
        intent: nextIntent,
        index,
        conversation,
        sessionContext,
        assumptions,
        summarizeMatches,
        writeNaturalReply,
        cfg,
      }),
    };
  }

  return {
    intent: nextIntent,
    payload: await buildAnswerFallbackPayload({
      cfg,
      index,
      conversation,
      userText,
      sessionContext,
      intent: nextIntent,
      summarizeMatches,
      writeNaturalReply,
    }),
  };
}

module.exports = {
  resolvePostClarificationRouting,
};
