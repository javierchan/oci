'use strict';

const { runChat, runMultimodalChat, extractChatText } = require('./genai');
const { normalizeIntentResult } = require('./normalizer');

const BASE_SCHEMA = '{"intent":"quote|discover|explain|clarify","shouldQuote":true,"needsClarification":false,"clarificationQuestion":"","reformulatedRequest":"","assumptions":[],"serviceFamily":"","serviceName":"","extractedInputs":{},"confidence":0.0,"annualRequested":false}';

const ANALYZE_PROMPT = [
  'You are an OCI pricing assistant controller.',
  'Return JSON only.',
  'Classify the user request and extract normalized OCI pricing intent.',
  'Decide whether the user is asking for a quotation, product discovery, clarification, or general OCI pricing guidance.',
  'If the user wants a price, set shouldQuote=true.',
  'If key sizing inputs are missing but a useful partial quote is still possible, keep shouldQuote=true and note the assumptions.',
  'If the request is too ambiguous to quote safely, set needsClarification=true and provide one short clarification question.',
  'Infer serviceFamily when possible using stable identifiers such as storage_block, network_fastconnect, serverless_functions, network_load_balancer, storage_object, compute_flex.',
  'Populate extractedInputs only with values supported by the user text. Useful keys include capacityGb, vpuPerGb, bandwidthGbps, invocationsPerDay, invocationsPerMonth, daysPerMonth, executionMs, memoryMb, provisionedConcurrencyUnits, hoursPerMonth, currencyCode.',
  'Respond with compact JSON using this exact schema:',
  BASE_SCHEMA,
].join('\n');

const IMAGE_ANALYZE_PROMPT = [
  'You are an OCI pricing extraction controller.',
  'Read the user text and the pasted image.',
  'The image may contain a spreadsheet, architecture, handwritten notes, screenshot, or sizing table.',
  'Extract only OCI pricing intent and sizing inputs that are visible or directly implied.',
  'Infer serviceFamily when possible using stable identifiers such as storage_block, network_fastconnect, serverless_functions, network_load_balancer, storage_object, compute_flex.',
  'Respond with compact JSON only using this exact schema:',
  BASE_SCHEMA,
  'If the image is sufficient for a useful quotation, set shouldQuote=true and build reformulatedRequest as one concise OCI pricing request.',
  'When the image shows OCI Functions or Serverless calculator fields, include visible numeric inputs in extractedInputs and reformulatedRequest, especially invocations per day/month, execution time per invocation in milliseconds, memory in MB, days per month, and provisioned concurrency units.',
  'Do not invent values that are not present.',
].join('\n');

function extractJson(text) {
  const source = String(text || '').trim();
  if (!source) return null;
  const fenced = source.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const candidate = fenced ? fenced[1].trim() : source;
  const first = candidate.indexOf('{');
  const last = candidate.lastIndexOf('}');
  if (first < 0 || last < first) return null;
  try {
    return JSON.parse(candidate.slice(first, last + 1));
  } catch {
    return null;
  }
}

async function analyzeIntent(cfg, conversation, userText) {
  const history = Array.isArray(conversation) ? conversation.slice(-6) : [];
  const messages = [
    ...history.map((item) => ({
      role: item.role === 'assistant' ? 'assistant' : 'user',
      content: String(item.content || ''),
    })),
    { role: 'user', content: userText },
  ];
  const response = await runChat({
    cfg,
    systemPrompt: ANALYZE_PROMPT,
    messages,
    maxTokens: 500,
    temperature: 0.1,
    topP: 0.2,
    topK: -1,
  });
  const text = extractChatText(response?.data || response);
  return normalizeIntentResult(extractJson(text) || {}, userText);
}

async function analyzeImageIntent(cfg, userText, imageDataUrl) {
  const response = await runMultimodalChat({
    cfg,
    systemPrompt: IMAGE_ANALYZE_PROMPT,
    userText: userText || 'Estimate OCI pricing from this image.',
    imageDataUrl,
    maxTokens: 700,
    temperature: 0.1,
    topP: 0.2,
    topK: -1,
  });
  const text = extractChatText(response?.data || response);
  const fallback = userText || 'Estimate OCI pricing from the pasted image.';
  const result = normalizeIntentResult(extractJson(text) || {}, fallback);
  if (!result.assumptions.length) result.assumptions = ['Sizing details were extracted from the pasted image.'];
  return result;
}

module.exports = {
  analyzeIntent,
  analyzeImageIntent,
};
