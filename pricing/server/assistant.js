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
const { resolveGenAIRequestOptions } = require('./genai-profiles');
const { analyzeIntent, analyzeImageIntent, buildSessionContextBlock } = require('./intent-extractor');
const { logger, summarizeTrace } = require('./logger');
const { recordAssistantRequestMetrics } = require('./metrics');
const { buildAssistantContextPack, buildCatalogListingReply, buildStructuredDiscoveryFallback, buildUncoveredComputeReply, canSafelyQuoteUncoveredComputeVariant, findUncoveredComputeVariant, stringifyContextPack, summarizeContextPack } = require('./context-packs');
const { buildServiceUnavailableMessage } = require('./assistant-response-helpers');
const { sanitizeQuoteEnrichment } = require('./assistant-quote-enrichment');
const { buildQuoteNarrative } = require('./assistant-quote-orchestrator');
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
  const requestOptions = resolveGenAIRequestOptions('narrative', cfg);

  const response = await runChat({
    cfg,
    ...requestOptions,
    systemPrompt: RESPONSE_PROMPT,
    messages,
    logger: context.logger,
    trace: context.trace,
  });
  return extractChatText(response?.data || response).trim();
}

async function writeStructuredContextReply(cfg, conversation, userText, sessionContext, contextPack, options = {}) {
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
  const requestOptions = resolveGenAIRequestOptions('discovery', cfg);

  try {
    const response = await runChat({
      cfg,
      ...requestOptions,
      systemPrompt: STRUCTURED_DISCOVERY_PROMPT,
      messages,
      logger: options.logger,
      trace: options.trace,
    });
    return extractChatText(response?.data || response).trim();
  } catch {
    return '';
  }
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

async function respondToAssistant({ cfg, index, conversation, userText, imageDataUrl, sessionContext, logger: requestLogger, trace }) {
  const activeLogger = requestLogger || logger;
  const activeTrace = trace || { genaiCalls: [] };
  const effectiveUserText = mergeSessionQuoteFollowUp(
    sessionContext,
    mergeClarificationAnswer(conversation, userText),
  );
  const respond = (payload) => ({
    ...payload,
    sessionContext: buildAssistantSessionContext(sessionContext, effectiveUserText, payload),
  });
  try {
    const contextualFollowUp = isShortContextualAnswer(userText);
    const compositeLike = isCompositeOrComparisonRequest(effectiveUserText);
    activeLogger.debug({
      event: 'assistant.pipeline.start',
      hasImage: Boolean(imageDataUrl),
      conversationDepth: Array.isArray(conversation) ? conversation.length : 0,
      contextualFollowUp,
      compositeLike,
    }, 'Starting assistant pipeline');
    const {
      payload: earlyRoutingPayload,
      flexComparison,
    } = resolveEarlyAssistantRouting({
      conversation,
      userText,
      effectiveUserText,
      index,
    }, {
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
    });
    if (earlyRoutingPayload) {
      logAssistantOutcome(activeLogger, activeTrace, 'early_exit', earlyRoutingPayload, earlyRoutingPayload.intent || null);
      return respond(earlyRoutingPayload);
    }

    const directQuoteFastPath = await resolveDirectQuoteFastPath({
      cfg,
      index,
      effectiveUserText,
      compositeLike,
    }, {
      buildCompositeQuoteFromSegments,
      buildQuoteNarrative,
      formatAssumptions,
      parsePromptRequest,
      quoteFromPrompt,
    });
    if (directQuoteFastPath) {
      logAssistantOutcome(activeLogger, activeTrace, 'fast_path', directQuoteFastPath, directQuoteFastPath.intent || null);
      return respond(directQuoteFastPath);
    }

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
    }, {
      analyzeIntent: (...args) => analyzeIntent(...args, { logger: activeLogger, trace: activeTrace }),
      analyzeImageIntent: (...args) => analyzeImageIntent(...args, { logger: activeLogger, trace: activeTrace }),
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
    });
    if (intentPipeline.payload) {
      logAssistantOutcome(activeLogger, activeTrace, 'full_pipeline', intentPipeline.payload, intentPipeline.payload.intent || null);
      return respond(intentPipeline.payload);
    }
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
    }, {
      buildRegistryQuery,
      searchServiceRegistry,
      serviceHasRequiredInputs,
      buildCatalogListingReply,
    });
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
    }, {
      buildAssistantContextPack,
      writeStructuredContextReply: (...args) => writeStructuredContextReply(...args, { logger: activeLogger, trace: activeTrace }),
      buildStructuredDiscoveryFallback,
      isConceptualPricingQuestion,
      hasExplicitQuoteLead,
      buildServiceUnavailableMessage,
      summarizeContextPack,
    });
    if (discoveryRoutePayload) {
      logAssistantOutcome(activeLogger, activeTrace, 'full_pipeline', discoveryRoutePayload, enrichedIntent);
      return respond(discoveryRoutePayload);
    }
    const quoteCandidateState = prepareQuoteCandidateState({
      index,
      sessionContext,
      userText,
      effectiveUserText,
      intent: enrichedIntent,
      topService,
      contextualFollowUp,
      compositeLike,
    }, {
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
    });
    if (quoteCandidateState.fallbackPayload) return respond(quoteCandidateState.fallbackPayload);
    const effectiveQuoteText = quoteCandidateState.effectiveQuoteText;
    Object.assign(enrichedIntent, quoteCandidateState.intent);
    const familyMeta = quoteCandidateState.familyMeta;
    const reformulatedRequest = quoteCandidateState.reformulatedRequest;
    const preflightQuote = quoteCandidateState.preflightQuote;
    const quoteClarificationState = reconcileQuoteClarificationState({
      intent: enrichedIntent,
      reformulatedRequest,
      effectiveUserText,
      userText,
      familyMeta,
      preflightQuote,
      getPreQuoteClarification,
      getMissingRequiredInputs,
      getClarificationMessage,
    });
    const postClarification = await resolvePostClarificationRouting({
      cfg,
      index,
      conversation,
      userText,
      effectiveUserText,
      sessionContext,
      intent: enrichedIntent,
      familyMeta,
      reformulatedRequest,
      preflightQuote,
      quoteClarificationState,
    }, {
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
      writeNaturalReply: (...args) => writeNaturalReply(...args, { logger: activeLogger, trace: activeTrace }),
    });
    Object.assign(enrichedIntent, postClarification.intent);
    logAssistantOutcome(activeLogger, activeTrace, 'full_pipeline', postClarification.payload, enrichedIntent);
    return respond(postClarification.payload);
  } catch (error) {
    recordAssistantRequestMetrics({ outcome: 'error', pathName: '' });
    throw error;
  }
}

