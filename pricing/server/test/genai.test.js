'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  buildChatDetails,
  shouldRetryWithMaxCompletionTokens,
  executeChatWithFallback,
  extractChatText,
} = require(path.join(ROOT, 'genai.js'));

test('genai builds chat details with maxTokens by default', () => {
  const details = buildChatDetails({
    cfg: { compartment: 'ocid1.compartment', modelId: 'ocid1.model' },
    messages: [{ role: 'USER', content: [{ type: 'TEXT', text: 'hi' }] }],
    maxTokens: 123,
    temperature: 0.7,
    topP: 0.8,
    topK: -1,
  });

  assert.equal(details.chatRequest.maxTokens, 123);
  assert.equal(details.chatRequest.maxCompletionTokens, undefined);
});

test('genai can build fallback chat details with maxCompletionTokens', () => {
  const details = buildChatDetails({
    cfg: { compartment: 'ocid1.compartment', modelId: 'ocid1.model' },
    messages: [{ role: 'USER', content: [{ type: 'TEXT', text: 'hi' }] }],
    maxTokens: 456,
    temperature: 0.7,
    topP: 0.8,
    topK: -1,
    maxTokenField: 'maxCompletionTokens',
  });

  assert.equal(details.chatRequest.maxTokens, undefined);
  assert.equal(details.chatRequest.maxCompletionTokens, 456);
});

test('genai detects unsupported max_tokens errors for retry', () => {
  assert.equal(
    shouldRetryWithMaxCompletionTokens(new Error("Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.")),
    true,
  );
  assert.equal(shouldRetryWithMaxCompletionTokens(new Error('network timeout')), false);
});

test('genai retries with maxCompletionTokens when the model rejects maxTokens', async () => {
  const requests = [];
  const client = {
    chat: async ({ chatDetails }) => {
      requests.push(chatDetails);
      if (requests.length === 1) {
        throw new Error("Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.");
      }
      return { text: 'ok' };
    },
  };

  const result = await executeChatWithFallback({
    client,
    cfg: { compartment: 'ocid1.compartment', modelId: 'ocid1.model' },
    messages: [{ role: 'USER', content: [{ type: 'TEXT', text: 'hi' }] }],
    maxTokens: 200,
    temperature: 0.7,
    topP: 0.8,
    topK: -1,
  });

  assert.equal(result.text, 'ok');
  assert.equal(requests.length, 2);
  assert.equal(requests[0].chatRequest.maxTokens, 200);
  assert.equal(requests[1].chatRequest.maxCompletionTokens, 200);
});

test('genai extracts text when message content is a plain string', () => {
  const text = extractChatText({
    chatResult: {
      chatResponse: {
        choices: [
          {
            message: {
              content: 'hello from model',
            },
          },
        ],
      },
    },
  });

  assert.equal(text, 'hello from model');
});
