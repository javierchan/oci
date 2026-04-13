'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  buildHeuristicIntentFromText,
  shouldApplyHeuristicIntentOverride,
  applyDiscoveryIntentOverride,
} = require(path.join(ROOT, 'lightweight-intent.js'));

test('lightweight intent builds discovery intent for conceptual SKU-composition prompts', () => {
  const intent = buildHeuristicIntentFromText("Cuales son los SKU's requeridos en una quote de OIC?");

  assert.ok(intent);
  assert.equal(intent.intent, 'discover');
  assert.equal(intent.route, 'product_discovery');
  assert.equal(intent.shouldQuote, false);
});

test('lightweight intent builds discovery intent for natural required-input prompts', () => {
  const intent = buildHeuristicIntentFromText('Que me pides para cotizar OCI Health Checks?');

  assert.ok(intent);
  assert.equal(intent.intent, 'discover');
  assert.equal(intent.route, 'product_discovery');
  assert.equal(intent.shouldQuote, false);
  assert.equal(intent.serviceFamily, 'edge_health_checks');
});

test('lightweight intent prefers discovery for hybrid quote-lead prompts that ask for missing inputs', () => {
  const intent = buildHeuristicIntentFromText('Cotiza Base Database Service, pero primero dime que informacion necesitas');

  assert.ok(intent);
  assert.equal(intent.intent, 'discover');
  assert.equal(intent.route, 'product_discovery');
  assert.equal(intent.shouldQuote, false);
  assert.equal(intent.serviceFamily, 'database_base_db');
});

test('lightweight intent builds quote intent for explicit quote leads', () => {
  const intent = buildHeuristicIntentFromText('Quote OCI FastConnect 10 Gbps');

  assert.ok(intent);
  assert.equal(intent.intent, 'quote');
  assert.equal(intent.route, 'quote_request');
  assert.equal(intent.shouldQuote, true);
});

test('lightweight intent decides when heuristic override should apply', () => {
  assert.equal(shouldApplyHeuristicIntentOverride('Quote OCI DNS 5000000 queries', { route: 'general_answer', shouldQuote: false }), true);
  assert.equal(shouldApplyHeuristicIntentOverride('How is OCI DNS billed?', { route: 'general_answer', shouldQuote: false }), true);
  assert.equal(shouldApplyHeuristicIntentOverride('How is OCI DNS billed?', { route: 'product_discovery', shouldQuote: false }), false);
  assert.equal(shouldApplyHeuristicIntentOverride('Quote OCI DNS, but tell me first what inputs you need', { route: 'quote_request', shouldQuote: true }), true);
});

test('lightweight intent can force a product discovery override shape', () => {
  const intent = applyDiscoveryIntentOverride({
    route: 'general_answer',
    intent: 'answer',
    shouldQuote: false,
    quotePlan: { domain: 'network' },
  });

  assert.equal(intent.route, 'product_discovery');
  assert.equal(intent.intent, 'discover');
  assert.equal(intent.shouldQuote, false);
  assert.equal(intent.quotePlan.action, 'discover');
  assert.equal(intent.quotePlan.targetType, 'service');
  assert.equal(intent.quotePlan.useDeterministicEngine, false);
  assert.equal(intent.quotePlan.domain, 'network');
});
