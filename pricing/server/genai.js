'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

const common = require('oci-common');
const genai = require('oci-generativeaiinference');
const {
  normalizeGenAIProfileName,
  resolveGenAIRequestOptions,
} = require('./genai-profiles');
const { GenAIError } = require('./errors');
const { logger, recordGenAICall } = require('./logger');

function parsePositiveInteger(value, fallback) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function getGenAITokenBudget(env = process.env) {
  return parsePositiveInteger(env?.OCI_GENAI_TOKEN_BUDGET, 12000);
}

function estimateTextTokens(text) {
  const source = String(text || '').trim();
  if (!source) return 0;
  return Math.ceil(source.length / 4);
}

function estimateChatInputTokens({ systemPrompt, messages }) {
  let total = estimateTextTokens(systemPrompt);
  for (const message of messages || []) {
    total += estimateTextTokens(message?.role);
    if (Array.isArray(message?.content)) {
      for (const content of message.content) {
        if (typeof content?.text === 'string') total += estimateTextTokens(content.text);
      }
      continue;
    }
    total += estimateTextTokens(message?.content);
  }
  return total;
}

function maybeWarnOnTokenBudget({ logger: requestLogger, profile, kind, modelId, systemPrompt, messages, env = process.env }) {
  const estimatedInputTokens = estimateChatInputTokens({ systemPrompt, messages });
  const tokenBudget = getGenAITokenBudget(env);
  if (estimatedInputTokens > tokenBudget) {
    (requestLogger || logger).warn({
      event: 'genai.token_budget.exceeded',
      profile: profile || '',
      kind: kind || 'chat',
      modelId: modelId || '',
      estimatedInputTokens,
      tokenBudget,
      messageCount: Array.isArray(messages) ? messages.length : 0,
    }, 'Estimated GenAI prompt exceeds configured token budget');
  }
  return {
    estimatedInputTokens,
    tokenBudget,
    exceeded: estimatedInputTokens > tokenBudget,
  };
}

function extractUsageMetadata(payload) {
  return payload?.chatResult?.chatResponse?.usage
    || payload?.chatResponse?.usage
    || payload?.usage
    || null;
}

function logGenAIUsage({ logger: requestLogger, profile, kind, modelId, response }) {
  const usage = extractUsageMetadata(response?.data || response);
  if (!usage) return null;
  const promptTokens = Number(usage?.promptTokens || 0);
  const completionTokens = Number(usage?.completionTokens || 0);
  const totalTokens = Number(usage?.totalTokens || 0);
  const cachedPromptTokens = Number(usage?.promptTokensDetails?.cachedTokens || 0);
  (requestLogger || logger).debug({
    event: 'genai.request.usage',
    profile: profile || '',
    kind: kind || 'chat',
    modelId: modelId || '',
    promptTokens,
    completionTokens,
    totalTokens,
    cachedPromptTokens,
  }, 'GenAI token usage reported');
  return {
    promptTokens,
    completionTokens,
    totalTokens,
    cachedPromptTokens,
  };
}

