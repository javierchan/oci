'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const intentExtractorPath = path.join(ROOT, 'intent-extractor.js');
const genaiPath = path.join(ROOT, 'genai.js');
const { resolveIntentPipeline } = require(path.join(ROOT, 'intent-pipeline.js'));
const {
  DECLARED_INTENT_FIELDS,
  DECLARED_QUOTE_PLAN_FIELDS,
  validateIntentPayload,
} = require(path.join(ROOT, 'intent-schema.js'));

const VALID_INTENT = {
  intent: 'quote',
  route: 'quote_request',
  shouldQuote: true,
  needsClarification: false,
  clarificationQuestion: '',
  reformulatedRequest: 'Quote OCI FastConnect 10 Gbps',
  assumptions: [],
  serviceFamily: 'network_fastconnect',
  serviceName: 'OCI FastConnect',
  extractedInputs: {
    bandwidthGbps: 10,
  },
  confidence: 0.9,
  annualRequested: false,
  quotePlan: {
    action: 'quote',
    targetType: 'service',
    domain: 'network',
    candidateFamilies: ['network_fastconnect'],
    missingInputs: [],
    useDeterministicEngine: true,
  },
};

function loadIntentExtractorWithModelOutput(modelOutput) {
  delete require.cache[intentExtractorPath];
  delete require.cache[genaiPath];

  require.cache[genaiPath] = {
    id: genaiPath,
    filename: genaiPath,
    loaded: true,
    exports: {
      runChat: async () => ({ data: { text: modelOutput } }),
      runMultimodalChat: async () => ({ data: { text: modelOutput } }),
      extractChatText: (payload) => String(payload?.text || ''),
      loadGenAISettings: () => ({}),
    },
  };

  return require(intentExtractorPath);
}

function buildFallbackIntent(userText = '') {
  return {
    intent: 'answer',
    route: 'general_answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: userText,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    annualRequested: false,
    quotePlan: {
      action: 'answer',
      targetType: 'general',
      domain: '',
      candidateFamilies: [],
      missingInputs: [],
      useDeterministicEngine: false,
    },
  };
}

async function withSuppressedConsoleWarn(run) {
  const originalWarn = console.warn;
  console.warn = () => {};
  try {
    return await run();
  } finally {
    console.warn = originalWarn;
  }
}

test('intent schema declares the intent fields used by assistant and dependency resolution', () => {
  const assistantFields = ['intent', 'serviceFamily', 'extractedInputs', 'reformulatedRequest', 'quotePlan', 'route'];
  const resolverFields = ['serviceFamily'];

  for (const field of assistantFields) {
    assert.equal(DECLARED_INTENT_FIELDS.includes(field), true, `missing declared assistant field: ${field}`);
  }
  for (const field of resolverFields) {
    assert.equal(DECLARED_INTENT_FIELDS.includes(field), true, `missing declared resolver field: ${field}`);
  }

  assert.equal(DECLARED_QUOTE_PLAN_FIELDS.includes('action'), true);
  assert.equal(DECLARED_QUOTE_PLAN_FIELDS.includes('targetType'), true);
  assert.equal(DECLARED_QUOTE_PLAN_FIELDS.includes('candidateFamilies'), true);
  assert.equal(validateIntentPayload(VALID_INTENT).ok, true);
});

test('intent pipeline falls back when genai returns malformed intent payloads', async () => {
  const malformedCases = [
    {
      name: 'non-json text',
      modelOutput: 'sorry, here is a sentence instead of JSON',
    },
    {
      name: 'missing required fields',
      modelOutput: JSON.stringify({ intent: 'quote' }),
    },
    {
      name: 'invalid route enum',
      modelOutput: JSON.stringify({ ...VALID_INTENT, route: 'quote_now' }),
    },
    {
      name: 'string shouldQuote',
      modelOutput: JSON.stringify({ ...VALID_INTENT, shouldQuote: 'yes' }),
    },
    {
      name: 'assumptions wrong type',
      modelOutput: JSON.stringify({ ...VALID_INTENT, assumptions: 'none' }),
    },
    {
      name: 'quotePlan wrong type',
      modelOutput: JSON.stringify({ ...VALID_INTENT, quotePlan: 'quote' }),
    },
  ];

  for (const malformedCase of malformedCases) {
    await withSuppressedConsoleWarn(async () => {
      const { analyzeIntent } = loadIntentExtractorWithModelOutput(malformedCase.modelOutput);
      let fallbackCalls = 0;

      const result = await resolveIntentPipeline(
        {
          cfg: {},
          conversation: [],
          effectiveUserText: 'quote something',
          userText: 'quote something',
          imageDataUrl: '',
          sessionContext: {},
          contextualFollowUp: false,
          flexComparison: null,
          index: {},
        },
        {
          analyzeIntent,
          analyzeImageIntent: async () => VALID_INTENT,
          fallbackIntentOnAnalysisFailure: (text) => {
            fallbackCalls += 1;
            return buildFallbackIntent(text);
          },
          buildServiceUnavailableMessage: () => '',
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

      assert.equal(fallbackCalls, 1, `${malformedCase.name} should trigger fallback exactly once`);
      assert.equal(result.payload, null);
      assert.equal(result.intent.intent, 'answer');
      assert.equal(result.intent.route, 'general_answer');
      assert.equal(result.intent.shouldQuote, false);
    });
  }
});
