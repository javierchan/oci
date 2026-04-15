'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  RESPONSE_PROMPT,
  STRUCTURED_DISCOVERY_PROMPT,
  buildConversationMessages,
  writeNaturalReply,
  writeStructuredContextReply,
} = require(path.join(ROOT, 'assistant-reply-writers.js'));

test('assistant reply writers keep the latest six conversation items plus the current prompt', () => {
  const messages = buildConversationMessages(
    [
      { role: 'user', content: '0' },
      { role: 'assistant', content: '1' },
      { role: 'user', content: '2' },
      { role: 'assistant', content: '3' },
      { role: 'user', content: '4' },
      { role: 'assistant', content: '5' },
      { role: 'user', content: '6' },
    ],
    'Current block',
  );

  assert.equal(messages.length, 7);
  assert.equal(messages[0].content, '1');
  assert.equal(messages[5].content, '6');
  assert.equal(messages[6].content, 'Current block');
});

test('assistant reply writers build natural replies with the existing response prompt and context fields', async () => {
  let captured = null;
  const result = await writeNaturalReply(
    { modelId: 'm', compartment: 'c' },
    [{ role: 'assistant', content: 'Previous reply' }],
    'Quote FastConnect',
    {
      intent: 'quote',
      summary: 'FastConnect summary',
      quoteMarkdown: '- line item',
      warningLines: ['warning'],
      assumptionLines: ['assumption'],
      candidateLines: ['candidate'],
    },
    { session: true },
    {
      buildSessionContextBlock: () => 'Session block',
      runChat: async (payload) => {
        captured = payload;
        return { data: { text: 'Final reply' } };
      },
      extractChatText: (payload) => payload.text,
    },
  );

  assert.equal(result, 'Final reply');
  assert.equal(captured.systemPrompt, RESPONSE_PROMPT);
  assert.equal(captured.maxTokens, 900);
  assert.match(captured.messages[1].content, /Session block/);
  assert.match(captured.messages[1].content, /Quotation markdown/);
  assert.match(captured.messages[1].content, /Candidates/);
});

test('assistant reply writers build structured replies with the existing discovery prompt and safe empty fallback', async () => {
  let captured = null;
  const success = await writeStructuredContextReply(
    { modelId: 'm', compartment: 'c' },
    [],
    'What do I need?',
    { session: true },
    { families: ['fastconnect'] },
    {
      buildSessionContextBlock: () => 'Session block',
      stringifyContextPack: () => 'Structured context',
      runChat: async (payload) => {
        captured = payload;
        return { data: { text: 'Structured reply' } };
      },
      extractChatText: (payload) => payload.text,
    },
  );
  const skipped = await writeStructuredContextReply(
    {},
    [],
    'What do I need?',
    {},
    {},
    {},
  );

  assert.equal(success, 'Structured reply');
  assert.equal(skipped, '');
  assert.equal(captured.systemPrompt, STRUCTURED_DISCOVERY_PROMPT);
  assert.equal(captured.maxTokens, 700);
  assert.match(captured.messages[0].content, /Structured product context/);
});

test('assistant reply writers return empty string when structured chat generation throws', async () => {
  const result = await writeStructuredContextReply(
    { modelId: 'm', compartment: 'c' },
    [],
    'Need discovery help',
    {},
    {},
    {
      buildSessionContextBlock: () => '',
      stringifyContextPack: () => '',
      runChat: async () => {
        throw new Error('boom');
      },
      extractChatText: () => 'ignored',
    },
  );

  assert.equal(result, '');
});
