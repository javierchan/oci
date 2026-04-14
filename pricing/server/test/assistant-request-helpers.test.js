'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  enrichExtractedInputsForFamily,
  isCompositeOrComparisonRequest,
  summarizeMatches,
} = require(path.join(ROOT, 'assistant-request-helpers.js'));

test('assistant request helpers summarize catalog matches with the current product and preset limits', () => {
  const result = summarizeMatches(
    { ok: true },
    'FastConnect',
    {
      searchProducts: (_index, text, limit) => {
        assert.equal(text, 'FastConnect');
        assert.equal(limit, 5);
        return [{ fullDisplayName: 'OCI FastConnect 10 Gbps' }];
      },
      searchPresets: (_index, text, limit) => {
        assert.equal(text, 'FastConnect');
        assert.equal(limit, 3);
        return [{ displayName: 'FastConnect preset' }];
      },
    },
  );

  assert.deepEqual(result, {
    products: ['OCI FastConnect 10 Gbps'],
    presets: ['FastConnect preset'],
  });
});

test('assistant request helpers detect composite or comparison prompts conservatively', () => {
  assert.equal(isCompositeOrComparisonRequest('Load Balancer with DNS and Health Checks'), true);
  assert.equal(isCompositeOrComparisonRequest('Compare VM.Standard.E4.Flex vs VM.Standard.E5.Flex'), true);
  assert.equal(isCompositeOrComparisonRequest('Single FastConnect quote'), false);
});

test('assistant request helpers enrich extracted inputs through family normalization', () => {
  const result = enrichExtractedInputsForFamily(
    {
      serviceFamily: 'security_waf',
      extractedInputs: { instanceCount: 2 },
    },
    {
      normalizeExtractedInputsForFamily: (family, inputs) => {
        assert.equal(family, 'security_waf');
        return {
          ...inputs,
          wafInstances: 2,
        };
      },
    },
  );

  assert.deepEqual(result, {
    serviceFamily: 'security_waf',
    extractedInputs: { instanceCount: 2, wafInstances: 2 },
  });
});
