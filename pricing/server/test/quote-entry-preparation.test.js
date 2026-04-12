'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  buildUnsupportedComputeFallbackPayload,
  prepareQuoteCandidateState,
  prepareQuoteEntry,
  promoteDeterministicTopService,
  resolveEffectiveQuoteText,
  resolveUnsupportedComputeVariantState,
  shouldPromoteDeterministicTopService,
} = require(path.join(ROOT, 'quote-entry-preparation.js'));

test('quote entry preparation prefers route-driven follow-up request text when available', () => {
  const effectiveQuoteText = resolveEffectiveQuoteText(
    { lastQuote: { source: 'Quote previous' } },
    { route: 'quote_followup' },
    'change to 20 VPUs',
    'change to 20 VPUs',
    () => 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM with 340 GB Block Storage and 20 VPUs',
  );

  assert.match(effectiveQuoteText, /20 VPUs/i);
  assert.doesNotMatch(effectiveQuoteText, /change to 20 VPUs/i);
});

test('quote entry preparation falls back to the effective user text when no route merge exists', () => {
  const effectiveQuoteText = resolveEffectiveQuoteText(
    {},
    { route: 'quote_request' },
    'Quote FastConnect 10 Gbps',
    'Quote FastConnect 10 Gbps',
    () => '',
  );

  assert.equal(effectiveQuoteText, 'Quote FastConnect 10 Gbps');
});

test('quote entry preparation detects unsupported compute variants that should fall back to discovery', () => {
  const state = resolveUnsupportedComputeVariantState(
    'Quote VM.Standard1.4 for 744 hours',
    'Quote VM.Standard1.4 for 744 hours',
    null,
    (text) => /VM\.Standard1\.4/i.test(text) ? 'VM.Standard1.4' : '',
    () => false,
  );

  assert.equal(state.unsupportedComputeVariant, 'VM.Standard1.4');
  assert.equal(state.shouldFallbackToDiscovery, true);
  assert.equal(state.requestText, 'Quote VM.Standard1.4 for 744 hours');
});

test('quote entry preparation does not fall back to unsupported compute discovery when a covered non-compute family owns the request', () => {
  const state = resolveUnsupportedComputeVariantState(
    'Quote OCI Exadata Cloud@Customer Database BYOL 12 OCPUs on base system X10M',
    '12 OCPUs',
    { id: 'database_exadata_cloud_customer', domain: 'database' },
    () => 'GPU.L40S',
    () => false,
  );

  assert.equal(state.unsupportedComputeVariant, 'GPU.L40S');
  assert.equal(state.shouldFallbackToDiscovery, false);
});

test('quote entry preparation allows deterministic promotion when discovery guards do not apply', () => {
  const shouldPromote = shouldPromoteDeterministicTopService({
    effectiveUserText: 'Quote Big Data Service - Compute - HPC with 16 OCPUs for 744 hours',
    compositeLike: false,
    topService: { deterministic: true, name: 'Big Data Service - Compute - HPC' },
    intent: { extractedInputs: { ocpus: 16 }, serviceFamily: '' },
    interpretedFamilyMeta: null,
    serviceHasRequiredInputs: () => true,
    isDiscoveryOrExplanationQuestion: () => false,
  });

  assert.equal(shouldPromote, true);
});

test('quote entry preparation does not promote deterministic top service when a covered family already owns the request', () => {
  const shouldPromote = shouldPromoteDeterministicTopService({
    effectiveUserText: 'Quote Oracle Integration Cloud Standard 3 instances',
    compositeLike: false,
    topService: { deterministic: true, name: 'Oracle Integration Cloud Standard' },
    intent: { extractedInputs: { instances: 3 }, serviceFamily: 'integration_oic_standard' },
    interpretedFamilyMeta: { id: 'integration_oic_standard' },
    serviceHasRequiredInputs: () => true,
    isDiscoveryOrExplanationQuestion: () => false,
  });

  assert.equal(shouldPromote, false);
});

