'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  buildQuoteRequestShape,
  normalizeFamilyIntent,
  preservesFamilyReplacementSignals,
} = require(path.join(ROOT, 'quote-request-shaping.js'));

test('quote request shaping preserves family-owned replacement signals when the candidate keeps the target metric', () => {
  const preserved = preservesFamilyReplacementSignals(
    'Quote Oracle Integration Cloud Standard 3 instances',
    'Quote Oracle Integration Cloud Standard BYOL 5 instances',
    'integration_oic_standard',
  );

  assert.equal(preserved, true);
});

test('quote request shaping rejects canonical rewrites that drop family-owned replacement signals', () => {
  const preserved = preservesFamilyReplacementSignals(
    'Quote Oracle Integration Cloud Standard 3 instances',
    'Quote Oracle Integration Cloud Standard BYOL',
    'integration_oic_standard',
  );

  assert.equal(preserved, false);
});

test('quote request shaping falls back to the safer family request when canonicalization drops replacement signals', () => {
  const result = buildQuoteRequestShape(
    {
      index: {},
      intent: {
        serviceFamily: 'integration_oic_standard',
        normalizedRequest: 'Quote Oracle Integration Cloud Standard 3 instances',
        reformulatedRequest: 'Quote Oracle Integration Cloud Standard 3 instances',
        extractedInputs: { instances: 3 },
      },
      effectiveQuoteText: 'Quote Oracle Integration Cloud Standard 3 instances',
      familyMeta: { id: 'integration_oic_standard' },
      preserveCriticalPromptModifiers: (prompt) => String(prompt || '').trim(),
      choosePreferredQuote: (primary) => primary,
    },
    {
      buildCanonicalRequest: () => 'Quote Oracle Integration Cloud Standard BYOL',
      parsePromptRequest: () => ({ instances: 3 }),
      quoteFromPrompt: (_index, prompt) => ({ ok: true, source: prompt, lineItems: [], totals: { monthly: 0 } }),
      normalizeExtractedInputsForFamily: (_familyId, inputs) => inputs,
      getActiveQuoteFollowUpReplacementRules: () => [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i,
        },
      ],
    },
  );

  assert.equal(result.canonicalFamilyRequest, 'Quote Oracle Integration Cloud Standard BYOL');
  assert.equal(result.preferredCanonicalFamilyRequest, '');
  assert.equal(result.reformulatedRequest, 'Quote Oracle Integration Cloud Standard 3 instances');
  assert.equal(result.preflightQuote.source, 'Quote Oracle Integration Cloud Standard 3 instances');
});

test('quote request shaping preserves critical prompt modifiers on the selected request', () => {
  const result = buildQuoteRequestShape(
    {
      index: {},
      intent: {
        serviceFamily: 'network_fastconnect',
        normalizedRequest: 'Quote OCI FastConnect 1 Gbps',
        extractedInputs: { bandwidthGbps: 1 },
      },
      effectiveQuoteText: 'Quote OCI FastConnect 1 Gbps metered',
      familyMeta: { id: 'network_fastconnect' },
      preserveCriticalPromptModifiers: (prompt, reference) => {
        const next = String(prompt || '').trim();
        return /\bmetered\b/i.test(String(reference || '')) && !/\bmetered\b/i.test(next)
          ? `${next} metered`.trim()
          : next;
      },
      choosePreferredQuote: (_primary, secondary) => secondary,
    },
    {
      buildCanonicalRequest: () => 'Quote OCI FastConnect 1 Gbps',
      parsePromptRequest: () => ({ bandwidthGbps: 1 }),
      quoteFromPrompt: (_index, prompt) => ({ ok: true, source: prompt, lineItems: [], totals: { monthly: 0 } }),
      normalizeExtractedInputsForFamily: (_familyId, inputs) => inputs,
      getActiveQuoteFollowUpReplacementRules: () => [],
    },
  );

  assert.equal(result.reformulatedRequest, 'Quote OCI FastConnect 1 Gbps metered');
  assert.equal(result.preflightQuote.source, 'Quote OCI FastConnect 1 Gbps metered');
});

test('quote request shaping normalizes family inputs before building the canonical request context', () => {
  const normalized = normalizeFamilyIntent(
    {
      serviceFamily: 'security_waf',
      extractedInputs: {
        instanceCount: 2,
        requestCount: 25000000,
      },
    },
  );

  assert.equal(normalized.extractedInputs.wafInstances, 2);
  assert.equal(normalized.extractedInputs.requestCount, 25000000);
});
