'use strict';

const { runChat, extractChatText } = require('./genai');
const { buildSessionContextBlock } = require('./intent-extractor');
const { stringifyContextPack } = require('./context-packs');

const RESPONSE_PROMPT = [
  'You are an OCI pricing specialist speaking to a customer.',
  'Be concise, natural, and practical.',
  'If a deterministic quotation is provided, explain what was matched and mention any assumptions or warnings.',
  'Do not invent prices, SKUs, tiers, or formulas.',
  'If no quotation is available, explain the situation clearly and ask at most one next question when needed.',
  'Do not render tables.',
  'Use plain markdown.',
].join('\n');

const STRUCTURED_DISCOVERY_PROMPT = [
  'You are an OCI pricing discovery specialist.',
  'Answer only using the structured product context provided by the system.',
  'Do not invent OCI services, shapes, pricing rules, modifiers, or availability.',
  'If the context does not contain enough information to answer safely, say the service is not available in the current pricing knowledge base.',
  'Do not generate a quote unless the system explicitly says this is a deterministic quote path.',
  'Use concise natural markdown and prefer short lists when enumerating options.',
].join('\n');

function buildConversationMessages(conversation = [], contextBlock = '') {
  const history = Array.isArray(conversation) ? conversation.slice(-6) : [];
  return [
    ...history.map((item) => ({
      role: item.role === 'assistant' ? 'assistant' : 'user',
      content: String(item.content || ''),
    })),
    { role: 'user', content: String(contextBlock || '') },
  ];
}

async function writeNaturalReply(cfg, conversation, userText, context = {}, sessionContext, deps = {}) {
  const {
    buildSessionContextBlock: buildSessionContextBlockImpl = buildSessionContextBlock,
    runChat: runChatImpl = runChat,
    extractChatText: extractChatTextImpl = extractChatText,
  } = deps;

  const sessionBlock = buildSessionContextBlockImpl(sessionContext);
  const contextBlock = [
    sessionBlock,
    `User request: ${userText}`,
    `Intent: ${context.intent || 'quote'}`,
    context.summary ? `Summary: ${context.summary}` : '',
    context.quoteMarkdown ? `Quotation markdown:\n${context.quoteMarkdown}` : '',
    context.warningLines?.length ? `Warnings:\n${context.warningLines.join('\n')}` : '',
    context.assumptionLines?.length ? `Assumptions:\n${context.assumptionLines.join('\n')}` : '',
    context.candidateLines?.length ? `Candidates:\n${context.candidateLines.join('\n')}` : '',
  ].filter(Boolean).join('\n\n');

  const response = await runChatImpl({
    cfg,
    systemPrompt: RESPONSE_PROMPT,
    messages: buildConversationMessages(conversation, contextBlock),
    maxTokens: 900,
    temperature: 0.35,
    topP: 0.7,
    topK: -1,
  });
  return extractChatTextImpl(response?.data || response).trim();
}

async function writeStructuredContextReply(cfg, conversation, userText, sessionContext, contextPack, deps = {}) {
  const {
    buildSessionContextBlock: buildSessionContextBlockImpl = buildSessionContextBlock,
    stringifyContextPack: stringifyContextPackImpl = stringifyContextPack,
    runChat: runChatImpl = runChat,
    extractChatText: extractChatTextImpl = extractChatText,
  } = deps;

  if (!cfg?.modelId || !cfg?.compartment) return '';

  const sessionBlock = buildSessionContextBlockImpl(sessionContext);
  const contextBlock = [
    sessionBlock,
    `User request: ${String(userText || '').trim()}`,
    `Structured product context:\n${stringifyContextPackImpl(contextPack)}`,
  ].filter(Boolean).join('\n\n');

  try {
    const response = await runChatImpl({
      cfg,
      systemPrompt: STRUCTURED_DISCOVERY_PROMPT,
      messages: buildConversationMessages(conversation, contextBlock),
      maxTokens: 700,
      temperature: 0.2,
      topP: 0.5,
      topK: -1,
    });
    return extractChatTextImpl(response?.data || response).trim();
  } catch {
    return '';
  }
}

module.exports = {
  RESPONSE_PROMPT,
  STRUCTURED_DISCOVERY_PROMPT,
  buildConversationMessages,
  writeNaturalReply,
  writeStructuredContextReply,
};
