'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  buildFlexComparisonClarificationPayload,
  resolveEarlyFlexComparisonClarification,
  buildFlexComparisonReplyPayload,
} = require(path.join(ROOT, 'flex-comparison-flow.js'));

test('early flex comparison clarification asks for capacity reservation utilization when missing', () => {
  const payload = resolveEarlyFlexComparisonClarification({
    effectiveUserText: 'Compare E4.Flex vs E5.Flex with capacity reservation',
    isFlexComparisonRequest: () => true,
    detectFlexComparisonModifier: () => 'capacity-reservation',
    parseCapacityReservationUtilization: () => null,
    parseBurstableBaseline: () => null,
  });

  assert.ok(payload);
  assert.equal(payload.mode, 'clarification');
  assert.match(payload.message, /capacity reservation utilization/i);
});

test('early flex comparison clarification asks for burstable baseline when missing', () => {
  const payload = resolveEarlyFlexComparisonClarification({
    effectiveUserText: 'Compare E4.Flex vs E5.Flex burstable',
    isFlexComparisonRequest: () => true,
    detectFlexComparisonModifier: () => 'burstable',
    parseCapacityReservationUtilization: () => null,
    parseBurstableBaseline: () => null,
  });

  assert.ok(payload);
  assert.equal(payload.mode, 'clarification');
  assert.match(payload.message, /burstable baseline/i);
});

test('comparison clarification asks for on-demand side when capacity reservation comparison lacks it', () => {
  const payload = buildFlexComparisonClarificationPayload({
    modifierKind: 'capacity-reservation',
    utilization: 0.7,
    withoutCrMode: '',
    requireWithoutCrMode: true,
  });

  assert.ok(payload);
  assert.equal(payload.mode, 'clarification');
  assert.match(payload.message, /On demand/i);
});

test('comparison clarification blocks unsupported reserved non-capacity-reservation side', () => {
  const payload = buildFlexComparisonClarificationPayload({
    modifierKind: 'capacity-reservation',
    utilization: 0.7,
    withoutCrMode: 'reserved',
    requireWithoutCrMode: true,
  });

  assert.ok(payload);
  assert.equal(payload.mode, 'clarification');
  assert.match(payload.message, /not modeled yet/i);
});

test('comparison reply builds deterministic quote payload when context is complete', () => {
  const payload = buildFlexComparisonReplyPayload({
    index: { id: 'stub' },
    flexComparison: {
      basePrompt: 'Compare E4.Flex vs E5.Flex',
      modifierKind: 'capacity-reservation',
      utilization: 1,
      withoutCrMode: 'on-demand',
      shapes: ['E4.Flex', 'E5.Flex'],
    },
    buildFlexComparisonQuote: () => ({
      ok: true,
      markdown: '| Shape |',
      rows: [],
      warnings: [],
    }),
    buildFlexComparisonNarrative: (context, comparison) => `${context.basePrompt}\n${comparison.markdown}`,
  });

  assert.ok(payload);
  assert.equal(payload.mode, 'quote');
  assert.equal(payload.quote.request.comparison, true);
  assert.match(payload.message, /Compare E4\.Flex vs E5\.Flex/);
});
