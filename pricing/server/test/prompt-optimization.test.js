'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const intentExtractorPath = path.join(ROOT, 'intent-extractor.js');
const genaiPath = path.join(ROOT, 'genai.js');

const VALID_INTENT = JSON.stringify({
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
});

function withEnv(overrides, fn) {
  const previous = {};
  for (const [key, value] of Object.entries(overrides)) {
    previous[key] = process.env[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }

  try {
    return fn();
  } finally {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

function loadIntentExtractorWithCapturedMessages({ modelOutput = VALID_INTENT } = {}) {
  delete require.cache[intentExtractorPath];
  delete require.cache[genaiPath];

  const calls = [];
  require.cache[genaiPath] = {
    id: genaiPath,
    filename: genaiPath,
    loaded: true,
    exports: {
      runChat: async ({ messages }) => {
        calls.push(messages);
        return { data: { text: modelOutput } };
      },
      runMultimodalChat: async () => ({ data: { text: modelOutput } }),
      extractChatText: (payload) => String(payload?.text || ''),
      loadGenAISettings: () => ({}),
    },
  };

  return {
    ...require(intentExtractorPath),
    calls,
  };
}

function buildConversation(turnCount) {
  return Array.from({ length: turnCount }, (_item, index) => ({
    role: index % 2 === 0 ? 'user' : 'assistant',
    content: `turn-${index + 1}`,
  }));
}

test('analyzeIntent sends at most the last 6 conversation turns to GenAI', async () => {
  await withEnv({
    OCI_GENAI_INTENT_HISTORY_TURNS: undefined,
  }, async () => {
    const { analyzeIntent, calls } = loadIntentExtractorWithCapturedMessages();
    const conversation = buildConversation(20);

    await analyzeIntent(
      { modelId: 'test-model', compartment: 'ocid1.compartment.oc1..example' },
      conversation,
      'Quote OCI FastConnect 10 Gbps',
      null,
    );

    assert.equal(calls.length, 1);
    const sentMessages = calls[0];
    assert.equal(sentMessages.length, 7);
    assert.deepEqual(
      sentMessages.slice(0, 6).map((entry) => entry.content),
      conversation.slice(-6).map((entry) => entry.content),
    );
    assert.equal(sentMessages[6].content, 'Quote OCI FastConnect 10 Gbps');
  });
});

test('analyzeIntent history limit honors OCI_GENAI_INTENT_HISTORY_TURNS override', async () => {
  await withEnv({
    OCI_GENAI_INTENT_HISTORY_TURNS: '3',
  }, async () => {
    const { analyzeIntent, calls } = loadIntentExtractorWithCapturedMessages();
    const conversation = buildConversation(10);

    await analyzeIntent(
      { modelId: 'test-model', compartment: 'ocid1.compartment.oc1..example' },
      conversation,
      'Quote OCI Block Volume',
      null,
    );

    assert.equal(calls.length, 1);
    const sentMessages = calls[0];
    assert.equal(sentMessages.length, 4);
    assert.deepEqual(
      sentMessages.slice(0, 3).map((entry) => entry.content),
      conversation.slice(-3).map((entry) => entry.content),
    );
    assert.equal(sentMessages[3].content, 'Quote OCI Block Volume');
  });
});

test('genai token budget guard logs a warning when the estimated input exceeds the threshold', () => {
  delete require.cache[genaiPath];
  const { maybeWarnOnTokenBudget } = require(genaiPath);
  const warnings = [];
  const requestLogger = {
    warn(payload, message) {
      warnings.push({ payload, message });
    },
  };

  const result = maybeWarnOnTokenBudget({
    logger: requestLogger,
    profile: 'intent',
    kind: 'chat',
    modelId: 'test-model',
    systemPrompt: 'S'.repeat(200),
    messages: [{ role: 'USER', content: [{ type: 'TEXT', text: 'U'.repeat(200) }] }],
    env: { OCI_GENAI_TOKEN_BUDGET: '50' },
  });

  assert.equal(result.exceeded, true);
  assert.equal(warnings.length, 1);
  assert.equal(warnings[0].payload.event, 'genai.token_budget.exceeded');
  assert.equal(warnings[0].payload.profile, 'intent');
  assert.equal(warnings[0].payload.kind, 'chat');
  assert.equal(warnings[0].payload.modelId, 'test-model');
  assert.equal(warnings[0].payload.tokenBudget, 50);
  assert.ok(warnings[0].payload.estimatedInputTokens > 50);
});

test('genai usage logging reports OCI token counts when usage metadata is present', () => {
  delete require.cache[genaiPath];
  const { logGenAIUsage } = require(genaiPath);
  const debugEntries = [];
  const requestLogger = {
    debug(payload, message) {
      debugEntries.push({ payload, message });
    },
  };

  const usage = logGenAIUsage({
    logger: requestLogger,
    profile: 'intent',
    kind: 'chat',
    modelId: 'test-model',
    response: {
      data: {
        chatResult: {
          chatResponse: {
            usage: {
              promptTokens: 111,
              completionTokens: 22,
              totalTokens: 133,
              promptTokensDetails: {
                cachedTokens: 44,
              },
            },
          },
        },
      },
    },
  });

  assert.deepEqual(usage, {
    promptTokens: 111,
    completionTokens: 22,
    totalTokens: 133,
    cachedPromptTokens: 44,
  });
  assert.equal(debugEntries.length, 1);
  assert.equal(debugEntries[0].payload.event, 'genai.request.usage');
  assert.equal(debugEntries[0].payload.promptTokens, 111);
  assert.equal(debugEntries[0].payload.completionTokens, 22);
  assert.equal(debugEntries[0].payload.totalTokens, 133);
  assert.equal(debugEntries[0].payload.cachedPromptTokens, 44);
});
