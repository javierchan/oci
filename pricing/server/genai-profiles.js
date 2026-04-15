'use strict';

const GENAI_PROFILES = Object.freeze({
  intent: Object.freeze({
    name: 'intent',
    maxTokens: 500,
    temperature: 0.1,
    topP: 0.2,
    topK: -1,
    modelConfigKey: 'intentModelId',
  }),
  narrative: Object.freeze({
    name: 'narrative',
    maxTokens: 900,
    temperature: 0.55,
    topP: 0.7,
    topK: -1,
    modelConfigKey: 'narrativeModelId',
  }),
  discovery: Object.freeze({
    name: 'discovery',
    maxTokens: 700,
    temperature: 0.55,
    topP: 0.7,
    topK: -1,
    modelConfigKey: 'discoveryModelId',
  }),
  image: Object.freeze({
    name: 'image',
    maxTokens: 700,
    temperature: 0.3,
    topP: 0.5,
    topK: -1,
    modelConfigKey: 'imageModelId',
  }),
});

function normalizeGenAIProfileName(name, fallback = 'narrative') {
  const requested = String(name || '').trim().toLowerCase();
  if (requested && GENAI_PROFILES[requested]) return requested;
  return GENAI_PROFILES[fallback] ? fallback : 'narrative';
}

function getGenAIProfileDefinition(name) {
  const normalized = normalizeGenAIProfileName(name);
  return GENAI_PROFILES[normalized];
}

function resolveGenAIModelId(profileName, cfg = {}, overrideModelId = '') {
  const explicitModelId = String(overrideModelId || '').trim();
  if (explicitModelId) return explicitModelId;
  const profile = getGenAIProfileDefinition(profileName);
  const profileModelId = String(cfg?.[profile.modelConfigKey] || '').trim();
  if (profileModelId) return profileModelId;
  return String(cfg?.modelId || '').trim();
}

function resolveGenAIRequestOptions(profileName, cfg = {}, overrides = {}) {
  const normalized = normalizeGenAIProfileName(profileName, cfg?.defaultProfile || 'narrative');
  const profile = getGenAIProfileDefinition(normalized);
  const resolved = {
    profile: normalized,
    modelId: resolveGenAIModelId(normalized, cfg, overrides.modelId),
    maxTokens: Number.isFinite(Number(overrides.maxTokens)) ? Number(overrides.maxTokens) : profile.maxTokens,
    temperature: Number.isFinite(Number(overrides.temperature)) ? Number(overrides.temperature) : profile.temperature,
    topP: Number.isFinite(Number(overrides.topP)) ? Number(overrides.topP) : profile.topP,
    topK: Number.isFinite(Number(overrides.topK)) ? Number(overrides.topK) : profile.topK,
  };
  return resolved;
}

module.exports = {
  GENAI_PROFILES,
  normalizeGenAIProfileName,
  getGenAIProfileDefinition,
  resolveGenAIModelId,
  resolveGenAIRequestOptions,
};
