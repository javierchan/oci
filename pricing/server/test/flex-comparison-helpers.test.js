'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const {
  detectFlexComparisonModifier,
  extractFlexComparisonContext,
  extractFlexShapes,
  findLatestFlexComparisonPrompt,
  isFlexComparisonRequest,
  parseBurstableBaseline,
  parseCapacityReservationUtilization,
  parseOnDemandMode,
  parseStandaloneNumericAnswer,
} = require(path.join(__dirname, '..', 'flex-comparison-helpers.js'));

test('isFlexComparisonRequest detects shape comparisons with two flex tokens', () => {
  assert.equal(isFlexComparisonRequest('Compare VM.Standard.E4.Flex vs VM.Standard.E5.Flex'), true);
  assert.equal(isFlexComparisonRequest('Quote VM.Standard.E4.Flex'), false);
});

test('flex comparison modifier and numeric parsers keep existing behavior', () => {
  assert.equal(detectFlexComparisonModifier('compare shapes with capacity reservation'), 'capacity-reservation');
  assert.equal(detectFlexComparisonModifier('compare shapes burstable'), 'burstable');
  assert.equal(parseCapacityReservationUtilization('capacity reservation utilization 0.7'), 0.7);
  assert.equal(parseBurstableBaseline('baseline 0.5'), 0.5);
  assert.equal(parseStandaloneNumericAnswer('0.7'), 0.7);
  assert.equal(parseStandaloneNumericAnswer('not-a-number'), null);
  assert.equal(parseOnDemandMode('on-demand'), 'on-demand');
  assert.equal(parseOnDemandMode('reserved pricing'), 'reserved');
});

test('extractFlexShapes and findLatestFlexComparisonPrompt preserve comparison context', () => {
  assert.deepEqual(
    extractFlexShapes('Compare VM.Standard.E4.Flex vs VM.Standard.E5.Flex and VM.Standard.E4.Flex again'),
    ['VM.Standard.E4.Flex', 'VM.Standard.E5.Flex'],
  );

  const prompt = findLatestFlexComparisonPrompt(
    [{ role: 'user', content: 'Compare VM.Standard.E4.Flex vs VM.Standard.E5.Flex' }],
    '0.7',
    '',
  );
  assert.equal(prompt, 'Compare VM.Standard.E4.Flex vs VM.Standard.E5.Flex');
});

test('extractFlexComparisonContext resolves modifier follow-up values from conversation', () => {
  const context = extractFlexComparisonContext(
    [{ role: 'user', content: 'Compare VM.Standard.E4.Flex vs VM.Standard.E5.Flex with capacity reservation' }],
    '0.7',
    '',
  );

  assert.ok(context);
  assert.equal(context.modifierKind, 'capacity-reservation');
  assert.equal(context.utilization, 0.7);
  assert.deepEqual(context.shapes, ['VM.Standard.E4.Flex', 'VM.Standard.E5.Flex']);
});