function parseSimpleYaml(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return {};
  const values = {};
  for (const line of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes(':')) continue;
    const idx = line.indexOf(':');
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    values[key] = value.replace(/^['"]|['"]$/g, '');
  }
  return values;
}

function defaultGenAIConfigPath() {
  return path.join(os.homedir(), '.config', 'oci-inv', 'genai.yaml');
}

function loadGenAISettings(env) {
  const configPath = env.OCI_PRICING_GENAI_CONFIG || env.OCI_INV_GENAI_CONFIG || defaultGenAIConfigPath();
  const cfg = parseSimpleYaml(configPath);

  const endpoint = env.OCI_GENAI_ENDPOINT || cfg.endpoint || '';
  const endpointRegion = endpoint.match(/inference\.generativeai\.([a-z0-9-]+)\./i)?.[1] || '';
  const region = endpointRegion || env.OCI_REGION || 'us-chicago-1';
  const baseModelId = env.OCI_GENAI_MODEL || cfg.base_model_id || '';
  const narrativeModelId = env.OCI_GENAI_MODEL_NARRATIVE || cfg.narrative_model_id || baseModelId;
  const discoveryModelId = env.OCI_GENAI_MODEL_DISCOVERY || cfg.discovery_model_id || narrativeModelId || baseModelId;
  const intentModelId = env.OCI_GENAI_MODEL_INTENT || cfg.intent_model_id || baseModelId || narrativeModelId || discoveryModelId;
  const imageModelId = env.OCI_GENAI_MODEL_IMAGE || cfg.image_model_id || narrativeModelId || discoveryModelId || baseModelId;

  return {
    configPath,
    profile: env.OCI_GENAI_PROFILE || cfg.oci_profile || env.OCI_CLI_PROFILE || 'DEFAULT',
    endpoint: endpoint || `https://inference.generativeai.${region}.oci.oraclecloud.com`,
    compartmentId: env.OCI_GENAI_COMPARTMENT || cfg.compartment_id || env.OCI_COMPARTMENT || '',
    modelId: baseModelId || narrativeModelId || discoveryModelId || intentModelId || imageModelId,
    defaultProfile: normalizeGenAIProfileName(env.OCI_GENAI_DEFAULT_PROFILE || cfg.default_profile || 'narrative'),
    narrativeModelId,
    discoveryModelId,
    intentModelId,
    imageModelId,
    region,
  };
}

function createAuthProvider(cfg) {
  return new common.SimpleAuthenticationDetailsProvider(
    cfg.tenancy,
    cfg.user,
    cfg.fingerprint,
    cfg.privateKeyPem,
    null,
  );
}

function createInferenceClient(cfg) {
  const authenticationDetailsProvider = createAuthProvider(cfg);
  const client = new genai.GenerativeAiInferenceClient({ authenticationDetailsProvider });
  if (cfg.endpoint) client.endpoint = cfg.endpoint;
  else client.regionId = cfg.region;
  return client;
}

function buildChatDetails({ cfg, messages, maxTokens, temperature, topP, topK, maxTokenField = 'maxTokens' }) {
  const chatRequest = {
    apiFormat: genai.models.GenericChatRequest.apiFormat,
    messages,
    temperature: Number(temperature),
    topP: Number(topP),
    topK: Number(topK),
    isStream: false,
  };
  chatRequest[maxTokenField] = Number(maxTokens);
  return {
    compartmentId: cfg.compartment,
    servingMode: {
      modelId: cfg.modelId,
      servingType: genai.models.OnDemandServingMode.servingType,
    },
    chatRequest,
  };
}

function shouldRetryWithMaxCompletionTokens(error) {
  const message = String(error?.message || error || '');
  return /max_tokens/i.test(message) && /max_completion_tokens/i.test(message);
}

function wrapGenAIError(error, defaults = {}) {
  if (error instanceof GenAIError) return error;
  const status = Number(error?.statusCode || error?.status);
  return new GenAIError(
    defaults.message || error?.message || 'OCI GenAI request failed.',
    {
      code: defaults.code || 'GENAI_UNAVAILABLE',
      httpStatus: Number.isFinite(status) && status >= 400 ? status : (defaults.httpStatus || 503),
      data: defaults.data && typeof defaults.data === 'object' ? { ...defaults.data } : null,
      cause: error,
    },
  );
}

async function executeChatWithFallback({ client, cfg, messages, maxTokens, temperature, topP, topK, logMeta = {} }) {
  const primaryChatDetails = buildChatDetails({
    cfg,
    messages,
    maxTokens,
    temperature,
    topP,
    topK,
    maxTokenField: 'maxTokens',
  });
  try {
    return await client.chat({ chatDetails: primaryChatDetails });
  } catch (error) {
    if (!shouldRetryWithMaxCompletionTokens(error)) throw error;
    logMeta.logger?.warn({
      event: 'genai.max_tokens_retry',
      profile: logMeta.profile,
      kind: logMeta.kind,
      modelId: cfg?.modelId || '',
      message: error.message,
      fallbackUsed: 'maxCompletionTokens',
    }, 'GenAI request rejected maxTokens; retrying with maxCompletionTokens');
    const fallbackChatDetails = buildChatDetails({
      cfg,
      messages,
      maxTokens,
      temperature,
      topP,
      topK,
      maxTokenField: 'maxCompletionTokens',
    });
    return client.chat({ chatDetails: fallbackChatDetails });
  }
}

function resolveChatExecutionOptions(cfg, profile, overrides = {}) {
  const resolved = resolveGenAIRequestOptions(profile, cfg, overrides);
  return {
    cfg: {
      ...cfg,
      modelId: resolved.modelId || cfg?.modelId || '',
    },
    maxTokens: resolved.maxTokens,
    temperature: resolved.temperature,
    topP: resolved.topP,
    topK: resolved.topK,
  };
}

async function runChat({ cfg, systemPrompt, messages, profile, maxTokens, temperature, topP, topK, modelId, logger: requestLogger, trace }) {
  const resolvedProfile = profile || cfg?.defaultProfile || 'narrative';
  const execution = resolveChatExecutionOptions(cfg, resolvedProfile, {
    maxTokens,
    temperature,
    topP,
    topK,
    modelId,
  });
  const client = createInferenceClient(cfg);
  const models = genai.models;
  const activeLogger = requestLogger || logger;

  const chatMessages = [];
  if (systemPrompt) {
    chatMessages.push({
      role: models.SystemMessage.role,
      content: [{ type: models.TextContent.type, text: systemPrompt }],
    });
  }
  for (const message of messages || []) {
    chatMessages.push({
      role: message.role === 'user' ? 'USER' : 'ASSISTANT',
      content: [{ type: models.TextContent.type, text: String(message.content || '') }],
    });
  }

  // The current OCI Node SDK surface does not expose a clear request-side prompt-cache
  // control for chat requests, so M6 relies on prompt truncation now. If SDK support
  // lands later, cache keys should be based on stable prompt/context content plus
  // profile, not conversation turn order.
  const tokenBudgetState = maybeWarnOnTokenBudget({
    logger: activeLogger,
    profile: resolvedProfile,
    kind: 'chat',
    modelId: execution.cfg?.modelId || '',
    systemPrompt,
    messages: chatMessages,
  });
  const startedAt = Date.now();
  activeLogger.debug({
    event: 'genai.request.start',
    kind: 'chat',
    profile: resolvedProfile,
    modelId: execution.cfg?.modelId || '',
    messageCount: chatMessages.length,
    estimatedInputTokens: tokenBudgetState.estimatedInputTokens,
  }, 'Starting GenAI chat request');

  try {
    const response = await executeChatWithFallback({
      client,
      cfg: execution.cfg,
      messages: chatMessages,
      maxTokens: execution.maxTokens,
      temperature: execution.temperature,
      topP: execution.topP,
      topK: execution.topK,
      logMeta: {
        kind: 'chat',
        profile: resolvedProfile,
        logger: activeLogger,
      },
    });
    const latencyMs = Date.now() - startedAt;
    recordGenAICall(trace, {
      kind: 'chat',
      profile: resolvedProfile,
      modelId: execution.cfg?.modelId || '',
      latencyMs,
      ok: true,
    });
    logGenAIUsage({
      logger: activeLogger,
      profile: resolvedProfile,
      kind: 'chat',
      modelId: execution.cfg?.modelId || '',
      response,
    });
    activeLogger.debug({
      event: 'genai.request.success',
      kind: 'chat',
      profile: resolvedProfile,
      modelId: execution.cfg?.modelId || '',
      latencyMs,
    }, 'Completed GenAI chat request');
    return response;
  } catch (error) {
    const latencyMs = Date.now() - startedAt;
    recordGenAICall(trace, {
      kind: 'chat',
      profile: resolvedProfile,
      modelId: execution.cfg?.modelId || '',
      latencyMs,
      ok: false,
      errorMessage: error.message,
    });
    activeLogger.warn({
      event: 'genai.request.failure',
      kind: 'chat',
      profile: resolvedProfile,
      modelId: execution.cfg?.modelId || '',
      latencyMs,
      errorMessage: error.message,
    }, 'GenAI chat request failed');
    throw wrapGenAIError(error);
  }
}

async function runMultimodalChat({ cfg, systemPrompt, userText, imageDataUrl, profile, maxTokens, temperature, topP, topK, modelId, logger: requestLogger, trace }) {
  const resolvedProfile = profile || 'image';
  const execution = resolveChatExecutionOptions(cfg, resolvedProfile, {
    maxTokens,
    temperature,
    topP,
    topK,
    modelId,
  });
  const client = createInferenceClient(cfg);
  const models = genai.models;
  const activeLogger = requestLogger || logger;

  const userContent = [];
  if (userText) {
    userContent.push({
      type: models.TextContent.type,
      text: String(userText),
    });
  }
  if (imageDataUrl) {
    userContent.push({
      type: models.ImageContent.type,
      imageUrl: {
        url: String(imageDataUrl),
        detail: models.ImageUrl.Detail.Auto,
      },
    });
  }

  const messages = [];
  if (systemPrompt) {
    messages.push({
      role: models.SystemMessage.role,
      content: [{ type: models.TextContent.type, text: systemPrompt }],
    });
  }
  messages.push({
    role: 'USER',
    content: userContent,
  });

  const tokenBudgetState = maybeWarnOnTokenBudget({
    logger: activeLogger,
    profile: resolvedProfile,
    kind: 'multimodal_chat',
    modelId: execution.cfg?.modelId || '',
    systemPrompt,
    messages,
  });
  const startedAt = Date.now();
  activeLogger.debug({
    event: 'genai.request.start',
    kind: 'multimodal_chat',
    profile: resolvedProfile,
    modelId: execution.cfg?.modelId || '',
    hasImage: Boolean(imageDataUrl),
    hasText: Boolean(userText),
    estimatedInputTokens: tokenBudgetState.estimatedInputTokens,
  }, 'Starting GenAI multimodal request');

  try {
    const response = await executeChatWithFallback({
      client,
      cfg: execution.cfg,
      messages,
      maxTokens: execution.maxTokens,
      temperature: execution.temperature,
      topP: execution.topP,
      topK: execution.topK,
      logMeta: {
        kind: 'multimodal_chat',
        profile: resolvedProfile,
        logger: activeLogger,
      },
    });
    const latencyMs = Date.now() - startedAt;
    recordGenAICall(trace, {
      kind: 'multimodal_chat',
      profile: resolvedProfile,
      modelId: execution.cfg?.modelId || '',
      latencyMs,
      ok: true,
    });
    logGenAIUsage({
      logger: activeLogger,
      profile: resolvedProfile,
      kind: 'multimodal_chat',
      modelId: execution.cfg?.modelId || '',
      response,
    });
    activeLogger.debug({
      event: 'genai.request.success',
      kind: 'multimodal_chat',
      profile: resolvedProfile,
      modelId: execution.cfg?.modelId || '',
      latencyMs,
    }, 'Completed GenAI multimodal request');
    return response;
  } catch (error) {
    const latencyMs = Date.now() - startedAt;
    recordGenAICall(trace, {
      kind: 'multimodal_chat',
      profile: resolvedProfile,
      modelId: execution.cfg?.modelId || '',
      latencyMs,
      ok: false,
      errorMessage: error.message,
    });
    activeLogger.warn({
      event: 'genai.request.failure',
      kind: 'multimodal_chat',
      profile: resolvedProfile,
      modelId: execution.cfg?.modelId || '',
      latencyMs,
      errorMessage: error.message,
    }, 'GenAI multimodal request failed');
    throw wrapGenAIError(error);
  }
}

function extractChatText(data) {
  if (!data) return '';
  const sdkWrapped = data?.chatResult?.chatResponse?.choices?.[0]?.message?.content?.[0]?.text;
  if (typeof sdkWrapped === 'string' && sdkWrapped.trim()) return sdkWrapped;
  const sdkWrappedString = data?.chatResult?.chatResponse?.choices?.[0]?.message?.content;
  if (typeof sdkWrappedString === 'string' && sdkWrappedString.trim()) return sdkWrappedString;
  const sdkWrappedContent = data?.chatResult?.chatResponse?.choices?.[0]?.message?.content;
  if (Array.isArray(sdkWrappedContent)) {
    const text = sdkWrappedContent.map((item) => item?.text || '').filter(Boolean).join('\n');
    if (text.trim()) return text;
  }
  const direct = data?.chatResponse?.choices?.[0]?.message?.content?.[0]?.text;
  if (typeof direct === 'string' && direct.trim()) return direct;
  const directString = data?.chatResponse?.choices?.[0]?.message?.content;
  if (typeof directString === 'string' && directString.trim()) return directString;
  const alt = data?.choices?.[0]?.message?.content?.[0]?.text;
  if (typeof alt === 'string' && alt.trim()) return alt;
  const altString = data?.choices?.[0]?.message?.content;
  if (typeof altString === 'string' && altString.trim()) return altString;
  const content = data?.chatResponse?.choices?.[0]?.message?.content;
  if (Array.isArray(content)) {
    return content.map((item) => item?.text || '').filter(Boolean).join('\n');
  }
  if (typeof data?.chatResponse?.text === 'string') return data.chatResponse.text;
  if (typeof data?.text === 'string') return data.text;
  return '';
}

module.exports = {
  loadGenAISettings,
  buildChatDetails,
  estimateChatInputTokens,
  resolveChatExecutionOptions,
  shouldRetryWithMaxCompletionTokens,
  executeChatWithFallback,
  extractUsageMetadata,
  getGenAITokenBudget,
  logGenAIUsage,
  maybeWarnOnTokenBudget,
  wrapGenAIError,
  runChat,
  runMultimodalChat,
  extractChatText,
};