test('quote entry preparation promotion clears stale clarification state and keeps the deterministic service name', () => {
  const promoted = promoteDeterministicTopService(
    {
      intent: 'discover',
      shouldQuote: false,
      needsClarification: true,
      clarificationQuestion: 'How many?',
      normalizedRequest: 'old',
    },
    { name: 'Big Data Service - Compute - HPC' },
    'Quote Big Data Service - Compute - HPC with 16 OCPUs for 744 hours',
  );

  assert.equal(promoted.serviceName, 'Big Data Service - Compute - HPC');
  assert.equal(promoted.intent, 'quote');
  assert.equal(promoted.shouldQuote, true);
  assert.equal(promoted.needsClarification, false);
  assert.equal(promoted.clarificationQuestion, '');
  assert.match(promoted.normalizedRequest, /16 OCPUs/);
});

test('quote entry preparation can build a safe unsupported-compute discovery payload', () => {
  const payload = buildUnsupportedComputeFallbackPayload(
    { requestText: 'Quote VM.Standard1.4 for 744 hours' },
    {
      route: 'quote_request',
      shouldQuote: true,
      needsClarification: true,
      clarificationQuestion: 'old',
    },
    {},
    {},
    (text) => `unsupported: ${text}`,
    (_index, { intent }) => ({ family: { id: intent.route } }),
    (contextPack) => contextPack,
  );

  assert.equal(payload.mode, 'answer');
  assert.match(payload.message, /VM\.Standard1\.4/);
  assert.equal(payload.intent.route, 'product_discovery');
  assert.equal(payload.intent.shouldQuote, false);
  assert.equal(payload.intent.needsClarification, false);
});

test('quote entry preparation returns fallback payload for unsupported compute variants', () => {
  const result = prepareQuoteEntry(
    {
      sessionContext: {},
      intent: {
        route: 'quote_request',
        shouldQuote: true,
        extractedInputs: {},
      },
      userText: 'Quote VM.Standard1.4 for 744 hours',
      effectiveUserText: 'Quote VM.Standard1.4 for 744 hours',
      compositeLike: false,
      topService: null,
      interpretedFamilyMeta: null,
      index: {},
    },
    {
      mergeSessionQuoteFollowUpByRoute: () => '',
      findUncoveredComputeVariant: () => 'VM.Standard1.4',
      canSafelyQuoteUncoveredComputeVariant: () => false,
      buildUncoveredComputeReply: (text) => `unsupported: ${text}`,
      buildAssistantContextPack: () => ({ family: { id: 'legacy_fixed_vm' } }),
      summarizeContextPack: (contextPack) => contextPack,
      serviceHasRequiredInputs: () => false,
      isDiscoveryOrExplanationQuestion: () => false,
    },
  );

  assert.match(result.effectiveQuoteText, /VM\.Standard1\.4/);
  assert.ok(result.fallbackPayload);
  assert.equal(result.fallbackPayload.intent.route, 'product_discovery');
});

test('quote entry preparation promotes deterministic top service when no unsupported compute fallback applies', () => {
  const result = prepareQuoteEntry(
    {
      sessionContext: {},
      intent: {
        route: 'quote_request',
        intent: 'discover',
        shouldQuote: false,
        needsClarification: true,
        clarificationQuestion: 'old',
        extractedInputs: { ocpus: 16 },
        serviceFamily: '',
      },
      userText: 'Quote Big Data Service - Compute - HPC with 16 OCPUs for 744 hours',
      effectiveUserText: 'Quote Big Data Service - Compute - HPC with 16 OCPUs for 744 hours',
      compositeLike: false,
      topService: { deterministic: true, name: 'Big Data Service - Compute - HPC' },
      interpretedFamilyMeta: null,
      index: {},
    },
    {
      mergeSessionQuoteFollowUpByRoute: () => '',
      findUncoveredComputeVariant: () => '',
      canSafelyQuoteUncoveredComputeVariant: () => true,
      buildUncoveredComputeReply: () => '',
      buildAssistantContextPack: () => ({}),
      summarizeContextPack: () => ({}),
      serviceHasRequiredInputs: () => true,
      isDiscoveryOrExplanationQuestion: () => false,
    },
  );

  assert.equal(result.fallbackPayload, null);
  assert.equal(result.intent.serviceName, 'Big Data Service - Compute - HPC');
  assert.equal(result.intent.shouldQuote, true);
  assert.equal(result.intent.needsClarification, false);
});

