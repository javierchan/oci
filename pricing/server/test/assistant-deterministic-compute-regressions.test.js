'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const { loadAssistantWithStubs, buildIndex } = require('./assistant-test-helpers');

const ROOT = path.resolve(__dirname, '..');
const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));

test('generic intel VM request asks for shape clarification instead of quoting block storage only', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm_generic',
    serviceName: '',
    extractedInputs: {
      ocpus: 4,
      memoryGb: 16,
      capacityGb: 200,
      processorVendor: 'intel',
    },
    confidence: 0.8,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Dame el quote para una virtual machine con procesador intel, 4 OCPUs, 16 GB RAM, 200 GB Block Storage',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'clarification');
  assert.match(reply.message, /which oci vm shape/i);
  assert.doesNotMatch(reply.message, /OCI Block Volume/i);
});

test('generic AMD VM request asks for AMD flex shape clarification instead of falling back to unresolved prose', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'explain',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: '',
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.2,
    annualRequested: false,
    normalizedRequest: '',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Dame el quote de una VM AMD con 8 OCPUs, 32 GB RAM y 1 TB de block storage',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'clarification');
  assert.match(reply.message, /amd vm shape/i);
  assert.match(reply.message, /VM\.Standard\.E4\.Flex/);
});

test('generic Arm VM request asks for A1 flex clarification instead of Intel options', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'explain',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: '',
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.2,
    annualRequested: false,
    normalizedRequest: '',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Dame un quote de una virtual machine arm con 2 OCPUs, 12 GB RAM y 100 GB Block Storage',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'clarification');
  assert.match(reply.message, /arm vm shape/i);
  assert.match(reply.message, /VM\.Standard\.A1\.Flex/);
  assert.doesNotMatch(reply.message, /For Intel/i);
});

test('generic intel VM shape follow-up keeps prior sizing and attached block storage', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'E4.Flex',
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {
      ocpus: 4,
      memoryGb: 16,
      capacityGb: 200,
      shapeSeries: 'E4.FLEX',
      processorVendor: 'intel',
    },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: 'E4.Flex',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [
      { role: 'user', content: 'Dame el quote para una virtual machine con procesador intel, 4 OCPUs, 16 GB RAM, 200 GB Block Storage' },
      { role: 'assistant', content: 'Which OCI VM shape should I use for that machine? For Intel, common options are `VM.Standard3.Flex`, `VM.Optimized3.Flex`, or the fixed-shape family `VM.Standard2.x`. Once you pick the shape, I can combine it with the attached Block Volume sizing.' },
    ],
    userText: 'E4.Flex',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B93113/);
  assert.match(reply.message, /B93114/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
});

test('VM.Standard3.Flex quote resolves to X9 compute plus block volume', async () => {
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard3.Flex 1 OCPU 8 GB RAM with 200 GB Block Storage 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B94176/);
  assert.match(quote.markdown, /B94177/);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
});

test('Standard3.Flex alias quote resolves to X9 compute plus block volume', async () => {
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote Standard3.Flex 1 OCPU 8 GB RAM with 200 GB Block Storage 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B94176/);
  assert.match(quote.markdown, /B94177/);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
});

test('VM.Optimized3.Flex quote resolves to optimized X9 compute', async () => {
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Optimized3.Flex 2 OCPUs 16 GB RAM 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B93311/);
  assert.match(quote.markdown, /B93312/);
});

test('Optimized3.Flex alias quote resolves to optimized X9 compute', async () => {
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote Optimized3.Flex 2 OCPUs 16 GB RAM 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B93311/);
  assert.match(quote.markdown, /B93312/);
});

test('VM.Standard2 fixed shape quote uses fixed X7 sizing even without explicit memory', async () => {
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard2.4 with 200 GB Block Storage');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B88514/);
  assert.match(quote.markdown, /\|\s*4\s*\|/);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
});

test('Standard2.4 alias quote uses fixed X7 sizing even without explicit memory', async () => {
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote Standard2.4 with 200 GB Block Storage');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B88514/);
  assert.match(quote.markdown, /\|\s*4\s*\|/);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
});

test('DenseIO.E4.Flex alias quote resolves to dense I/O compute lines', async () => {
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote DenseIO.E4.Flex 2 OCPUs 16 GB RAM 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B93121/);
  assert.match(quote.markdown, /B93122/);
});

test('VM.Standard.A2.Flex quote resolves to A2 compute lines', async () => {
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard.A2.Flex 1 OCPU 6 GB RAM 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B109529/);
  assert.match(quote.markdown, /B109530/);
});

test('VM.Standard.A4.Flex quote resolves to A4 compute lines', async () => {
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard.A4.Flex 2 OCPUs 12 GB RAM 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B112145/);
  assert.match(quote.markdown, /B112146/);
});
