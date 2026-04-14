'use strict';

const { buildDeterministicQuotePayload } = require('./quote-response-payload');

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
        ...(await buildDeterministicQuotePayload({
          cfg,
          userText: effectiveUserText,
          quote: compositeQuote,
          assumptions: formatAssumptions([], parsePromptRequest(effectiveUserText)),
          intent: {
            intent: 'quote',
            shouldQuote: true,
            needsClarification: false,
            clarificationQuestion: '',
          },
        }, {
          buildQuoteNarrative,
        })),
      };
    }
  }

  const rawParsedRequest = parsePromptRequest(effectiveUserText);
  if (isSimpleTransactionalQuoteRequest(rawParsedRequest, compositeLike)) {
    const rawQuote = quoteFromPrompt(index, effectiveUserText);
    if (rawQuote.ok && rawQuote.resolution?.type === 'service') {
      return {
        ...(await buildDeterministicQuotePayload({
          cfg,
          userText: effectiveUserText,
          quote: rawQuote,
          assumptions: formatAssumptions([], rawParsedRequest),
          intent: {
            intent: 'quote',
            shouldQuote: true,
            needsClarification: false,
            clarificationQuestion: '',
          },
        }, {
          buildQuoteNarrative,
        })),
      };
    }
  }

  return null;
}

module.exports = {
  isSimpleTransactionalQuoteRequest,
  resolveDirectQuoteFastPath,
};
