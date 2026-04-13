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

test('normalizer routes natural spanish required-input questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Antes de cotizar Base Database Service, que informacion necesito?',
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'Antes de cotizar Base Database Service, que informacion necesito?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes natural quote-preparation questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Como preparo una quote de OIC Standard?',
    assumptions: [],
    serviceFamily: 'integration_oic_standard',
    serviceName: 'Oracle Integration Cloud Standard',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'Como preparo una quote de OIC Standard?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes hybrid quote-lead missing-input questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Ayudame a cotizar OIC Standard, que datos faltan?',
    assumptions: [],
    serviceFamily: 'integration_oic_standard',
    serviceName: 'Oracle Integration Cloud Standard',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'Ayudame a cotizar OIC Standard, que datos faltan?');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes hybrid quote-lead explanation-first questions to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Quote OCI DNS, but tell me first what inputs you need',
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'DNS',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'Quote OCI DNS, but tell me first what inputs you need');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes generic OIC SKU composition questions to product discovery and infers the generic OIC family', () => {
  const result = normalizeIntentResult({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: "Cuales son los SKU's requeridos en una quote de OIC?",
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, "Cuales son los SKU's requeridos en una quote de OIC?");

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.serviceFamily, 'integration_oic');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes generic VM SKU composition questions to product discovery and infers the generic VM family', () => {
  const result = normalizeIntentResult({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: "Cuales son los SKU's requeridos en una quote de Virtual Machines (Instances)?",
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, "Cuales son los SKU's requeridos en una quote de Virtual Machines (Instances)?");

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.serviceFamily, 'compute_vm_generic');
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

test('normalizer routes pricing-dimension questions with explicit measurable inputs to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'quote',
    route: 'quote_request',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Explain OCI FastConnect pricing dimensions for 10 Gbps.',
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { bandwidthGbps: 10 },
    confidence: 0.78,
    annualRequested: false,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'network', useDeterministicEngine: true },
  }, 'Explain OCI FastConnect pricing dimensions for 10 Gbps.');

  assert.equal(result.route, 'product_discovery');
  assert.equal(result.quotePlan.action, 'discover');
  assert.equal(result.quotePlan.targetType, 'service');
  assert.equal(result.quotePlan.useDeterministicEngine, false);
});

test('normalizer routes billing questions with explicit endpoint counts to product discovery instead of quote', () => {
  const result = normalizeIntentResult({
    intent: 'quote',
    route: 'quote_request',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'How is OCI Health Checks billed for 12 endpoints?',
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 12 },
    confidence: 0.77,
    annualRequested: false,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'network', useDeterministicEngine: true },
  }, 'How is OCI Health Checks billed for 12 endpoints?');

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

test('normalizer extracts spanish memory and storage wording from compute prompts', () => {
  const result = normalizeIntentResult({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Quote VM.Standard.E4.Flex 4 OCPUs con 32 GB de memoria y 200 GB de almacenamiento',
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Virtual Machine Flex',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'Quote VM.Standard.E4.Flex 4 OCPUs con 32 GB de memoria y 200 GB de almacenamiento');

  assert.equal(result.extractedInputs.ocpus, 4);
  assert.equal(result.extractedInputs.memoryGb, 32);
  assert.equal(result.extractedInputs.capacityGb, 200);
});

test('normalizer extracts spanish users wording from analytics prompts', () => {
  const result = normalizeIntentResult({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Quote Oracle Analytics Cloud Enterprise 50 usuarios',
    assumptions: [],
    serviceFamily: 'analytics_oac_enterprise',
    serviceName: 'Oracle Analytics Cloud Enterprise',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'Quote Oracle Analytics Cloud Enterprise 50 usuarios');

  assert.equal(result.extractedInputs.users, 50);
});

test('normalizer extracts spanish waf instance wording from security prompts', () => {
  const result = normalizeIntentResult({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Quote Web Application Firewall con 2 instancias de WAF y 25000000 requests por mes',
    assumptions: [],
    serviceFamily: 'security_waf',
    serviceName: 'Web Application Firewall',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'Quote Web Application Firewall con 2 instancias de WAF y 25000000 requests por mes');

  assert.equal(result.extractedInputs.wafInstances, 2);
  assert.equal(result.extractedInputs.requestCount, 25000000);
});

test('normalizer extracts spanish storage wording in tb units', () => {
  const result = normalizeIntentResult({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Quote Base Database Service con 2 TB de almacenamiento',
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.8,
    annualRequested: false,
    quotePlan: {},
  }, 'Quote Base Database Service con 2 TB de almacenamiento');

  assert.equal(result.extractedInputs.capacityGb, 2048);
});
