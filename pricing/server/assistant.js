'use strict';

const { quoteFromPrompt, parsePromptRequest } = require('./quotation-engine');
const { searchProducts, searchPresets, searchServiceRegistry, serviceHasRequiredInputs } = require('./catalog');
const { getServiceFamily, getMissingRequiredInputs, buildCanonicalRequest, getClarificationMessage, getPreQuoteClarification } = require('./service-families');
const { inferConsumptionPattern, explainConsumptionPattern } = require('./consumption-model');
const { runChat, extractChatText } = require('./genai');
const { analyzeIntent, analyzeImageIntent, buildSessionContextBlock } = require('./intent-extractor');
const { buildAssistantContextPack, buildCatalogListingReply, buildUncoveredComputeReply, canSafelyQuoteUncoveredComputeVariant, findUncoveredComputeVariant, stringifyContextPack, summarizeContextPack } = require('./context-packs');

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

const QUOTE_ENRICHMENT_PROMPT = [
  'You are enriching an OCI pricing response that was already calculated deterministically.',
  'Do not change any numbers, SKUs, totals, assumptions, or warnings.',
  'Do not invent pricing, architecture, licensing, or migration facts.',
  'Do not restate totals, do not rebuild arithmetic, and do not infer discrepancies.',
  'Write short, useful markdown only, with the tone of the requested OCI expert role.',
  'Return at most two short bullet lists:',
  '- OCI considerations for this technology',
  '- Migration notes when the source clearly comes from VMware or RVTools',
  'If a section does not apply, omit it.',
].join('\n');

function summarizeMatches(index, text) {
  const products = searchProducts(index, text, 5).map((item) => item.fullDisplayName);
  const presets = searchPresets(index, text, 3).map((item) => item.displayName);
  return { products, presets };
}

function buildServiceUnavailableMessage(userText) {
  const source = String(userText || '').trim();
  return [
    'This OCI pricing guidance service is not available for that request right now.',
    source ? `I could not interpret \`${source}\` safely with the current GenAI controller and structured pricing context.` : 'I could not interpret the request safely with the current GenAI controller and structured pricing context.',
    'I prefer to stop here rather than return an unreliable answer or quote.',
  ].join('\n\n');
}

function buildRegistryQuery(text, intent = {}) {
  return String(text || '')
    .replace(/\bquote\b/ig, ' ')
    .replace(/\b\d[\d,]*(?:\.\d+)?\s*(?:requests?|api calls?|transactions?|queries?|emails?|messages?|sms(?: messages?)?|tokens?|gb|tb|mbps|gbps|users?|named users?|ocpus?|ecpus?|hours?|days?)\b/ig, ' ')
    .replace(/[,+]/g, ' ')
    .replace(/\bper month\b|\bper hour\b|\bper day\b|\bmonthly\b|\bhourly\b/ig, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function isGreeting(text) {
  return /^(hola|hello|hi|hey|buenas|good morning|good afternoon|good evening)\b[!. ]*$/i.test(String(text || '').trim());
}

function isFastConnectText(text) {
  return /\bfast\s*connect\b|\bfastconnect\b/i.test(String(text || ''));
}

function conversationMentionsFastConnect(conversation) {
  return (conversation || []).some((item) => isFastConnectText(item.content || ''));
}

function isConfidenceQuestion(text) {
  return /\b(estas seguro|estás seguro|seguro de ese precio|are you sure|is that price correct|is that accurate)\b/i.test(String(text || ''));
}

function parseRegionAnswer(text) {
  const source = String(text || '').trim().toLowerCase();
  if (!source) return null;
  if (/quer[eé]taro/.test(source)) return { code: 'mx-queretaro-1', label: 'Mexico Central (Queretaro)' };
  if (/monterrey/.test(source)) return { code: 'mx-monterrey-1', label: 'Mexico Northeast (Monterrey)' };
  return null;
}

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

function isShortContextualAnswer(text) {
  const source = String(text || '').trim();
  if (!source || source.length > 80) return false;
  if (isShortClarificationAnswer(source) || isLicenseModeFollowUp(source)) return true;
  if (/^(on[- ]?demand|reserved|reserve[d]? pricing)$/i.test(source)) return true;
  if (/^\d+(?:\.\d+)?$/.test(source)) return true;
  if (/^(?:(?:vm|bm)\.)?(?:[a-z0-9.]+\.)?[a-z]\d+\.flex$/i.test(source)) return true;
  return false;
}

function isShapeSelectionFollowUp(text) {
  const source = String(text || '').trim();
  return /^(?:(?:vm|bm)\.)?(?:[a-z0-9.]+\.)?[a-z]\d+\.flex$/i.test(source);
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
  if (/\b(?:instances?|instancias?|vpus?|ocpus?|ecpus?|gb|tb|mbps|gbps|users?|firewalls?|endpoints?|databases?|workspaces?|managed resources?|jobs?|queries?|api calls?|emails?|messages?|delivery operations?|transactions?)\b/i.test(source)) return true;
  if (/\b(?:byol|license included|licencia incluida|on[- ]?demand|reserved|amd|intel|ampere|arm)\b/i.test(source)) return true;
  if (/\b(?:usd|mxn|eur|brl|gbp|cad|jpy)\b/i.test(source)) return true;
  if (/\b(?:capacity reservation|reservation utilization|preemptible|burstable|baseline)\b/i.test(source)) return true;
  if (isShapeSelectionFollowUp(source)) return true;
  return false;
}

function removeCompositeServiceSegment(basePrompt, pattern) {
  const source = String(basePrompt || '').trim();
  if (!source) return source;
  const prefixMatch = source.match(/^\s*quote\s+/i);
  const prefix = prefixMatch ? prefixMatch[0] : '';
  const body = prefix ? source.slice(prefix.length).trim() : source;
  const separators = /\s+\+\s+|\s+plus\s+/i;
  if (!separators.test(body)) return source;
  const kept = body
    .split(separators)
    .map((segment) => segment.trim())
    .filter(Boolean)
    .filter((segment) => !(new RegExp(pattern, 'i')).test(segment));
  if (!kept.length) return source;
  return `${prefix}${kept.join(' plus ')}`.trim();
}

function replaceOrAppendPattern(basePrompt, regex, replacement) {
  const source = String(basePrompt || '').trim();
  if (!source) return String(replacement || '').trim();
  if (regex.test(source)) return source.replace(regex, replacement);
  return `${source} ${replacement}`.trim();
}

function replaceCurrencyInPrompt(basePrompt, currencyCode) {
  const source = String(basePrompt || '').trim();
  const nextCode = String(currencyCode || '').trim().toUpperCase();
  if (!source || !nextCode) return source;
  if (/\b(?:USD|MXN|EUR|BRL|GBP|CAD|JPY)\b/i.test(source)) {
    return source.replace(/\b(?:USD|MXN|EUR|BRL|GBP|CAD|JPY)\b/i, nextCode);
  }
  return `${source} ${nextCode}`.trim();
}

function applySessionFollowUpDirective(basePrompt, followUp) {
  const source = String(followUp || '').trim();
  let nextPrompt = String(basePrompt || '').trim();
  if (!source) return nextPrompt;
  if (/\b(?:sin|without)\s+(?:waf|web application firewall)\b/i.test(source)) {
    nextPrompt = removeCompositeServiceSegment(nextPrompt, String.raw`(?:waf|web application firewall)`);
  }
  if (/\b(?:sin|without)\s+dns\b/i.test(source)) {
    nextPrompt = removeCompositeServiceSegment(nextPrompt, String.raw`dns`);
  }
  if (/\b(?:sin|without)\s+(?:load balancer|lb)\b/i.test(source)) {
    nextPrompt = removeCompositeServiceSegment(nextPrompt, String.raw`(?:flexible\s+)?load balancer|\blb\b`);
  }
  if (/\b(?:sin|without)\s+health checks?\b/i.test(source)) {
    nextPrompt = removeCompositeServiceSegment(nextPrompt, String.raw`health checks?`);
  }
  if (/\b(?:sin|without)\s+api gateway\b/i.test(source)) {
    nextPrompt = removeCompositeServiceSegment(nextPrompt, String.raw`api gateway`);
  }

  if (/\b(?:mxn|usd|eur|brl|gbp|cad|jpy)\b/i.test(source)) {
    const code = source.match(/\b(mxn|usd|eur|brl|gbp|cad|jpy)\b/i)?.[1]?.toUpperCase();
    if (code) nextPrompt = replaceCurrencyInPrompt(nextPrompt, code);
  }

  if (/\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i, source.match(/\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i)?.[0] || source);
  }
  if (/\b\d+(?:\.\d+)?\s*(?:users?|usuarios?)\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d+(?:\.\d+)?\s*(?:users?|usuarios?)\b/i, source.match(/\b\d+(?:\.\d+)?\s*(?:users?|usuarios?)\b/i)?.[0] || source);
  }
  if (/\b\d+(?:\.\d+)?\s*firewalls?\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d+(?:\.\d+)?\s*firewalls?\b/i, source.match(/\b\d+(?:\.\d+)?\s*firewalls?\b/i)?.[0] || source);
  }
  if (/\b\d+(?:\.\d+)?\s*endpoints?\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d+(?:\.\d+)?\s*endpoints?\b/i, source.match(/\b\d+(?:\.\d+)?\s*endpoints?\b/i)?.[0] || source);
  }
  if (/\b\d+(?:\.\d+)?\s*target\s+databases?\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d+(?:\.\d+)?\s*target\s+databases?\b/i, source.match(/\b\d+(?:\.\d+)?\s*target\s+databases?\b/i)?.[0] || source);
  } else if (/\b\d+(?:\.\d+)?\s*databases?\b/i.test(source)) {
    if (/\b\d+(?:\.\d+)?\s*target\s+databases?\b/i.test(nextPrompt)) {
      const amount = source.match(/\b\d+(?:\.\d+)?\b/i)?.[0];
      if (amount) nextPrompt = nextPrompt.replace(/\b\d+(?:\.\d+)?\s*target\s+databases?\b/i, `${amount} target databases`);
    } else {
      nextPrompt = nextPrompt.replace(/\b\d+(?:\.\d+)?\s*databases?\b/i, source.match(/\b\d+(?:\.\d+)?\s*databases?\b/i)?.[0] || source);
    }
  }
  if (/\b\d+(?:\.\d+)?\s*workspaces?\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d+(?:\.\d+)?\s*workspaces?\b/i, source.match(/\b\d+(?:\.\d+)?\s*workspaces?\b/i)?.[0] || source);
  }
  if (/\b\d+(?:\.\d+)?\s*managed resources?\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d+(?:\.\d+)?\s*managed resources?\b/i, source.match(/\b\d+(?:\.\d+)?\s*managed resources?\b/i)?.[0] || source);
  }
  if (/\b\d+(?:\.\d+)?\s*jobs?\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d+(?:\.\d+)?\s*jobs?\b/i, source.match(/\b\d+(?:\.\d+)?\s*jobs?\b/i)?.[0] || source);
  }
  if (/\b\d[\d,]*(?:\.\d+)?\s*queries?\b(?:\s+per\s+month)?/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d[\d,]*(?:\.\d+)?\s*queries?\b(?:\s+per\s+month)?/i, source.match(/\b\d[\d,]*(?:\.\d+)?\s*queries?\b(?:\s+per\s+month)?/i)?.[0] || source);
  }
  if (/\b\d[\d,]*(?:\.\d+)?\s*api calls?\b(?:\s+per\s+month)?/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d[\d,]*(?:\.\d+)?\s*api calls?\b(?:\s+per\s+month)?/i, source.match(/\b\d[\d,]*(?:\.\d+)?\s*api calls?\b(?:\s+per\s+month)?/i)?.[0] || source);
  }
  if (/\b\d[\d,]*(?:\.\d+)?\s*emails?\b(?:\s+per\s+month)?/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d[\d,]*(?:\.\d+)?\s*emails?\b(?:\s+per\s+month)?/i, source.match(/\b\d[\d,]*(?:\.\d+)?\s*emails?\b(?:\s+per\s+month)?/i)?.[0] || source);
  }
  if (/\b\d[\d,]*(?:\.\d+)?\s*sms messages?\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d[\d,]*(?:\.\d+)?\s*sms messages?\b/i, source.match(/\b\d[\d,]*(?:\.\d+)?\s*sms messages?\b/i)?.[0] || source);
  } else if (/\b\d[\d,]*(?:\.\d+)?\s*messages?\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d[\d,]*(?:\.\d+)?\s*messages?\b/i, source.match(/\b\d[\d,]*(?:\.\d+)?\s*messages?\b/i)?.[0] || source);
  }
  if (/\b\d[\d,]*(?:\.\d+)?\s*delivery operations?\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d[\d,]*(?:\.\d+)?\s*delivery operations?\b/i, source.match(/\b\d[\d,]*(?:\.\d+)?\s*delivery operations?\b/i)?.[0] || source);
  }
  if (/\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i, source.match(/\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i)?.[0] || source);
  }
  if (/\b\d+(?:\.\d+)?\s*vpu'?s?\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d+(?:\.\d+)?\s*vpu'?s?\b/i, source.match(/\b\d+(?:\.\d+)?\s*vpu'?s?\b/i)?.[0] || source);
  }
  if (/\b\d+(?:\.\d+)?\s*(?:gbps|mbps)\b/i.test(source)) {
    nextPrompt = nextPrompt.replace(/\b\d+(?:\.\d+)?\s*(?:gbps|mbps)\b/i, source.match(/\b\d+(?:\.\d+)?\s*(?:gbps|mbps)\b/i)?.[0] || source);
  }
  if (/\b(?:preemptible|capacity reservation|burstable)\b/i.test(source)) {
    nextPrompt = replaceOrAppendPattern(nextPrompt, /\b(?:preemptible|capacity reservation(?: utilization)?\s*[:=]?\s*\d+(?:\.\d+)?|burstable(?: baseline)?\s*[:=]?\s*\d+(?:\.\d+)?)\b/i, source);
  }

  if (nextPrompt !== String(basePrompt || '').trim()) return nextPrompt.trim();
  return `${String(basePrompt || '').trim()} ${source}`.trim();
}

