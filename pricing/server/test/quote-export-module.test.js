'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const XLSX = require('xlsx');

const {
  buildQuoteExportRows,
  buildQuoteExportCsv,
  buildQuoteExportWorkbook,
} = require('../quote-export');

function sampleQuote() {
  return {
    lineItems: [
      {
        environment: 'Env A',
        service: 'Compute - Virtual Machine',
        partNumber: 'B94176',
        product: 'Compute - Standard - X9 - OCPU',
        metric: 'OCPU Per Hour',
        quantity: 2,
        instances: 1,
        hours: 744,
        rate: 1,
        unitPrice: 0.04,
        monthly: 59.52,
        annual: 714.24,
        currencyCode: 'USD',
      },
    ],
    totals: {
      monthly: 59.52,
      annual: 714.24,
      currencyCode: 'USD',
    },
  };
}

function sampleQuoteMxn() {
  return {
    lineItems: [
      {
        environment: 'Env MX',
        service: 'Compute - Virtual Machine',
        partNumber: 'B94176',
        product: 'Compute - Standard - X9 - OCPU',
        metric: 'OCPU Per Hour',
        quantity: 2,
        instances: 1,
        hours: 744,
        rate: 1,
        unitPrice: 0.68,
        monthly: 1011.84,
        annual: 12142.08,
        currencyCode: 'MXN',
      },
    ],
    totals: {
      monthly: 1011.84,
      annual: 12142.08,
      currencyCode: 'MXN',
    },
  };
}

test('quote export rows include normalized line items plus total row', () => {
  const quote = sampleQuote();
  const rows = buildQuoteExportRows(quote.lineItems, quote.totals);
  assert.equal(rows.length, 2);
  assert.equal(rows[0]['#'], 1);
  assert.equal(rows[0]['Part#'], 'B94176');
  assert.equal(rows[0]['$/Mo'], 59.52);
  assert.equal(rows[1]['#'], 'Total');
  assert.equal(rows[1].Annual, 714.24);
});

test('quote export csv emits header and data rows', () => {
  const quote = sampleQuote();
  const csv = buildQuoteExportCsv(quote.lineItems, quote.totals);
  assert.match(csv, /^#,Environment,Service,Part#/);
  assert.match(csv, /B94176/);
  assert.match(csv, /59\.52/);
  assert.match(csv, /714\.24/);
});

test('quote export workbook produces xlsx payload with quote sheet rows', () => {
  const quote = sampleQuote();
  const payload = buildQuoteExportWorkbook(quote.lineItems, quote.totals);
  assert.ok(Buffer.isBuffer(payload));
  const workbook = XLSX.read(payload, { type: 'buffer' });
  assert.ok(workbook.Sheets.Quote);
  const rows = XLSX.utils.sheet_to_json(workbook.Sheets.Quote, { defval: '' });
  assert.equal(rows.length, 2);
  assert.equal(rows[0]['Part#'], 'B94176');
  assert.equal(rows[1]['#'], 'Total');
});

test('quote export rows preserve explicit non-USD currency codes', () => {
  const quote = sampleQuoteMxn();
  const rows = buildQuoteExportRows(quote.lineItems, quote.totals);
  assert.equal(rows[0].Currency, 'MXN');
  assert.equal(rows[1].Currency, 'MXN');
});

test('quote export csv preserves non-USD currency codes', () => {
  const quote = sampleQuoteMxn();
  const csv = buildQuoteExportCsv(quote.lineItems, quote.totals);
  assert.match(csv, /Currency/);
  assert.match(csv, /MXN/);
});

test('quote export workbook preserves non-USD currency codes', () => {
  const quote = sampleQuoteMxn();
  const payload = buildQuoteExportWorkbook(quote.lineItems, quote.totals);
  const workbook = XLSX.read(payload, { type: 'buffer' });
  const rows = XLSX.utils.sheet_to_json(workbook.Sheets.Quote, { defval: '' });
  assert.equal(rows[0].Currency, 'MXN');
  assert.equal(rows[1].Currency, 'MXN');
});
