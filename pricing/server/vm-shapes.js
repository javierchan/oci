'use strict';

const path = require('path');

const { shapes } = require(path.join('..', 'data', 'rule-registry', 'vm_shape_rules.json'));

function normalizeShapeToken(value) {
  return String(value || '')
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '');
}

function normalizeProcessorVendor(vendor) {
  const source = String(vendor || '').trim().toLowerCase();
  if (source === 'arm') return 'ampere';
  if (source === 'ampere' || source === 'intel' || source === 'amd') return source;
  return null;
}

function findVmShapeByText(text) {
  const source = String(text || '');
  const normalized = source.toUpperCase();
  const compactSource = normalizeShapeToken(source);

  for (const shape of shapes || []) {
    const candidates = Array.isArray(shape.aliases) && shape.aliases.length
      ? shape.aliases
      : [shape.shapeName];
    const matched = candidates.some((candidate) => {
      const raw = String(candidate || '').toUpperCase();
      const compact = normalizeShapeToken(candidate);
      return (raw && normalized.includes(raw)) || (compact && compactSource.includes(compact));
    });
    if (matched) {
      return {
        kind: shape.kind,
        shapeName: String(shape.shapeName || '').toUpperCase(),
        vendor: shape.vendor,
        family: shape.family,
        series: shape.series,
        fixedOcpus: shape.fixedOcpus ?? null,
        fixedMemoryGb: shape.fixedMemoryGb ?? null,
        productLabel: shape.productLabel || null,
        ocpuToVcpuRatio: shape.ocpuToVcpuRatio ?? null,
      };
    }
  }

  const denseIo = normalized.match(/\b(DENSEIO\.[EA]\d+\.FLEX)\b/i);
  if (denseIo) {
    const series = String(denseIo[1] || '').match(/([EA]\d+)\.FLEX/i)?.[1]?.toUpperCase() || null;
    if (series) {
      return {
        kind: 'flex',
        shapeName: `VM.DENSEIO.${series}.FLEX`,
        vendor: 'amd',
        family: 'denseio',
        series,
        ocpuToVcpuRatio: 2,
      };
    }
  }

  const optimized = normalized.match(/\b(OPTIMIZED3\.FLEX)\b/i);
  if (optimized) {
    return {
      kind: 'flex',
      shapeName: 'VM.OPTIMIZED3.FLEX',
      vendor: 'intel',
      family: 'optimized',
      series: 'X9',
      ocpuToVcpuRatio: 2,
    };
  }

  const standardFixed = normalized.match(/\b(STANDARD2\.(?:1|2|4|8|16|24))\b/i);
  if (standardFixed) {
    const normalizedName = `VM.${String(standardFixed[1] || '').toUpperCase()}`;
    const found = (shapes || []).find((shape) => String(shape.shapeName || '').toUpperCase() === normalizedName);
    if (found) {
      return {
        kind: found.kind,
        shapeName: String(found.shapeName || '').toUpperCase(),
        vendor: found.vendor,
        family: found.family,
        series: found.series,
        fixedOcpus: found.fixedOcpus ?? null,
        fixedMemoryGb: found.fixedMemoryGb ?? null,
        productLabel: found.productLabel || null,
        ocpuToVcpuRatio: found.ocpuToVcpuRatio ?? null,
      };
    }
  }

  const shorthand = normalized.match(/\b([EA]\d+)\.FLEX\b/);
  if (shorthand) {
    const series = shorthand[1];
    const vendor = series.startsWith('A') ? 'ampere' : 'amd';
    return {
      kind: 'flex',
      shapeName: `${series}.FLEX`,
      vendor,
      family: 'standard',
      series,
      ocpuToVcpuRatio: vendor === 'ampere' ? 1 : 2,
    };
  }

  return null;
}

function listFlexShapesByVendor(vendor) {
  const normalizedVendor = normalizeProcessorVendor(vendor);
  if (!normalizedVendor) return [];
  return (shapes || [])
    .filter((shape) => shape.kind === 'flex' && normalizeProcessorVendor(shape.vendor) === normalizedVendor)
    .map((shape) => ({
      kind: shape.kind,
      shapeName: String(shape.shapeName || '').toUpperCase(),
      vendor: normalizeProcessorVendor(shape.vendor),
      family: shape.family,
      series: shape.series,
      ocpuToVcpuRatio: shape.ocpuToVcpuRatio ?? null,
    }));
}

module.exports = {
  VM_SHAPES: shapes || [],
  findVmShapeByText,
  listFlexShapesByVendor,
  normalizeProcessorVendor,
};