function mergeSessionQuoteFollowUpByRoute(sessionContext, intent, userText) {
  const route = String(intent?.route || '').trim().toLowerCase();
  const lastQuoteSource = String(sessionContext?.lastQuote?.source || '').trim();
  const source = String(userText || '').trim();
  if (route !== 'quote_followup' || !lastQuoteSource || !source) return '';
  return applySessionFollowUpDirective(lastQuoteSource, source);
}

function preserveCriticalPromptModifiers(basePrompt, referencePrompt) {
  let nextPrompt = String(basePrompt || '').trim();
  const reference = String(referencePrompt || '').trim();
  if (!nextPrompt || !reference) return nextPrompt;
  if (/\bmetered\b/i.test(reference) && !/\bmetered\b/i.test(nextPrompt)) {
    nextPrompt = `${nextPrompt} metered`.trim();
  }
  return nextPrompt;
}

function mergeSessionQuoteFollowUp(sessionContext, userText) {
  const source = String(userText || '').trim();
  if (!isSessionQuoteFollowUp(source)) return source;
  const lastQuoteSource = String(sessionContext?.lastQuote?.source || '').trim();
  if (!lastQuoteSource) return source;
  const normalized = source
    .replace(/^(?:y|and|ahora|now)\s+/i, '')
    .trim();
  if (!normalized) return lastQuoteSource;
  return applySessionFollowUpDirective(lastQuoteSource, normalized);
}

function shouldForceSessionQuoteFollowUp(sessionContext, userText) {
  const source = String(userText || '').trim();
  if (!String(sessionContext?.lastQuote?.source || '').trim()) return false;
  if (!isSessionQuoteFollowUp(source)) return false;
  if (/\b(?:how|what|why|which|que|qué|como|cómo|cual|cuál|opciones?|difference|diff|billing|priced|billed|cobra)\b/i.test(source)) {
    return false;
  }
  return true;
}

function isFlexComparisonRequest(text) {
  const source = String(text || '');
  const matches = source.match(/\b[a-z]\d+\.flex\b/ig) || [];
  return /\bcompare\b/i.test(source) && matches.length >= 2;
}

