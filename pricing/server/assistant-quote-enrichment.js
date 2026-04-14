'use strict';

const { formatMoney } = require('./assistant-quote-narrative');
const { fmt, money } = require('./assistant-quote-rendering');

function shouldAllowMigrationNotes(userText, quote) {
  const request = quote?.request || {};
  return request?.metadata?.inventorySource === 'rvtools' || /\bvmware\b|\brvtools\b/i.test(String(userText || ''));
}

function buildQuoteEnrichmentContextBlock(userText, quote, assumptions, technologyProfile) {
  const lineItems = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const request = quote?.request || {};
  const totals = quote?.totals || {};
  return [
    `User request: ${String(userText || '').trim()}`,
    `Expert role: ${technologyProfile?.role || 'OCI pricing specialist'}`,
    `Technology profile: ${technologyProfile?.name || 'General OCI pricing'}`,
    `OCI expert focus: ${technologyProfile?.focus || 'main billable dimensions and follow-up checks'}`,
    `Matched label: ${quote?.resolution?.label || 'n/a'}`,
    `Monthly total: ${formatMoney(totals.monthly, totals.currencyCode || 'USD')}`,
    `Annual total: ${formatMoney(totals.annual, totals.currencyCode || 'USD')}`,
    Array.isArray(assumptions) && assumptions.length ? `Assumptions:\n${assumptions.join('\n')}` : '',
    quote?.warnings?.length ? `Warnings:\n${quote.warnings.map((item) => `- ${item}`).join('\n')}` : '',
    `Line items:\n${lineItems.slice(0, 12).map((line) => `- ${line.service || '-'} | ${line.product} | ${line.metric || '-'} | qty ${fmt(line.quantity)} | monthly ${money(line.monthly)}`).join('\n')}`,
    request?.metadata?.inventorySource ? `Inventory source: ${request.metadata.inventorySource}` : '',
    request?.metadata?.vmwareVcpus ? `VMware vCPUs in source request: ${request.metadata.vmwareVcpus}` : '',
  ].filter(Boolean).join('\n\n');
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

module.exports = {
  buildQuoteEnrichmentContextBlock,
  sanitizeQuoteEnrichment,
  shouldAllowMigrationNotes,
};
