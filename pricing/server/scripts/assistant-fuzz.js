'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_BASE_URL = 'http://localhost:8742';
const DEFAULT_COUNT = 1000;
const DEFAULT_CONCURRENCY = 2;
const DEFAULT_SEED = 20260410;
const DEFAULT_DELAY_MS = 400;
const DEFAULT_JITTER_MS = 250;
const DEFAULT_MAX_RETRIES = 2;
const DEFAULT_RETRY_BASE_MS = 1500;
const DEFAULT_RETRY_MAX_MS = 10000;

function parseArgs(argv) {
  const out = {
    baseUrl: DEFAULT_BASE_URL,
    count: DEFAULT_COUNT,
    concurrency: DEFAULT_CONCURRENCY,
    seed: DEFAULT_SEED,
    delayMs: DEFAULT_DELAY_MS,
    jitterMs: DEFAULT_JITTER_MS,
    maxRetries: DEFAULT_MAX_RETRIES,
    retryBaseMs: DEFAULT_RETRY_BASE_MS,
    retryMaxMs: DEFAULT_RETRY_MAX_MS,
    report: '',
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = argv[i + 1];
    if (arg === '--base-url' && next) {
      out.baseUrl = String(next).trim();
      i += 1;
    } else if (arg === '--count' && next) {
      out.count = Number(next);
      i += 1;
    } else if (arg === '--concurrency' && next) {
      out.concurrency = Number(next);
      i += 1;
    } else if (arg === '--seed' && next) {
      out.seed = Number(next);
      i += 1;
    } else if (arg === '--delay-ms' && next) {
      out.delayMs = Number(next);
      i += 1;
    } else if (arg === '--jitter-ms' && next) {
      out.jitterMs = Number(next);
      i += 1;
    } else if (arg === '--max-retries' && next) {
      out.maxRetries = Number(next);
      i += 1;
    } else if (arg === '--retry-base-ms' && next) {
      out.retryBaseMs = Number(next);
      i += 1;
    } else if (arg === '--retry-max-ms' && next) {
      out.retryMaxMs = Number(next);
      i += 1;
    } else if (arg === '--report' && next) {
      out.report = String(next).trim();
      i += 1;
    }
  }
  if (!Number.isFinite(out.count) || out.count <= 0) out.count = DEFAULT_COUNT;
  if (!Number.isFinite(out.concurrency) || out.concurrency <= 0) out.concurrency = DEFAULT_CONCURRENCY;
  if (!Number.isFinite(out.seed)) out.seed = DEFAULT_SEED;
  if (!Number.isFinite(out.delayMs) || out.delayMs < 0) out.delayMs = DEFAULT_DELAY_MS;
  if (!Number.isFinite(out.jitterMs) || out.jitterMs < 0) out.jitterMs = DEFAULT_JITTER_MS;
  if (!Number.isFinite(out.maxRetries) || out.maxRetries < 0) out.maxRetries = DEFAULT_MAX_RETRIES;
  if (!Number.isFinite(out.retryBaseMs) || out.retryBaseMs <= 0) out.retryBaseMs = DEFAULT_RETRY_BASE_MS;
  if (!Number.isFinite(out.retryMaxMs) || out.retryMaxMs <= 0) out.retryMaxMs = DEFAULT_RETRY_MAX_MS;
  return out;
}