function isCompositeOrComparisonRequest(text) {
  const source = String(text || '').toLowerCase();
  const segments = splitCompositeQuoteSegments(source);
  const signaledSegments = segments.filter((segment) => hasCompositeServiceSignal(segment)).length;
  if (segments.length >= 2 && signaledSegments >= 2) return true;
  const serviceHits = [
    /\bload balancer\b/.test(source),
    /\bblock storage\b|\bblock volumes?\b/.test(source),
    /\bobject storage\b/.test(source),
    /\bfastconnect\b|\bfast connect\b/.test(source),
    /\bweb application firewall\b|\bwaf\b/.test(source),
    /\bnetwork firewall\b/.test(source),
    /\bdns\b/.test(source),
    /\bapi gateway\b/.test(source),
    /\bintegration cloud\b/.test(source),
    /\banalytics cloud\b/.test(source),
    /\bdata integration\b/.test(source),
    /\bmonitoring\b/.test(source),
    /\bnotifications\b/.test(source),
    /\bhttps delivery\b|\bemail delivery\b/.test(source),
    /\biam sms\b|\bsms messages?\b/.test(source),
    /\bthreat intelligence\b/.test(source),
    /\bhealth checks?\b/.test(source),
    /\bfleet application management\b/.test(source),
    /\boci batch\b|\bbatch\b/.test(source),
    /\bdata safe\b/.test(source),
    /\blog analytics\b/.test(source),
    /\bfunctions\b/.test(source),
    /\bgenerative ai\b/.test(source),
    /\bvision\b|\bspeech\b|\bmedia flow\b/.test(source),
    /\bfile storage\b/.test(source),
    /\bautonomous(?: ai)? lakehouse\b|\bautonomous data warehouse\b|\bbase database service\b|\bexadata\b|\bdatabase cloud service\b/.test(source),
    /\b(?:vm|bm)\.[a-z0-9.]+\.flex\b/.test(source) || /\b[a-z]\d+\.flex\b/.test(source),
  ].filter(Boolean).length;
  if (/\bcompare\b/.test(source) && /\b[a-z]\d+\.flex\b/.test(source)) return true;
  return serviceHits >= 2 || /\b3-tier\b|\bthree-tier\b|\barchitecture\b|\bworkload\b|\bbundle\b|\bstack\b|\bplatform\b/.test(source);
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

function enrichExtractedInputsForFamily(intent = {}) {
  const extractedInputs = {
    ...((intent && typeof intent.extractedInputs === 'object' && intent.extractedInputs) || {}),
  };
  if (intent.serviceFamily === 'security_waf') {
    const genericInstances = Number(extractedInputs.instanceCount);
    if (Number.isFinite(genericInstances) && genericInstances > 0 && !Number.isFinite(Number(extractedInputs.wafInstances))) {
      extractedInputs.wafInstances = genericInstances;
    }
  }
  if (intent.serviceFamily === 'security_data_safe') {
    const dbCount = Number(extractedInputs.numberOfDatabases);
    if (Number.isFinite(dbCount) && dbCount > 0 && !Number.isFinite(Number(extractedInputs.quantity))) {
      extractedInputs.quantity = dbCount;
    }
  }
  return {
    ...intent,
    extractedInputs,
  };
}

function detectFlexComparisonModifier(text) {
  const source = String(text || '');
  if (/\bcapacity reservation\b/i.test(source)) return 'capacity-reservation';
  if (/\bpreemptible\b/i.test(source)) return 'preemptible';
  if (/\bburstable\b/i.test(source)) return 'burstable';
  return '';
}

function extractFlexShapes(text) {
  const matches = String(text || '').match(/\b[a-z]\d+\.flex\b/ig) || [];
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

function buildFlexComparisonQuote(index, context) {
  const rows = [];
  const warnings = [];
  for (const shape of context.shapes) {
    const basePrompt = `Quote ${shape} ${context.ocpus} OCPUs ${context.memoryGb} GB RAM ${context.hours}h`;
    const onDemandQuote = quoteFromPrompt(index, basePrompt);
    let variantPrompt = '';
    if (context.modifierKind === 'capacity-reservation') variantPrompt = `${basePrompt} capacity reservation ${context.utilization}`;
    if (context.modifierKind === 'preemptible') variantPrompt = `${basePrompt} preemptible`;
    if (context.modifierKind === 'burstable') variantPrompt = `${basePrompt} burstable baseline ${context.burstableBaseline}`;
    const modifierQuote = quoteFromPrompt(index, variantPrompt);
    if (!onDemandQuote.ok || !modifierQuote.ok) {
      warnings.push(`Could not build a complete comparison for ${shape}.`);
      continue;
    }
    if (Array.isArray(onDemandQuote.warnings) && onDemandQuote.warnings.length) {
      warnings.push(...onDemandQuote.warnings.map((item) => `${shape.toUpperCase()}: ${item}`));
    }
    if (Array.isArray(modifierQuote.warnings) && modifierQuote.warnings.length) {
      warnings.push(...modifierQuote.warnings.map((item) => `${shape.toUpperCase()}: ${item}`));
    }
    rows.push({
      shape: shape.toUpperCase(),
      onDemandMonthly: Number(onDemandQuote.totals?.monthly || 0),
      variantMonthly: Number(modifierQuote.totals?.monthly || 0),
      deltaMonthly: Number(modifierQuote.totals?.monthly || 0) - Number(onDemandQuote.totals?.monthly || 0),
      onDemandAnnual: Number(onDemandQuote.totals?.annual || 0),
      variantAnnual: Number(modifierQuote.totals?.annual || 0),
    });
  }
  if (!rows.length) {
    return { ok: false, warnings: warnings.length ? warnings : ['No Flex shapes could be compared.'] };
  }
  rows.sort((a, b) => a.onDemandMonthly - b.onDemandMonthly);
  const variantLabel = context.modifierKind === 'capacity-reservation'
    ? 'Capacity Reservation'
    : context.modifierKind === 'preemptible'
      ? 'Preemptible'
      : 'Burstable';
  const markdown = [
    `| Shape | On-demand $/Mo | ${variantLabel} $/Mo | Delta $/Mo | On-demand Annual | ${variantLabel} Annual |`,
    '|---|---:|---:|---:|---:|---:|',
    ...rows.map((row) => `| ${row.shape} | ${money(row.onDemandMonthly)} | ${money(row.variantMonthly)} | ${money(row.deltaMonthly)} | ${money(row.onDemandAnnual)} | ${money(row.variantAnnual)} |`),
  ].join('\n');
  return { ok: true, rows, markdown, warnings: Array.from(new Set(warnings)) };
}

function buildFlexComparisonNarrative(context, comparison) {
  const modifierLabel = context.modifierKind === 'capacity-reservation'
    ? 'Capacity Reservation'
    : context.modifierKind === 'preemptible'
      ? 'Preemptible'
      : 'Burstable';
  const assumptions = [
    `- Compared shapes: ${context.shapes.map((shape) => shape.toUpperCase()).join(', ')}.`,
    `- Size used for each shape: ${context.ocpus} OCPUs, ${context.memoryGb} GB RAM, ${context.hours} hours/month.`,
    `- Base side uses on-demand pricing.`,
  ];
  if (context.modifierKind === 'capacity-reservation') {
    assumptions.push(`- Non-capacity-reservation side uses ${context.withoutCrMode}.`);
    assumptions.push(`- Capacity reservation utilization: ${context.utilization}.`);
  }
  if (context.modifierKind === 'burstable') {
    assumptions.push(`- Burstable baseline: ${context.burstableBaseline}.`);
  }
  if (comparison.warnings?.length) {
    assumptions.push(...comparison.warnings.map((item) => `- ${item}`));
  }
  return [
    `I prepared a deterministic OCI Flex shape comparison for \`${context.shapes.map((shape) => shape.toUpperCase()).join(' vs ')}\`.`,
    `The comparison shows the monthly and annual totals with and without ${modifierLabel} for the same sizing.`,
    `Key assumptions:\n${assumptions.join('\n')}`,
    `### OCI comparison\n\n${comparison.markdown}`,
  ].join('\n\n');
}

function hasCompositeServiceSignal(text) {
  const source = String(text || '');
  return /\b(?:vm|bm)\.[a-z0-9.]+(?:\.flex|\.\d+)\b|\b(?:standard|optimized)\d+(?:\.\d+|\.flex)\b|\bdenseio\.[ea]\d+\.flex\b|\b[a-z]\d+\.flex\b|\bload balancer\b|\blb\b|\bblock storage\b|\bblock volumes?\b|\bobject storage\b|\bfile storage\b|\bfastconnect\b|\bfast connect\b|\bdns\b|\bapi gateway\b|\bweb application firewall\b|\bwaf\b|\bnetwork firewall\b|\bautonomous(?: ai)? lakehouse\b|\bautonomous data warehouse\b|\bbase database service\b|\bdata integration\b|\bintegration cloud\b|\boic\b|\banalytics cloud\b|\boac\b|\bdata safe\b|\blog analytics\b|\bfunctions\b|\bgenerative ai\b|\bvector store\b|\bweb search\b|\bagents data ingestion\b|\bmemory ingestion\b|\bexadata\b|\bdatabase cloud service\b|\bmonitoring\b|\bnotifications\b|\bhttps delivery\b|\bemail delivery\b|\biam sms\b|\bsms messages?\b|\bthreat intelligence\b|\bhealth checks?\b|\bfleet application management\b|\boci batch\b|\bvision\b|\bspeech\b|\bmedia flow\b/i.test(source);
}

function splitCompositeQuoteSegments(text) {
  const source = String(text || '').trim();
  const body = source.includes(':') ? source.slice(source.indexOf(':') + 1) : source;
  const rawSegments = body
    .split(/\s*(?:,|\+|\bplus\b)\s*/i)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => !/^\d+(?:\.\d+)?\s*h(?:ours?)?(?:\/month)?$/i.test(item))
    .filter((item) => !/^\d+(?:\.\d+)?\s*days?\/month$/i.test(item));

  const merged = [];
  for (const segment of rawSegments) {
    if (
      merged.length &&
      /^\b(?:active|archiv(?:e|al))\b/i.test(segment) &&
      /\blog analytics\b/i.test(merged[merged.length - 1])
    ) {
      merged.push(`Log Analytics ${segment}`.trim());
      continue;
    }
    if (!merged.length || hasCompositeServiceSignal(segment)) {
      merged.push(segment);
      continue;
    }
    merged[merged.length - 1] = `${merged[merged.length - 1]} ${segment}`.trim();
  }
  return merged;
}

function shouldAppendGlobalHours(segment) {
  const source = String(segment || '');
  return /\b(?:vm|bm)\.[a-z0-9.]+\.flex\b|\b[a-z]\d+\.flex\b|\bfunctions\b|\bfastconnect\b|\bfast connect\b|\bload balancer\b|\bfirewall\b|\bintegration cloud\b|\bworkspace usage\b|\bprocessed per hour\b|\bautonomous\b|\bexadata\b|\bdatabase cloud service\b/i.test(source);
}

function normalizeCompositeSegment(segment, fullText) {
  let out = String(segment || '').trim().replace(/^and\s+/i, '');
  out = out.replace(/^(?:quote\s+)?(?:a|an)\s+.+?\b(?:stack|platform|workload|architecture|bundle|fabric)\s+with\s+/i, '');
  const multipliedInstances = out.match(/^(\d+)\s*x\s+(.*)$/i);
  if (multipliedInstances) {
    out = `${multipliedInstances[2]} ${multipliedInstances[1]} instances`;
  }
  out = out.replace(/\bLB\b/i, 'Flexible Load Balancer');
  out = out.replace(/\bOIC\b\s+enterprise\b/i, 'Oracle Integration Cloud Enterprise');
  out = out.replace(/\bOIC\b\s+standard\b/i, 'Oracle Integration Cloud Standard');
  out = out.replace(/\bOAC\b\s+enterprise\b/i, 'Oracle Analytics Cloud Enterprise');
  out = out.replace(/\bOAC\b\s+professional\b/i, 'Oracle Analytics Cloud Professional');
  out = out.replace(/\bLI\b/i, 'License Included');
  if (/\bvector store retrieval\b/i.test(out) && !/\bgenerative ai\b/i.test(out)) {
    out = `OCI Generative AI ${out}`;
  } else if (/\bweb search\b/i.test(out) && !/\bgenerative ai\b/i.test(out)) {
    out = `OCI Generative AI ${out}`;
  } else if (/\bagents data ingestion\b/i.test(out) && !/\bgenerative ai\b/i.test(out)) {
    out = `OCI Generative AI ${out}`;
  } else if (/\bmemory ingestion\b/i.test(out) && !/\bgenerative ai\b/i.test(out)) {
    out = `OCI Generative AI ${out}`;
  }
  const globalHours = String(fullText || '').match(/(\d+(?:\.\d+)?)\s*h(?:ours?)?(?:\/month)?/i) ||
    String(fullText || '').match(/(\d+(?:\.\d+)?)\s*hours?\s*\/\s*month/i);
  if (globalHours && !/\b\d+(?:\.\d+)?\s*h(?:ours?)?(?:\/month)?\b/i.test(out) && shouldAppendGlobalHours(out)) {
    out = `${out} ${globalHours[1]}h/month`;
  }
  if (!/^quote\b/i.test(out)) out = `Quote ${out}`;
  return out.trim();
}

function buildCompositeQuoteFromSegments(index, text) {
  const segments = splitCompositeQuoteSegments(text);
  if (segments.length < 2) return null;
  const serviceSignalCount = segments.filter((segment) => hasCompositeServiceSignal(segment)).length;
  if (serviceSignalCount < 2) return null;

  const mergedLineItems = [];
  const warnings = [];
  const candidates = [];

  for (const segment of segments) {
    const prompt = normalizeCompositeSegment(segment, text);
    const quote = quoteSegmentWithCanonicalFallback(index, prompt);
    if (!quote.ok || !Array.isArray(quote.lineItems) || !quote.lineItems.length) {
      warnings.push(`Could not deterministically quote segment: ${segment}`);
      continue;
    }
    mergedLineItems.push(...quote.lineItems);
    if (Array.isArray(quote.warnings) && quote.warnings.length) warnings.push(...quote.warnings);
    candidates.push(...((quote.resolution?.candidates) || []));
  }

  if (mergedLineItems.length < 2) return null;

  const totals = mergedLineItems.reduce((acc, line) => {
    acc.monthly += Number(line.monthly || 0);
    acc.annual += Number(line.annual || 0);
    return acc;
  }, { monthly: 0, annual: 0, currencyCode: 'USD' });

  return {
    ok: true,
    request: { source: text },
    resolution: {
      type: 'workload',
      label: 'Composite OCI workload',
      candidates: candidates.filter(Boolean),
    },
    warnings: Array.from(new Set(warnings)),
    lineItems: mergedLineItems,
    totals,
    markdown: toMarkdownQuote(mergedLineItems, totals),
  };
}

function formatAssumptions(assumptions, parsedRequest) {
  const lines = [];
  const sourceAssumptions = Array.isArray(assumptions) ? assumptions.filter(Boolean) : [];
  for (const item of sourceAssumptions) {
    const text = String(item || '').trim();
    if (!text) continue;
    const lower = text.toLowerCase();
    if (!shouldKeepSourceAssumption(lower, parsedRequest)) continue;
    if (/\b(?:usage|hours?\/month|monthly usage|uptime)\b/.test(lower)) {
      const explicitHours = lower.match(/(\d+(?:\.\d+)?)\s*hours?\/month/);
      if (explicitHours && Number(explicitHours[1]) !== Number(parsedRequest.hours)) continue;
    }
    if (/\binstance count\b|\binstances?\b/.test(lower)) {
      const explicitInstances = lower.match(/(\d+(?:\.\d+)?)/);
      if (explicitInstances && Number(explicitInstances[1]) !== Number(parsedRequest.instances)) continue;
    }
    if (/\bcurrency\b/.test(lower) && !lower.includes(String(parsedRequest.currencyCode || '').toLowerCase())) {
      continue;
    }
    lines.push(`- ${text}`);
  }
  const normalizedAssumptions = sourceAssumptions.join(' ').toLowerCase();
  const mentionsUsageDefault = /\b(?:usage|hours?\/month|monthly usage|uptime)\b/.test(normalizedAssumptions);
  const mentionsInstanceDefault = /\binstance count\b|\binstances?\b/.test(normalizedAssumptions);
  const mentionsCurrencyDefault = /\bcurrency\b|\busd\b|\bmxn\b|\beur\b|\bbrl\b|\bgbp\b|\bcad\b|\bjpy\b/.test(normalizedAssumptions);
  if (!mentionsUsageDefault && !/\b\d+(?:\.\d+)?\s*h(?:ours?)?\b/i.test(parsedRequest.source || '')) {
    lines.push(`- Monthly usage defaulted to ${parsedRequest.hours} hours.`);
  }
  if (parsedRequest.annualRequested) {
    lines.push('- Annual total assumes 12 months of the quoted monthly usage.');
  }
  if (!mentionsInstanceDefault && !/\b\d+(?:\.\d+)?\s*(?:instances?|nodes?|vms?)\b/i.test(parsedRequest.source || '')) {
    lines.push(`- Instance count defaulted to ${parsedRequest.instances}.`);
  }
  if (!mentionsCurrencyDefault && !/\b(usd|mxn|eur|brl|gbp|cad|jpy)\b/i.test(parsedRequest.source || '')) {
    lines.push(`- Currency defaulted to ${parsedRequest.currencyCode}.`);
  }
  return Array.from(new Set(lines));
}

function shouldKeepSourceAssumption(lower, parsedRequest) {
  const source = String(parsedRequest?.source || '').toLowerCase();
  if (!lower) return false;
  if (/pasted image|extracted from the pasted image|sizing details were extracted from the pasted image|visible in the image/.test(lower)) {
    return true;
  }
  if (/\b(?:usage|hours?\/month|monthly usage|uptime)\b/.test(lower)) return true;
  if (/\binstance count\b|\binstances?\b/.test(lower)) return true;
  if (/\bcurrency\b/.test(lower)) return true;
  if (/\bbyol\b|\blicense included\b|\blicencia incluida\b/.test(lower)) {
    return /\bbyol\b|\blicense included\b|\blicencia incluida\b/.test(source);
  }
  if (/\bcapacity reservation\b|\bpreemptible\b|\bburstable\b/.test(lower)) {
    return /\bcapacity reservation\b|\bpreemptible\b|\bburstable\b/.test(source);
  }
  return false;
}

async function writeNaturalReply(cfg, conversation, userText, context, sessionContext) {
  const history = Array.isArray(conversation) ? conversation.slice(-6) : [];
  const sessionBlock = buildSessionContextBlock(sessionContext);
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

  const messages = [
    ...history.map((item) => ({
      role: item.role === 'assistant' ? 'assistant' : 'user',
      content: String(item.content || ''),
    })),
    { role: 'user', content: contextBlock },
  ];

  const response = await runChat({
    cfg,
    systemPrompt: RESPONSE_PROMPT,
    messages,
    maxTokens: 900,
    temperature: 0.35,
    topP: 0.7,
    topK: -1,
  });
  return extractChatText(response?.data || response).trim();
}

async function writeStructuredContextReply(cfg, conversation, userText, sessionContext, contextPack) {
  if (!cfg?.modelId || !cfg?.compartment) return '';
  const history = Array.isArray(conversation) ? conversation.slice(-6) : [];
  const sessionBlock = buildSessionContextBlock(sessionContext);
  const contextBlock = [
    sessionBlock,
    `User request: ${String(userText || '').trim()}`,
    `Structured product context:\n${stringifyContextPack(contextPack)}`,
  ].filter(Boolean).join('\n\n');

  const messages = [
    ...history.map((item) => ({
      role: item.role === 'assistant' ? 'assistant' : 'user',
      content: String(item.content || ''),
    })),
    { role: 'user', content: contextBlock },
  ];

  try {
    const response = await runChat({
      cfg,
      systemPrompt: STRUCTURED_DISCOVERY_PROMPT,
      messages,
      maxTokens: 700,
      temperature: 0.2,
      topP: 0.5,
      topK: -1,
    });
    return extractChatText(response?.data || response).trim();
  } catch {
    return '';
  }
}

function summarizeQuoteForSession(quote) {
  if (!quote?.ok) return null;
  if (quote.comparison) {
    return {
      type: 'comparison',
      label: 'Flex comparison',
      monthly: Number(quote.comparison.monthlyTotal || 0),
      annual: Number(quote.comparison.annualTotal || 0),
      currencyCode: quote.comparison.currencyCode || 'USD',
      lineItemCount: Array.isArray(quote.comparison.items) ? quote.comparison.items.length : 0,
    };
  }
  const lineItems = Array.isArray(quote.lineItems) ? quote.lineItems : [];
  const request = quote.request || {};
  return {
    type: 'quote',
    label: quote.resolution?.label || request.shape || request.serviceName || request.source || '',
    source: request.source || '',
    monthly: Number(quote.totals?.monthly || 0),
    annual: Number(quote.totals?.annual || 0),
    currencyCode: quote.totals?.currencyCode || 'USD',
    lineItemCount: lineItems.length,
    shapeName: request.shape || request.shapeSeries || '',
    serviceFamily: request.serviceFamily || '',
    processorVendor: request.processorVendor || '',
    vpuPerGb: Number.isFinite(Number(request.vpuPerGb)) ? Number(request.vpuPerGb) : null,
    partNumbers: Array.from(new Set(lineItems.map((line) => line.partNumber).filter(Boolean))).slice(0, 12),
  };
}

function buildQuoteExportPayload(quote) {
  if (!quote?.ok || !Array.isArray(quote.lineItems) || !quote.lineItems.length) return null;
  return {
    formatVersion: 1,
    generatedAt: new Date().toISOString(),
    totals: quote.totals || null,
    lineItems: quote.lineItems.map((line, index) => ({
      rowNumber: index + 1,
      environment: line.environment || '-',
      service: line.service || '-',
      partNumber: line.partNumber || '-',
      product: line.product || '-',
      metric: line.metric || '-',
      quantity: Number.isFinite(Number(line.quantity)) ? Number(line.quantity) : '',
      instances: Number.isFinite(Number(line.instances)) ? Number(line.instances) : '',
      hours: Number.isFinite(Number(line.hours)) ? Number(line.hours) : '',
      rate: Number.isFinite(Number(line.rate)) ? Number(line.rate) : '',
      unitPrice: Number.isFinite(Number(line.unitPrice)) ? Number(line.unitPrice) : '',
      monthly: Number.isFinite(Number(line.monthly)) ? Number(line.monthly) : '',
      annual: Number.isFinite(Number(line.annual)) ? Number(line.annual) : '',
      currencyCode: line.currencyCode || quote.totals?.currencyCode || 'USD',
    })),
  };
}

function buildAssistantSessionSummary(nextContext) {
  if (!nextContext || typeof nextContext !== 'object') return '';
  const lines = [];
  if (nextContext.workbookContext?.fileName) {
    const workbook = nextContext.workbookContext;
    let line = `Active workbook ${workbook.fileName}`;
    if (workbook.shapeName) line += ` using ${workbook.shapeName}`;
    if (Number.isFinite(Number(workbook.vpuPerGb))) line += ` with ${Number(workbook.vpuPerGb)} VPU`;
    lines.push(line);
  }
  if (nextContext.lastQuote?.label) {
    const quote = nextContext.lastQuote;
    let line = `Last quote ${quote.label}`;
    if (Number.isFinite(Number(quote.monthly))) line += ` monthly ${formatMoney(Number(quote.monthly), quote.currencyCode || 'USD')}`;
    if (Number.isFinite(Number(quote.lineItemCount))) line += ` across ${Number(quote.lineItemCount)} lines`;
    lines.push(line);
  }
  if (nextContext.pendingClarification?.question) {
    lines.push(`Pending clarification: ${nextContext.pendingClarification.question}`);
  }
  if (nextContext.lastIntent?.route) {
    lines.push(`Last route ${nextContext.lastIntent.route}`);
  }
  return lines.join('. ');
}

function buildAssistantSessionContext(previous, effectiveUserText, payload) {
  const next = previous && typeof previous === 'object' ? JSON.parse(JSON.stringify(previous)) : {};
  next.lastUserText = String(effectiveUserText || '').trim();
  if (payload?.intent?.intent) next.currentIntent = payload.intent.intent;
  if (payload?.intent && typeof payload.intent === 'object') {
    next.lastIntent = {
      intent: payload.intent.intent || '',
      route: payload.intent.route || '',
      serviceFamily: payload.intent.serviceFamily || '',
      serviceName: payload.intent.serviceName || '',
      confidence: Number.isFinite(Number(payload.intent.confidence)) ? Number(payload.intent.confidence) : null,
      quotePlan: payload.intent.quotePlan && typeof payload.intent.quotePlan === 'object'
        ? JSON.parse(JSON.stringify(payload.intent.quotePlan))
        : null,
    };
  }
  if (payload?.contextPackSummary) {
    next.lastContextPack = JSON.parse(JSON.stringify(payload.contextPackSummary));
  }
  if (payload?.mode === 'clarification' && payload?.message) {
    next.pendingClarification = {
      question: String(payload.message).trim(),
      serviceFamily: payload.intent?.serviceFamily || '',
    };
  } else {
    delete next.pendingClarification;
  }
  if (payload?.quote?.ok) {
    next.lastQuote = summarizeQuoteForSession(payload.quote);
    next.quoteExport = buildQuoteExportPayload(payload.quote);
  }
  next.sessionSummary = buildAssistantSessionSummary(next);
  return next;
}

async function buildGenAIQuoteEnrichment(cfg, userText, quote, assumptions) {
  if (!cfg?.ok || !quote?.ok) return '';
  const lineItems = Array.isArray(quote.lineItems) ? quote.lineItems : [];
  if (!lineItems.length) return '';
  const request = quote.request || {};
  const totals = quote.totals || {};
  const technologyProfile = inferQuoteTechnologyProfile(quote);
  const allowMigrationNotes = request?.metadata?.inventorySource === 'rvtools' || /\bvmware\b|\brvtools\b/i.test(String(userText || ''));
  const contextBlock = [
    `User request: ${String(userText || '').trim()}`,
    `Expert role: ${technologyProfile.role}`,
    `Technology profile: ${technologyProfile.name}`,
    `OCI expert focus: ${technologyProfile.focus}`,
    `Matched label: ${quote.resolution?.label || 'n/a'}`,
    `Monthly total: ${formatMoney(totals.monthly, totals.currencyCode || 'USD')}`,
    `Annual total: ${formatMoney(totals.annual, totals.currencyCode || 'USD')}`,
    assumptions.length ? `Assumptions:\n${assumptions.join('\n')}` : '',
    quote.warnings?.length ? `Warnings:\n${quote.warnings.map((item) => `- ${item}`).join('\n')}` : '',
    `Line items:\n${lineItems.slice(0, 12).map((line) => `- ${line.service || '-'} | ${line.product} | ${line.metric || '-'} | qty ${fmt(line.quantity)} | monthly ${money(line.monthly)}`).join('\n')}`,
    request?.metadata?.inventorySource ? `Inventory source: ${request.metadata.inventorySource}` : '',
    request?.metadata?.vmwareVcpus ? `VMware vCPUs in source request: ${request.metadata.vmwareVcpus}` : '',
  ].filter(Boolean).join('\n\n');

  try {
    const response = await runChat({
      cfg,
      systemPrompt: QUOTE_ENRICHMENT_PROMPT,
      messages: [{ role: 'user', content: contextBlock }],
      maxTokens: 350,
      temperature: 0.2,
      topP: 0.6,
      topK: -1,
    });
    return sanitizeQuoteEnrichment(extractChatText(response?.data || response).trim(), { allowMigrationNotes });
  } catch (_error) {
    return '';
  }
}

function sanitizeQuoteEnrichment(text, options = {}) {
  const source = String(text || '').trim();
  if (!source) return '';
  const allowMigrationNotes = options.allowMigrationNotes !== false;
  const lines = source.split('\n');
  const kept = [];
  let activeSection = '';
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (kept.length && kept[kept.length - 1] !== '') kept.push('');
      continue;
    }
    if (/^#{1,6}\s+/i.test(trimmed)) {
      if (/migration notes/i.test(trimmed)) {
        if (!allowMigrationNotes) {
          activeSection = '';
          continue;
        }
        activeSection = 'migration';
        kept.push('## Migration Notes');
      } else if (/oci considerations/i.test(trimmed)) {
        activeSection = 'considerations';
        kept.push('## OCI Considerations');
      } else {
        activeSection = '';
      }
      continue;
    }
    if (!activeSection) continue;
    if (/\$|monthly total|annual total|breakdown of costs|costs are calculated|potential miscalculation|discrepanc/i.test(trimmed)) continue;
    if (/\b=\b/.test(trimmed) && /\d/.test(trimmed)) continue;
    kept.push(line);
  }
  return kept.join('\n').trim();
}

