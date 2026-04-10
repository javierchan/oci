'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const XLSX = require('xlsx');

const ROOT = path.resolve(__dirname, '..');
const { buildQuoteExportHttpResponse } = require(path.join(ROOT, 'index.js'));
const sessionStore = require(path.join(ROOT, 'session-store.js'));

test('quote export endpoint returns persisted quote export as json', async () => {
  const clientId = `test_quote_export_json_${Date.now()}`;
  const session = sessionStore.createSession(clientId, 'Quote Export JSON');
  sessionStore.updateSessionState(clientId, session.id, {
    sessionContext: {
      quoteExport: {
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
      },
    },
  });

  const response = buildQuoteExportHttpResponse(clientId, session.id, 'json');
  assert.equal(response.status, 200);
  assert.equal(response.json.ok, true);
  assert.equal(response.json.quoteExport.lineItems.length, 1);
  assert.equal(response.json.quoteExport.lineItems[0].partNumber, 'B94176');
  assert.equal(response.json.quoteExport.totals.monthly, 59.52);

  sessionStore.clearSessions(clientId);
});

test('quote export endpoint returns csv derived from persisted quote export', async () => {
  const clientId = `test_quote_export_csv_${Date.now()}`;
  const session = sessionStore.createSession(clientId, 'Quote Export CSV');
  sessionStore.updateSessionState(clientId, session.id, {
    sessionContext: {
      quoteExport: {
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
      },
    },
  });

  const response = buildQuoteExportHttpResponse(clientId, session.id, 'csv');
  assert.equal(response.status, 200);
  assert.match(String(response.headers['Content-Type'] || ''), /text\/csv/i);
  const payload = String(response.body || '');
  assert.match(payload, /#,Environment,Service,Part#/);
  assert.match(payload, /B94176/);
  assert.match(payload, /59\.52/);
  assert.match(payload, /714\.24/);

  sessionStore.clearSessions(clientId);
});

test('quote export endpoint returns xlsx derived from persisted quote export', async () => {
  const clientId = `test_quote_export_xlsx_${Date.now()}`;
  const session = sessionStore.createSession(clientId, 'Quote Export XLSX');
  sessionStore.updateSessionState(clientId, session.id, {
    sessionContext: {
      quoteExport: {
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
      },
    },
  });

  const response = buildQuoteExportHttpResponse(clientId, session.id, 'xlsx');
  assert.equal(response.status, 200);
  assert.match(String(response.headers['Content-Type'] || ''), /spreadsheetml/i);
  const workbook = XLSX.read(response.body, { type: 'buffer' });
  const rows = XLSX.utils.sheet_to_json(workbook.Sheets.Quote, { defval: '' });
  assert.equal(rows.length, 2);
  assert.equal(rows[0]['Part#'], 'B94176');
  assert.equal(rows[1]['#'], 'Total');

  sessionStore.clearSessions(clientId);
});
