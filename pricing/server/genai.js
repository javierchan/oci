'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

const common = require('oci-common');
const genai = require('oci-generativeaiinference');

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

  return {
    configPath,
    profile: env.OCI_GENAI_PROFILE || cfg.oci_profile || env.OCI_CLI_PROFILE || 'DEFAULT',
    endpoint: endpoint || `https://inference.generativeai.${region}.oci.oraclecloud.com`,
    compartmentId: env.OCI_GENAI_COMPARTMENT || cfg.compartment_id || env.OCI_COMPARTMENT || '',
    modelId: env.OCI_GENAI_MODEL || cfg.base_model_id || '',
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

async function runChat({ cfg, systemPrompt, messages, maxTokens, temperature = 0.7, topP = 0.75, topK = -1 }) {
  const client = createInferenceClient(cfg);
  const models = genai.models;

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

  const chatDetails = {
    compartmentId: cfg.compartment,
    servingMode: {
      modelId: cfg.modelId,
      servingType: genai.models.OnDemandServingMode.servingType,
    },
    chatRequest: {
      apiFormat: genai.models.GenericChatRequest.apiFormat,
      messages: chatMessages,
      maxTokens: Number(maxTokens || 2000),
      temperature: Number(temperature),
      topP: Number(topP),
      topK: Number(topK),
      isStream: false,
    },
  };

  return client.chat({ chatDetails });
}

async function runMultimodalChat({ cfg, systemPrompt, userText, imageDataUrl, maxTokens, temperature = 0.2, topP = 0.5, topK = -1 }) {
  const client = createInferenceClient(cfg);
  const models = genai.models;

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

  const chatDetails = {
    compartmentId: cfg.compartment,
    servingMode: {
      modelId: cfg.modelId,
      servingType: genai.models.OnDemandServingMode.servingType,
    },
    chatRequest: {
      apiFormat: genai.models.GenericChatRequest.apiFormat,
      messages,
      maxTokens: Number(maxTokens || 1200),
      temperature: Number(temperature),
      topP: Number(topP),
      topK: Number(topK),
      isStream: false,
    },
  };

  return client.chat({ chatDetails });
}

function extractChatText(data) {
  if (!data) return '';
  const sdkWrapped = data?.chatResult?.chatResponse?.choices?.[0]?.message?.content?.[0]?.text;
  if (typeof sdkWrapped === 'string' && sdkWrapped.trim()) return sdkWrapped;
  const sdkWrappedContent = data?.chatResult?.chatResponse?.choices?.[0]?.message?.content;
  if (Array.isArray(sdkWrappedContent)) {
    const text = sdkWrappedContent.map((item) => item?.text || '').filter(Boolean).join('\n');
    if (text.trim()) return text;
  }
  const direct = data?.chatResponse?.choices?.[0]?.message?.content?.[0]?.text;
  if (typeof direct === 'string' && direct.trim()) return direct;
  const alt = data?.choices?.[0]?.message?.content?.[0]?.text;
  if (typeof alt === 'string' && alt.trim()) return alt;
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
  runChat,
  runMultimodalChat,
  extractChatText,
};
