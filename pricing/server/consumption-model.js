'use strict';

function inferConsumptionPattern(metricName, serviceName) {
  const metric = String(metricName || '').toLowerCase();
  const service = String(serviceName || '').toLowerCase();
  if (!metric && !service) return 'unknown';
  if (metric.includes('port hour')) return 'port-hour';
  if (metric.includes('load balancer hour')) return 'load-balancer-hour';
  if (metric.includes('mbps per hour')) return 'bandwidth-mbps-hour';
  if (metric.includes('gigabyte storage capacity per month')) return 'capacity-gb-month';
  if (metric.includes('gigabyte (gb) of data processed')) return 'data-processed-gb-month';
  if (metric.includes('logging analytics storage unit per month')) return 'log-analytics-storage-unit-month';
  if (metric.includes('workspace usage per hour')) return 'workspace-hour';
  if (metric.includes('gigabyte of data processed per hour')) return 'data-processed-gb-hour';
  if (metric.includes('execution hour')) return 'execution-hour-utilized';
  if (metric.includes('training hour')) return 'utilized-hour';
  if (metric.includes('transcription hour')) return 'utilized-hour';
  if (metric.includes('performance units per gigabyte per month')) return 'performance-units-per-gb-month';
  if (metric.includes('10,000 gb memory-seconds')) return 'functions-gb-memory-seconds';
  if (metric.includes('1mil function invocations')) return 'functions-invocations-million';
  if (metric.includes('processed video minute')) return 'media-output-minute';
  if (metric.includes('minute of output media content')) return 'media-output-minute';
  if (metric === 'each') return 'count-each';
  if (metric.includes('managed resource per month')) return 'count-each';
  if (metric.includes('target database per month')) return 'count-each';
  if (metric.includes('endpoints per month')) return 'count-each';
  if (metric.includes('ocpu per hour')) return 'ocpu-hour';
  if (metric.includes('ecpu per hour')) return 'ecpu-hour';
  if (metric.includes('gb ram per hour') || (metric.includes('memory') && metric.includes('hour'))) return 'memory-gb-hour';
  if (metric.includes('user per month') || metric.includes('named user')) return 'users-per-month';
  if (
    metric.includes('api calls') ||
    metric.includes('requests') ||
    metric.includes('invocations') ||
    metric.includes('queries') ||
    metric.includes('transactions') ||
    metric.includes('emails sent') ||
    metric.includes('sms message') ||
    metric.includes('tokens') ||
    metric.includes('datapoints') ||
    metric.includes('delivery operations') ||
    metric.includes('events') ||
    metric === 'request' ||
    metric === 'token'
  ) return 'requests';
  if (
    metric.includes('training hour') ||
    metric.includes('transcription hour') ||
    metric.includes('migration hour') ||
    metric.includes('cluster hour')
  ) return 'generic-hourly';
  if (
    metric.includes('processed video minute') ||
    metric.includes('minute of output media content')
  ) return 'generic-monthly';
  if (metric.includes('per hour')) return 'generic-hourly';
  if (metric.includes('per month')) return 'generic-monthly';
  if (service.includes('functions')) return 'functions';
  return 'unknown';
}

