'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const {
  fmt,
  money,
  toMarkdownQuote,
} = require(path.join(__dirname, '..', 'assistant-quote-rendering.js'));

test('fmt preserves integers and rounds fractional values to assistant precision', () => {
  assert.equal(fmt(4), '4');
  assert.equal(fmt(1.23456), '1.2346');
  assert.equal(fmt('not-a-number'), 'not-a-number');
});

test('money keeps assistant formatting conventions for numeric and invalid values', () => {
  assert.equal(money(12), '$12');
  assert.equal(money(12.34567), '$12.3457');
  assert.equal(money('bad'), '$-');
});

test('toMarkdownQuote renders deterministic markdown rows and totals', () => {
  const markdown = toMarkdownQuote([
    {
      environment: 'prod',
      service: 'Compute',
      partNumber: 'B111129',
      product: 'OCI Compute',
      metric: 'OCPU Per Hour',
      quantity: 2,
      instances: 1,
      hours: 744,
      rate: 1488,
      unitPrice: 0.1,
      monthly: 148.8,
      annual: 1785.6,
    },
  ], {
    monthly: 148.8,
    annual: 1785.6,
  });

  assert.match(markdown, /\| # \| Environment \| Service \| Part# \|/);
  assert.match(markdown, /\| 1 \| prod \| Compute \| B111129 \|/);
  assert.match(markdown, /\| Total \| - \| - \| - \| - \| - \| - \| - \| - \| - \| - \| \$148.8 \| \$1785.6 \|/);
});