function inferQuoteTechnologyProfile(quote) {
  const request = quote?.request || {};
  const lineItems = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const blob = [
    request?.source || '',
    request?.serviceFamily || '',
    request?.metadata?.inventorySource || '',
    ...lineItems.map((line) => `${line.service || ''} ${line.product || ''} ${line.metric || ''}`),
  ].join('\n').toLowerCase();

  if (request?.metadata?.inventorySource === 'rvtools' || /\bvmware\b|\brvtools\b/.test(blob)) {
    return {
      key: 'vmware-migration',
      role: 'OCI VMware migration specialist',
      name: 'VMware migration to OCI',
      focus: 'right-sizing, VMware vCPU to OCI OCPU normalization, exclusion of platform VMs, and follow-up items such as Windows licensing',
    };
  }
  const storageSignalCount = [
    /\bfile storage\b/.test(blob),
    /\bobject storage\b/.test(blob),
    /\bblock volume\b/.test(blob),
  ].filter(Boolean).length;
  const edgeSignalCount = [
    /\bdns\b/.test(blob),
    /\bload balancer\b/.test(blob),
    /\bfastconnect\b/.test(blob),
    /\bnetwork firewall\b/.test(blob),
    /\bwaf\b|\bweb application firewall\b/.test(blob),
  ].filter(Boolean).length;

  const scoreMonthly = (patterns) => lineItems.reduce((sum, line) => {
    const lineBlob = `${line.service || ''} ${line.product || ''} ${line.metric || ''}`.toLowerCase();
    if (patterns.some((pattern) => pattern.test(lineBlob))) return sum + Number(line.monthly || 0);
    return sum;
  }, 0);

  const networkPatterns = [/\bfastconnect\b/, /\bload balancer\b/, /\bdns\b/, /\bnetwork firewall\b/, /\bwaf\b|\bweb application firewall\b/];
  const databasePatterns = [/\bautonomous\b/, /\bdatabase\b/, /\bexadata\b/, /\bdata safe\b/];
  const serverlessAiPatterns = [/\bfunctions\b/, /\bgenerative ai\b/, /\bvector store\b/, /\bweb search\b/, /\bagents\b/, /\bapi gateway\b/];
  const analyticsPatterns = [/\bintegration cloud\b/, /\banalytics cloud\b/, /\bdata integration\b/];
  const observabilityPatterns = [/\bmonitoring\b/, /\blog analytics\b/, /\bnotifications\b/, /\bhealth checks\b/];
  const operationsPatterns = [/\bfleet application management\b/, /\boci batch\b/, /\bbatch\b/, /\bemail delivery\b/, /\biam sms\b/];
  const computeStoragePatterns = [/\bcompute\b/, /\bflex\b/, /\bocpu\b/, /\bram\b/, /\bblock volume\b/, /\bobject storage\b/, /\bfile storage\b/];

  const databaseMonthly = scoreMonthly(databasePatterns);
  const networkMonthly = scoreMonthly(networkPatterns);
  const serverlessAiMonthly = scoreMonthly(serverlessAiPatterns);
  const analyticsMonthly = scoreMonthly(analyticsPatterns);
  const observabilityMonthly = scoreMonthly(observabilityPatterns);
  const operationsMonthly = scoreMonthly(operationsPatterns);
  const computeStorageMonthly = scoreMonthly(computeStoragePatterns);
  const totalMonthly = lineItems.reduce((sum, line) => sum + Number(line.monthly || 0), 0) || 0;
  const maxDomainShare = totalMonthly > 0
    ? Math.max(
      networkMonthly,
      databaseMonthly,
      serverlessAiMonthly,
      analyticsMonthly,
      observabilityMonthly + operationsMonthly,
      computeStorageMonthly,
    ) / totalMonthly
    : 0;
  const domainScores = [
    networkMonthly,
    databaseMonthly,
    serverlessAiMonthly,
    analyticsMonthly,
    observabilityMonthly + operationsMonthly,
    computeStorageMonthly,
  ];
  const signalDomainCount = [
    networkPatterns.some((pattern) => pattern.test(blob)),
    databasePatterns.some((pattern) => pattern.test(blob)),
    serverlessAiPatterns.some((pattern) => pattern.test(blob)),
    analyticsPatterns.some((pattern) => pattern.test(blob)),
    observabilityPatterns.some((pattern) => pattern.test(blob)),
    operationsPatterns.some((pattern) => pattern.test(blob)),
    computeStoragePatterns.some((pattern) => pattern.test(blob)),
  ].filter(Boolean).length;

  const hasAnalyticsSignals = analyticsPatterns.filter((pattern) => pattern.test(blob)).length >= 2;
  const hasDatabaseSignals = databasePatterns.some((pattern) => pattern.test(blob));
  const hasObservabilitySignals = observabilityPatterns.filter((pattern) => pattern.test(blob)).length >= 2;
  const hasOperationsSignals = operationsPatterns.filter((pattern) => pattern.test(blob)).length >= 2;

  if (signalDomainCount >= 5 && maxDomainShare <= 0.75) {
    return {
      key: 'solutions-architecture',
      role: 'OCI solutions architect',
      name: 'OCI multi-service architecture',
      focus: 'cross-domain cost drivers across compute, storage, networking, database, observability, and platform services, plus which components are foundational versus workload-specific',
    };
  }

  if (hasDatabaseSignals && totalMonthly > 0 && databaseMonthly / totalMonthly >= 0.35) {
    return {
      key: 'database',
      role: 'OCI database architect',
      name: 'OCI database platform',
      focus: 'license model, compute plus storage composition, and prerequisites or infrastructure components that may sit outside the direct metered lines',
    };
  }
  if (hasObservabilitySignals && totalMonthly > 0 && observabilityMonthly / totalMonthly >= 0.2 && operationsMonthly / totalMonthly < 0.15) {
    return {
      key: 'observability',
      role: 'OCI observability architect',
      name: 'OCI observability and notifications',
      focus: 'ingestion, retrieval, storage-unit, and delivery-operation metrics across monitoring, log analytics, and notifications',
    };
  }
  if (hasOperationsSignals && totalMonthly > 0 && (operationsMonthly / totalMonthly >= 0.15 || (observabilityMonthly + operationsMonthly) / totalMonthly >= 0.3)) {
    return {
      key: 'operations-platform',
      role: 'OCI operations and platform services architect',
      name: 'OCI operations and platform services',
      focus: 'counted operational units, observability storage and retrieval metrics, and which lines are free-tier versus usage-bearing',
    };
  }
  if (hasAnalyticsSignals && totalMonthly > 0 && analyticsMonthly / totalMonthly >= 0.25) {
    return {
      key: 'analytics-integration',
      role: 'OCI analytics and integration architect',
      name: 'OCI analytics and integration services',
      focus: 'user, OCPU/ECPU, data processed, and storage-unit metrics, plus BYOL versus License Included where applicable',
    };
  }
  if (storageSignalCount >= 2 && edgeSignalCount <= 2) {
    return {
      key: 'compute-storage',
      role: 'OCI compute and storage architect',
      name: 'OCI compute and storage platform',
      focus: 'shape selection, OCPU and memory sizing, attached storage assumptions, and whether usage is capacity-driven or hourly',
    };
  }
  const profiles = [
    {
      key: 'network-security',
      role: 'OCI networking and security architect',
      name: 'OCI networking and edge security',
      focus: 'port-hour, bandwidth, request, and processed-data dimensions, plus which components are fixed versus usage-driven',
      patterns: [/\bfastconnect\b/, /\bload balancer\b/, /\bdns\b/, /\bnetwork firewall\b/, /\bwaf\b|\bweb application firewall\b/],
    },
    {
      key: 'database',
      role: 'OCI database architect',
      name: 'OCI database platform',
      focus: 'license model, compute plus storage composition, and prerequisites or infrastructure components that may sit outside the direct metered lines',
      patterns: [/\bautonomous\b/, /\bdatabase\b/, /\bexadata\b/, /\bdata safe\b/],
    },
    {
      key: 'serverless-ai',
      role: 'OCI serverless and AI architect',
      name: 'OCI serverless and AI services',
      focus: 'request volume, execution sizing, token or transaction metrics, and when a service is dedicated versus serverless',
      patterns: [/\bfunctions\b/, /\bgenerative ai\b/, /\bvector store\b/, /\bweb search\b/, /\bagents\b/],
    },
    {
      key: 'operations-platform',
      role: 'OCI operations and platform services architect',
      name: 'OCI operations and platform services',
      focus: 'counted operational units such as jobs, managed resources, and delivery volumes, plus which lines are free-tier versus usage-bearing',
      patterns: [/\bfleet application management\b/, /\boci batch\b/, /\bbatch\b/, /\bemail delivery\b/],
    },
    {
      key: 'observability',
      role: 'OCI observability architect',
      name: 'OCI observability and notifications',
      focus: 'ingestion, retrieval, storage-unit, and delivery-operation metrics across monitoring, log analytics, and notifications',
      patterns: [/\bmonitoring\b/, /\blog analytics\b/, /\bnotifications\b/, /\bhealth checks\b/],
    },
    {
      key: 'analytics-integration',
      role: 'OCI analytics and integration architect',
      name: 'OCI analytics and integration services',
      focus: 'user, OCPU/ECPU, data processed, and storage-unit metrics, plus BYOL versus License Included where applicable',
      patterns: [/\bintegration cloud\b/, /\banalytics cloud\b/, /\bdata integration\b/],
    },
    {
      key: 'ai-media',
      role: 'OCI AI and media services architect',
      name: 'OCI AI and media services',
      focus: 'training-hour, transcription-hour, and processed-minute metrics across OCI AI and media pipelines',
      patterns: [/\bvision\b/, /\bspeech\b/, /\bmedia flow\b/, /\bprocessed video\b/],
    },
    {
      key: 'compute-storage',
      role: 'OCI compute and storage architect',
      name: 'OCI compute and storage platform',
      focus: 'shape selection, OCPU and memory sizing, attached storage assumptions, and whether usage is capacity-driven or hourly',
      patterns: [/\bcompute\b/, /\bflex\b/, /\bocpu\b/, /\bram\b/, /\bblock volume\b/, /\bobject storage\b/, /\bfile storage\b/],
    },
  ];
  const scored = profiles
    .map((profile) => ({
      profile,
      score: profile.patterns.reduce((sum, pattern) => sum + (pattern.test(blob) ? 1 : 0), 0),
    }))
    .sort((a, b) => b.score - a.score);
  if (scored[0]?.score > 0) return scored[0].profile;
  return {
    key: 'general',
    role: 'OCI pricing specialist',
    name: 'General OCI pricing',
    focus: 'the main billable dimensions, assumptions, and follow-up checks that a customer should validate before taking the estimate as final',
  };
}

