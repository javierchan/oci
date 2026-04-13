'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const {
  formatAssumptions,
  shouldKeepSourceAssumption,
} = require(path.join(__dirname, '..', 'quote-assumptions.js'));

test('shouldKeepSourceAssumption keeps pasted-image trace assumptions for transparency', () => {
  assert.equal(
    shouldKeepSourceAssumption('sizing details were extracted from the pasted image', { source: '' }),
    true,
  );
});

test('shouldKeepSourceAssumption keeps license and modifier assumptions only when the source request supports them', () => {
  assert.equal(
    shouldKeepSourceAssumption('license included was selected.', { source: 'Quote OIC License Included 2 instances' }),
    true,
  );
  assert.equal(
    shouldKeepSourceAssumption('license included was selected.', { source: 'Quote OIC 2 instances' }),
    false,
  );
  assert.equal(
    shouldKeepSourceAssumption('preemptible mode was requested.', { source: 'Quote E4 Flex preemptible' }),
    true,
  );
});

test('formatAssumptions keeps matching assumptions and adds missing defaults once', () => {
  const lines = formatAssumptions(
    [
      'Monthly usage defaulted to 744 hours.',
      'Currency defaulted to USD.',
      'An unrelated note.',
    ],
    {
      source: 'Quote FastConnect 10 Gbps',
      hours: 744,
      instances: 1,
      currencyCode: 'USD',
      annualRequested: false,
    },
  );

  assert.deepEqual(lines, [
    '- Monthly usage defaulted to 744 hours.',
    '- Currency defaulted to USD.',
    '- Instance count defaulted to 1.',
  ]);
});

test('formatAssumptions preserves existing source assumptions and still adds annual note', () => {
  const lines = formatAssumptions(
    [
      'Monthly usage defaulted to 100 hours.',
      'Instance count defaulted to 3.',
      'Currency defaulted to EUR.',
    ],
    {
      source: 'Quote Object Storage annual',
      hours: 744,
      instances: 1,
      currencyCode: 'USD',
      annualRequested: true,
    },
  );

  assert.deepEqual(lines, [
    '- Monthly usage defaulted to 100 hours.',
    '- Annual total assumes 12 months of the quoted monthly usage.',
  ]);
});
