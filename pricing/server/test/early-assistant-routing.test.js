'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  buildComputeShapeClarificationPayload,
  buildDirectFlexReply,
  resolveEarlyAssistantRouting,
  resolveEarlyFlexClarification,
} = require(path.join(ROOT, 'early-assistant-routing.js'));

test('early assistant routing returns deterministic greeting payloads before any other early logic', () => {
  const result = resolveEarlyAssistantRouting(
    {
      conversation: [],
      userText: 'hola',
      effectiveUserText: 'hola',
      index: {},
    },
    {
      buildEarlyAssistantReply: () => ({ mode: 'answer', message: 'hola-context' }),
      detectGenericComputeShapeClarification: () => null,
      extractFlexComparisonContext: () => null,
      resolveEarlyFlexComparisonClarification: () => null,
      isFlexComparisonRequest: () => false,
      detectFlexComparisonModifier: () => '',
      parseCapacityReservationUtilization: () => null,
      parseBurstableBaseline: () => null,
      buildFlexComparisonReplyPayload: () => null,
      buildFlexComparisonQuote: () => null,
      buildFlexComparisonNarrative: () => '',
    },
  );

  assert.equal(result.payload.mode, 'answer');
  assert.equal(result.payload.message, 'hola-context');
});

test('early assistant routing turns generic compute sizing into a clarification payload', () => {
  const result = resolveEarlyAssistantRouting(
    {
      conversation: [],
      userText: 'quote vm',
      effectiveUserText: 'quote vm',
      index: {},
    },
    {
      buildEarlyAssistantReply: () => null,
      detectGenericComputeShapeClarification: () => ({
        question: 'Which OCI VM shape should I use?',
        serviceFamily: 'compute_vm_generic',
        extractedInputs: { ocpus: 4, memoryGb: 16 },
      }),
      extractFlexComparisonContext: () => null,
      resolveEarlyFlexComparisonClarification: () => null,
      isFlexComparisonRequest: () => false,
      detectFlexComparisonModifier: () => '',
      parseCapacityReservationUtilization: () => null,
      parseBurstableBaseline: () => null,
      buildFlexComparisonReplyPayload: () => null,
      buildFlexComparisonQuote: () => null,
      buildFlexComparisonNarrative: () => '',
    },
  );

  assert.equal(result.payload.mode, 'clarification');
  assert.match(result.payload.message, /which oci vm shape/i);
  assert.equal(result.payload.intent.serviceFamily, 'compute_vm_generic');
});

test('early assistant routing returns flex clarification when comparison context is incomplete', () => {
  const result = resolveEarlyAssistantRouting(
    {
      conversation: [],
      userText: 'compare e4 vs e5',
      effectiveUserText: 'Compare E4.Flex vs E5.Flex with capacity reservation',
      index: {},
    },
    {
      buildEarlyAssistantReply: () => null,
      detectGenericComputeShapeClarification: () => null,
      extractFlexComparisonContext: () => ({ basePrompt: 'Compare E4.Flex vs E5.Flex' }),
      resolveEarlyFlexComparisonClarification: () => ({ mode: 'clarification', message: 'Need utilization' }),
      isFlexComparisonRequest: () => true,
      detectFlexComparisonModifier: () => 'capacity-reservation',
      parseCapacityReservationUtilization: () => null,
      parseBurstableBaseline: () => null,
      buildFlexComparisonReplyPayload: () => null,
      buildFlexComparisonQuote: () => null,
      buildFlexComparisonNarrative: () => '',
    },
  );

  assert.equal(result.payload.mode, 'clarification');
  assert.match(result.payload.message, /utilization/i);
  assert.deepEqual(result.flexComparison, { basePrompt: 'Compare E4.Flex vs E5.Flex' });
});

test('early assistant routing returns deterministic flex comparison quote payload when context is complete', () => {
  const result = resolveEarlyAssistantRouting(
    {
      conversation: [],
      userText: 'compare e4 vs e5',
      effectiveUserText: 'Compare E4.Flex vs E5.Flex',
      index: { id: 'stub' },
    },
    {
      buildEarlyAssistantReply: () => null,
      detectGenericComputeShapeClarification: () => null,
      extractFlexComparisonContext: () => ({ basePrompt: 'Compare E4.Flex vs E5.Flex' }),
      resolveEarlyFlexComparisonClarification: () => null,
      isFlexComparisonRequest: () => true,
      detectFlexComparisonModifier: () => '',
      parseCapacityReservationUtilization: () => null,
      parseBurstableBaseline: () => null,
      buildFlexComparisonReplyPayload: ({ flexComparison }) => ({ mode: 'quote', message: flexComparison.basePrompt }),
      buildFlexComparisonQuote: () => null,
      buildFlexComparisonNarrative: () => '',
    },
  );

  assert.equal(result.payload.mode, 'quote');
  assert.match(result.payload.message, /Compare E4\.Flex vs E5\.Flex/);
});

test('early assistant routing preserves flex comparison context when no early payload applies', () => {
  const result = resolveEarlyAssistantRouting(
    {
      conversation: [],
      userText: 'Quote Oracle Integration Cloud Standard',
      effectiveUserText: 'Quote Oracle Integration Cloud Standard',
      index: {},
    },
    {
      buildEarlyAssistantReply: () => null,
      detectGenericComputeShapeClarification: () => null,
      extractFlexComparisonContext: () => ({ shapes: ['E4.Flex', 'E5.Flex'] }),
      resolveEarlyFlexComparisonClarification: () => null,
      isFlexComparisonRequest: () => false,
      detectFlexComparisonModifier: () => '',
      parseCapacityReservationUtilization: () => null,
      parseBurstableBaseline: () => null,
      buildFlexComparisonReplyPayload: () => null,
      buildFlexComparisonQuote: () => null,
      buildFlexComparisonNarrative: () => '',
    },
  );

  assert.equal(result.payload, null);
  assert.deepEqual(result.flexComparison, { shapes: ['E4.Flex', 'E5.Flex'] });
});

test('early assistant routing exposes focused builders for compute-shape and flex reply paths', () => {
  const computePayload = buildComputeShapeClarificationPayload({
    question: 'Which OCI VM shape should I use?',
    serviceFamily: 'compute_vm_generic',
    extractedInputs: { ocpus: 4 },
  });
  const flexPayload = buildDirectFlexReply(
    { id: 'stub' },
    { basePrompt: 'Compare E4.Flex vs E5.Flex' },
    {
      buildFlexComparisonReplyPayload: ({ flexComparison }) => ({ mode: 'quote', message: flexComparison.basePrompt }),
      buildFlexComparisonQuote: () => null,
      buildFlexComparisonNarrative: () => '',
    },
  );
  const flexClarification = resolveEarlyFlexClarification('Compare E4.Flex vs E5.Flex', {
    resolveEarlyFlexComparisonClarification: ({ effectiveUserText }) => ({ mode: 'clarification', message: effectiveUserText }),
    isFlexComparisonRequest: () => true,
    detectFlexComparisonModifier: () => '',
    parseCapacityReservationUtilization: () => null,
    parseBurstableBaseline: () => null,
  });

  assert.equal(computePayload.intent.serviceFamily, 'compute_vm_generic');
  assert.match(flexPayload.message, /Compare E4\.Flex vs E5\.Flex/);
  assert.equal(flexClarification.mode, 'clarification');
});
