'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const {
  buildAssistantSessionContext,
  buildAssistantSessionSummary,
  buildQuoteExportPayload,
  extractInlinePartNumbers,
  summarizeQuoteForSession,
} = require(path.join(__dirname, '..', 'assistant-session-context.js'));

test('extractInlinePartNumbers returns unique OCI part numbers', () => {
  assert.deepEqual(
    extractInlinePartNumbers('Use B12345 and B123456 plus duplicate B12345 and noise X12345'),
    ['B12345', 'B123456'],
  );
});

test('summarizeQuoteForSession returns quote summary fields', () => {
  const summary = summarizeQuoteForSession({
    ok: true,
    resolution: { label: 'OCI Compute' },
    request: {
      source: 'Quote OCI Compute',
      shape: 'VM.Standard.E5.Flex',
      serviceFamily: 'compute_flex',
      processorVendor: 'AMD',
      vpuPerGb: 20,
    },
    totals: {
      monthly: 123.45,
      annual: 1481.4,
      currencyCode: 'USD',
    },
    lineItems: [
      { partNumber: 'B111129' },
      { partNumber: 'B111130' },
      { partNumber: 'B111129' },
    ],
  });

  assert.deepEqual(summary, {
    type: 'quote',
    label: 'OCI Compute',
    source: 'Quote OCI Compute',
    monthly: 123.45,
    annual: 1481.4,
    currencyCode: 'USD',
    lineItemCount: 3,
    shapeName: 'VM.Standard.E5.Flex',
    serviceFamily: 'compute_flex',
    processorVendor: 'AMD',
    vpuPerGb: 20,
    partNumbers: ['B111129', 'B111130'],
  });
});

test('buildQuoteExportPayload normalizes line item fields for export', () => {
  const payload = buildQuoteExportPayload({
    ok: true,
    totals: { monthly: 25, annual: 300, currencyCode: 'USD' },
    lineItems: [
      {
        service: 'Compute',
        partNumber: 'B111129',
        product: 'OCI - Compute - Standard - E5 - OCPU',
        metric: 'OCPU Per Hour',
        quantity: '2',
        instances: '1',
        hours: '744',
        rate: '0.1',
        unitPrice: '0.1',
        monthly: '148.8',
        annual: '1785.6',
      },
    ],
  });

  assert.equal(payload.formatVersion, 1);
  assert.ok(Date.parse(payload.generatedAt));
  assert.equal(payload.lineItems[0].rowNumber, 1);
  assert.equal(payload.lineItems[0].service, 'Compute');
  assert.equal(payload.lineItems[0].quantity, 2);
  assert.equal(payload.lineItems[0].currencyCode, 'USD');
});

test('buildAssistantSessionSummary renders workbook, quote, clarification, and route context', () => {
  const summary = buildAssistantSessionSummary({
    workbookContext: {
      fileName: 'inventory.xlsx',
      shapeName: 'VM.Standard.E5.Flex',
      vpuPerGb: 30,
    },
    lastQuote: {
      label: 'OCI Compute',
      monthly: 123.45,
      currencyCode: 'USD',
      lineItemCount: 2,
    },
    pendingClarification: {
      question: 'How many OCPUs?',
    },
    lastIntent: {
      route: 'quote_request',
    },
  });

  assert.match(summary, /Active workbook inventory\.xlsx using VM\.Standard\.E5\.Flex with 30 VPU/);
  assert.match(summary, /Last quote OCI Compute monthly \$123\.45 across 2 lines/);
  assert.match(summary, /Pending clarification: How many OCPUs\?/);
  assert.match(summary, /Last route quote_request/);
});

test('buildAssistantSessionContext preserves context and updates quote and clarification state', () => {
  const previous = {
    workbookContext: {
      fileName: 'inventory.xlsx',
    },
    pendingClarification: {
      question: 'Old question',
      serviceFamily: 'old_family',
    },
  };

  const payload = {
    mode: 'clarification',
    message: 'How many OCPUs?',
    intent: {
      intent: 'quote_request',
      route: 'quote_request',
      serviceFamily: 'compute_flex',
      serviceName: 'OCI Compute Virtual Machine',
      confidence: '0.92',
      quotePlan: {
        family: 'compute_flex',
      },
    },
    contextPackSummary: {
      family: 'compute_flex',
    },
    quote: {
      ok: true,
      resolution: { label: 'OCI Compute' },
      request: {
        source: 'Quote OCI Compute',
        shapeSeries: 'E5',
        serviceFamily: 'compute_flex',
      },
      totals: {
        monthly: 50,
        annual: 600,
        currencyCode: 'USD',
      },
      lineItems: [
        {
          service: 'Compute',
          product: 'OCI Compute',
          partNumber: 'B111129',
          metric: 'OCPU Per Hour',
          quantity: 1,
          monthly: 50,
          annual: 600,
        },
      ],
    },
  };

  const next = buildAssistantSessionContext(previous, ' Quote compute ', payload);

  assert.equal(next.lastUserText, 'Quote compute');
  assert.equal(next.currentIntent, 'quote_request');
  assert.equal(next.lastIntent.route, 'quote_request');
  assert.equal(next.lastIntent.confidence, 0.92);
  assert.deepEqual(next.lastContextPack, { family: 'compute_flex' });
  assert.deepEqual(next.pendingClarification, {
    question: 'How many OCPUs?',
    serviceFamily: 'compute_flex',
  });
  assert.equal(next.lastQuote.label, 'OCI Compute');
  assert.equal(next.quoteExport.lineItems[0].partNumber, 'B111129');
  assert.match(next.sessionSummary, /Pending clarification: How many OCPUs\?/);
  assert.equal(previous.pendingClarification.question, 'Old question');
});

test('buildAssistantSessionContext clears stale clarification when payload is not a clarification', () => {
  const next = buildAssistantSessionContext(
    {
      pendingClarification: {
        question: 'Old question',
      },
    },
    'Show status',
    {
      mode: 'answer',
      intent: {
        route: 'answer',
      },
    },
  );

  assert.equal(next.lastUserText, 'Show status');
  assert.equal(next.pendingClarification, undefined);
  assert.match(next.sessionSummary, /Last route answer/);
});
