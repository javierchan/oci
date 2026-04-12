'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  fallbackIntentOnAnalysisFailure,
  reconcileIntentWithHeuristics,
} = require(path.join(ROOT, 'intent-reconciliation.js'));

test('intent reconciliation falls back to lightweight heuristic intent after analysis failure', () => {
  const intent = fallbackIntentOnAnalysisFailure("Cuales son los SKU's requeridos en una quote de OIC?");

  assert.ok(intent);
  assert.equal(intent.route, 'product_discovery');
  assert.equal(intent.intent, 'discover');
  assert.equal(intent.shouldQuote, false);
});

test('intent reconciliation upgrades general answers to heuristic quote requests when the user has an explicit quote lead', () => {
  const reconciled = reconcileIntentWithHeuristics('Quote OCI DNS 5000000 queries per month', {
    route: 'general_answer',
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    quotePlan: {},
  });

  assert.equal(reconciled.route, 'quote_request');
  assert.equal(reconciled.intent, 'quote');
  assert.equal(reconciled.shouldQuote, true);
});

test('intent reconciliation forces billing and SKU-composition prompts into product discovery', () => {
  const billing = reconcileIntentWithHeuristics('How is OCI Health Checks billed for 12 endpoints?', {
    route: 'general_answer',
    intent: 'answer',
    shouldQuote: false,
    quotePlan: { domain: 'network' },
  });
  const skuComposition = reconcileIntentWithHeuristics("Cuales son los SKU's requeridos en una quote de OIC?", {
    route: 'general_answer',
    intent: 'answer',
    shouldQuote: false,
    quotePlan: { domain: 'integration' },
  });

  assert.equal(billing.route, 'product_discovery');
  assert.equal(billing.intent, 'discover');
  assert.equal(billing.quotePlan.useDeterministicEngine, false);
  assert.equal(skuComposition.route, 'product_discovery');
  assert.equal(skuComposition.intent, 'discover');
  assert.equal(skuComposition.quotePlan.useDeterministicEngine, false);
});
