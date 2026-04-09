'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('path');
const XLSX = require('xlsx');

const ROOT = path.resolve(__dirname, '..');
const { app } = require(path.join(ROOT, 'index.js'));
const sessionStore = require(path.join(ROOT, 'session-store.js'));

async function withServer(run) {
  const server = await new Promise((resolve) => {
    const instance = app.listen(0, '127.0.0.1', () => resolve(instance));
  });
  server.unref();
  try {
    const address = server.address();
    const baseUrl = `http://127.0.0.1:${address.port}`;
    return await run(baseUrl);
  } finally {
    if (typeof server.closeAllConnections === 'function') server.closeAllConnections();
    if (typeof server.closeIdleConnections === 'function') server.closeIdleConnections();
    await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
  }
}

function httpGet(baseUrl, pathname, headers = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(pathname, baseUrl);
    const req = http.request(url, {
      method: 'GET',
      headers: {
        Connection: 'close',
        ...headers,
      },
    }, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        resolve({
          status: res.statusCode || 0,
          headers: res.headers,
          body: Buffer.concat(chunks),
        });
      });
    });
    req.on('error', reject);
    req.end();
  });
}

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

  await withServer(async (baseUrl) => {
    const response = await httpGet(
      baseUrl,
      `/api/sessions/${encodeURIComponent(session.id)}/quote-export?format=json`,
      { 'x-client-id': clientId },
    );
    assert.equal(response.status, 200);
    const payload = JSON.parse(response.body.toString('utf8'));
    assert.equal(payload.ok, true);
    assert.equal(payload.quoteExport.lineItems.length, 1);
    assert.equal(payload.quoteExport.lineItems[0].partNumber, 'B94176');
    assert.equal(payload.quoteExport.totals.monthly, 59.52);
  });

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

  await withServer(async (baseUrl) => {
    const response = await httpGet(
      baseUrl,
      `/api/sessions/${encodeURIComponent(session.id)}/quote-export?format=csv`,
      { 'x-client-id': clientId },
    );
    assert.equal(response.status, 200);
    assert.match(String(response.headers['content-type'] || ''), /text\/csv/i);
    const payload = response.body.toString('utf8');
    assert.match(payload, /#,Environment,Service,Part#/);
    assert.match(payload, /B94176/);
    assert.match(payload, /59\.52/);
    assert.match(payload, /714\.24/);
  });

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

  await withServer(async (baseUrl) => {
    const response = await httpGet(
      baseUrl,
      `/api/sessions/${encodeURIComponent(session.id)}/quote-export?format=xlsx`,
      { 'x-client-id': clientId },
    );
    assert.equal(response.status, 200);
    assert.match(String(response.headers['content-type'] || ''), /spreadsheetml/i);
    const workbook = XLSX.read(response.body, { type: 'buffer' });
    const rows = XLSX.utils.sheet_to_json(workbook.Sheets.Quote, { defval: '' });
    assert.equal(rows.length, 2);
    assert.equal(rows[0]['Part#'], 'B94176');
    assert.equal(rows[1]['#'], 'Total');
  });

  sessionStore.clearSessions(clientId);
});
