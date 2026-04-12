'use strict';

function buildDiscoveryRoutingState(options = {}, deps = {}) {
  const {
    index,
    effectiveUserText = '',
    userText = '',
    intent = {},
  } = options;
  const {
    buildRegistryQuery,
    searchServiceRegistry,
    serviceHasRequiredInputs,
    buildCatalogListingReply,
  } = deps;

  const registryQuery = buildRegistryQuery(
    String(effectiveUserText || userText || intent.normalizedRequest || intent.reformulatedRequest || '').trim(),
    intent,
  );
  const registryMatches = searchServiceRegistry(index.serviceRegistry, registryQuery, 5);
  const topService = registryMatches.find((item) => item.deterministic && serviceHasRequiredInputs(item, intent.extractedInputs)) || registryMatches[0];
  const catalogReply = buildCatalogListingReply(index, registryQuery || userText, intent);
  const isDiscoveryIntent = (
    intent.route === 'product_discovery' ||
    String(intent.intent || '').toLowerCase() === 'discover'
  );

  return {
    registryQuery,
    registryMatches,
    topService,
    catalogReply,
    isDiscoveryIntent,
  };
}

async function resolveDiscoveryRoutePayload(options = {}, deps = {}) {
  const {
    cfg,
    index,
    conversation,
    userText = '',
    effectiveUserText = '',
    sessionContext,
    intent = {},
    catalogReply = '',
    isDiscoveryIntent = false,
  } = options;
  const {
    buildAssistantContextPack,
    writeStructuredContextReply,
    buildStructuredDiscoveryFallback,
    isConceptualPricingQuestion,
    hasExplicitQuoteLead,
    buildServiceUnavailableMessage,
    summarizeContextPack,
  } = deps;

  if (
    isDiscoveryIntent &&
    (
      intent.quotePlan?.targetType === 'catalog' ||
      catalogReply
    )
  ) {
    if (catalogReply) {
      return {
        ok: true,
        mode: 'answer',
        message: catalogReply,
        intent: {
          ...intent,
          intent: 'discover',
          shouldQuote: false,
          needsClarification: false,
          clarificationQuestion: '',
        },
      };
    }
  }

  if ((intent.route === 'product_discovery' || intent.route === 'general_answer') && !intent.shouldQuote) {
    const contextPack = buildAssistantContextPack(index, {
      userText: effectiveUserText,
      intent,
      sessionContext,
    });
    const structuredReply = await writeStructuredContextReply(cfg, conversation, userText, sessionContext, contextPack);
    const fallbackReply = buildStructuredDiscoveryFallback(contextPack);
    const allowLocalFallback = isConceptualPricingQuestion(userText) || hasExplicitQuoteLead(userText);
    const message = allowLocalFallback
      ? ((isConceptualPricingQuestion(userText) && fallbackReply) ? fallbackReply : (structuredReply || fallbackReply || buildServiceUnavailableMessage(userText)))
      : (structuredReply || buildServiceUnavailableMessage(userText));
    return {
      ok: true,
      mode: 'answer',
      message,
      contextPackSummary: summarizeContextPack(contextPack),
      intent,
    };
  }

  return null;
}

module.exports = {
  buildDiscoveryRoutingState,
  resolveDiscoveryRoutePayload,
};