function buildDeterministicExpertSummary(quote) {
  const profile = inferQuoteTechnologyProfile(quote);
  const totals = quote?.totals || {};
  const currencyCode = totals.currencyCode || 'USD';
  const lineItems = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const topDrivers = [...lineItems]
    .sort((a, b) => Number(b.monthly || 0) - Number(a.monthly || 0))
    .slice(0, 3);
  const sections = [];

  sections.push('## OCI Expert Summary');
  sections.push(`- Perspective: **${profile.role}**.`);
  sections.push(`- This estimate is centered on **${profile.name}** pricing.`);
  sections.push(`- Monthly total: ${formatMoney(totals.monthly, currencyCode)}. Annual total: ${formatMoney(totals.annual, currencyCode)}.`);
  sections.push(`- The quote contains ${lineItems.length} priced line${lineItems.length === 1 ? '' : 's'} derived from the OCI catalog and deterministic pricing rules.`);
  if (topDrivers.length) {
    sections.push(`- Main cost drivers: ${topDrivers.map((line) => `\`${line.partNumber}\` (${line.product}) = ${formatMoney(line.monthly, currencyCode)}/month`).join('; ')}.`);
  }

  return sections.join('\n');
}

function buildDeterministicConsiderationsFallback(quote, assumptions) {
  const profile = inferQuoteTechnologyProfile(quote);
  const lineItems = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const sections = [];

  sections.push('## OCI Considerations');
  if (profile.key === 'vmware-migration') {
    sections.push('- Validate that non-migrated VMware platform VMs stay excluded from the target scope.');
    sections.push('- Review Windows workloads separately because OCI infrastructure pricing does not automatically include Microsoft licensing adjustments in this pass.');
  } else if (profile.key === 'network-security') {
    sections.push('- As an OCI networking/security review, validate throughput assumptions, request volumes, and whether the edge controls shown here align with the intended ingress and egress paths.');
    sections.push('- Review which lines are fixed monthly components versus variable traffic or request-driven charges.');
    sections.push('- Confirm whether the quoted edge/security services match the intended throughput and request profile.');
  } else if (profile.key === 'database') {
    sections.push('- As an OCI database review, validate the service architecture first: Base DB, Autonomous, and Exadata families have materially different operational and licensing behavior.');
    sections.push('- Confirm the intended license model before taking the quote as final if the family supports BYOL and License Included variants.');
    sections.push('- Review whether any deployment or infrastructure prerequisites sit outside the direct metered lines shown here.');
  } else if (profile.key === 'serverless-ai') {
    sections.push('- As an OCI serverless/AI review, validate whether the service is genuinely usage-driven or whether Oracle exposes it as a dedicated hourly construct in the live catalog.');
    sections.push('- Validate request volume and execution sizing because those two dimensions usually dominate the monthly result.');
    sections.push('- For dedicated AI services, confirm whether the catalog exposes the service as usage-based or hour-based before assuming a transactional quote.');
  } else if (profile.key === 'operations-platform') {
    sections.push('- As an OCI operations/platform services review, validate which lines are truly paid units versus free-tier operational counts.');
    sections.push('- Review whether the quoted counts match the intended managed-resource, job, or notification-delivery volumes for the target operating model.');
  } else if (profile.key === 'solutions-architecture') {
    sections.push('- As an OCI solutions-architecture review, validate the service boundaries first: this quote spans multiple OCI domains and should be checked as an integrated platform, not as a single-service estimate.');
    sections.push('- Review which lines are foundational platform components versus workload-specific consumption, because those categories usually drive optimization decisions differently.');
    sections.push('- Confirm the intended commercial model for each major domain, especially where user-based, request-based, and infrastructure-based pricing are mixed together.');
  } else if (profile.key === 'analytics-integration') {
    sections.push('- As an OCI analytics/integration review, verify which commercial unit actually applies: users, OCPUs/ECPUs, processed data, or storage units.');
    sections.push('- Confirm whether the service is billed by users, OCPUs/ECPUs, storage units, or data processed, because different variants in the same family bill differently.');
    sections.push('- Review BYOL versus License Included where the selected product family supports both modes.');
  } else if (profile.key === 'compute-storage') {
    sections.push('- As an OCI compute/storage review, validate shape family, OCPU-to-memory ratio, and whether block or object storage should be sized from provisioned capacity or observed consumption.');
    sections.push('- Review whether attached storage should remain block-based or whether file or object storage would better match the workload pattern.');
  } else {
    sections.push(`- Main OCI expert focus for this estimate: ${profile.focus}.`);
    if (assumptions.length) sections.push('- Validate the sizing assumptions before treating the quote as final.');
  }

  return sections.join('\n');
}

function formatMoney(value, currencyCode = 'USD') {
  const num = Number(value);
  if (!Number.isFinite(num)) return `${currencyCode} -`;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currencyCode,
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(num);
}

async function buildQuoteNarrative(cfg, userText, quote, assumptions) {
  const matched = quote.resolution?.label || 'the requested OCI product';
  const totals = quote.totals || {};
  const request = quote.request || {};
  const lineCount = Array.isArray(quote.lineItems) ? quote.lineItems.length : 0;
  const currencyCode = totals.currencyCode || 'USD';
  const totalSentence = request.annualRequested
    ? `The estimate includes ${lineCount} priced line${lineCount === 1 ? '' : 's'} and the calculated annual total is **${formatMoney(totals.annual, currencyCode)}**.`
    : `The estimate includes ${lineCount} priced line${lineCount === 1 ? '' : 's'} and the calculated monthly total is **${formatMoney(totals.monthly, currencyCode)}**.`;
  const parts = [
    `I prepared a deterministic OCI quotation for \`${matched}\`.`,
    totalSentence,
  ];
  if (assumptions.length) {
    parts.push(`Key assumptions:\n${assumptions.join('\n')}`);
  }
  parts.push(buildDeterministicExpertSummary(quote));
  const enrichment = await buildGenAIQuoteEnrichment(cfg, userText, quote, assumptions);
  parts.push(enrichment || buildDeterministicConsiderationsFallback(quote, assumptions));
  const explanation = buildConsumptionExplanation(quote);
  if (explanation.length) {
    parts.push(`How OCI measures this:\n${explanation.join('\n')}`);
  }
  parts.push(`### OCI quotation\n\n${quote.markdown}`);
  if (quote.warnings?.length) {
    parts.push(`Warnings:\n${quote.warnings.map((item) => `- ${item}`).join('\n')}`);
  }
  return parts.join('\n\n');
}

