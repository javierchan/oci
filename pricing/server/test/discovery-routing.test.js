'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  buildDiscoveryRoutingState,
  resolveDiscoveryRoutePayload,
} = require(path.join(ROOT, 'discovery-routing.js'));

test('discovery routing state prefers deterministic top service that has required inputs', () => {
  const state = buildDiscoveryRoutingState(
    {
      index: { serviceRegistry: [] },
      effectiveUserText: 'Quote Health Checks 12 endpoints',
      userText: 'Quote Health Checks 12 endpoints',
      intent: { extractedInputs: { endpoints: 12 }, route: 'quote_request', intent: 'quote' },
    },
    {
      buildRegistryQuery: () => 'Health Checks',
      searchServiceRegistry: () => [
        { name: 'Fallback', deterministic: false },
        { name: 'Health Checks', deterministic: true },
      ],
      serviceHasRequiredInputs: (item) => item.name === 'Health Checks',
      buildCatalogListingReply: () => '',
    },
  );

  assert.equal(state.registryQuery, 'Health Checks');
  assert.equal(state.topService.name, 'Health Checks');
  assert.equal(state.isDiscoveryIntent, false);
});

test('discovery routing state marks product discovery intents and keeps catalog reply', () => {
  const state = buildDiscoveryRoutingState(
    {
      index: { serviceRegistry: [] },
      effectiveUserText: 'What FastConnect options are available in the catalog?',
      userText: 'What FastConnect options are available in the catalog?',
      intent: { extractedInputs: {}, route: 'product_discovery', intent: 'discover' },
    },
    {
      buildRegistryQuery: () => 'FastConnect',
      searchServiceRegistry: () => [],
      serviceHasRequiredInputs: () => false,
      buildCatalogListingReply: () => 'catalog-reply',
    },
  );

  assert.equal(state.catalogReply, 'catalog-reply');
  assert.equal(state.isDiscoveryIntent, true);
});

test('discovery routing returns catalog payload when discovery targets the catalog', async () => {
  const payload = await resolveDiscoveryRoutePayload(
    {
      cfg: {},
      index: {},
      conversation: [],
      userText: 'What FastConnect options are available in the catalog?',
      effectiveUserText: 'What FastConnect options are available in the catalog?',
      sessionContext: {},
      intent: {
        route: 'product_discovery',
        intent: 'discover',
        shouldQuote: false,
        quotePlan: { targetType: 'catalog' },
      },
      catalogReply: 'catalog-reply',
      isDiscoveryIntent: true,
    },
    {
      buildAssistantContextPack: () => ({}),
      writeStructuredContextReply: async () => '',
      buildStructuredDiscoveryFallback: () => '',
      isConceptualPricingQuestion: () => false,
      hasExplicitQuoteLead: () => false,
      buildServiceUnavailableMessage: () => 'unavailable',
      summarizeContextPack: () => ({}),
    },
  );

  assert.equal(payload.mode, 'answer');
  assert.equal(payload.message, 'catalog-reply');
  assert.equal(payload.intent.shouldQuote, false);
});

test('discovery routing returns structured context payload for general discovery answers', async () => {
  const payload = await resolveDiscoveryRoutePayload(
    {
      cfg: {},
      index: {},
      conversation: [],
      userText: 'How is OCI Block Volume billed?',
      effectiveUserText: 'How is OCI Block Volume billed?',
      sessionContext: {},
      intent: {
        route: 'product_discovery',
        intent: 'discover',
        shouldQuote: false,
      },
      catalogReply: '',
      isDiscoveryIntent: true,
    },
    {
      buildAssistantContextPack: () => ({ family: { id: 'storage_block' } }),
      writeStructuredContextReply: async () => 'structured-reply',
      buildStructuredDiscoveryFallback: () => 'fallback-reply',
      isConceptualPricingQuestion: () => false,
      hasExplicitQuoteLead: () => false,
      buildServiceUnavailableMessage: () => 'unavailable',
      summarizeContextPack: () => ({ family: 'storage_block' }),
    },
  );

  assert.equal(payload.mode, 'answer');
  assert.equal(payload.message, 'structured-reply');
  assert.deepEqual(payload.contextPackSummary, { family: 'storage_block' });
});

test('discovery routing returns null when the request should continue into quote flow', async () => {
  const payload = await resolveDiscoveryRoutePayload(
    {
      cfg: {},
      index: {},
      conversation: [],
      userText: 'Quote Oracle Integration Cloud Standard 2 instances',
      effectiveUserText: 'Quote Oracle Integration Cloud Standard 2 instances',
      sessionContext: {},
      intent: {
        route: 'quote_request',
        intent: 'quote',
        shouldQuote: true,
      },
      catalogReply: '',
      isDiscoveryIntent: false,
    },
    {
      buildAssistantContextPack: () => ({}),
      writeStructuredContextReply: async () => '',
      buildStructuredDiscoveryFallback: () => '',
      isConceptualPricingQuestion: () => false,
      hasExplicitQuoteLead: () => false,
      buildServiceUnavailableMessage: () => 'unavailable',
      summarizeContextPack: () => ({}),
    },
  );

  assert.equal(payload, null);
});
