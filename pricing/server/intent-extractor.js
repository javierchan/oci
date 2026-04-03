'use strict';

const { runChat, runMultimodalChat, extractChatText } = require('./genai');
const { normalizeIntentResult } = require('./normalizer');

const BASE_SCHEMA = '{"route":"general_answer|product_discovery|quote_request|quote_followup|workbook_followup|clarify","intent":"quote|discover|explain|clarify|answer","shouldQuote":true,"needsClarification":false,"clarificationQuestion":"","reformulatedRequest":"","assumptions":[],"serviceFamily":"","serviceName":"","extractedInputs":{},"confidence":0.0,"annualRequested":false,"quotePlan":{"action":"answer|discover|quote|modify_quote|modify_workbook|clarify","targetType":"general|service|bundle|shape|workbook|quote","domain":"","candidateFamilies":[],"missingInputs":[],"useDeterministicEngine":false}}';

const ANALYZE_PROMPT = [
  'You are an OCI pricing assistant controller.',
  'Return JSON only.',
  'Classify the user request and extract normalized OCI pricing intent plus a routing decision.',
  'Decide whether the user is asking for a quotation, quote follow-up, workbook follow-up, product discovery, clarification, or general OCI pricing guidance.',
  'Use route=product_discovery for human questions about available products, shape options, pricing models, or OCI service choices that should not immediately generate a quote.',
  'Use route=general_answer for explanatory pricing guidance that should stay in natural language.',
  'Use route=quote_request when the user wants a fresh quote, and route=quote_followup when the user is modifying an active quote in session context.',
  'Use route=workbook_followup when the user is modifying an active workbook or RVTools estimate in session context.',
  'If the user wants a price, set shouldQuote=true and useDeterministicEngine=true in quotePlan.',
  'If key sizing inputs are missing but a useful partial quote is still possible, keep shouldQuote=true and note the assumptions.',
  'If the request is too ambiguous to quote safely, set needsClarification=true and provide one short clarification question.',
  'Infer serviceFamily when possible using stable identifiers such as storage_block, network_fastconnect, serverless_functions, network_load_balancer, storage_object, compute_flex.',
  'Populate extractedInputs only with values supported by the user text. Useful keys include capacityGb, vpuPerGb, bandwidthGbps, invocationsPerDay, invocationsPerMonth, daysPerMonth, executionMs, memoryMb, provisionedConcurrencyUnits, hoursPerMonth, currencyCode.',
  'Populate quotePlan with the most likely action, targetType, domain, candidateFamilies, and missingInputs.',
  'Respond with compact JSON using this exact schema:',
  BASE_SCHEMA,
].join('\n');

const IMAGE_ANALYZE_PROMPT = [
  'You are an OCI pricing extraction controller.',
  'Read the user text and the pasted image.',
  'The image may contain a spreadsheet, architecture, handwritten notes, screenshot, or sizing table.',
  'Extract only OCI pricing intent and sizing inputs that are visible or directly implied.',
  'If the image implies an editable workbook or migration sheet, prefer route=quote_request or route=workbook_followup depending on the user text.',
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

function buildSessionContextBlock(sessionContext) {
  if (!sessionContext || typeof sessionContext !== 'object') return '';
  const lines = [];
  if (sessionContext.currentIntent) lines.push(`Current intent: ${sessionContext.currentIntent}`);
  if (sessionContext.sessionSummary) lines.push(`Session summary: ${String(sessionContext.sessionSummary).trim()}`);
  const workbook = sessionContext.workbookContext;
  if (workbook && typeof workbook === 'object') {
    lines.push(`Active workbook: ${workbook.fileName || 'workbook'}`);
    if (workbook.sourcePlatform) lines.push(`Workbook source platform: ${workbook.sourcePlatform}`);
    if (workbook.processorVendor) lines.push(`Workbook processor vendor: ${workbook.processorVendor}`);
    if (workbook.shapeName) lines.push(`Workbook target shape: ${workbook.shapeName}`);
    if (Number.isFinite(Number(workbook.vpuPerGb))) lines.push(`Workbook VPU override: ${Number(workbook.vpuPerGb)}`);
  }
  const quote = sessionContext.lastQuote;
  if (quote && typeof quote === 'object') {
    if (quote.label) lines.push(`Last quote label: ${quote.label}`);
    if (Number.isFinite(Number(quote.monthly))) lines.push(`Last quote monthly total: ${Number(quote.monthly)}`);
    if (Number.isFinite(Number(quote.lineItemCount))) lines.push(`Last quote line count: ${Number(quote.lineItemCount)}`);
    if (quote.shapeName) lines.push(`Last quote shape: ${quote.shapeName}`);
  }
  if (!lines.length) return '';
  return `Session context:\n- ${lines.join('\n- ')}`;
}

async function analyzeIntent(cfg, conversation, userText, sessionContext) {
  const history = Array.isArray(conversation) ? conversation.slice(-6) : [];
  const contextBlock = buildSessionContextBlock(sessionContext);
  const messages = [
    ...history.map((item) => ({
      role: item.role === 'assistant' ? 'assistant' : 'user',
      content: String(item.content || ''),
    })),
    ...(contextBlock ? [{ role: 'user', content: contextBlock }] : []),
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
  buildSessionContextBlock,
};
