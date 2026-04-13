'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const {
  buildCompositeQuoteFromSegments,
  choosePreferredQuote,
  quoteSegmentWithCanonicalFallback,
} = require(path.join(__dirname, '..', 'composite-quote-builder.js'));
const { buildIndex } = require(path.join(__dirname, 'assistant-test-helpers.js'));

test('choosePreferredQuote prefers successful quotes over failed ones', () => {
  const preferred = choosePreferredQuote(
    { ok: false },
    { ok: true, lineItems: [{ partNumber: 'B1' }], totals: { monthly: 10 } },
  );

  assert.equal(preferred.ok, true);
});

test('choosePreferredQuote prefers richer quote results when both succeed', () => {
  const preferred = choosePreferredQuote(
    { ok: true, lineItems: [{}, {}], totals: { monthly: 10 } },
    { ok: true, lineItems: [{}], totals: { monthly: 50 } },
  );

  assert.equal(preferred.lineItems.length, 2);
});

test('quoteSegmentWithCanonicalFallback keeps direct quotes for covered prompts', () => {
  const index = buildIndex();
  const quote = quoteSegmentWithCanonicalFallback(index, 'Quote DNS 1000000 queries per month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B88525/);
});

test('buildCompositeQuoteFromSegments composes multiple deterministic service quotes', () => {
  const index = buildIndex();
  const quote = buildCompositeQuoteFromSegments(
    index,
    'Quote Flexible Load Balancer 50 Mbps plus DNS 1000000 queries per month',
  );

  assert.equal(quote.ok, true);
  assert.equal(quote.resolution.type, 'workload');
  assert.ok(Array.isArray(quote.lineItems));
  assert.ok(quote.lineItems.length >= 3);
  assert.match(quote.markdown, /B93030/);
  assert.match(quote.markdown, /B88525/);
});

test('buildCompositeQuoteFromSegments returns null when fewer than two quotable segments survive', () => {
  const index = buildIndex();
  const quote = buildCompositeQuoteFromSegments(index, 'Quote Flexible Load Balancer 50 Mbps');

  assert.equal(quote, null);
});
