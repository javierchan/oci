'use strict';

const FLEX_SHAPE_TOKEN_PATTERN_SOURCE = '(?:(?:vm|bm)\\.)?(?:(?:[a-z][a-z0-9]*)\\.)*(?:[a-z]+\\d+|[a-z]\\d+)\\.flex';

function hasCompositeServiceSignal(text) {
  const source = String(text || '');
  return new RegExp(`${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}|\\b(?:vm|bm)\\.[a-z0-9.]+\\.\\d+\\b|\\bload balancer\\b|\\blb\\b|\\bblock storage\\b|\\bblock volumes?\\b|\\bobject storage\\b|\\bfile storage\\b|\\bfastconnect\\b|\\bfast connect\\b|\\bdns\\b|\\bapi gateway\\b|\\bweb application firewall\\b|\\bwaf\\b|\\bnetwork firewall\\b|\\bautonomous(?: ai)? lakehouse\\b|\\bautonomous data warehouse\\b|\\bbase database service\\b|\\bdata integration\\b|\\bintegration cloud\\b|\\boic\\b|\\banalytics cloud\\b|\\boac\\b|\\bdata safe\\b|\\blog analytics\\b|\\bfunctions\\b|\\bgenerative ai\\b|\\bvector store\\b|\\bweb search\\b|\\bagents data ingestion\\b|\\bmemory ingestion\\b|\\bexadata\\b|\\bdatabase cloud service\\b|\\bmonitoring\\b|\\bnotifications\\b|\\bhttps delivery\\b|\\bemail delivery\\b|\\biam sms\\b|\\bsms messages?\\b|\\bthreat intelligence\\b|\\bhealth checks?\\b|\\bfleet application management\\b|\\boci batch\\b|\\bvision\\b|\\bspeech\\b|\\bmedia flow\\b`, 'i').test(source);
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
  return new RegExp(`${FLEX_SHAPE_TOKEN_PATTERN_SOURCE}|\\bfunctions\\b|\\bfastconnect\\b|\\bfast connect\\b|\\bload balancer\\b|\\bfirewall\\b|\\bintegration cloud\\b|\\bworkspace usage\\b|\\bprocessed per hour\\b|\\bautonomous\\b|\\bexadata\\b|\\bdatabase cloud service\\b`, 'i').test(source);
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

module.exports = {
  hasCompositeServiceSignal,
  normalizeCompositeSegment,
  shouldAppendGlobalHours,
  splitCompositeQuoteSegments,
};
