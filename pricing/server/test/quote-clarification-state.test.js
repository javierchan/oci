'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const { reconcileQuoteClarificationState } = require(path.join(ROOT, 'quote-clarification-state.js'));

test('quote clarification state returns pre-quote clarification payload when preflight clarification exists', () => {
  const result = reconcileQuoteClarificationState({
    intent: {
      shouldQuote: true,
      extractedInputs: {},
      serviceFamily: 'sample',
    },
    reformulatedRequest: 'Quote sample',
    effectiveUserText: 'Quote sample',
    userText: 'Quote sample',
    familyMeta: { clarificationQuestion: 'fallback question' },
    preflightQuote: null,
    getPreQuoteClarification: () => 'What size do you need?',
    getMissingRequiredInputs: () => [],
    getClarificationMessage: () => '',
  });

  assert.ok(result.clarificationPayload);
  assert.equal(result.clarificationPayload.mode, 'clarification');
  assert.equal(result.clarificationPayload.message, 'What size do you need?');
  assert.equal(result.intent.clarificationQuestion, 'What size do you need?');
});

test('quote clarification state clears clarification flags when family can quote despite no missing inputs', () => {
  const result = reconcileQuoteClarificationState({
    intent: {
      shouldQuote: true,
      needsClarification: true,
      clarificationQuestion: 'old',
      extractedInputs: {},
    },
    reformulatedRequest: 'Quote sample',
    effectiveUserText: 'Quote sample',
    userText: 'Quote sample',
    familyMeta: { clarificationQuestion: 'fallback question' },
    preflightQuote: { ok: true },
    getPreQuoteClarification: () => '',
    getMissingRequiredInputs: () => [],
    getClarificationMessage: () => '',
  });

  assert.equal(result.clarificationPayload, null);
  assert.equal(result.intent.needsClarification, false);
  assert.equal(result.intent.clarificationQuestion, '');
});

test('quote clarification state returns family clarification when required inputs are still missing', () => {
  const result = reconcileQuoteClarificationState({
    intent: {
      shouldQuote: true,
      extractedInputs: {},
    },
    reformulatedRequest: 'Quote sample',
    effectiveUserText: 'Quote sample',
    userText: 'Quote sample',
    familyMeta: { clarificationQuestion: 'Fallback family question' },
    preflightQuote: { ok: false },
    getPreQuoteClarification: () => '',
    getMissingRequiredInputs: () => ['instances'],
    getClarificationMessage: () => 'How many instances do you need?',
  });

  assert.ok(result.clarificationPayload);
  assert.equal(result.clarificationPayload.message, 'How many instances do you need?');
  assert.deepEqual(result.missingInputs, ['instances']);
  assert.equal(result.canQuoteDespiteMissingInputs, false);
});

test('quote clarification state does not force clarification when preflight quote can satisfy missing inputs', () => {
  const result = reconcileQuoteClarificationState({
    intent: {
      shouldQuote: true,
      extractedInputs: {},
    },
    reformulatedRequest: 'Quote sample',
    effectiveUserText: 'Quote sample',
    userText: 'Quote sample',
    familyMeta: { clarificationQuestion: 'Fallback family question' },
    preflightQuote: { ok: true },
    getPreQuoteClarification: () => '',
    getMissingRequiredInputs: () => ['instances'],
    getClarificationMessage: () => 'How many instances do you need?',
  });

  assert.equal(result.clarificationPayload, null);
  assert.deepEqual(result.missingInputs, ['instances']);
  assert.equal(result.canQuoteDespiteMissingInputs, true);
});
