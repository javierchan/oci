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

test('normalizer routes pricing model questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Como se cobra Web Application Firewall en OCI?',
    assumptions: [],
    serviceFamily: 'security_waf',
    serviceName: 'Web Application Firewall',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'Como se cobra Web Application Firewall en OCI?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes licensing and prerequisite questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'What is the difference between BYOL and License Included for Base Database Service?',
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'What is the difference between BYOL and License Included for Base Database Service?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes OIC prerequisite questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'What information do I need to quote Oracle Integration Cloud Standard?',
    assumptions: [],
    serviceFamily: 'integration_oic_standard',
    serviceName: 'Oracle Integration Cloud Standard',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'What information do I need to quote Oracle Integration Cloud Standard?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes file storage billing questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'How is OCI File Storage billed?',
    assumptions: [],
    serviceFamily: 'storage_file',
    serviceName: 'OCI File Storage',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'How is OCI File Storage billed?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes OCI Functions billing questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'How is OCI Functions billed?',
    assumptions: [],
    serviceFamily: 'serverless_functions',
    serviceName: 'OCI Functions',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'How is OCI Functions billed?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes Generative AI retrieval billing questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'How is OCI Generative AI Vector Store Retrieval billed?',
    assumptions: [],
    serviceFamily: 'ai_vector_store_retrieval',
    serviceName: 'OCI Generative AI Vector Store Retrieval',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'How is OCI Generative AI Vector Store Retrieval billed?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes Vision Custom Training billing questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'How is Vision Custom Training billed in OCI?',
    assumptions: [],
    serviceFamily: 'ai_vision_custom_training',
    serviceName: 'Vision Custom Training',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'How is Vision Custom Training billed in OCI?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes Fleet Application Management billing questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'How is OCI Fleet Application Management billed?',
    assumptions: [],
    serviceFamily: 'ops_fleet_application_management',
    serviceName: 'OCI Fleet Application Management',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'How is OCI Fleet Application Management billed?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes Email Delivery billing questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'How is Email Delivery billed?',
    assumptions: [],
    serviceFamily: 'operations_email_delivery',
    serviceName: 'Email Delivery',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'How is Email Delivery billed?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes IAM SMS billing questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'How is IAM SMS billed?',
    assumptions: [],
    serviceFamily: 'operations_iam_sms',
    serviceName: 'IAM SMS',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'How is IAM SMS billed?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes AI Language billing questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'How is OCI AI Language billed?',
    assumptions: [],
    serviceFamily: 'ai_language',
    serviceName: 'OCI AI Language',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'How is OCI AI Language billed?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes Data Integration prerequisite questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'What information do I need to quote OCI Data Integration?',
    assumptions: [],
    serviceFamily: 'integration_data',
    serviceName: 'OCI Data Integration',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'What information do I need to quote OCI Data Integration?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes service options questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Que opciones tenemos para Exadata Dedicated Infrastructure?',
    assumptions: [],
    serviceFamily: 'database_exadata_dedicated',
    serviceName: 'Exadata Dedicated Infrastructure Database',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'Que opciones tenemos para Exadata Dedicated Infrastructure?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes GPU and HPC options questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'What GPU and HPC options do we have in OCI Compute?',
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'What GPU and HPC options do we have in OCI Compute?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes catalog listing questions to product discovery with catalog target', () => {
  const result = normalizeIntentResult({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'List all SKUs for FastConnect',
    assumptions: [],
    serviceFamily: 'network_fastconnect',
    serviceName: 'FastConnect',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'List all SKUs for FastConnect');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'catalog');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});
