'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const { normalizeIntentResult } = require(path.join(__dirname, '..', 'normalizer.js'));

test('normalizer routes VM shape comparison questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Que diferencia hay entre VM.Standard3.Flex y VM.Standard.E4.Flex?',
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'Que diferencia hay entre VM.Standard3.Flex y VM.Standard.E4.Flex?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'shape');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});
