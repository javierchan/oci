'use strict';

function isSimpleTransactionalQuoteRequest(parsedRequest = {}, compositeLike = false) {
  return !compositeLike &&
    Number.isFinite(Number(parsedRequest.requestCount)) &&
    !Number.isFinite(Number(parsedRequest.ocpus)) &&
    !Number.isFinite(Number(parsedRequest.ecpus)) &&
    !Number.isFinite(Number(parsedRequest.capacityGb)) &&
    !Number.isFinite(Number(parsedRequest.users)) &&
    !parsedRequest.shape &&
    !parsedRequest.serviceFamily;
}

async function resolveDirectQuoteFastPath(options = {}, deps = {}) {
  const {
    cfg,
    index,
    effectiveUserText = '',
    compositeLike = false,
  } = options;
  const {
    buildCompositeQuoteFromSegments,
    buildQuoteNarrative,
    formatAssumptions,
    parsePromptRequest,
    quoteFromPrompt,
  } = deps;

  if (compositeLike) {
    const compositeQuote = buildCompositeQuoteFromSegments(index, effectiveUserText);
    if (compositeQuote?.ok) {
      return {
        ok: true,
        mode: 'quote',
        message: await buildQuoteNarrative(
          cfg,
          effectiveUserText,
          compositeQuote,
          formatAssumptions([], parsePromptRequest(effectiveUserText)),
        ),
        quote: compositeQuote,
        intent: {
          intent: 'quote',
          shouldQuote: true,
          needsClarification: false,
          clarificationQuestion: '',
        },
      };
    }
  }

  const rawParsedRequest = parsePromptRequest(effectiveUserText);
  if (isSimpleTransactionalQuoteRequest(rawParsedRequest, compositeLike)) {
    const rawQuote = quoteFromPrompt(index, effectiveUserText);
    if (rawQuote.ok && rawQuote.resolution?.type === 'service') {
      return {
        ok: true,
        mode: 'quote',
        message: await buildQuoteNarrative(
          cfg,
          effectiveUserText,
          rawQuote,
          formatAssumptions([], rawParsedRequest),
        ),
        quote: rawQuote,
        intent: {
          intent: 'quote',
          shouldQuote: true,
          needsClarification: false,
          clarificationQuestion: '',
        },
      };
    }
  }

  return null;
}

module.exports = {
  isSimpleTransactionalQuoteRequest,
  resolveDirectQuoteFastPath,
};
