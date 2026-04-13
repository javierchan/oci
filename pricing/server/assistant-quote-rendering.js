'use strict';

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

module.exports = {
  fmt,
  money,
  toMarkdownQuote,
};
