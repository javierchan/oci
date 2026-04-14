'use strict';

const { quoteFromPrompt, parsePromptRequest } = require('./quotation-engine');
const { searchProducts, searchPresets, searchServiceRegistry, serviceHasRequiredInputs } = require('./catalog');
const { getServiceFamily, getMissingRequiredInputs, getClarificationMessage, getPreQuoteClarification, inferServiceFamily, normalizeExtractedInputsForFamily } = require('./service-families');
const {
  buildConsumptionExplanation: buildConsumptionExplanationHelper,
  classifyConsumptionGroup: classifyConsumptionGroupHelper,
  buildDeterministicConsiderationsFallback: buildDeterministicConsiderationsFallbackHelper,
  buildDeterministicExpertSummary: buildDeterministicExpertSummaryHelper,
  formatMoney: formatMoneyHelper,
  inferQuoteTechnologyProfile: inferQuoteTechnologyProfileHelper,
} = require('./assistant-quote-narrative');
const { runChat, extractChatText } = require('./genai');
const { analyzeIntent, analyzeImageIntent, buildSessionContextBlock } = require('./intent-extractor');
const { buildAssistantContextPack, buildCatalogListingReply, buildStructuredDiscoveryFallback, buildUncoveredComputeReply, canSafelyQuoteUncoveredComputeVariant, findUncoveredComputeVariant, stringifyContextPack, summarizeContextPack } = require('./context-packs');
const { buildServiceUnavailableMessage } = require('./assistant-response-helpers');
const { sanitizeQuoteEnrichment } = require('./assistant-quote-enrichment');
const { buildQuoteNarrative } = require('./assistant-quote-orchestrator');
const {
  writeNaturalReply: writeNaturalReplyHelper,
  writeStructuredContextReply: writeStructuredContextReplyHelper,
} = require('./assistant-reply-writers');
const { toMarkdownQuote } = require('./assistant-quote-rendering');
const {
  buildAssistantSessionContext,
} = require('./assistant-session-context');
const {
  hasCompositeServiceSignal,
  splitCompositeQuoteSegments,
} = require('./composite-quote-segmentation');
const {
  buildCompositeQuoteFromSegments,
  choosePreferredQuote,
} = require('./composite-quote-builder');
const {
  detectFlexComparisonModifier,
  extractFlexComparisonContext,
  isFlexComparisonRequest,
  parseBurstableBaseline,
  parseCapacityReservationUtilization,
} = require('./flex-comparison-helpers');
const { buildRegistryQuery } = require('./request-query-helpers');
const { hasExplicitQuoteLead, isConceptualPricingQuestion, isDiscoveryOrExplanationQuestion } = require('./discovery-classifier');
const { fallbackIntentOnAnalysisFailure, reconcileIntentWithHeuristics } = require('./intent-reconciliation');
const { shouldForceQuoteFollowUpRoute, applyQuoteFollowUpIntentOverride } = require('./quote-followup-intent');
const { reconcilePostIntentFollowUp } = require('./post-intent-followup');
const { buildEarlyAssistantReply } = require('./early-assistant-replies');
const { detectGenericComputeShapeClarification } = require('./compute-shape-clarification');
const { buildQuoteUnresolvedPayload } = require('./quote-unresolved');
const { buildAnswerFallbackPayload } = require('./answer-fallback');
const { reconcileQuoteClarificationState } = require('./quote-clarification-state');
const { buildQuoteRequestShape } = require('./quote-request-shaping');
const { resolveDirectQuoteFastPath } = require('./direct-quote-fast-paths');
const { resolveEarlyAssistantRouting } = require('./early-assistant-routing');
const { buildDiscoveryRoutingState, resolveDiscoveryRoutePayload } = require('./discovery-routing');
const { resolvePostClarificationRouting } = require('./post-clarification-routing');
const { resolveAssistantQuoteRouting } = require('./assistant-quote-routing');
const {
  buildDiscoveryRoutePayloadDeps,
  buildDiscoveryRoutingStateDeps,
  buildEarlyAssistantRoutingDeps,
  buildIntentPipelineDeps,
} = require('./assistant-orchestration-deps');
const {
  buildAssistantQuoteRoutingDeps,
  buildDirectQuoteFastPathDeps,
} = require('./quote-routing-deps');
const { resolveIntentPipeline } = require('./intent-pipeline');
const { prepareQuoteCandidateState } = require('./quote-entry-preparation');
const {
  mergeSessionQuoteFollowUp,
  mergeSessionQuoteFollowUpByRoute,
  preserveCriticalPromptModifiers,
} = require('./session-quote-followup');
const {
  isSessionQuoteFollowUp,
  isShortContextualAnswer,
  mergeClarificationAnswer,
} = require('./clarification-followup');
const {
  hasExplicitByolChoice,
  detectByolAmbiguity,
  filterQuoteByByolChoice,
  shouldAskLicenseChoice,
  buildLicenseChoiceClarificationPayload,
  buildByolAmbiguityClarificationPayload,
} = require('./license-choice');
const { formatAssumptions } = require('./quote-assumptions');
const {
  resolveEarlyFlexComparisonClarification,
  buildFlexComparisonQuote,
  buildFlexComparisonNarrative,
  buildFlexComparisonReplyPayload,
} = require('./flex-comparison-flow');