test('quote candidate state returns fallback payload before quote request shaping when compute is unsupported', () => {
  const result = prepareQuoteCandidateState(
    {
      index: {},
      sessionContext: {},
      userText: 'Quote VM.Standard1.4 for 744 hours',
      effectiveUserText: 'Quote VM.Standard1.4 for 744 hours',
      intent: {
        route: 'quote_request',
        shouldQuote: true,
        extractedInputs: {},
        serviceFamily: '',
      },
      topService: null,
      contextualFollowUp: false,
      compositeLike: false,
    },
    {
      getServiceFamily: () => null,
      mergeSessionQuoteFollowUpByRoute: () => '',
      findUncoveredComputeVariant: () => 'VM.Standard1.4',
      canSafelyQuoteUncoveredComputeVariant: () => false,
      buildUncoveredComputeReply: (text) => `unsupported: ${text}`,
      buildAssistantContextPack: () => ({ family: { id: 'legacy_fixed_vm' } }),
      summarizeContextPack: (contextPack) => contextPack,
      serviceHasRequiredInputs: () => false,
      isDiscoveryOrExplanationQuestion: () => false,
      buildQuoteRequestShape: () => {
        throw new Error('should not be called');
      },
      preserveCriticalPromptModifiers: (text) => text,
      choosePreferredQuote: (primary) => primary,
    },
  );

  assert.ok(result.fallbackPayload);
  assert.equal(result.reformulatedRequest, '');
  assert.equal(result.preflightQuote, null);
});

test('quote candidate state returns quote-ready fields after safe promotion and request shaping', () => {
  const result = prepareQuoteCandidateState(
    {
      index: {},
      sessionContext: {},
      userText: 'Quote Big Data Service - Compute - HPC with 16 OCPUs for 744 hours',
      effectiveUserText: 'Quote Big Data Service - Compute - HPC with 16 OCPUs for 744 hours',
      intent: {
        route: 'quote_request',
        intent: 'discover',
        shouldQuote: false,
        needsClarification: true,
        clarificationQuestion: 'old',
        extractedInputs: { ocpus: 16 },
        serviceFamily: '',
      },
      topService: { deterministic: true, name: 'Big Data Service - Compute - HPC' },
      contextualFollowUp: false,
      compositeLike: false,
    },
    {
      getServiceFamily: () => null,
      mergeSessionQuoteFollowUpByRoute: () => '',
      findUncoveredComputeVariant: () => '',
      canSafelyQuoteUncoveredComputeVariant: () => true,
      buildUncoveredComputeReply: () => '',
      buildAssistantContextPack: () => ({}),
      summarizeContextPack: () => ({}),
      serviceHasRequiredInputs: () => true,
      isDiscoveryOrExplanationQuestion: () => false,
      buildQuoteRequestShape: ({ effectiveQuoteText, intent }) => ({
        reformulatedRequest: `${effectiveQuoteText} shaped`,
        preflightQuote: { ok: true, source: intent.serviceName },
      }),
      preserveCriticalPromptModifiers: (text) => text,
      choosePreferredQuote: (primary) => primary,
    },
  );

  assert.equal(result.fallbackPayload, null);
  assert.equal(result.intent.serviceName, 'Big Data Service - Compute - HPC');
  assert.match(result.reformulatedRequest, /shaped$/);
  assert.equal(result.preflightQuote.source, 'Big Data Service - Compute - HPC');
});
