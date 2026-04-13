'use strict';

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

function extractInlinePartNumbers(text = '') {
  return Array.from(new Set((String(text || '').match(/\bB\d{5,6}\b/g) || []).filter(Boolean)));
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

module.exports = {
  buildAssistantSessionContext,
  buildAssistantSessionSummary,
  buildQuoteExportPayload,
  extractInlinePartNumbers,
  summarizeQuoteForSession,
};
