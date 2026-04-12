'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const { loadAssistantWithStubs, buildIndex, metric, payg, product } = require('./assistant-test-helpers');

const ROOT = path.resolve(__dirname, '..');
const { normalizeCatalog } = require(path.join(ROOT, 'catalog.js'));

test('each-metric quote uses explicit job count for OCI Batch instead of defaulting to one', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 4 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Batch 4 jobs',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B112107/);
  assert.match(reply.message, /\$8\b/);
});

test('monitoring datapoints quote converts datapoints into million-datapoint units', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { requestCount: 2500000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Monitoring Ingestion 2500000 datapoints',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90925/);
  assert.match(reply.message, /\$3\.125\b/);
});

test('https delivery quote converts delivery operations into million-operation units', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { requestCount: 3000000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Notifications HTTPS Delivery 3000000 delivery operations',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90940/);
  assert.match(reply.message, /\$12\b/);
});

test('fleet application management uses managed resource count directly', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 5 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Fleet Application Management 5 managed resources per month',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B110475/);
  assert.match(reply.message, /\$35\b/);
});

test('data safe on-prem uses target database count directly', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_data_safe',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Data Safe for On-Premises Databases 2 target databases',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B92733/);
  assert.match(reply.message, /\$40\b/);
});

test('registry-backed request-volume quote overrides weak clarification from the intent model', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: true,
    clarificationQuestion: 'What is the average size of each event in MB?',
    reformulatedRequest: 'OCI Generative AI Memory Ingestion for 2000 events',
    assumptions: [],
    serviceFamily: 'ai_generative',
    serviceName: 'oci_generative_ai',
    extractedInputs: { requestCount: 2000 },
    confidence: 0.8,
    annualRequested: false,
    normalizedRequest: 'Quote OCI Generative AI Memory Ingestion 2000 events',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Generative AI Memory Ingestion 2000 events',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B112383/);
  assert.doesNotMatch(reply.message, /B112384/);
  assert.doesNotMatch(reply.message, /average size of each event in MB/i);
});

test('memory ingestion unresolved quote uses family metadata instead of a hardcoded assistant branch', async () => {
  const unresolvedIndex = normalizeCatalog({
    'metrics.json': {
      items: [
        metric('m-transactions-ten-thousand', '10,000 Transactions'),
        metric('m-storage-hour', 'Gigabyte Storage Per Hour'),
      ],
    },
    'products.json': {
      items: [
        product({
          partNumber: 'B110463',
          displayName: 'OCI Generative AI Agents - Data Ingestion',
          serviceCategoryDisplayName: 'OCI Generative AI Agents',
          metricId: 'm-transactions-ten-thousand',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(0.0003)],
        }),
        product({
          partNumber: 'B112384',
          displayName: 'OCI Generative AI - Memory Retention',
          serviceCategoryDisplayName: 'OCI Generative AI - Search and Retrieval',
          metricId: 'm-storage-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.01)],
        }),
      ],
    },
    'productpresets.json': { items: [] },
  });

  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ai_memory_ingestion',
    serviceName: 'OCI Generative AI - Memory Ingestion',
    extractedInputs: { requestCount: 2000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: {
      action: 'quote',
      targetType: 'service',
      domain: 'analytics',
      candidateFamilies: ['ai_memory_ingestion'],
      missingInputs: [],
      useDeterministicEngine: true,
    },
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index: unresolvedIndex,
    conversation: [],
    userText: 'Quote OCI Generative AI Memory Ingestion 2000 events',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote_unresolved');
  assert.match(reply.message, /does not expose a direct quotable SKU/i);
  assert.match(reply.message, /B110463/);
  assert.match(reply.message, /B112384/);
});

test('vector store retrieval converts 1000-request metrics without requiring commas in the metric name', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { requestCount: 5000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Generative AI Vector Store Retrieval 5000 requests',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B112416/);
  assert.match(reply.message, /\$2\.5\b/);
});

test('web search converts 1000-request metrics without requiring commas in the metric name', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { requestCount: 12000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Generative AI Web Search 12000 requests',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B111973/);
  assert.match(reply.message, /\$120\b/);
});

test('generic rerank transaction prompt asks for dedicated cluster-hours instead of inventing a transactional quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { requestCount: 25000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Generative AI Cohere Rerank 25000 transactions',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'clarification');
  assert.match(reply.message, /cluster-hours/i);
  assert.doesNotMatch(reply.message, /B111015/);
});