function explainConsumptionPattern(pattern, product) {
  const name = product?.displayName || product?.fullDisplayName || 'this service';
  switch (pattern) {
    case 'port-hour':
      return `${name} is billed by port-hour. One provisioned port for 744 hours equals 744 billable port-hours in a standard month.`;
    case 'load-balancer-hour':
      return `${name} is billed by load balancer-hour. One active load balancer for 744 hours equals 744 billable hours in a standard month.`;
    case 'bandwidth-mbps-hour':
      return `${name} is billed by configured bandwidth in Mbps per hour. The requested Mbps value is multiplied by the hours in the month.`;
    case 'capacity-gb-month':
      return `${name} is billed by provisioned storage capacity in GB-month. The requested GB or TB value is converted to monthly storage units.`;
    case 'data-processed-gb-month':
      return `${name} is billed by GB of data processed in the month. The agent uses monthly processed traffic volume directly as the billable quantity.`;
    case 'log-analytics-storage-unit-month':
      return `${name} is billed by Log Analytics storage units per month. The agent applies the first 10 GB free, converts remaining storage at 300 GB per storage unit, and enforces the documented 1-unit minimum for billable usage.`;
    case 'workspace-hour':
      return `${name} is billed by workspace-hour. The requested workspace count is multiplied by active monthly hours.`;
    case 'data-processed-gb-hour':
      return `${name} is billed by GB of data processed per hour. The requested hourly data volume is multiplied by monthly hours.`;
    case 'execution-hour-utilized':
      return `${name} is billed by utilized execution hours. The monthly execution-hour quantity is billed directly without multiplying by monthly uptime again.`;
    case 'utilized-hour':
      return `${name} is billed by consumed service hours. The requested hour quantity is billed directly and is not multiplied by monthly uptime again.`;
    case 'performance-units-per-gb-month':
      return `${name} is billed as performance units per GB-month. The agent multiplies storage capacity by the requested VPU density.`;
    case 'functions-gb-memory-seconds':
      return `${name} is billed in 10,000 GB Memory-Seconds. The agent calculates invocations × execution seconds × memory in GB, then converts to billable units.`;
    case 'functions-invocations-million':
      return `${name} is billed in millions of function invocations. The agent converts monthly invocation volume into 1M-invocation units.`;
    case 'media-output-minute':
      return `${name} is billed by output or processed media minutes. The requested minute count is used directly as the billable quantity.`;
    case 'count-each':
      return `${name} is billed as a direct counted quantity. The requested item count is used directly as the billable quantity without multiplying by monthly uptime.`;
    case 'ocpu-hour':
      return `${name} is billed by OCPU-hour. The requested OCPU count is multiplied by the hours in the month.`;
    case 'ecpu-hour':
      return `${name} is billed by ECPU-hour. The requested ECPU count is multiplied by the hours in the month.`;
    case 'memory-gb-hour':
      return `${name} is billed by memory GB-hour. The requested memory quantity is multiplied by the hours in the month.`;
    case 'users-per-month':
      return `${name} is billed by active users per month. The requested user count is used directly as the monthly billable quantity.`;
    case 'requests':
      return `${name} is billed by request volume. The agent converts the request count into the request unit defined by the SKU metric.`;
    case 'generic-hourly':
      return `${name} is billed hourly. The requested quantity is multiplied by the monthly hour assumption when the SKU is hourly.`;
    case 'generic-monthly':
      return `${name} is billed monthly. The requested quantity maps directly to the SKU metric for the month.`;
    default:
      return `${name} uses the OCI catalog metric attached to the SKU.`;
  }
}

function inferQuantityForPattern(pattern, product, request) {
  const source = String(request?.source || '');
  const metric = String(product?.metricDisplayName || '').toLowerCase();
  switch (pattern) {
    case 'port-hour':
    case 'load-balancer-hour':
    case 'generic-hourly':
      return 1;
    case 'bandwidth-mbps-hour': {
      const mbps = parseBandwidthMbps(source);
      return Number.isFinite(mbps) ? mbps : null;
    }
    case 'capacity-gb-month': {
      const gb = parseCapacityGb(source);
      return Number.isFinite(gb) ? gb : null;
    }
    case 'data-processed-gb-month': {
      const gb = parseDataProcessedGb(source);
      return Number.isFinite(gb) ? gb : null;
    }
    case 'log-analytics-storage-unit-month': {
      const gb = parseCapacityGb(source);
      if (!Number.isFinite(gb)) return null;
      const billableGb = Math.max(0, gb - 10);
      return billableGb <= 0 ? 0 : Math.max(1, billableGb / 300);
    }
    case 'workspace-hour': {
      const workspaces = parseLabeledNumber(source, [/(\d[\d,]*(?:\.\d+)?)\s*workspaces?\b/i]) || 1;
      return workspaces;
    }
    case 'data-processed-gb-hour': {
      const gb = parseDataProcessedGb(source) || parseCapacityGb(source);
      return Number.isFinite(gb) ? gb : null;
    }
    case 'execution-hour-utilized': {
      return parseLabeledNumber(source, [/(\d[\d,]*(?:\.\d+)?)\s*execution hours?\b/i]);
    }
    case 'utilized-hour': {
      return parseLabeledNumber(source, [
        /(\d[\d,]*(?:\.\d+)?)\s*(?:training|transcription)\s*hours?\b/i,
        /(\d[\d,]*(?:\.\d+)?)\s*hours?\b/i,
      ]);
    }
    case 'performance-units-per-gb-month': {
      const gb = parseCapacityGb(source);
      const vpu = parseVpuPerGb(source);
      if (!Number.isFinite(gb) || !Number.isFinite(vpu)) return null;
      return gb * vpu;
    }
    case 'ocpu-hour':
      return parseLabeledNumber(source, [/(\d[\d,]*(?:\.\d+)?)\s*ocpus?\b/i]);
    case 'ecpu-hour':
      return parseLabeledNumber(source, [/(\d[\d,]*(?:\.\d+)?)\s*ecpus?\b/i]);
    case 'memory-gb-hour':
      return parseMemoryGb(source);
    case 'users-per-month':
      return parseLabeledNumber(source, [/(\d[\d,]*(?:\.\d+)?)\s*(?:users?|named users?)\b/i]) || request?.quantity || null;
    case 'requests': {
      const requests = parseLabeledNumber(source, [
        /(\d[\d,]*(?:\.\d+)?)\s*(?:requests?|api calls?|invocations?|queries?|transactions?|emails?|messages?|sms(?: messages?)?|tokens?|datapoints?|events?|delivery operations?)\b/i,
      ]);
      if (!Number.isFinite(requests)) return null;
      const divisor = inferRequestMetricDivisor(metric);
      if (divisor > 1) return requests / divisor;
      return requests;
    }
    case 'count-each':
      return parseLabeledNumber(source, [
        /(\d[\d,]*(?:\.\d+)?)\s*(?:(?:managed|target)\s+)?(?:databases?|devices?|stations?|jobs?|resources?|nodes?|clusters?|models?|endpoints?)\b/i,
      ]) || request?.quantity || null;
    case 'generic-monthly':
    case 'media-output-minute':
      return request?.quantity || null;
    default:
      return null;
  }
}

