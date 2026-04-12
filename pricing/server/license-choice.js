'use strict';

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
    .replace(/\s*-\s*License Included\b/ig, '')
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

function filterQuoteByByolChoice(quote, choice, renderQuoteMarkdown) {
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
    markdown: typeof renderQuoteMarkdown === 'function'
      ? renderQuoteMarkdown(filtered, totals)
      : quote.markdown,
  };
}

function buildLicenseChoiceClarificationPayload(familyMeta, intent) {
  const message = familyMeta?.licenseClarificationQuestion || `Before I quote ${familyMeta?.canonical || 'this service'}, do you want BYOL or License Included?`;
  return {
    ok: true,
    mode: 'clarification',
    message,
    intent: {
      ...intent,
      needsClarification: true,
      clarificationQuestion: familyMeta?.licenseClarificationQuestion || 'Do you want BYOL or License Included?',
    },
  };
}

function buildByolAmbiguityClarificationPayload(productName, intent) {
  return {
    ok: true,
    mode: 'clarification',
    message: `Antes de cotizar ${productName}, necesito confirmar la modalidad de licencia: ¿quieres **BYOL** o **License Included**?`,
    intent: {
      ...intent,
      needsClarification: true,
      clarificationQuestion: 'Do you want BYOL or License Included?',
    },
  };
}

module.exports = {
  hasExplicitByolChoice,
  normalizeByolKey,
  shouldAskLicenseChoice,
  detectByolAmbiguity,
  filterQuoteByByolChoice,
  buildLicenseChoiceClarificationPayload,
  buildByolAmbiguityClarificationPayload,
};