const FLEX_SHAPE_TOKEN_PATTERN_SOURCE = '(?:(?:vm|bm)\\.)?(?:(?:[a-z][a-z0-9]*)\\.)*(?:[a-z]+\\d+|[a-z]\\d+)\\.flex';
const FLEX_SHAPE_TOKEN_INLINE_PATTERN = new RegExp(`\\b${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}\\b`, 'i');

function summarizeMatches(index, text) {
  const products = searchProducts(index, text, 5).map((item) => item.fullDisplayName);
  const presets = searchPresets(index, text, 3).map((item) => item.displayName);
  return { products, presets };
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
    FLEX_SHAPE_TOKEN_INLINE_PATTERN.test(source),
  ].filter(Boolean).length;
  if (/\bcompare\b/.test(source) && FLEX_SHAPE_TOKEN_INLINE_PATTERN.test(source)) return true;
  return serviceHits >= 2 || /\b3-tier\b|\bthree-tier\b|\barchitecture\b|\bworkload\b|\bbundle\b|\bstack\b|\bplatform\b/.test(source);
}

function enrichExtractedInputsForFamily(intent = {}) {
  return {
    ...intent,
    extractedInputs: normalizeExtractedInputsForFamily(intent.serviceFamily, intent.extractedInputs),
  };
}

async function writeNaturalReply(cfg, conversation, userText, context, sessionContext) {
  return writeNaturalReplyHelper(cfg, conversation, userText, context, sessionContext, {
    buildSessionContextBlock,
    runChat,
    extractChatText,
  });
}

async function writeStructuredContextReply(cfg, conversation, userText, sessionContext, contextPack) {
  return writeStructuredContextReplyHelper(cfg, conversation, userText, sessionContext, contextPack, {
    buildSessionContextBlock,
    stringifyContextPack,
    runChat,
    extractChatText,
  });
}

function inferQuoteTechnologyProfile(quote) {
  return inferQuoteTechnologyProfileHelper(quote);
}

function buildDeterministicExpertSummary(quote) {
  return buildDeterministicExpertSummaryHelper(quote);
}

function buildDeterministicConsiderationsFallback(quote, assumptions) {
  return buildDeterministicConsiderationsFallbackHelper(quote, assumptions);
}

function formatMoney(value, currencyCode = 'USD') {
  return formatMoneyHelper(value, currencyCode);
}

function buildConsumptionExplanation(quote) {
  return buildConsumptionExplanationHelper(quote);
}