function inferRequestMetricDivisor(metric) {
  const source = String(metric || '').toLowerCase();
  if (!source) return 1;
  if (/\b1,?000,?000\b/.test(source) || /\b1mil\b/.test(source) || /\bmillion\b/.test(source)) return 1000000;
  if (/\b10,?000\b/.test(source)) return 10000;
  if (/\b1,?000\b/.test(source)) return 1000;
  return 1;
}

function parseLabeledNumber(source, patterns) {
  for (const pattern of patterns) {
    const match = String(source || '').match(pattern);
    if (match) return Number(String(match[1]).replace(/,/g, ''));
  }
  return null;
}

function parseBandwidthMbps(source) {
  const match = String(source || '').match(/(\d[\d,]*(?:\.\d+)?)\s*(m|g)bps?\b/i);
  if (!match) return null;
  const value = Number(String(match[1]).replace(/,/g, ''));
  if (!Number.isFinite(value)) return null;
  return match[2].toLowerCase() === 'g' ? value * 1000 : value;
}

function parseCapacityGb(source) {
  const match = String(source || '').match(/(\d[\d,]*(?:\.\d+)?)\s*(tb|gb)\b/i);
  if (!match) return null;
  const value = Number(String(match[1]).replace(/,/g, ''));
  if (!Number.isFinite(value)) return null;
  return match[2].toLowerCase() === 'tb' ? value * 1024 : value;
}

function parseVpuPerGb(source) {
  const direct = String(source || '').match(/(\d[\d,]*(?:\.\d+)?)\s*vpu'?s?\b/i);
  if (!direct) return null;
  const value = Number(String(direct[1]).replace(/,/g, ''));
  return Number.isFinite(value) ? value : null;
}

function parseDataProcessedGb(source) {
  const direct = String(source || '').match(/(\d[\d,]*(?:\.\d+)?)\s*gb\b[^\n,.;]*data processed/i);
  if (direct) {
    const value = Number(String(direct[1]).replace(/,/g, ''));
    return Number.isFinite(value) ? value : null;
  }
  const reverse = String(source || '').match(/data processed[^\d]*(\d[\d,]*(?:\.\d+)?)\s*gb\b/i);
  if (reverse) {
    const value = Number(String(reverse[1]).replace(/,/g, ''));
    return Number.isFinite(value) ? value : null;
  }
  return null;
}

function parseMemoryGb(source) {
  const gbMatch = String(source || '').match(/(\d[\d,]*(?:\.\d+)?)\s*gb\s*(?:ram|memory)?\b/i);
  if (gbMatch) {
    const value = Number(String(gbMatch[1]).replace(/,/g, ''));
    return Number.isFinite(value) ? value : null;
  }
  const mbMatch = String(source || '').match(/(\d[\d,]*(?:\.\d+)?)\s*mb\s*(?:ram|memory)?\b/i);
  if (mbMatch) {
    const value = Number(String(mbMatch[1]).replace(/,/g, ''));
    return Number.isFinite(value) ? value / 1024 : null;
  }
  return null;
}

module.exports = {
  inferConsumptionPattern,
  explainConsumptionPattern,
  inferQuantityForPattern,
};
