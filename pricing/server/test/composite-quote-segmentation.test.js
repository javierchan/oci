'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const {
  hasCompositeServiceSignal,
  normalizeCompositeSegment,
  shouldAppendGlobalHours,
  splitCompositeQuoteSegments,
} = require(path.join(__dirname, '..', 'composite-quote-segmentation.js'));

test('hasCompositeServiceSignal detects common composite quote services', () => {
  assert.equal(hasCompositeServiceSignal('Flexible Load Balancer 50 Mbps'), true);
  assert.equal(hasCompositeServiceSignal('VM.Standard.E5.Flex 2 OCPU 16 GB'), true);
  assert.equal(hasCompositeServiceSignal('plain narrative without OCI service'), false);
});

test('splitCompositeQuoteSegments keeps service segments separate and drops trailing global-hours fragments', () => {
  const segments = splitCompositeQuoteSegments('Quote architecture: VM.Standard.E5.Flex 2 OCPU 16 GB + Load Balancer 50 Mbps + 744h/month');
  assert.deepEqual(segments, [
    'VM.Standard.E5.Flex 2 OCPU 16 GB',
    'Load Balancer 50 Mbps',
  ]);
});

test('splitCompositeQuoteSegments preserves log analytics active and archival variants', () => {
  const segments = splitCompositeQuoteSegments('Quote Log Analytics + active 20 GB + archival 10 GB');
  assert.deepEqual(segments, [
    'Quote Log Analytics',
    'Log Analytics active 20 GB',
    'Log Analytics archival 10 GB',
  ]);
});

test('normalizeCompositeSegment expands shorthands and appends shared hours only when appropriate', () => {
  assert.equal(
    normalizeCompositeSegment('LB 50 Mbps', 'Quote LB 50 Mbps + DNS 1m queries 744h/month'),
    'Quote Flexible Load Balancer 50 Mbps 744h/month',
  );
  assert.equal(
    normalizeCompositeSegment('OIC Standard 2 instances', 'Quote OIC Standard 2 instances + DNS 1m queries 744h/month'),
    'Quote Oracle Integration Cloud Standard 2 instances 744h/month',
  );
  assert.equal(
    normalizeCompositeSegment('DNS 1m queries', 'Quote OIC Standard 2 instances + DNS 1m queries 744h/month'),
    'Quote DNS 1m queries',
  );
});

test('shouldAppendGlobalHours stays focused on hour-based services', () => {
  assert.equal(shouldAppendGlobalHours('Flexible Load Balancer 50 Mbps'), true);
  assert.equal(shouldAppendGlobalHours('DNS 1m queries'), false);
});