function classifyConsumptionGroup(pattern, line) {
  return classifyConsumptionGroupHelper(pattern, line);
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
  const {
    payload: earlyRoutingPayload,
    flexComparison,
  } = resolveEarlyAssistantRouting({
    conversation,
    userText,
    effectiveUserText,
    index,
  }, buildEarlyAssistantRoutingDeps({
    buildEarlyAssistantReply,
    detectGenericComputeShapeClarification,
    extractFlexComparisonContext,
    resolveEarlyFlexComparisonClarification,
    isFlexComparisonRequest,
    detectFlexComparisonModifier,
    parseCapacityReservationUtilization,
    parseBurstableBaseline,
    buildFlexComparisonReplyPayload,
    buildFlexComparisonQuote,
    buildFlexComparisonNarrative,
  }));
  if (earlyRoutingPayload) return respond(earlyRoutingPayload);

  const directQuoteFastPath = await resolveDirectQuoteFastPath({
    cfg,
    index,
    effectiveUserText,
    compositeLike,
  }, buildDirectQuoteFastPathDeps({
    buildCompositeQuoteFromSegments,
    buildQuoteNarrative,
    formatAssumptions,
    parsePromptRequest,
    quoteFromPrompt,
  }));
  if (directQuoteFastPath) return respond(directQuoteFastPath);

  const intentPipeline = await resolveIntentPipeline({
    cfg,
    conversation,
    effectiveUserText,
    userText,
    imageDataUrl,
    sessionContext,
    contextualFollowUp,
    flexComparison,
    index,
  }, buildIntentPipelineDeps({
    analyzeIntent,
    analyzeImageIntent,
    fallbackIntentOnAnalysisFailure,
    buildServiceUnavailableMessage,
    enrichExtractedInputsForFamily,
    reconcileIntentWithHeuristics,
    shouldForceQuoteFollowUpRoute,
    isSessionQuoteFollowUp,
    applyQuoteFollowUpIntentOverride,
    reconcilePostIntentFollowUp,
    extractFlexComparisonContext,
    buildFlexComparisonReplyPayload,
    buildFlexComparisonQuote,
    buildFlexComparisonNarrative,
  }));
  if (intentPipeline.payload) return respond(intentPipeline.payload);
  const enrichedIntent = intentPipeline.intent;
  const {
    topService,
    catalogReply,
    isDiscoveryIntent,
  } = buildDiscoveryRoutingState({
    index,
    effectiveUserText,
    userText,
    intent: enrichedIntent,
  }, buildDiscoveryRoutingStateDeps({
    buildRegistryQuery,
    searchServiceRegistry,
    serviceHasRequiredInputs,
    buildCatalogListingReply,
  }));
  const discoveryRoutePayload = await resolveDiscoveryRoutePayload({
    cfg,
    index,
    conversation,
    userText,
    effectiveUserText,
    sessionContext,
    intent: enrichedIntent,
    catalogReply,
    isDiscoveryIntent,
  }, buildDiscoveryRoutePayloadDeps({
    buildAssistantContextPack,
    writeStructuredContextReply,
    buildStructuredDiscoveryFallback,
    isConceptualPricingQuestion,
    hasExplicitQuoteLead,
    buildServiceUnavailableMessage,
    summarizeContextPack,
  }));
  if (discoveryRoutePayload) return respond(discoveryRoutePayload);
  const quoteRoute = await resolveAssistantQuoteRouting({
    cfg,
    index,
    conversation,
    userText,
    effectiveUserText,
    sessionContext,
    intent: enrichedIntent,
    topService,
    contextualFollowUp,
    compositeLike,
  }, buildAssistantQuoteRoutingDeps({
    prepareQuoteCandidateState,
    getServiceFamily,
    mergeSessionQuoteFollowUpByRoute,
    findUncoveredComputeVariant,
    canSafelyQuoteUncoveredComputeVariant,
    buildUncoveredComputeReply,
    buildAssistantContextPack,
    summarizeContextPack,
    serviceHasRequiredInputs,
    isDiscoveryOrExplanationQuestion,
    buildQuoteRequestShape,
    preserveCriticalPromptModifiers,
    choosePreferredQuote,
    reconcileQuoteClarificationState,
    getPreQuoteClarification,
    getMissingRequiredInputs,
    getClarificationMessage,
    resolvePostClarificationRouting,
    hasExplicitByolChoice,
    shouldAskLicenseChoice,
    buildLicenseChoiceClarificationPayload,
    quoteFromPrompt,
    parsePromptRequest,
    formatAssumptions,
    detectByolAmbiguity,
    buildByolAmbiguityClarificationPayload,
    filterQuoteByByolChoice,
    toMarkdownQuote,
    buildQuoteNarrative,
    buildQuoteUnresolvedPayload,
    buildAnswerFallbackPayload,
    summarizeMatches,
    writeNaturalReply,
  }));
  Object.assign(enrichedIntent, quoteRoute.intent);
  return respond(quoteRoute.payload);
}

module.exports = {
  buildDeterministicExpertSummary,
  respondToAssistant,
  sanitizeQuoteEnrichment,
};
