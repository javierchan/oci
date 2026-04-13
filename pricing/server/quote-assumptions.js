'use strict';

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

module.exports = {
  formatAssumptions,
  shouldKeepSourceAssumption,
};
