'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const { loadAssistantWithStubs, metric, payg, product, assertWithin, extendIndexWithProducts, buildIndex } = require('./assistant-test-helpers');

const ROOT = path.resolve(__dirname, '..');
const { normalizeCatalog } = require(path.join(ROOT, 'catalog.js'));

test('explicit GPU compute quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - A10 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B95909');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 2678.4, 0.001);
});

test('explicit GPU A100 v2 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - A100 - v2 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B95910');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 3571.2, 0.001);
});

test('explicit GPU E3 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - E3 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B95911');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 1785.6, 0.001);
});

test('explicit GPU B200 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - B200 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B95912');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 9225.6, 0.001);
});

test('explicit GPU GB200 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - GB200 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B95913');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 10564.8, 0.001);
});

test('explicit Big Data Service HPC quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 16 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Big Data Service - Compute - HPC with 16 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B91130');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 16);
  assertWithin(reply.quote?.totals?.monthly, 3928.32, 0.001);
});

test('HPC compute quote with node wording still resolves deterministically through the matched OCPU SKU', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute HPC - X7 with 2 nodes for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /not available yet/i);
  assert.match(reply.message, /OCI Compute HPC - X7/i);
});

test('explicit HPC compute quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 52 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute HPC - X7 with 52 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B90398');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 52);
  assertWithin(reply.quote?.totals?.monthly, 11606.4, 0.001);
});

test('explicit HPC E5 compute quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 40 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute HPC - E5 with 40 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B96531');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 40);
  assertWithin(reply.quote?.totals?.monthly, 8035.2, 0.001);
});

test('explicit bare metal GPU metered quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Bare Metal GPU Standard - X7 - Metered with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89141');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 4761.6, 0.001);
});

test('explicit bare metal standard x7 metered quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 52 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Bare Metal Standard - X7 - Metered with 52 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89137');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 52);
  assertWithin(reply.quote?.totals?.monthly, 2901.6, 0.001);
});

test('explicit bare metal dense i/o x7 metered quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 52 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Bare Metal Dense I/O - X7 - Metered with 52 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89139');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 52);
  assertWithin(reply.quote?.totals?.monthly, 3327.168, 0.001);
});

test('explicit vm standard x7 metered quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Standard - X7 - Metered with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89135');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 327.36, 0.001);
});

test('explicit vm standard x5 quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Standard - X5 with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B88511');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 267.84, 0.001);
});

test('explicit vm standard B1 quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 4 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Standard - B1 with 4 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B91120');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 4);
  assertWithin(reply.quote?.totals?.monthly, 59.52, 0.001);
});

test('explicit standard E2 quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Standard - E2 with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B90425');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 184.512, 0.001);
});

test('explicit vm standard x5 metered quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Standard - X5 - Metered with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89133');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 297.6, 0.001);
});

test('explicit vm dense i/o x7 metered quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Dense I/O - X7 - Metered with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89136');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 386.88, 0.001);
});

test('explicit vm dense i/o x7 quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Dense I/O - X7 with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B88515');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 476.16, 0.001);
});

test('explicit vm dense i/o x5 metered quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Dense I/O - X5 - Metered with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89134');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 416.64, 0.001);
});

test('explicit bare metal GPU quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Bare Metal GPU Standard - X7 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B88517');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 4315.2, 0.001);
});

test('explicit vm gpu standard x7 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine GPU Standard - X7 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B88518');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 4017.6, 0.001);
});

test('explicit GPU Standard V2 metered quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote GPU Standard - V2 - Metered with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89735');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 3571.2, 0.001);
});

test('explicit GPU Standard V2 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote GPU Standard - V2 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89734');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 3273.6, 0.001);
});

test('explicit GPU H100 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - H100 with 4 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B98415');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 4);
  assertWithin(reply.quote?.totals?.monthly, 14284.8, 0.001);
});

test('explicit GPU L40S quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - L40S with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B98416');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 5356.8, 0.001);
});

test('explicit GPU H200 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - H200 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B98417');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 8035.2, 0.001);
});

test('explicit GPU MI300X quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - MI300X with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B98418');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 6249.6, 0.001);
});

test('legacy fixed VM alias quote resolves to the mapped fixed-shape SKU when deterministic coverage exists', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote VM.Standard1.4 for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /not available yet/i);
  assert.match(reply.message, /Virtual Machine Standard - X5/i);
});

