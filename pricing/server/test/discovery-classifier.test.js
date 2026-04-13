'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  hasExplicitQuoteLead,
  isConceptualPricingQuestion,
  isDiscoveryOrExplanationQuestion,
} = require(path.join(ROOT, 'discovery-classifier.js'));

test('discovery classifier detects explicit quote leads', () => {
  assert.equal(hasExplicitQuoteLead('Quote OCI FastConnect 10 Gbps'), true);
  assert.equal(hasExplicitQuoteLead('Estimate OCI FastConnect 10 Gbps'), true);
  assert.equal(hasExplicitQuoteLead('How is OCI FastConnect billed?'), false);
});

test('discovery classifier detects conceptual pricing questions', () => {
  assert.equal(isConceptualPricingQuestion("Cuales son los SKU's requeridos en una quote de OIC?"), true);
  assert.equal(isConceptualPricingQuestion('How do I build a quote for Virtual Machines in OCI?'), true);
  assert.equal(isConceptualPricingQuestion('Quote OIC Enterprise 2 instances'), false);
});

test('discovery classifier keeps billing and pricing-dimensions prompts in discovery mode', () => {
  assert.equal(isDiscoveryOrExplanationQuestion('How is OCI Health Checks billed for 12 endpoints?'), true);
  assert.equal(isDiscoveryOrExplanationQuestion('Explain OCI FastConnect pricing dimensions for 10 Gbps.'), true);
  assert.equal(isDiscoveryOrExplanationQuestion('What options do we have for Network Firewall in OCI?'), true);
  assert.equal(isDiscoveryOrExplanationQuestion('Que me pides para cotizar OCI Health Checks?'), true);
  assert.equal(isDiscoveryOrExplanationQuestion('Antes de cotizar Base Database Service, que informacion necesito?'), true);
  assert.equal(isDiscoveryOrExplanationQuestion('Como preparo una quote de OIC Standard?'), true);
  assert.equal(isDiscoveryOrExplanationQuestion('Cotiza Base Database Service, pero primero dime que informacion necesitas'), true);
  assert.equal(isDiscoveryOrExplanationQuestion('Quote OCI DNS, but tell me first what inputs you need'), true);
});

test('discovery classifier does not misclassify explicit quote prompts as discovery', () => {
  assert.equal(isDiscoveryOrExplanationQuestion('Quote OCI Web Application Firewall with 2 instances and 25000000 requests per month'), false);
  assert.equal(isDiscoveryOrExplanationQuestion('Estimate OCI File Storage 10 TB'), false);
});
