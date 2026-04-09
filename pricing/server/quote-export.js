'use strict';

const XLSX = require('xlsx');

function buildQuoteExportRows(lineItems = [], totals = null) {
  const rows = (Array.isArray(lineItems) ? lineItems : []).map((line, index) => ({
    '#': index + 1,
    Environment: line.environment || '-',
    Service: line.service || '-',
    'Part#': line.partNumber || '-',
    Product: line.product || '-',
    Metric: line.metric || '-',
    Qty: Number.isFinite(Number(line.quantity)) ? Number(line.quantity) : '',
    Inst: Number.isFinite(Number(line.instances)) ? Number(line.instances) : '',
    Hours: Number.isFinite(Number(line.hours)) ? Number(line.hours) : '',
    Rate: Number.isFinite(Number(line.rate)) ? Number(line.rate) : '',
    Unit: Number.isFinite(Number(line.unitPrice)) ? Number(line.unitPrice) : '',
    '$/Mo': Number.isFinite(Number(line.monthly)) ? Number(line.monthly) : '',
    Annual: Number.isFinite(Number(line.annual)) ? Number(line.annual) : '',
    Currency: line.currencyCode || totals?.currencyCode || 'USD',
  }));
  if (totals) {
    rows.push({
      '#': 'Total',
      Environment: '',
      Service: '',
      'Part#': '',
      Product: '',
      Metric: '',
      Qty: '',
      Inst: '',
      Hours: '',
      Rate: '',
      Unit: '',
      '$/Mo': Number.isFinite(Number(totals.monthly)) ? Number(totals.monthly) : '',
      Annual: Number.isFinite(Number(totals.annual)) ? Number(totals.annual) : '',
      Currency: totals.currencyCode || 'USD',
    });
  }
  return rows;
}

function buildQuoteExportCsv(lineItems = [], totals = null) {
  const rows = buildQuoteExportRows(lineItems, totals);
  if (!rows.length) return '';
  const headers = Object.keys(rows[0]);
  const escapeCell = (value) => {
    const text = String(value ?? '');
    if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
    return text;
  };
  return [
    headers.map(escapeCell).join(','),
    ...rows.map((row) => headers.map((key) => escapeCell(row[key])).join(',')),
  ].join('\n');
}

function buildQuoteExportWorkbook(lineItems = [], totals = null) {
  const workbook = XLSX.utils.book_new();
  const sheet = XLSX.utils.json_to_sheet(buildQuoteExportRows(lineItems, totals));
  XLSX.utils.book_append_sheet(workbook, sheet, 'Quote');
  return XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' });
}

module.exports = {
  buildQuoteExportRows,
  buildQuoteExportCsv,
  buildQuoteExportWorkbook,
};
