'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  GENAI_PROFILES,
  normalizeGenAIProfileName,
  resolveGenAIRequestOptions,
} = require(path.join(ROOT, 'genai-profiles.js'));

test('genai profiles expose the named request profiles expected by the runtime', () => {
  assert.deepEqual(Object.keys(GENAI_PROFILES), ['intent', 'narrative', 'discovery', 'image']);
  assert.equal(normalizeGenAIProfileName('INTENT'), 'intent');
  assert.equal(normalizeGenAIProfileName('unknown'), 'narrative');
});

test('genai profiles resolve intent parameters and intent-specific model ids without OCI calls', () => {
  const resolved = resolveGenAIRequestOptions('intent', {
    modelId: 'base-model',
    intentModelId: 'intent-model',
  });

  assert.deepEqual(resolved, {
    profile: 'intent',
    modelId: 'intent-model',
    maxTokens: 500,
    temperature: 0.1,
    topP: 0.2,
    topK: -1,
  });
});

test('genai profiles resolve narrative and discovery defaults independently', () => {
  const narrative = resolveGenAIRequestOptions('narrative', {
    modelId: 'base-model',
    narrativeModelId: 'narrative-model',
  });
  const discovery = resolveGenAIRequestOptions('discovery', {
    modelId: 'base-model',
    discoveryModelId: 'discovery-model',
  });

  assert.deepEqual(narrative, {
    profile: 'narrative',
    modelId: 'narrative-model',
    maxTokens: 900,
    temperature: 0.55,
    topP: 0.7,
    topK: -1,
  });
  assert.deepEqual(discovery, {
    profile: 'discovery',
    modelId: 'discovery-model',
    maxTokens: 700,
    temperature: 0.55,
    topP: 0.7,
    topK: -1,
  });
});

test('genai profiles resolve image defaults and allow explicit overrides', () => {
  const resolved = resolveGenAIRequestOptions('image', {
    modelId: 'base-model',
    imageModelId: 'image-model',
  }, {
    maxTokens: 850,
    temperature: 0.45,
  });

  assert.deepEqual(resolved, {
    profile: 'image',
    modelId: 'image-model',
    maxTokens: 850,
    temperature: 0.45,
    topP: 0.5,
    topK: -1,
  });
});