function classifyAssistantOutcome(payload = {}, intent = null) {
  if (payload?.needsClarification || payload?.question) return 'clarification';
  if (payload?.quote || payload?.quoteMarkdown || payload?.totals || payload?.mode === 'quote') return 'quote';
  if (intent?.route === 'product_discovery' || intent?.route === 'general_answer' || payload?.mode === 'discovery') return 'discovery';
  return 'discovery';
}

function logAssistantOutcome(activeLogger, trace, routingPath, payload, intent) {
  const traceSummary = summarizeTrace(trace);
  const outcome = classifyAssistantOutcome(payload, intent);
  recordAssistantRequestMetrics({
    outcome,
    pathName: routingPath,
  });
  activeLogger.info({
    event: 'assistant.pipeline.complete',
    routingPath,
    outcome,
    route: intent?.route || payload?.intent?.route || '',
    serviceFamily: intent?.serviceFamily || payload?.intent?.serviceFamily || '',
    shouldQuote: Boolean(intent?.shouldQuote ?? payload?.intent?.shouldQuote),
    genaiCallCount: traceSummary.genaiCallCount,
    genaiLatencyMs: traceSummary.genaiLatencyMs,
    quoteProduced: outcome === 'quote',
    clarificationTriggered: outcome === 'clarification',
  }, 'Completed assistant pipeline');
}

module.exports = {
  buildDeterministicExpertSummary,
  respondToAssistant,
  sanitizeQuoteEnrichment,
};