test('legacy DenseIO VM alias quote resolves to the mapped fixed-shape SKU when deterministic coverage exists', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote VM.DenseIO2.8 for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /not available yet/i);
  assert.match(reply.message, /Virtual Machine Dense I\/O - X7/i);
});

test('metered legacy DenseIO VM alias quote resolves to the mapped metered SKU when deterministic coverage exists', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote VM.DenseIO2.8 metered for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /not available yet/i);
  assert.match(reply.message, /Virtual Machine Dense I\/O - X7 \(Metered\)/i);
  assert.match(reply.message, /VM\.DenseIO\.E4\.Flex/i);
});

test('explicit E2 micro quote with OCPU units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote VM.Standard.E2.1.Micro with 1 OCPU for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B91444');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 1);
  assertWithin(reply.quote?.totals?.monthly, 0, 0.001);
  assert.doesNotMatch(reply.message, /Full Stack Disaster Recovery/i);
});

test('unsupported Windows OS compute quote returns safe unavailability instead of an unreliable quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute - Windows OS for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /not available yet/i);
  assert.match(reply.message, /Windows OS/i);
  assert.match(reply.message, /Guest OS licensing lines/i);
  assert.match(reply.message, /Quote the underlying OCI compute shape separately/i);
});

test('explicit Windows OS compute quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute - Windows OS with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B88318/);
  assert.match(reply.message, /\$273\.79/);
});

test('unsupported metered Windows OS compute quote keeps metered licensing guidance', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Windows OS - Metered for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /Windows OS - Metered/i);
  assert.match(reply.message, /Metered guest OS licensing lines/i);
});

test('explicit metered Windows OS compute quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute - Windows OS - Metered with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B87674/);
  assert.match(reply.message, /\$309\.50/);
});

test('explicit Microsoft SQL Enterprise quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute - Microsoft SQL Enterprise with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91372/);
  assert.match(reply.message, /\$1,845\.12/);
});

test('explicit Microsoft SQL Standard quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute - Microsoft SQL Standard with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91373/);
  assert.match(reply.message, /\$833\.28/);
});

test('unsupported Cloud@Customer GPU quote returns safe unavailability with public-region alternatives', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote GPU.L40S on Compute Cloud@Customer for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /not available yet/i);
  assert.match(reply.message, /Cloud@Customer/i);
  assert.match(reply.message, /VM\.Standard\.E5\.Flex/i);
});

test('explicit Cloud@Customer GPU quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Oracle Compute Cloud@Customer - Compute - GPU.L40S with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B110965/);
  assert.match(reply.message, /\$5,208\.00/);
});

test('explicit Cloud@Customer GPU resource commit quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Oracle Compute Cloud@Customer - Compute - GPU.L40S - Resource Commit with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B111454/);
  assert.match(reply.message, /\$892\.80/);
});

test('transaction-based ai quote handles 10,000-transaction metrics', async () => {
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
    extractedInputs: { requestCount: 50000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Generative AI Large Cohere 50000 transactions',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B108077/);
});

test('vision custom training bills direct training hours instead of multiplying by monthly uptime', async () => {
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
    extractedInputs: { serviceHours: 10 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Vision Custom Training 10 training hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94977/);
  assert.match(reply.message, /\$14\.7\b/);
});

test('speech bills direct transcription hours instead of default monthly uptime', async () => {
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
    extractedInputs: { serviceHours: 3 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Speech 3 transcription hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94896/);
  assert.match(reply.message, /\$0\.048\b/);
});

test('media flow prompt prefers the exact below-30fps variant and bills explicit minutes', async () => {
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
    extractedInputs: { minuteQuantity: 120 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Media Flow HD below 30fps 120 minutes of output media content',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B95282/);
  assert.match(reply.message, /\$0\.72\b/);
});

test('stored video analysis bills explicit processed video minutes', async () => {
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
    extractedInputs: { minuteQuantity: 90 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Vision Stored Video Analysis 90 processed video minutes',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B110617/);
  assert.match(reply.message, /\$0\.27\b/);
});

test('data safe each-metric quote uses explicit database count instead of defaulting to one', async () => {
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
    extractedInputs: { quantity: 3 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Data Safe for Database Cloud Service 3 databases',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91632/);
  assert.match(reply.message, /\$30\b/);
});