function buildConsumptionExplanation(quote) {
  const items = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const patternEntries = [];
  const seenPatterns = new Set();
  for (const line of items) {
    const pattern = inferConsumptionPattern(line.metric, `${line.service} ${line.product}`);
    if (!pattern || pattern === 'unknown' || seenPatterns.has(pattern)) continue;
    seenPatterns.add(pattern);
    patternEntries.push({ pattern, line });
  }

  if (patternEntries.length <= 3 && items.length <= 6) {
    return patternEntries.map(({ pattern, line }) => {
      const text = explainConsumptionPattern(pattern, {
        displayName: line.product,
        fullDisplayName: line.product,
      });
      return text ? `- ${text}` : null;
    }).filter(Boolean);
  }

  const grouped = new Map();
  for (const line of items) {
    const pattern = inferConsumptionPattern(line.metric, `${line.service} ${line.product}`);
    const group = classifyConsumptionGroup(pattern, line);
    if (!grouped.has(group.key)) grouped.set(group.key, { ...group, examples: [], patterns: new Set() });
    const bucket = grouped.get(group.key);
    bucket.patterns.add(pattern);
    if (bucket.examples.length < 3) bucket.examples.push(line.product);
  }

  const priority = ['compute', 'storage', 'requests', 'users', 'platform', 'media', 'network', 'other'];
  return Array.from(grouped.values())
    .sort((a, b) => priority.indexOf(a.key) - priority.indexOf(b.key))
    .slice(0, 5)
    .map((group) => {
      const examples = Array.from(new Set(group.examples)).slice(0, 2).map((item) => `\`${item}\``).join(', ');
      return `- ${group.description}${examples ? ` Example lines: ${examples}.` : ''}`;
    });
}

function classifyConsumptionGroup(pattern, line) {
  const serviceBlob = `${line?.service || ''} ${line?.product || ''}`.toLowerCase();
  if (['ocpu-hour', 'ecpu-hour', 'memory-gb-hour', 'functions-gb-memory-seconds', 'functions-invocations-million'].includes(pattern)) {
    return {
      key: 'compute',
      description: 'Compute-style charges are driven by provisioned CPU, memory, or execution usage over time. For hourly SKUs the requested size is multiplied by monthly hours; for serverless functions OCI separately charges execution memory-seconds and invocation volume.',
    };
  }
  if (['capacity-gb-month', 'performance-units-per-gb-month', 'log-analytics-storage-unit-month'].includes(pattern)) {
    return {
      key: 'storage',
      description: 'Storage-style charges are driven by provisioned or retained capacity. OCI bills GB-month, performance density, or storage-unit constructs depending on the storage service.',
    };
  }
  if (['requests', 'count-each', 'data-processed-gb-month', 'data-processed-gb-hour'].includes(pattern)) {
    return {
      key: 'requests',
      description: 'Transaction and request charges are volume-based. The agent converts API calls, requests, processed traffic, deliveries, or counted items into the billing unit defined by each SKU.',
    };
  }
  if (pattern === 'users-per-month') {
    return {
      key: 'users',
      description: 'User-based charges are billed directly from the active user count per month rather than from hourly uptime.',
    };
  }
  if (['workspace-hour', 'execution-hour-utilized', 'generic-hourly', 'generic-monthly', 'utilized-hour'].includes(pattern)) {
    return {
      key: 'platform',
      description: 'Platform-service charges use service-specific hourly or monthly units such as workspaces, execution hours, or dedicated service hours, depending on the SKU metric.',
    };
  }
  if (pattern === 'media-output-minute') {
    return {
      key: 'media',
      description: 'Media and AI pipeline charges are billed from directly consumed training hours, transcription hours, or processed/output media minutes.',
    };
  }
  if (['port-hour', 'load-balancer-hour', 'bandwidth-mbps-hour'].includes(pattern) || /\bfastconnect\b|\bload balancer\b|\bdns\b|\bhealth checks?\b/.test(serviceBlob)) {
    return {
      key: 'network',
      description: 'Network charges are driven by provisioned connectivity, bandwidth configuration, or request/query volume depending on the service.',
    };
  }
  return {
    key: 'other',
    description: 'Some lines use OCI service-specific billing units that are quoted directly from the catalog metric attached to the SKU.',
  };
}

function detectGenericComputeShapeClarification(text) {
  const source = String(text || '');
  const parsed = parsePromptRequest(source);
  const hasVmSignal = /\bvirtual machine\b|\bcompute instance\b|\bvm\b/i.test(source) || !!parsed.processorVendor;
  const hasSizing = Number(parsed.ocpus || 0) > 0 && Number(parsed.memoryQuantity || 0) > 0;
  const missingShape = !parsed.shapeSeries && !parsed.shape;
  if (!hasVmSignal || !hasSizing || !missingShape) return null;
  return {
    serviceFamily: 'compute_vm_generic',
    extractedInputs: {
      ocpus: parsed.ocpus,
      memoryGb: parsed.memoryQuantity,
      capacityGb: parsed.capacityGb,
      processorVendor: parsed.processorVendor,
    },
    question: getClarificationMessage({
      serviceFamily: 'compute_vm_generic',
      extractedInputs: { processorVendor: parsed.processorVendor },
    }),
  };
}

function hasExplicitByolChoice(text) {
  const source = String(text || '');
  if (/\bbyol\b|\bbring your own license\b/i.test(source)) return 'byol';
  if (/\blicense included\b|\binclude license\b|\bcon licencia incluida\b|\blicencia incluida\b/i.test(source)) return 'license-included';
  return '';
}

