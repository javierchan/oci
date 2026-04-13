'use strict';

const FLEX_SHAPE_TOKEN_PATTERN_SOURCE = '(?:(?:vm|bm)\\.)?(?:(?:[a-z][a-z0-9]*)\\.)*(?:[a-z]+\\d+|[a-z]\\d+)\\.flex';
const FLEX_SHAPE_TOKEN_PATTERN = new RegExp(`^${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}$`, 'i');
const FLEX_SHAPE_TOKEN_INLINE_PATTERN = new RegExp(`\\b${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}\\b`, 'i');
const FLEX_SHAPE_TOKEN_GLOBAL_PATTERN = new RegExp(`\\b${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}\\b`, 'ig');

function isShortClarificationAnswer(text) {
  const source = String(text || '').trim();
  if (!source) return false;
  if (source.length > 80) return false;
  return /^(byol|bring your own license|license included|included|con licencia incluida|licencia incluida)$/i.test(source);
}

function isLicenseModeFollowUp(text) {
  const source = String(text || '').trim();
  if (!source || source.length > 160) return false;
  return /\b(byol|bring your own license|license included|included|con licencia incluida|licencia incluida)\b/i.test(source);
}

function isShapeSelectionFollowUp(text) {
  const source = String(text || '').trim();
  return FLEX_SHAPE_TOKEN_PATTERN.test(source);
}

function isShortContextualAnswer(text) {
  const source = String(text || '').trim();
  if (!source || source.length > 80) return false;
  if (isShortClarificationAnswer(source) || isLicenseModeFollowUp(source)) return true;
  if (/^(on[- ]?demand|reserved|reserve[d]? pricing)$/i.test(source)) return true;
  if (/^\d+(?:\.\d+)?$/.test(source)) return true;
  if (FLEX_SHAPE_TOKEN_PATTERN.test(source)) return true;
  return false;
}

function lastConversationItems(conversation = []) {
  const items = Array.isArray(conversation) ? conversation : [];
  let lastAssistant = null;
  let lastUser = null;
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (!lastAssistant && item.role === 'assistant') lastAssistant = item;
    if (!lastUser && item.role === 'user') lastUser = item;
    if (lastAssistant && lastUser) break;
  }
  return { lastAssistant, lastUser };
}

function extractProductContextFromAssistant(text) {
  const source = String(text || '').trim();
  if (!source) return '';
  const clarificationMatch = source.match(/do you want\s+(.+?)\s+as byol or license included\??/i);
  if (clarificationMatch) return String(clarificationMatch[1] || '').trim();
  const quoteMatch = source.match(/quotation for\s+`([^`]+)`/i);
  if (quoteMatch) return String(quoteMatch[1] || '').trim();
  return '';
}

function findPriorProductPrompt(conversation = []) {
  const items = Array.isArray(conversation) ? conversation : [];
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (item.role !== 'user') continue;
    const content = String(item.content || '').trim();
    if (!content) continue;
    if (isLicenseModeFollowUp(content)) continue;
    return content;
  }
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (item.role !== 'assistant') continue;
    const extracted = extractProductContextFromAssistant(item.content || '');
    if (extracted) return `Quote ${extracted}`;
  }
  return '';
}

function normalizeLicenseModeText(text) {
  const source = String(text || '').trim();
  if (/\bbyol\b|\bbring your own license\b/i.test(source)) return 'BYOL';
  if (/\blicense included\b|\binclude license\b|\bcon licencia incluida\b|\blicencia incluida\b|\bincluded\b/i.test(source)) return 'License Included';
  return source;
}

function extractLicenseModeDirective(text) {
  const normalized = normalizeLicenseModeText(text);
  if (/^BYOL$/i.test(normalized)) return 'BYOL';
  if (/^License Included$/i.test(normalized)) return 'License Included';
  return '';
}

function mergeClarificationAnswer(conversation, userText) {
  const isLicenseFollowUp = isLicenseModeFollowUp(userText);
  const isShapeFollowUp = isShapeSelectionFollowUp(userText);
  if (!isLicenseFollowUp && !isShapeFollowUp) return userText;
  const { lastAssistant, lastUser } = lastConversationItems(conversation);
  const assistantText = String(lastAssistant?.content || '');
  const previousPrompt = findPriorProductPrompt(conversation) || String(lastUser?.content || '').trim();
  if (!previousPrompt) return userText;
  const assistantProductContext = extractProductContextFromAssistant(assistantText);
  if (isShapeFollowUp && /which oci vm shape should i use|which .*shape should i use/i.test(assistantText)) {
    return `${previousPrompt} ${String(userText || '').trim()}`.trim();
  }
  if (/\b(BYOL|License Included)\b/i.test(assistantText) || assistantProductContext) {
    return `${previousPrompt} ${normalizeLicenseModeText(userText)}`.trim();
  }
  return userText;
}

function isSessionQuoteFollowUp(text) {
  const source = String(text || '').trim();
  if (!source || source.length > 220) return false;
  if (/^(y|and|ahora|now)\b/i.test(source)) return true;
  if (/\b(?:with|without|con|sin)\b/i.test(source)) return true;
  if (/\b(?:standard|enterprise|high performance|extreme performance)\b/i.test(source)) return true;
  if (/\b(?:instances?|instancias?|vpus?|ocpus?|ecpus?|gb|tb|mbps|gbps|users?|firewalls?|endpoints?|databases?|workspaces?|managed resources?|jobs?|queries?|consultas?|api calls?|solicitudes?|peticiones?|emails?|messages?|delivery operations?|datapoints?|transactions?)\b/i.test(source)) return true;
  if (/\b(?:byol|license included|licencia incluida|on[- ]?demand|reserved|amd|intel|ampere|arm)\b/i.test(source)) return true;
  if (/\b(?:usd|mxn|eur|brl|gbp|cad|jpy)\b/i.test(source)) return true;
  if (/\b(?:capacity reservation|reservation utilization|preemptible|burstable|baseline)\b/i.test(source)) return true;
  if (/\b(?:on\s+)?(?:base system|quarter rack|half rack|full rack|database server|storage server|expansion rack)(?:\s+x11m|\s+x10m|\s+x9m|\s+x8m|\s+x8|\s+x7)?\b/i.test(source)) return true;
  if (isShapeSelectionFollowUp(source)) return true;
  return false;
}

function stripQuotePrefix(text) {
  return String(text || '').trim().replace(/^\s*quote\s+/i, '').trim();
}

function replaceShapeInPrompt(basePrompt, nextShape) {
  const source = String(basePrompt || '').trim();
  const shape = String(nextShape || '').trim();
  if (!source || !shape) return source;
  return source.replace(FLEX_SHAPE_TOKEN_INLINE_PATTERN, shape);
}

function extractInlineShapeSelection(text) {
  const match = String(text || '').match(FLEX_SHAPE_TOKEN_GLOBAL_PATTERN);
  return Array.isArray(match) && match.length ? String(match[0] || '').trim() : '';
}

module.exports = {
  extractInlineShapeSelection,
  extractLicenseModeDirective,
  extractProductContextFromAssistant,
  findPriorProductPrompt,
  isLicenseModeFollowUp,
  isSessionQuoteFollowUp,
  isShapeSelectionFollowUp,
  isShortClarificationAnswer,
  isShortContextualAnswer,
  lastConversationItems,
  mergeClarificationAnswer,
  normalizeLicenseModeText,
  replaceShapeInPrompt,
  stripQuotePrefix,
};
