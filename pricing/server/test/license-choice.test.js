'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  hasExplicitByolChoice,
  normalizeByolKey,
  shouldAskLicenseChoice,
  detectByolAmbiguity,
  filterQuoteByByolChoice,
  buildLicenseChoiceClarificationPayload,
  buildByolAmbiguityClarificationPayload,
} = require(path.join(ROOT, 'license-choice.js'));

test('license choice detects explicit byol answers', () => {
  assert.equal(hasExplicitByolChoice('BYOL'), 'byol');
  assert.equal(hasExplicitByolChoice('bring your own license'), 'byol');
});

test('license choice detects explicit license included answers', () => {
  assert.equal(hasExplicitByolChoice('License Included'), 'license-included');
  assert.equal(hasExplicitByolChoice('con licencia incluida'), 'license-included');
});

test('license choice clarification is required when family demands it and no skip inputs exist', () => {
  const shouldAsk = shouldAskLicenseChoice(
    { requireLicenseChoice: true, licenseNotRequiredWhenAnyInputs: ['users'] },
    { extractedInputs: { ocpus: 2 } },
    '',
  );

  assert.equal(shouldAsk, true);
});

test('license choice clarification is skipped when a skip input is already present', () => {
  const shouldAsk = shouldAskLicenseChoice(
    { requireLicenseChoice: true, licenseNotRequiredWhenAnyInputs: ['users'] },
    { extractedInputs: { users: 25 } },
    '',
  );

  assert.equal(shouldAsk, false);
});

test('license choice clarification payload preserves the incoming intent', () => {
  const payload = buildLicenseChoiceClarificationPayload(
    {
      canonical: 'Oracle Integration Cloud Standard',
      licenseClarificationQuestion: 'Do you want BYOL or License Included?',
    },
    {
      intent: 'quote',
      shouldQuote: true,
      serviceFamily: 'integration_oic_standard',
    },
  );

  assert.equal(payload.mode, 'clarification');
  assert.match(payload.message, /BYOL or License Included/i);
  assert.equal(payload.intent.serviceFamily, 'integration_oic_standard');
  assert.equal(payload.intent.needsClarification, true);
});

test('license choice normalizes byol keys consistently across variants', () => {
  assert.equal(
    normalizeByolKey('B12345 - Oracle Integration Cloud Standard - BYOL'),
    normalizeByolKey('Oracle Integration Cloud Standard'),
  );
});

test('license choice detects ambiguous quotes that mix byol and license included lines', () => {
  const product = detectByolAmbiguity({
    lineItems: [
      { service: 'OIC', metric: 'hour', product: 'Oracle Integration Cloud Standard - BYOL' },
      { service: 'OIC', metric: 'hour', product: 'Oracle Integration Cloud Standard - License Included' },
    ],
  });

  assert.match(product, /Oracle Integration Cloud Standard/i);
});

test('license choice filtering keeps the selected byol variant and preserves shared non-license lines', () => {
  const quote = filterQuoteByByolChoice(
    {
      ok: true,
      lineItems: [
        { product: 'Oracle Integration Cloud Standard - BYOL', monthly: 10, annual: 120 },
        { product: 'Oracle Integration Cloud Standard - License Included', monthly: 20, annual: 240 },
        { product: 'Shared autonomous database storage SKU', monthly: 5, annual: 60 },
      ],
      totals: { monthly: 35, annual: 420, currencyCode: 'USD' },
      markdown: 'old',
    },
    'byol',
    () => 'rendered-markdown',
  );

  assert.equal(quote.lineItems.length, 2);
  assert.match(quote.lineItems[0].product, /BYOL/i);
  assert.match(quote.lineItems[1].product, /Shared autonomous database storage/i);
  assert.equal(quote.totals.monthly, 15);
  assert.equal(quote.markdown, 'rendered-markdown');
});

test('license choice can build an ambiguity clarification payload for mixed-license quotes', () => {
  const payload = buildByolAmbiguityClarificationPayload(
    'Oracle Integration Cloud Standard',
    {
      intent: 'quote',
      shouldQuote: true,
      serviceFamily: 'integration_oic_standard',
    },
  );

  assert.equal(payload.mode, 'clarification');
  assert.match(payload.message, /Oracle Integration Cloud Standard/);
  assert.match(payload.message, /BYOL/);
  assert.match(payload.message, /License Included/);
  assert.equal(payload.intent.serviceFamily, 'integration_oic_standard');
  assert.equal(payload.intent.needsClarification, true);
});
