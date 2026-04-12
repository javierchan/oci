'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const { resolveIntentPipeline } = require(path.join(ROOT, 'intent-pipeline.js'));

test('intent pipeline returns service-unavailable payload when analysis and fallback both fail', async () => {
  const result = await resolveIntentPipeline(
    {
      cfg: {},
      conversation: [],
      effectiveUserText: 'unknown request',
      userText: 'unknown request',
      imageDataUrl: '',
      sessionContext: {},
      contextualFollowUp: false,
      flexComparison: null,
      index: {},
    },
    {
      analyzeIntent: async () => {
        throw new Error('boom');
      },
      analyzeImageIntent: async () => {
        throw new Error('boom');
      },
      fallbackIntentOnAnalysisFailure: () => null,
      buildServiceUnavailableMessage: (text) => `unavailable: ${text}`,
      enrichExtractedInputsForFamily: (intent) => intent,
      reconcileIntentWithHeuristics: (_text, intent) => intent,
      shouldForceQuoteFollowUpRoute: () => false,
      isSessionQuoteFollowUp: () => false,
      applyQuoteFollowUpIntentOverride: (intent) => intent,
      reconcilePostIntentFollowUp: ({ intent }) => ({ intent, postIntentFlexComparison: null }),
      extractFlexComparisonContext: () => null,
      buildFlexComparisonReplyPayload: () => null,
      buildFlexComparisonQuote: () => null,
      buildFlexComparisonNarrative: () => '',
    },
  );

  assert.equal(result.payload.mode, 'answer');
  assert.match(result.payload.message, /unavailable/);
  assert.equal(result.intent, null);
});

test('intent pipeline applies quote-followup override before post-intent follow-up reconciliation', async () => {
  const result = await resolveIntentPipeline(
    {
      cfg: {},
      conversation: [],
      effectiveUserText: '20 VPUs',
      userText: '20 VPUs',
      imageDataUrl: '',
      sessionContext: { lastQuote: { source: 'Quote previous' } },
      contextualFollowUp: true,
      flexComparison: null,
      index: {},
    },
    {
      analyzeIntent: async () => ({ route: 'general_answer', extractedInputs: {} }),
      analyzeImageIntent: async () => ({ route: 'general_answer', extractedInputs: {} }),
      fallbackIntentOnAnalysisFailure: () => null,
      buildServiceUnavailableMessage: () => '',
      enrichExtractedInputsForFamily: (intent) => intent,
      reconcileIntentWithHeuristics: (_text, intent) => ({ ...intent, shouldQuote: false }),
      shouldForceQuoteFollowUpRoute: () => true,
      isSessionQuoteFollowUp: () => true,
      applyQuoteFollowUpIntentOverride: (intent) => ({ ...intent, route: 'quote_followup', shouldQuote: true }),
      reconcilePostIntentFollowUp: ({ intent }) => ({ intent: { ...intent, reformulatedRequest: 'Quote updated' }, postIntentFlexComparison: null }),
      extractFlexComparisonContext: () => null,
      buildFlexComparisonReplyPayload: () => null,
      buildFlexComparisonQuote: () => null,
      buildFlexComparisonNarrative: () => '',
    },
  );

  assert.equal(result.payload, null);
  assert.equal(result.intent.route, 'quote_followup');
  assert.equal(result.intent.shouldQuote, true);
  assert.equal(result.intent.reformulatedRequest, 'Quote updated');
});

test('intent pipeline returns post-intent flex reply when follow-up creates a complete comparison', async () => {
  const result = await resolveIntentPipeline(
    {
      cfg: {},
      conversation: [],
      effectiveUserText: 'Compare E4.Flex vs E5.Flex',
      userText: 'Compare E4.Flex vs E5.Flex',
      imageDataUrl: '',
      sessionContext: {},
      contextualFollowUp: false,
      flexComparison: { basePrompt: 'Compare E4.Flex vs E5.Flex' },
      index: { id: 'stub' },
    },
    {
      analyzeIntent: async () => ({ route: 'quote_request', extractedInputs: {} }),
      analyzeImageIntent: async () => ({ route: 'quote_request', extractedInputs: {} }),
      fallbackIntentOnAnalysisFailure: () => null,
      buildServiceUnavailableMessage: () => '',
      enrichExtractedInputsForFamily: (intent) => intent,
      reconcileIntentWithHeuristics: (_text, intent) => ({ ...intent, shouldQuote: true }),
      shouldForceQuoteFollowUpRoute: () => false,
      isSessionQuoteFollowUp: () => false,
      applyQuoteFollowUpIntentOverride: (intent) => intent,
      reconcilePostIntentFollowUp: ({ intent }) => ({ intent, postIntentFlexComparison: { basePrompt: 'Compare E4.Flex vs E5.Flex' } }),
      extractFlexComparisonContext: () => ({ basePrompt: 'Compare E4.Flex vs E5.Flex' }),
      buildFlexComparisonReplyPayload: ({ flexComparison }) => ({ mode: 'quote', message: flexComparison.basePrompt }),
      buildFlexComparisonQuote: () => null,
      buildFlexComparisonNarrative: () => '',
    },
  );

  assert.equal(result.payload.mode, 'quote');
  assert.match(result.payload.message, /Compare E4\.Flex vs E5\.Flex/);
});

test('intent pipeline returns enriched intent when no immediate payload applies', async () => {
  const result = await resolveIntentPipeline(
    {
      cfg: {},
      conversation: [],
      effectiveUserText: 'Quote Oracle Integration Cloud Standard 2 instances',
      userText: 'Quote Oracle Integration Cloud Standard 2 instances',
      imageDataUrl: '',
      sessionContext: {},
      contextualFollowUp: false,
      flexComparison: null,
      index: {},
    },
    {
      analyzeIntent: async () => ({ route: 'quote_request', extractedInputs: { instances: 2 } }),
      analyzeImageIntent: async () => ({ route: 'quote_request', extractedInputs: { instances: 2 } }),
      fallbackIntentOnAnalysisFailure: () => null,
      buildServiceUnavailableMessage: () => '',
      enrichExtractedInputsForFamily: (intent) => ({ ...intent, serviceFamily: 'integration_oic_standard' }),
      reconcileIntentWithHeuristics: (_text, intent) => ({ ...intent, shouldQuote: true }),
      shouldForceQuoteFollowUpRoute: () => false,
      isSessionQuoteFollowUp: () => false,
      applyQuoteFollowUpIntentOverride: (intent) => intent,
      reconcilePostIntentFollowUp: ({ intent }) => ({ intent, postIntentFlexComparison: null }),
      extractFlexComparisonContext: () => null,
      buildFlexComparisonReplyPayload: () => null,
      buildFlexComparisonQuote: () => null,
      buildFlexComparisonNarrative: () => '',
    },
  );

  assert.equal(result.payload, null);
  assert.equal(result.intent.serviceFamily, 'integration_oic_standard');
  assert.equal(result.intent.shouldQuote, true);
});
