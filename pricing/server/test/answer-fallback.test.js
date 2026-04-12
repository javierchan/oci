'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const { buildAnswerFallbackPayload } = require(path.join(ROOT, 'answer-fallback.js'));

test('answer fallback uses natural reply when available', async () => {
  const payload = await buildAnswerFallbackPayload({
    cfg: {},
    index: { id: 'stub' },
    conversation: [],
    userText: 'help me understand OCI pricing',
    sessionContext: null,
    intent: {
      intent: 'discover',
      assumptions: ['assumption a'],
    },
    summarizeMatches: () => ({ products: ['Product A'], presets: ['Preset A'] }),
    writeNaturalReply: async (_cfg, _conversation, _userText, context) => {
      assert.equal(context.intent, 'discover');
      assert.match(context.summary, /pricing guidance rather than a deterministic quote/i);
      assert.deepEqual(context.candidateLines, ['- Product: Product A', '- Preset: Preset A']);
      assert.deepEqual(context.assumptionLines, ['- assumption a']);
      return 'Natural answer';
    },
  });

  assert.equal(payload.mode, 'answer');
  assert.equal(payload.message, 'Natural answer');
});

test('answer fallback uses default message when natural reply is empty', async () => {
  const payload = await buildAnswerFallbackPayload({
    cfg: {},
    index: {},
    conversation: [],
    userText: 'help',
    sessionContext: null,
    intent: { intent: 'answer', assumptions: [] },
    summarizeMatches: () => ({ products: [], presets: [] }),
    writeNaturalReply: async () => '',
  });

  assert.equal(payload.mode, 'answer');
  assert.match(payload.message, /I can help with OCI pricing guidance/i);
});
