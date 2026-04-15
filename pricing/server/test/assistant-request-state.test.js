'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  buildAssistantRequestState,
  buildAssistantResponse,
} = require(path.join(ROOT, 'assistant-request-state.js'));

test('assistant request state derives effective text and request flags from existing helpers', () => {
  const result = buildAssistantRequestState(
    {
      conversation: [{ role: 'user', content: 'prev' }],
      userText: 'with DNS',
      sessionContext: { quote: true },
    },
    {
      mergeClarificationAnswer: (_conversation, userText) => `merged:${userText}`,
      mergeSessionQuoteFollowUp: (_sessionContext, mergedText) => `${mergedText} + fastconnect`,
      isShortContextualAnswer: (userText) => userText === 'with DNS',
      isCompositeOrComparisonRequest: (text) => /dns/i.test(text),
    },
  );

  assert.deepEqual(result, {
    effectiveUserText: 'merged:with DNS + fastconnect',
    contextualFollowUp: true,
    compositeLike: true,
  });
});

test('assistant request state wraps payloads with derived session context', () => {
  const result = buildAssistantResponse(
    { mode: 'quote', message: 'ok' },
    { quote: true },
    'Quote FastConnect',
    {
      buildAssistantSessionContext: (sessionContext, effectiveUserText, payload) => ({
        sessionContext,
        effectiveUserText,
        payloadMode: payload.mode,
      }),
    },
  );

  assert.deepEqual(result, {
    mode: 'quote',
    message: 'ok',
    sessionContext: {
      sessionContext: { quote: true },
      effectiveUserText: 'Quote FastConnect',
      payloadMode: 'quote',
    },
  });
});
