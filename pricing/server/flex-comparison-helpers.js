'use strict';

const { parsePromptRequest } = require('./quotation-engine');

const FLEX_SHAPE_TOKEN_PATTERN_SOURCE = '(?:(?:vm|bm)\\.)?(?:(?:[a-z][a-z0-9]*)\\.)*(?:[a-z]+\\d+|[a-z]\\d+)\\.flex';
const FLEX_SHAPE_TOKEN_GLOBAL_PATTERN = new RegExp(`\\b${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}\\b`, 'ig');

function isFlexComparisonRequest(text) {
  const source = String(text || '');
  const matches = source.match(FLEX_SHAPE_TOKEN_GLOBAL_PATTERN) || [];
  return /\bcompare\b/i.test(source) && matches.length >= 2;
}

function parseCapacityReservationUtilization(text) {
  const source = String(text || '');
  const match = source.match(/\b(?:capacity reservation(?: utilization)?|reservation utilization)\s*[:=]?\s*(\d+(?:\.\d+)?)\b/i);
  if (!match) return null;
  return Number(match[1]);
}

function parseBurstableBaseline(text) {
  const source = String(text || '');
  const match = source.match(/\bburstable(?: baseline)?\s*[:=]?\s*(\d+(?:\.\d+)?)\b/i) || source.match(/\bbaseline\s*[:=]?\s*(\d+(?:\.\d+)?)\b/i);
  if (!match) return null;
  return Number(match[1]);
}

function parseStandaloneNumericAnswer(text) {
  const source = String(text || '').trim();
  if (!/^\d+(?:\.\d+)?$/.test(source)) return null;
  const value = Number(source);
  return Number.isFinite(value) ? value : null;
}

function parseOnDemandMode(text) {
  const source = String(text || '').trim();
  if (/^on[- ]?demand$/i.test(source)) return 'on-demand';
  if (/^reserved(?: pricing)?$/i.test(source)) return 'reserved';
  return '';
}

function detectFlexComparisonModifier(text) {
  const source = String(text || '');
  if (/\bcapacity reservation\b/i.test(source)) return 'capacity-reservation';
  if (/\bpreemptible\b/i.test(source)) return 'preemptible';
  if (/\bburstable\b/i.test(source)) return 'burstable';
  return '';
}

function extractFlexShapes(text) {
  const matches = String(text || '').match(FLEX_SHAPE_TOKEN_GLOBAL_PATTERN) || [];
  const seen = new Set();
  return matches.filter((item) => {
    const key = item.toUpperCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function findLatestFlexComparisonPrompt(conversation = [], userText = '', fallbackPrompt = '') {
  const current = String(userText || '').trim();
  if (isFlexComparisonRequest(current)) return current;
  const fallback = String(fallbackPrompt || '').trim();
  if (isFlexComparisonRequest(fallback)) return fallback;
  const items = Array.isArray(conversation) ? conversation : [];
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (item.role !== 'user') continue;
    const content = String(item.content || '').trim();
    if (isFlexComparisonRequest(content)) return content;
  }
  return '';
}

function extractFlexComparisonContext(conversation = [], userText = '', fallbackPrompt = '') {
  const basePrompt = findLatestFlexComparisonPrompt(conversation, userText, fallbackPrompt);
  if (!basePrompt) return null;
  const shapes = extractFlexShapes(basePrompt);
  if (shapes.length < 2) return null;

  const parsed = parsePromptRequest(basePrompt);
  const modifierKind = detectFlexComparisonModifier(basePrompt);
  let utilization = parseCapacityReservationUtilization(basePrompt);
  let burstableBaseline = parseBurstableBaseline(basePrompt);
  let withoutCrMode = parseOnDemandMode(basePrompt);

  const items = [...(Array.isArray(conversation) ? conversation : []), { role: 'user', content: userText }];
  for (const item of items) {
    if (item.role !== 'user') continue;
    const content = String(item.content || '');
    if (modifierKind === 'capacity-reservation' && utilization === null) {
      const explicitUtil = parseCapacityReservationUtilization(content);
      const standalone = parseStandaloneNumericAnswer(content);
      if (explicitUtil !== null) utilization = explicitUtil;
      else if (standalone !== null && standalone >= 0 && standalone <= 1) utilization = standalone;
    }
    if (modifierKind === 'burstable' && burstableBaseline === null) {
      const explicitBaseline = parseBurstableBaseline(content);
      const standalone = parseStandaloneNumericAnswer(content);
      if (explicitBaseline !== null) burstableBaseline = explicitBaseline;
      else if (standalone !== null && standalone > 0 && standalone <= 1) burstableBaseline = standalone;
    }
    if (modifierKind === 'capacity-reservation' && !withoutCrMode) {
      withoutCrMode = parseOnDemandMode(content) || withoutCrMode;
    }
  }

  return {
    basePrompt,
    shapes,
    ocpus: parsed.ocpus,
    memoryGb: parsed.memoryQuantity,
    hours: parsed.hours,
    modifierKind,
    utilization,
    burstableBaseline,
    withoutCrMode,
  };
}

module.exports = {
  detectFlexComparisonModifier,
  extractFlexComparisonContext,
  extractFlexShapes,
  findLatestFlexComparisonPrompt,
  isFlexComparisonRequest,
  parseBurstableBaseline,
  parseCapacityReservationUtilization,
  parseOnDemandMode,
  parseStandaloneNumericAnswer,
};