function mulberry32(seed) {
  let t = seed >>> 0;
  return function rand() {
    t += 0x6D2B79F5;
    let x = t;
    x = Math.imul(x ^ (x >>> 15), x | 1);
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

function pick(rand, items) {
  return items[Math.floor(rand() * items.length)];
}

function int(rand, min, max) {
  return Math.floor(rand() * (max - min + 1)) + min;
}

function chance(rand, value) {
  return rand() < value;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function shuffle(rand, items) {
  const copy = items.slice();
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rand() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function normalizeLabel(value) {
  return String(value || '').trim().toLowerCase();
}

function extractPartNumbers(blob) {
  const matches = String(blob || '').match(/\bB\d{5,6}\b/g) || [];
  return Array.from(new Set(matches));
}

function lowerIncludesAll(haystack, needles) {
  const source = normalizeLabel(haystack);
  return needles.every((needle) => source.includes(normalizeLabel(needle)));
}

function createDiscoveryScenario(id, weight, factory) {
  return { id, weight, kind: 'discovery', factory };
}

function createQuoteScenario(id, weight, factory) {
  return { id, weight, kind: 'quote', factory };
}

function buildScenarioCatalog() {
  return [
    createDiscoveryScenario('oic_generic_discovery', 8, (rand) => ({
      prompt: pick(rand, [
        "Cuales son los SKU's requeridos en una quote de OIC?",
        'Que SKUs necesito para cotizar Oracle Integration Cloud?',
        'Como se compone una quote de Oracle Integration Cloud?',
      ]),
      expectedFamily: 'integration_oic',
      expectedPartNumbers: ['B89639', 'B89643', 'B89640', 'B89644'],
      minPartMatches: 2,
    })),
    createDiscoveryScenario('vm_generic_discovery', 8, (rand) => ({
      prompt: pick(rand, [
        "Cuales son los SKU's requeridos en una quote de Virtual Machines (Instances)?",
        'Que necesito para cotizar OCI Virtual Machines?',
        'Como se arma una quote de Compute Virtual Machine en OCI?',
      ]),
      expectedFamily: 'compute_vm_generic',
      requiredGuidance: ['ocpus', 'memory', 'shape'],
    })),
    createDiscoveryScenario('load_balancer_discovery', 10, (_rand) => ({
      prompt: "Cuales son los SKU's requeridos en una quote de Flexible Load Balancer?",
      expectedFamily: 'network_load_balancer',
      expectedPartNumbers: ['B93030', 'B93031'],
      minPartMatches: 2,
    })),
    createDiscoveryScenario('functions_discovery', 10, (_rand) => ({
      prompt: "Cuales son los SKU's requeridos en una quote de OCI Functions?",
      expectedFamily: 'serverless_functions',
      expectedPartNumbers: ['B90617', 'B90618'],
      minPartMatches: 2,
    })),
    createDiscoveryScenario('block_volume_discovery', 8, (_rand) => ({
      prompt: "Cuales son los SKU's requeridos en una quote de OCI Block Volume?",
      expectedFamily: 'storage_block',
      expectedPartNumbers: ['B91961', 'B91962'],
      minPartMatches: 2,
    })),
    createDiscoveryScenario('file_storage_discovery', 8, (_rand) => ({
      prompt: "Cuales son los SKU's requeridos en una quote de OCI File Storage?",
      expectedFamily: 'storage_file',
      expectedPartNumbers: ['B89057', 'B109546'],
      minPartMatches: 2,
    })),
    createDiscoveryScenario('base_db_discovery', 6, (_rand) => ({
      prompt: "Cuales son los SKU's requeridos en una quote de Base Database Service?",
      expectedFamily: 'database_base_db',
      expectedPartNumbers: ['B90570', 'B90573', 'B111584'],
      minPartMatches: 2,
    })),
    createDiscoveryScenario('lakehouse_discovery', 6, (_rand) => ({
      prompt: "Cuales son los SKU's requeridos en una quote de Autonomous AI Lakehouse?",
      expectedFamily: 'database_autonomous_dw',
      expectedPartNumbers: ['B95701', 'B95703', 'B95706'],
      minPartMatches: 2,
    })),
    createDiscoveryScenario('exascale_discovery', 6, (_rand) => ({
      prompt: "Cuales son los SKU's requeridos en una quote de Exadata Exascale?",
      expectedFamily: 'database_exadata_exascale',
      expectedPartNumbers: ['B109356', 'B107951', 'B107952'],
      minPartMatches: 2,
    })),
    createDiscoveryScenario('network_firewall_discovery', 6, (_rand) => ({
      prompt: "Cuales son los SKU's requeridos en una quote de OCI Network Firewall?",
      expectedFamily: 'network_firewall',
      expectedPartNumbers: ['B95403', 'B95404'],
      minPartMatches: 2,
    })),
    createDiscoveryScenario('waf_discovery', 6, (_rand) => ({
      prompt: "Cuales son los SKU's requeridos en una quote de Web Application Firewall?",
      expectedFamily: 'security_waf',
      expectedPartNumbers: ['B94579', 'B94277'],
      minPartMatches: 2,
    })),
    createQuoteScenario('load_balancer_quote', 12, (rand) => ({
      prompt: `Quote Flexible Load Balancer ${pick(rand, [50, 100, 150, 200, 300, 500])} Mbps`,
      expectedPartNumbers: ['B93030', 'B93031'],
    })),
    createQuoteScenario('functions_quote', 12, (rand) => ({
      prompt: `Quote OCI Functions ${pick(rand, [1000000, 2000000, 3100000, 5000000])} invocations per month ${pick(rand, [1000, 2000, 5000, 30000])} ms per invocation ${pick(rand, [128, 256, 512])} MB memory`,
      expectedPartNumbers: ['B90617', 'B90618'],
    })),
    createQuoteScenario('block_volume_quote', 10, (rand) => ({
      prompt: `Quote Block Volume ${pick(rand, [400, 750, 1000, 3000, 6279])} GB with ${pick(rand, [10, 20, 30])} VPUs`,
      expectedPartNumbers: ['B91961', 'B91962'],
    })),
    createQuoteScenario('file_storage_quote', 10, (rand) => ({
      prompt: `Quote File Storage ${pick(rand, [2, 5, 10])} TB and ${pick(rand, [5, 10, 20])} performance units per GB per month`,
      expectedPartNumbers: ['B89057', 'B109546'],
    })),
    createQuoteScenario('waf_quote', 8, (rand) => ({
      prompt: `Quote Web Application Firewall with ${pick(rand, [1, 2, 3])} instances and ${pick(rand, [25000000, 50000000, 100000000])} requests per month`,
      expectedPartNumbers: ['B94579', 'B94277'],
    })),
    createQuoteScenario('network_firewall_quote', 8, (rand) => ({
      prompt: `Quote Network Firewall ${pick(rand, [1, 2, 3])} firewalls and ${pick(rand, [5000, 10000, 20000])} GB data processed per month`,
      expectedPartNumbers: ['B95403', 'B95404'],
    })),
    createQuoteScenario('base_db_quote', 8, (rand) => {
      const byol = chance(rand, 0.5);
      return {
        prompt: `Quote Base Database Service Enterprise ${byol ? 'BYOL' : 'License Included'} ${pick(rand, [4, 8])} OCPUs and ${pick(rand, [500, 1000, 2000])} GB storage`,
        expectedPartNumbers: [byol ? 'B90573' : 'B90570', 'B111584'],
      };
    }),
    createQuoteScenario('lakehouse_quote', 8, (rand) => {
      const byol = chance(rand, 0.5);
      return {
        prompt: `Quote Autonomous AI Lakehouse ${byol ? 'BYOL' : 'License Included'} ${pick(rand, [2, 4, 8])} ECPUs and ${pick(rand, [100, 500, 2000])} GB storage per month`,
        expectedPartNumbers: [byol ? 'B95703' : 'B95701', 'B95706'],
      };
    }),
    createQuoteScenario('exascale_quote', 8, (rand) => ({
      prompt: `Quote Exadata Exascale License Included ${pick(rand, [4, 8])} ECPUs and ${pick(rand, [1000, 2000])} GB filesystem storage`,
      expectedPartNumbers: ['B109356', 'B107951'],
    })),
    createQuoteScenario('serverless_edge_bundle', 10, (rand) => ({
      prompt: `Quote OCI Functions ${pick(rand, [1000000, 2000000, 3100000])} invocations per month ${pick(rand, [2000, 5000, 30000])} ms per invocation ${pick(rand, [128, 256])} MB memory plus API Gateway ${pick(rand, [3000000, 5000000])} API calls per month plus DNS ${pick(rand, [3000000, 5000000])} queries per month`,
      expectedPartNumbers: ['B90617', 'B90618', 'B92072', 'B88525'],
    })),
    createQuoteScenario('secure_edge_bundle', 10, (rand) => ({
      prompt: `Quote Flexible Load Balancer ${pick(rand, [100, 200, 300])} Mbps plus Web Application Firewall with ${pick(rand, [2, 3])} instances and ${pick(rand, [50000000, 100000000])} requests per month plus DNS ${pick(rand, [4000000, 5000000])} queries per month plus Health Checks ${pick(rand, [5, 10])} endpoints`,
      expectedPartNumbers: ['B93030', 'B93031', 'B94579', 'B94277', 'B88525', 'B90323', 'B90325'],
      minPartMatches: 6,
    })),
    createQuoteScenario('integration_storage_bundle', 8, (rand) => {
      const edition = pick(rand, ['Standard', 'Enterprise']);
      const analytics = pick(rand, ['Professional', 'Enterprise']);
      const bundle = pick(rand, ['object_lb', 'file_fastconnect']);
      const prompt = bundle === 'object_lb'
        ? `Quote Oracle Integration Cloud ${edition} License Included ${pick(rand, [2, 3])} instances 744h/month plus Oracle Analytics Cloud ${analytics} ${analytics === 'Professional' ? '25 users' : '50 users'} plus Object Storage 10 TB per month plus Flexible Load Balancer 100 Mbps`
        : `Quote Oracle Integration Cloud ${edition} License Included ${pick(rand, [2, 3])} instances 744h/month plus Oracle Analytics Cloud ${analytics} ${analytics === 'Professional' ? '25 users' : '50 users'} plus File Storage 5 TB and 10 performance units per GB per month plus FastConnect 10 Gbps`;
      return {
        prompt,
        expectedPartNumbers: bundle === 'object_lb'
          ? [edition === 'Standard' ? 'B89639' : 'B89640', analytics === 'Professional' ? 'B92682' : 'B92683', 'B91628', 'B93030', 'B93031']
          : [edition === 'Standard' ? 'B89639' : 'B89640', analytics === 'Professional' ? 'B92682' : 'B92683', 'B89057', 'B109546', 'B88326'],
      };
    }),
    createQuoteScenario('lakehouse_bundle', 8, (rand) => {
      const branch = pick(rand, ['object_storage', 'fastconnect_monitoring']);
      return {
        prompt: branch === 'object_storage'
          ? 'Quote Autonomous AI Lakehouse BYOL 8 ECPUs and 2000 GB storage per month plus Data Integration 500 GB processed per hour for 744h/month plus Object Storage 20 TB per month'
          : 'Quote Autonomous AI Lakehouse BYOL 8 ECPUs and 2000 GB storage per month plus Data Integration 500 GB processed per hour for 744h/month plus FastConnect 10 Gbps plus Monitoring Ingestion 2500000 datapoints',
        expectedPartNumbers: branch === 'object_storage'
          ? ['B95703', 'B95706', 'B92599', 'B91628']
          : ['B95703', 'B95706', 'B92599', 'B88326', 'B90925'],
      };
    }),
    createQuoteScenario('exascale_storage_bundle', 6, (_rand) => ({
      prompt: 'Quote Exadata Exascale License Included 4 ECPUs and 1000 GB filesystem storage plus File Storage 5 TB and 10 performance units per GB per month plus DNS 5000000 queries per month',
      expectedPartNumbers: ['B109356', 'B107951', 'B89057', 'B109546', 'B88525'],
    })),
  ];
}

function buildScenarioSequence(rand, count) {
  const catalog = buildScenarioCatalog();
  const weighted = [];
  for (const scenario of catalog) {
    for (let i = 0; i < scenario.weight; i += 1) weighted.push(scenario);
  }
  const sequence = [];
  for (let i = 0; i < count; i += 1) {
    const template = pick(rand, weighted);
    const built = template.factory(rand);
    sequence.push({
      id: `${template.id}#${i + 1}`,
      templateId: template.id,
      kind: template.kind,
      ...built,
    });
  }
  return sequence;
}

async function postAssistant(baseUrl, clientId, prompt) {
  const response = await fetch(`${baseUrl}/api/assistant`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-client-id': clientId,
    },
    body: JSON.stringify({ text: prompt }),
  });
  const text = await response.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch (error) {
    throw new Error(`Invalid JSON response (${response.status}): ${text.slice(0, 300)}`);
  }
  return { status: response.status, payload };
}

function detectThrottleSignal(result, error) {
  const status = Number(result?.status || 0);
  if (status === 429 || status === 503) return true;
  const payload = result?.payload || {};
  const fragments = [
    payload.error,
    payload.message,
    payload.details,
    error?.message,
  ]
    .filter(Boolean)
    .map((value) => normalizeLabel(value));
  return fragments.some((value) => (
    value.includes('throttl')
    || value.includes('rate limit')
    || value.includes('request limit is exceeded')
    || value.includes('too many requests')
  ));
}

async function postAssistantWithRetry(options, rand, clientId, prompt) {
  let attempt = 0;
  let lastError = null;

  while (attempt <= options.maxRetries) {
    const delayMs = options.delayMs + (options.jitterMs > 0 ? int(rand, 0, options.jitterMs) : 0);
    if (delayMs > 0) await sleep(delayMs);

    try {
      const result = await postAssistant(options.baseUrl, clientId, prompt);
      if (!detectThrottleSignal(result, null) || attempt >= options.maxRetries) {
        return {
          ...result,
          requestMeta: {
            attempts: attempt + 1,
            throttledRetries: attempt,
          },
        };
      }
      const retryDelay = Math.min(options.retryBaseMs * (2 ** attempt), options.retryMaxMs);
      await sleep(retryDelay + (options.jitterMs > 0 ? int(rand, 0, options.jitterMs) : 0));
    } catch (error) {
      lastError = error;
      if (!detectThrottleSignal(null, error) || attempt >= options.maxRetries) throw error;
      const retryDelay = Math.min(options.retryBaseMs * (2 ** attempt), options.retryMaxMs);
      await sleep(retryDelay + (options.jitterMs > 0 ? int(rand, 0, options.jitterMs) : 0));
    }

    attempt += 1;
  }

  throw lastError || new Error('Assistant request failed after retries');
}

function validateDiscovery(result, scenario) {
  const errors = [];
  const payload = result.payload || {};
  if (result.status !== 200) errors.push(`HTTP ${result.status}`);
  if (!payload.ok) errors.push(`payload.ok=false (${payload.error || 'unknown error'})`);
  if (payload.mode !== 'answer') errors.push(`expected mode=answer but got ${payload.mode || 'unknown'}`);
  if (String(payload.intent?.route || '') !== 'product_discovery') {
    errors.push(`expected intent.route=product_discovery but got ${payload.intent?.route || 'unknown'}`);
  }
  if (payload.intent?.shouldQuote !== false) {
    errors.push(`expected intent.shouldQuote=false but got ${String(payload.intent?.shouldQuote)}`);
  }
  const actualFamily = String(payload.contextPackSummary?.family?.id || payload.intent?.serviceFamily || '');
  if (scenario.expectedFamily && actualFamily !== scenario.expectedFamily) {
    errors.push(`expected family ${scenario.expectedFamily} but got ${actualFamily || 'none'}`);
  }
  if (Array.isArray(scenario.requiredGuidance) && scenario.requiredGuidance.length) {
    const labels = [
      ...(Array.isArray(payload.contextPackSummary?.family?.requiredInputGuidance)
        ? payload.contextPackSummary.family.requiredInputGuidance
        : []),
    ].map(normalizeLabel);
    for (const required of scenario.requiredGuidance) {
      if (!labels.some((label) => label.includes(normalizeLabel(required)))) {
        errors.push(`missing required guidance token ${required}`);
      }
    }
  }
  if (Array.isArray(scenario.expectedPartNumbers) && scenario.expectedPartNumbers.length) {
    const found = extractPartNumbers(payload.message);
    const minMatches = Number.isFinite(Number(scenario.minPartMatches))
      ? Number(scenario.minPartMatches)
      : scenario.expectedPartNumbers.length;
    const matchCount = scenario.expectedPartNumbers.filter((part) => found.includes(part)).length;
    if (matchCount < minMatches) {
      errors.push(`expected at least ${minMatches} part numbers in discovery answer but found ${matchCount} (${found.join(', ') || 'none'})`);
    }
  }
  return errors;
}

function validateQuote(result, scenario) {
  const errors = [];
  const payload = result.payload || {};
  if (result.status !== 200) errors.push(`HTTP ${result.status}`);
  if (!payload.ok) errors.push(`payload.ok=false (${payload.error || 'unknown error'})`);
  if (payload.mode !== 'quote') errors.push(`expected mode=quote but got ${payload.mode || 'unknown'}`);
  if (!payload.quote?.ok) errors.push('quote.ok=false');
  const actualParts = Array.isArray(payload.quote?.lineItems)
    ? Array.from(new Set(payload.quote.lineItems.map((line) => String(line.partNumber || '')).filter(Boolean)))
    : [];
  const minMatches = Number.isFinite(Number(scenario.minPartMatches))
    ? Number(scenario.minPartMatches)
    : (Array.isArray(scenario.expectedPartNumbers) ? scenario.expectedPartNumbers.length : 0);
  const matchCount = (scenario.expectedPartNumbers || []).filter((part) => actualParts.includes(part)).length;
  if (matchCount < minMatches) {
    errors.push(`expected at least ${minMatches} quote part numbers but found ${matchCount} (${actualParts.join(', ') || 'none'})`);
  }
  return errors;
}

function summarizeFailure(scenario, result, errors) {
  return {
    id: scenario.id,
    templateId: scenario.templateId,
    kind: scenario.kind,
    prompt: scenario.prompt,
    errors,
    status: result.status,
    mode: result.payload?.mode || '',
    route: result.payload?.intent?.route || '',
    family: result.payload?.contextPackSummary?.family?.id || result.payload?.intent?.serviceFamily || '',
    partNumbersInMessage: extractPartNumbers(result.payload?.message || ''),
    quotePartNumbers: Array.isArray(result.payload?.quote?.lineItems)
      ? Array.from(new Set(result.payload.quote.lineItems.map((line) => line.partNumber).filter(Boolean)))
      : [],
    messagePreview: String(result.payload?.message || '').slice(0, 500),
  };
}

async function runSequence(options) {
  const rand = mulberry32(options.seed);
  const sequence = buildScenarioSequence(rand, options.count);
  const failures = [];
  const templateStats = new Map();
  let cursor = 0;
  let completed = 0;
  let throttledRetries = 0;
  let hardThrottleFailures = 0;
  const clientId = `assistant-fuzz-${options.seed}`;

  async function worker() {
    while (true) {
      const current = cursor;
      cursor += 1;
      if (current >= sequence.length) return;
      const scenario = sequence[current];
      let result;
      try {
        result = await postAssistantWithRetry(options, rand, clientId, scenario.prompt);
      } catch (error) {
        hardThrottleFailures += detectThrottleSignal(null, error) ? 1 : 0;
        result = {
          status: 599,
          payload: {
            ok: false,
            mode: 'error',
            error: error.message || String(error),
          },
          requestMeta: {
            attempts: options.maxRetries + 1,
            throttledRetries: detectThrottleSignal(null, error) ? options.maxRetries : 0,
          },
        };
      }
      throttledRetries += Number(result.requestMeta?.throttledRetries || 0);
      const errors = scenario.kind === 'discovery'
        ? validateDiscovery(result, scenario)
        : validateQuote(result, scenario);
      const stat = templateStats.get(scenario.templateId) || { total: 0, failed: 0 };
      stat.total += 1;
      if (errors.length) {
        stat.failed += 1;
        failures.push(summarizeFailure(scenario, result, errors));
      }
      templateStats.set(scenario.templateId, stat);
      completed += 1;
      if (completed % 50 === 0 || completed === sequence.length) {
        process.stdout.write(`Completed ${completed}/${sequence.length} tests. Failures so far: ${failures.length}. Throttled retries: ${throttledRetries}\n`);
      }
    }
  }

  const workers = [];
  for (let i = 0; i < options.concurrency; i += 1) workers.push(worker());
  await Promise.all(workers);

  const stats = Array.from(templateStats.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([templateId, stat]) => ({
      templateId,
      total: stat.total,
      failed: stat.failed,
      passed: stat.total - stat.failed,
      failureRate: stat.total ? Number((stat.failed / stat.total).toFixed(4)) : 0,
    }));

  return {
    ok: failures.length === 0,
    seed: options.seed,
    count: sequence.length,
    concurrency: options.concurrency,
    delayMs: options.delayMs,
    jitterMs: options.jitterMs,
    maxRetries: options.maxRetries,
    throttledRetries,
    hardThrottleFailures,
    baseUrl: options.baseUrl,
    failures,
    stats,
    generatedAt: new Date().toISOString(),
  };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const reportPath = options.report || path.join('/tmp', `assistant-fuzz-${options.seed}-${Date.now()}.json`);
  const report = await runSequence(options);
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);

  console.log('\nAssistant fuzz summary');
  console.log(`- Base URL: ${report.baseUrl}`);
  console.log(`- Seed: ${report.seed}`);
  console.log(`- Count: ${report.count}`);
  console.log(`- Concurrency: ${report.concurrency}`);
  console.log(`- Delay: ${report.delayMs}ms + jitter ${report.jitterMs}ms`);
  console.log(`- Max retries: ${report.maxRetries}`);
  console.log(`- Failures: ${report.failures.length}`);
  console.log(`- Throttled retries: ${report.throttledRetries}`);
  console.log(`- Hard throttle failures: ${report.hardThrottleFailures}`);
  console.log(`- Report: ${reportPath}`);

  const topFailures = report.stats
    .filter((item) => item.failed > 0)
    .sort((a, b) => b.failed - a.failed)
    .slice(0, 10);
  if (topFailures.length) {
    console.log('- Failing templates:');
    for (const item of topFailures) {
      console.log(`  - ${item.templateId}: ${item.failed}/${item.total}`);
    }
  }

  if (report.failures.length) {
    console.log('\nSample failures:');
    for (const failure of report.failures.slice(0, 10)) {
      console.log(`- ${failure.templateId}`);
      console.log(`  Prompt: ${failure.prompt}`);
      console.log(`  Errors: ${failure.errors.join(' | ')}`);
      console.log(`  Family: ${failure.family || 'none'} | Mode: ${failure.mode || 'unknown'} | Route: ${failure.route || 'unknown'}`);
    }
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
