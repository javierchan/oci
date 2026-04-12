'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const { loadAssistantWithStubs, metric, payg, product, assertWithin, extendIndexWithProducts, buildIndex } = require('./assistant-test-helpers');

const ROOT = path.resolve(__dirname, '..');
const { normalizeCatalog } = require(path.join(ROOT, 'catalog.js'));

test('flex comparison follow-ups produce a comparison table instead of collapsing to one shape', async () => {
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

  const conversation = [
    {
      role: 'user',
      content: 'Compare E4.Flex vs E5.Flex vs A1.Flex for 8 OCPUs 128 GB RAM, 744h, with and without Capacity Reservation',
    },
    {
      role: 'assistant',
      content: 'For the Flex shape comparison, what capacity reservation utilization should I use: for example `1.0`, `0.7`, or `0.5`?',
    },
    { role: 'user', content: '1.0' },
    {
      role: 'assistant',
      content: 'For the non-capacity-reservation side of the comparison, should I use `On demand` pricing?',
    },
  ];

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation,
    userText: 'On demand',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /\| Shape \| On-demand \$\/Mo \| Capacity Reservation \$\/Mo \|/);
  assert.match(reply.message, /\| E4\.FLEX \|/);
  assert.match(reply.message, /\| E5\.FLEX \|/);
  assert.match(reply.message, /\| A1\.FLEX \|/);
  assert.doesNotMatch(reply.message, /API Gateway/i);
});