function normalizeByolKey(text) {
  return String(text || '')
    .replace(/^B\d+\s*-\s*/i, '')
    .replace(/\s*-\s*BYOL\b/ig, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function shouldAskLicenseChoice(familyMeta, intent, byolChoice) {
  if (!familyMeta?.requireLicenseChoice || byolChoice) return false;
  const inputs = intent?.extractedInputs || {};
  const skipKeys = Array.isArray(familyMeta.licenseNotRequiredWhenAnyInputs)
    ? familyMeta.licenseNotRequiredWhenAnyInputs
    : [];
  if (skipKeys.some((key) => {
    const value = inputs[key];
    if (typeof value === 'string') return value.trim().length > 0;
    return Number.isFinite(Number(value)) && Number(value) > 0;
  })) {
    return false;
  }
  return true;
}

function detectByolAmbiguity(quote) {
  const lineItems = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const groups = new Map();
  for (const line of lineItems) {
    const product = String(line.product || '');
    const isByol = /\bBYOL\b/i.test(product);
    const key = `${line.service || ''}|${line.metric || ''}|${normalizeByolKey(product)}`;
    if (!groups.has(key)) groups.set(key, { byol: false, included: false, sample: product });
    const entry = groups.get(key);
    if (isByol) entry.byol = true;
    else entry.included = true;
  }
  for (const entry of groups.values()) {
    if (entry.byol && entry.included) return entry.sample;
  }
  return '';
}

function filterQuoteByByolChoice(quote, choice) {
  if (!quote?.ok || !choice) return quote;
  const selected = String(choice).toLowerCase();
  const lineItems = Array.isArray(quote.lineItems) ? quote.lineItems : [];
  const filtered = lineItems.filter((line) => {
    const product = String(line.product || '');
    const isByol = /\bBYOL\b/i.test(product);
    if (!/\bBYOL\b/i.test(product) && !lineItems.some((other) => normalizeByolKey(other.product) === normalizeByolKey(product) && /\bBYOL\b/i.test(other.product))) {
      return true;
    }
    return selected === 'byol' ? isByol : !isByol;
  });
  if (!filtered.length) return quote;
  const totals = filtered.reduce((acc, line) => {
    acc.monthly += Number(line.monthly || 0);
    acc.annual += Number(line.annual || 0);
    return acc;
  }, { monthly: 0, annual: 0, currencyCode: quote.totals?.currencyCode || 'USD' });
  return {
    ...quote,
    lineItems: filtered,
    totals,
    markdown: toMarkdownQuote(filtered, totals),
  };
}

function toMarkdownQuote(lineItems, totals) {
  const header = '| # | Environment | Service | Part# | Product | Metric | Qty | Inst | Hours | Rate | Unit | $/Mo | Annual |\n|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|';
  const body = (lineItems || []).map((line, index) => `| ${[
    index + 1,
    line.environment,
    line.service || '-',
    line.partNumber,
    line.product,
    line.metric || '-',
    fmt(line.quantity),
    fmt(line.instances),
    fmt(line.hours),
    fmt(line.rate),
    money(line.unitPrice),
    money(line.monthly),
    money(line.annual),
  ].join(' | ')} |`).join('\n');
  const total = `| Total | - | - | - | - | - | - | - | - | - | - | ${money(totals.monthly)} | ${money(totals.annual)} |`;
  return `${header}\n${body}\n${total}`;
}

function fmt(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value ?? '-');
  return Number.isInteger(num) ? String(num) : String(Number(num.toFixed(4)));
}

function money(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '$-';
  return `$${Number(num.toFixed(4))}`;
}

function choosePreferredQuote(primary, secondary) {
  if (primary?.ok && !secondary?.ok) return primary;
  if (secondary?.ok && !primary?.ok) return secondary;
  if (!primary?.ok && !secondary?.ok) return primary || secondary || null;
  const primaryLines = Array.isArray(primary?.lineItems) ? primary.lineItems.length : 0;
  const secondaryLines = Array.isArray(secondary?.lineItems) ? secondary.lineItems.length : 0;
  if (primaryLines !== secondaryLines) return primaryLines > secondaryLines ? primary : secondary;
  const primaryMonthly = Number(primary?.totals?.monthly || 0);
  const secondaryMonthly = Number(secondary?.totals?.monthly || 0);
  if (primaryMonthly !== secondaryMonthly) return primaryMonthly > secondaryMonthly ? primary : secondary;
  return secondary || primary;
}

function quoteSegmentWithCanonicalFallback(index, prompt) {
  const direct = quoteFromPrompt(index, prompt);
  const parsed = parsePromptRequest(prompt);
  const familyMeta = parsed?.serviceFamily ? getServiceFamily(parsed.serviceFamily) : null;
  if (!familyMeta) return direct;
  const canonical = String(buildCanonicalRequest({
    serviceFamily: parsed.serviceFamily,
    extractedInputs: parsed,
    normalizedRequest: prompt,
    reformulatedRequest: prompt,
  }, prompt) || '').trim();
  if (!canonical || canonical === prompt) return direct;
  const canonicalQuote = quoteFromPrompt(index, canonical);
  return choosePreferredQuote(direct, canonicalQuote);
}

async function respondToAssistant({ cfg, index, conversation, userText, imageDataUrl, sessionContext }) {
  const effectiveUserText = mergeSessionQuoteFollowUp(
    sessionContext,
    mergeClarificationAnswer(conversation, userText),
  );
  const respond = (payload) => ({
    ...payload,
    sessionContext: buildAssistantSessionContext(sessionContext, effectiveUserText, payload),
  });
  const contextualFollowUp = isShortContextualAnswer(userText);
  const compositeLike = isCompositeOrComparisonRequest(effectiveUserText);
  const flexComparison = extractFlexComparisonContext(conversation, userText);
  const computeShapeClarification = detectGenericComputeShapeClarification(effectiveUserText);
  if (isGreeting(userText)) {
    return respond({
      ok: true,
      mode: 'answer',
      message: 'Hola. Puedo ayudarte a cotizar servicios de OCI, comparar SKUs, explicar pricing o estimar un Excel. Si quieres una cotización directa, dime el producto y las variables clave como cantidad, horas, OCPU/ECPU, storage o bandwidth.',
      intent: { intent: 'answer', shouldQuote: false, needsClarification: false },
    });
  }

  if (conversationMentionsFastConnect(conversation) && isConfidenceQuestion(userText)) {
    return respond({
      ok: true,
      mode: 'answer',
      message: 'Sí para el cargo base del puerto. En OCI, el precio de FastConnect para el puerto es uniforme entre regiones, así que la región no cambia esa cotización base. Si quieres, puedo ayudarte a revisar además otros cargos relacionados, como conectividad adicional o tráfico de salida, pero el puerto de 1 Gbps sigue siendo el mismo.',
      intent: { intent: 'answer', shouldQuote: false, needsClarification: false },
    });
  }

  const explicitRegion = parseRegionAnswer(userText);
  if (conversationMentionsFastConnect(conversation) && explicitRegion) {
    return respond({
      ok: true,
      mode: 'answer',
      message: `${explicitRegion.label} es una región válida de OCI (${explicitRegion.code}). Para FastConnect, el precio base del puerto no cambia por región, así que la cotización del puerto se mantiene. Si quieres, el siguiente paso es revisar si en tu caso hay cargos adicionales asociados al diseño de conectividad.`,
      intent: { intent: 'answer', shouldQuote: false, needsClarification: false },
    });
  }

  if (computeShapeClarification) {
    return respond({
      ok: true,
      mode: 'clarification',
      message: computeShapeClarification.question,
      intent: {
        intent: 'quote',
        shouldQuote: true,
        needsClarification: true,
        clarificationQuestion: computeShapeClarification.question,
        serviceFamily: computeShapeClarification.serviceFamily,
        extractedInputs: computeShapeClarification.extractedInputs,
      },
    });
  }

  if (isFlexComparisonRequest(effectiveUserText)) {
    const modifierKind = detectFlexComparisonModifier(effectiveUserText);
    if (modifierKind === 'capacity-reservation' && parseCapacityReservationUtilization(effectiveUserText) === null) {
      return respond({
        ok: true,
        mode: 'clarification',
        message: 'For the Flex shape comparison, what capacity reservation utilization should I use: for example `1.0`, `0.7`, or `0.5`?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'What capacity reservation utilization should I use for the comparison?' },
      });
    }
    if (modifierKind === 'burstable' && parseBurstableBaseline(effectiveUserText) === null) {
      return respond({
        ok: true,
        mode: 'clarification',
        message: 'For the Flex shape comparison, what burstable baseline should I use: for example `0.5`, `0.25`, or `0.125`?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'What burstable baseline should I use for the comparison?' },
      });
    }
  }

  if (flexComparison) {
    if (flexComparison.modifierKind === 'capacity-reservation' && flexComparison.utilization === null) {
      return respond({
        ok: true,
        mode: 'clarification',
        message: 'For the Flex shape comparison, what capacity reservation utilization should I use: for example `1.0`, `0.7`, or `0.5`?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'What capacity reservation utilization should I use for the comparison?' },
      });
    }
    if (flexComparison.modifierKind === 'burstable' && flexComparison.burstableBaseline === null) {
      return respond({
        ok: true,
        mode: 'clarification',
        message: 'For the Flex shape comparison, what burstable baseline should I use: for example `0.5`, `0.25`, or `0.125`?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'What burstable baseline should I use for the comparison?' },
      });
    }
    if (flexComparison.modifierKind === 'capacity-reservation' && !flexComparison.withoutCrMode) {
      return respond({
        ok: true,
        mode: 'clarification',
        message: 'For the non-capacity-reservation side of the comparison, should I use `On demand` pricing?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'Should I use On demand pricing for the non-capacity-reservation side?' },
      });
    }
    if (flexComparison.modifierKind === 'capacity-reservation' && flexComparison.withoutCrMode !== 'on-demand') {
      return respond({
        ok: true,
        mode: 'clarification',
        message: 'Reserved pricing for the non-capacity-reservation side is not modeled yet in this comparison flow. If you want, reply with `On demand` and I will generate the deterministic comparison.',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'Reply with On demand to continue the Flex comparison.' },
      });
    }
    const comparison = buildFlexComparisonQuote(index, flexComparison);
    if (comparison.ok) {
      return respond({
        ok: true,
        mode: 'quote',
        message: buildFlexComparisonNarrative(flexComparison, comparison),
        quote: {
          ok: true,
          request: {
            source: flexComparison.basePrompt,
            comparison: true,
          },
          comparison,
        },
        intent: {
          intent: 'quote',
          shouldQuote: true,
          needsClarification: false,
          clarificationQuestion: '',
        },
      });
    }
  }

  if (compositeLike) {
    const compositeQuote = buildCompositeQuoteFromSegments(index, effectiveUserText);
    if (compositeQuote?.ok) {
      return respond({
        ok: true,
        mode: 'quote',
        message: await buildQuoteNarrative(cfg, effectiveUserText, compositeQuote, formatAssumptions([], parsePromptRequest(effectiveUserText))),
        quote: compositeQuote,
        intent: {
          intent: 'quote',
          shouldQuote: true,
          needsClarification: false,
          clarificationQuestion: '',
        },
      });
    }
  }

  const rawParsedRequest = parsePromptRequest(effectiveUserText);
  const isSimpleTransactionalQuote = !compositeLike &&
    Number.isFinite(Number(rawParsedRequest.requestCount)) &&
    !Number.isFinite(Number(rawParsedRequest.ocpus)) &&
    !Number.isFinite(Number(rawParsedRequest.ecpus)) &&
    !Number.isFinite(Number(rawParsedRequest.capacityGb)) &&
    !Number.isFinite(Number(rawParsedRequest.users)) &&
    !rawParsedRequest.shape &&
    !rawParsedRequest.serviceFamily;
  if (isSimpleTransactionalQuote) {
    const rawQuote = quoteFromPrompt(index, effectiveUserText);
    if (rawQuote.ok && rawQuote.resolution?.type === 'service') {
      return respond({
        ok: true,
        mode: 'quote',
        message: await buildQuoteNarrative(cfg, effectiveUserText, rawQuote, formatAssumptions([], rawParsedRequest)),
        quote: rawQuote,
        intent: {
          intent: 'quote',
          shouldQuote: true,
          needsClarification: false,
          clarificationQuestion: '',
        },
      });
    }
  }

  let intent;
  try {
    intent = imageDataUrl
      ? await analyzeImageIntent(cfg, effectiveUserText, imageDataUrl)
      : await analyzeIntent(cfg, conversation, effectiveUserText, sessionContext);
  } catch (_error) {
    return respond({
      ok: true,
      mode: 'answer',
      message: buildServiceUnavailableMessage(userText),
      intent: {
        intent: 'answer',
        route: 'general_answer',
        shouldQuote: false,
        needsClarification: false,
      },
    });
  }
  const enrichedIntent = enrichExtractedInputsForFamily(intent);
  if (
    shouldForceSessionQuoteFollowUp(sessionContext, userText) &&
    enrichedIntent.route !== 'quote_followup'
  ) {
    enrichedIntent.route = 'quote_followup';
    enrichedIntent.intent = 'quote';
    enrichedIntent.shouldQuote = true;
    enrichedIntent.needsClarification = false;
    enrichedIntent.clarificationQuestion = '';
    enrichedIntent.quotePlan = {
      ...((enrichedIntent.quotePlan && typeof enrichedIntent.quotePlan === 'object' && enrichedIntent.quotePlan) || {}),
      action: 'modify_quote',
      targetType: 'quote',
      useDeterministicEngine: true,
    };
  }
  const mergedContextualFollowUp = contextualFollowUp && effectiveUserText !== userText;
  if (mergedContextualFollowUp) {
    enrichedIntent.reformulatedRequest = effectiveUserText;
    enrichedIntent.normalizedRequest = effectiveUserText;
  }
  if (contextualFollowUp && enrichedIntent?.reformulatedRequest) {
    enrichedIntent.normalizedRequest = String(enrichedIntent.reformulatedRequest).trim();
  }
  const postIntentFlexComparison = flexComparison || extractFlexComparisonContext(
    conversation,
    userText,
    enrichedIntent?.reformulatedRequest || enrichedIntent?.normalizedRequest || '',
  );
  if (postIntentFlexComparison) {
    if (postIntentFlexComparison.modifierKind === 'capacity-reservation' && postIntentFlexComparison.utilization === null) {
      return respond({
        ok: true,
        mode: 'clarification',
        message: 'For the Flex shape comparison, what capacity reservation utilization should I use: for example `1.0`, `0.7`, or `0.5`?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'What capacity reservation utilization should I use for the comparison?' },
      });
    }
    if (postIntentFlexComparison.modifierKind === 'burstable' && postIntentFlexComparison.burstableBaseline === null) {
      return respond({
        ok: true,
        mode: 'clarification',
        message: 'For the Flex shape comparison, what burstable baseline should I use: for example `0.5`, `0.25`, or `0.125`?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'What burstable baseline should I use for the comparison?' },
      });
    }
    if (postIntentFlexComparison.modifierKind === 'capacity-reservation' && !postIntentFlexComparison.withoutCrMode) {
      return respond({
        ok: true,
        mode: 'clarification',
        message: 'For the non-capacity-reservation side of the comparison, should I use `On demand` pricing?',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'Should I use On demand pricing for the non-capacity-reservation side?' },
      });
    }
    if (postIntentFlexComparison.modifierKind === 'capacity-reservation' && postIntentFlexComparison.withoutCrMode !== 'on-demand') {
      return respond({
        ok: true,
        mode: 'clarification',
        message: 'Reserved pricing for the non-capacity-reservation side is not modeled yet in this comparison flow. If you want, reply with `On demand` and I will generate the deterministic comparison.',
        intent: { intent: 'quote', shouldQuote: true, needsClarification: true, clarificationQuestion: 'Reply with On demand to continue the Flex comparison.' },
      });
    }
    const comparison = buildFlexComparisonQuote(index, postIntentFlexComparison);
    if (comparison.ok) {
      return respond({
        ok: true,
        mode: 'quote',
        message: buildFlexComparisonNarrative(postIntentFlexComparison, comparison),
        quote: {
          ok: true,
          request: {
            source: postIntentFlexComparison.basePrompt,
            comparison: true,
          },
          comparison,
        },
        intent: {
          intent: 'quote',
          shouldQuote: true,
          needsClarification: false,
          clarificationQuestion: '',
        },
      });
    }
  }
  const registryQuery = buildRegistryQuery(
    String(effectiveUserText || userText || enrichedIntent.normalizedRequest || enrichedIntent.reformulatedRequest || '').trim(),
    enrichedIntent,
  );
  const registryMatches = searchServiceRegistry(index.serviceRegistry, registryQuery, 5);
  const topService = registryMatches.find((item) => item.deterministic && serviceHasRequiredInputs(item, enrichedIntent.extractedInputs)) || registryMatches[0];
  const catalogReply = buildCatalogListingReply(index, registryQuery || userText, enrichedIntent);
  const isDiscoveryIntent = (
    enrichedIntent.route === 'product_discovery' ||
    String(enrichedIntent.intent || '').toLowerCase() === 'discover'
  );
  if (
    isDiscoveryIntent &&
    (
      enrichedIntent.quotePlan?.targetType === 'catalog' ||
      catalogReply
    )
  ) {
    if (catalogReply) {
      return respond({
        ok: true,
        mode: 'answer',
        message: catalogReply,
        intent: {
          ...enrichedIntent,
          intent: 'discover',
          shouldQuote: false,
          needsClarification: false,
          clarificationQuestion: '',
        },
      });
    }
  }
  if ((enrichedIntent.route === 'product_discovery' || enrichedIntent.route === 'general_answer') && !enrichedIntent.shouldQuote) {
    const contextPack = buildAssistantContextPack(index, {
      userText: effectiveUserText,
      intent: enrichedIntent,
      sessionContext,
    });
    const structuredReply = await writeStructuredContextReply(cfg, conversation, userText, sessionContext, contextPack);
    return respond({
      ok: true,
      mode: 'answer',
      message: structuredReply || buildServiceUnavailableMessage(userText),
      contextPackSummary: summarizeContextPack(contextPack),
      intent: enrichedIntent,
    });
  }
  const interpretedFamilyMeta = getServiceFamily(enrichedIntent.serviceFamily);
  const routeMergedFollowUp = mergeSessionQuoteFollowUpByRoute(sessionContext, enrichedIntent, userText);
  const effectiveQuoteText = String(routeMergedFollowUp || effectiveUserText || userText || '').trim() || effectiveUserText;
  const unsupportedComputeVariant = findUncoveredComputeVariant(effectiveQuoteText || userText);
  if (enrichedIntent.shouldQuote && unsupportedComputeVariant && !canSafelyQuoteUncoveredComputeVariant(unsupportedComputeVariant, effectiveQuoteText || userText)) {
    return respond({
      ok: true,
      mode: 'answer',
      message: buildUncoveredComputeReply(effectiveQuoteText || userText),
      contextPackSummary: summarizeContextPack(buildAssistantContextPack(index, {
        userText: effectiveQuoteText || userText,
        intent: {
          ...enrichedIntent,
          route: 'product_discovery',
          shouldQuote: false,
        },
        sessionContext,
      })),
      intent: {
        ...enrichedIntent,
        route: 'product_discovery',
        shouldQuote: false,
        needsClarification: false,
        clarificationQuestion: '',
      },
    });
  }
  if (!compositeLike && topService && topService.deterministic && serviceHasRequiredInputs(topService, enrichedIntent.extractedInputs) && (!enrichedIntent.serviceFamily || !interpretedFamilyMeta)) {
    enrichedIntent.serviceName = topService.name;
    enrichedIntent.normalizedRequest = String(effectiveQuoteText || enrichedIntent.normalizedRequest || '').trim();
    if (!enrichedIntent.shouldQuote || enrichedIntent.needsClarification) {
      enrichedIntent.intent = 'quote';
      enrichedIntent.shouldQuote = true;
      enrichedIntent.needsClarification = false;
      enrichedIntent.clarificationQuestion = '';
    }
  }
  const familyMeta = interpretedFamilyMeta;
  const canonicalFamilyRequest = !compositeLike && familyMeta
    ? String(buildCanonicalRequest(enrichedIntent, effectiveQuoteText) || '').trim()
    : '';
  const reformulatedRequest = preserveCriticalPromptModifiers(compositeLike
    ? effectiveQuoteText
    : familyMeta
      ? (canonicalFamilyRequest || String(
        (contextualFollowUp
          ? (enrichedIntent.reformulatedRequest || enrichedIntent.normalizedRequest)
          : (enrichedIntent.normalizedRequest || enrichedIntent.reformulatedRequest))
        || effectiveQuoteText,
      ).trim() || effectiveQuoteText)
      : effectiveQuoteText, effectiveQuoteText);
  const preflightQuote = !compositeLike && familyMeta
    ? choosePreferredQuote(
      quoteFromPrompt(index, effectiveQuoteText),
      quoteFromPrompt(index, reformulatedRequest),
    )
    : null;
  const preQuoteClarification = getPreQuoteClarification({
    ...enrichedIntent,
    extractedInputs: enrichedIntent.extractedInputs || {},
    reformulatedRequest,
  }, effectiveUserText || userText);
  if (preQuoteClarification) {
    return {
      ok: true,
      mode: 'clarification',
      message: preQuoteClarification,
      intent: {
        ...enrichedIntent,
        needsClarification: true,
        clarificationQuestion: preQuoteClarification,
      },
    };
  }
  const missingInputs = getMissingRequiredInputs(enrichedIntent);
  const canQuoteDespiteMissingInputs = !!(familyMeta && missingInputs.length && preflightQuote?.ok);
  if (familyMeta && enrichedIntent.shouldQuote && (!missingInputs.length || canQuoteDespiteMissingInputs)) {
    enrichedIntent.needsClarification = false;
    enrichedIntent.clarificationQuestion = '';
  }
  const byolChoice = hasExplicitByolChoice(`${userText}\n${reformulatedRequest}`);
  if (shouldAskLicenseChoice(familyMeta, enrichedIntent, byolChoice)) {
    return respond({
      ok: true,
      mode: 'clarification',
      message: familyMeta.licenseClarificationQuestion || `Before I quote ${familyMeta.canonical}, do you want BYOL or License Included?`,
      intent: {
        ...enrichedIntent,
        needsClarification: true,
        clarificationQuestion: familyMeta.licenseClarificationQuestion || 'Do you want BYOL or License Included?',
      },
    });
  }
  if (familyMeta && missingInputs.length && familyMeta.clarificationQuestion && !canQuoteDespiteMissingInputs) {
    const clarificationMessage = getClarificationMessage(enrichedIntent, effectiveUserText || userText) || familyMeta.clarificationQuestion;
    return respond({
      ok: true,
      mode: 'clarification',
      message: clarificationMessage,
      intent: {
        ...enrichedIntent,
        needsClarification: true,
        clarificationQuestion: clarificationMessage,
      },
    });
  }

  if (enrichedIntent.needsClarification && enrichedIntent.clarificationQuestion) {
    return respond({
      ok: true,
      mode: 'clarification',
      message: String(enrichedIntent.clarificationQuestion).trim(),
      intent: enrichedIntent,
    });
  }

  if (enrichedIntent.shouldQuote) {
    let quote = preflightQuote?.ok ? preflightQuote : quoteFromPrompt(index, reformulatedRequest);
    const parsed = parsePromptRequest(reformulatedRequest);
    const assumptions = formatAssumptions(enrichedIntent.assumptions, parsed);

    const byolAmbiguousProduct = quote.ok && !byolChoice ? detectByolAmbiguity(quote) : '';
    if (byolAmbiguousProduct) {
      return respond({
        ok: true,
        mode: 'clarification',
        message: `Antes de cotizar ${byolAmbiguousProduct}, necesito confirmar la modalidad de licencia: ¿quieres **BYOL** o **License Included**?`,
        intent: {
          ...enrichedIntent,
          needsClarification: true,
          clarificationQuestion: 'Do you want BYOL or License Included?',
        },
      });
    }
    if (quote.ok && byolChoice) {
      quote = filterQuoteByByolChoice(quote, byolChoice);
    }

    if (quote.ok) {
      return respond({
        ok: true,
        mode: 'quote',
      message: await buildQuoteNarrative(cfg, effectiveUserText, quote, assumptions),
      quote,
      intent: enrichedIntent,
    });
    }

    if (typeof familyMeta?.quoteUnavailableMessage === 'function') {
      return respond({
        ok: true,
        mode: 'quote_unresolved',
        message: familyMeta.quoteUnavailableMessage({
          userText,
          reformulatedRequest,
          quote,
          intent: enrichedIntent,
        }),
        quote,
        intent: enrichedIntent,
      });
    }

    const matches = summarizeMatches(index, reformulatedRequest);
    const natural = await writeNaturalReply(cfg, conversation, userText, {
      intent: enrichedIntent.intent || 'quote',
      summary: quote.error || 'No deterministic quotation could be produced.',
      warningLines: (quote.warnings || []).map((item) => `- ${item}`),
      candidateLines: [
        ...matches.products.map((item) => `- Product: ${item}`),
        ...matches.presets.map((item) => `- Preset: ${item}`),
      ],
      assumptionLines: assumptions,
    }, sessionContext);
    return respond({
      ok: true,
      mode: 'quote_unresolved',
      message: natural || quote.error || 'No quotation could be generated.',
      quote,
      intent: enrichedIntent,
    });
  }

  const matches = summarizeMatches(index, userText);
  const natural = await writeNaturalReply(cfg, conversation, userText, {
    intent: enrichedIntent.intent || 'explain',
    summary: 'The user is asking for OCI pricing guidance rather than a deterministic quote.',
    candidateLines: [
      ...matches.products.map((item) => `- Product: ${item}`),
      ...matches.presets.map((item) => `- Preset: ${item}`),
    ],
    assumptionLines: Array.isArray(enrichedIntent.assumptions) ? enrichedIntent.assumptions.map((item) => `- ${item}`) : [],
  }, sessionContext);

  return respond({
    ok: true,
    mode: 'answer',
    message: natural || 'I can help with OCI pricing guidance or prepare a deterministic quotation if you share the sizing details.',
    intent: enrichedIntent,
  });
}

module.exports = {
  buildDeterministicExpertSummary,
  respondToAssistant,
  sanitizeQuoteEnrichment,
};
