'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_BASE_URL = 'http://localhost:8742';
const DEFAULT_COUNT = 100;
const DEFAULT_CONCURRENCY = 1;
const DEFAULT_SEED = 20260410;
const DEFAULT_DELAY_MS = 800;
const DEFAULT_JITTER_MS = 300;
const DEFAULT_MAX_RETRIES = 3;
const DEFAULT_RETRY_BASE_MS = 2500;
const DEFAULT_RETRY_MAX_MS = 15000;
const PASS_SCORE = 0.85;

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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeLabel(value) {
  return String(value || '').trim().toLowerCase();
}

function extractPartNumbers(blob) {
  const matches = String(blob || '').match(/\bB\d{5,6}\b/g) || [];
  return Array.from(new Set(matches));
}

function buildScenarioCatalog() {
  return [
    {
      id: 'vm_sku_composition',
      weight: 10,
      factory: (rand) => ({
        prompt: pick(rand, [
          "Cuales son los SKU's requeridos en una quote de Virtual Machines (Instances)?",
          'Que necesito para cotizar OCI Virtual Machines?',
          'Como se compone una quote consistente de OCI Compute Virtual Machine?',
        ]),
        expectedFamily: 'compute_vm_generic',
        conceptGroups: [
          ['ocpu', 'ocpus'],
          ['memory', 'ram'],
          ['shape'],
          ['block storage', 'block volume'],
          ['vpu', 'performance'],
        ],
      }),
    },
    {
      id: 'oic_sku_composition',
      weight: 8,
      factory: (rand) => ({
        prompt: pick(rand, [
          "Cuales son los SKU's requeridos en una quote de OIC?",
          'Como se compone una quote de Oracle Integration Cloud?',
          "Que SKU's intervienen en una quote consistente de Oracle Integration Cloud?",
        ]),
        expectedFamily: 'integration_oic',
        conceptGroups: [
          ['standard'],
          ['enterprise'],
          ['byol', 'license included'],
          ['instances', 'instance'],
        ],
        minimumConceptMatches: 3,
        expectedPartNumbers: ['B89639', 'B89643', 'B89640', 'B89644'],
        minPartMatches: 2,
      }),
    },
    {
      id: 'load_balancer_billing',
      weight: 8,
      factory: () => ({
        prompt: 'How is OCI Load Balancer billed?',
        expectedFamily: 'network_load_balancer',
        conceptGroups: [
          ['base', 'capacidad base', 'load balancer hour'],
          ['bandwidth', 'mbps'],
        ],
        expectedPartNumbers: ['B93030', 'B93031'],
        minPartMatches: 1,
      }),
    },
    {
      id: 'load_balancer_sku_composition',
      weight: 8,
      factory: () => ({
        prompt: "Cuales son los SKU's requeridos en una quote de Flexible Load Balancer?",
        expectedFamily: 'network_load_balancer',
        conceptGroups: [
          ['base', 'capacidad base', 'load balancer hour'],
          ['bandwidth', 'mbps'],
        ],
        expectedPartNumbers: ['B93030', 'B93031'],
        minPartMatches: 2,
      }),
    },
    {
      id: 'block_volume_billing',
      weight: 8,
      factory: () => ({
        prompt: 'How is OCI Block Volume billed?',
        expectedFamily: 'storage_block',
        conceptGroups: [
          ['gb-month', 'storage capacity', 'capacity'],
          ['vpu', 'performance'],
        ],
        expectedPartNumbers: ['B91961', 'B91962'],
        minPartMatches: 1,
      }),
    },
    {
      id: 'file_storage_billing',
      weight: 6,
      factory: () => ({
        prompt: 'How is OCI File Storage billed?',
        expectedFamily: 'storage_file',
        conceptGroups: [
          ['gb', 'tb', 'storage capacity', 'capacity'],
          ['performance units', 'performance unit'],
        ],
        expectedPartNumbers: ['B89057', 'B109546'],
        minPartMatches: 1,
      }),
    },
    {
      id: 'functions_billing',
      weight: 8,
      factory: () => ({
        prompt: 'How is OCI Functions billed?',
        expectedFamily: 'serverless_functions',
        conceptGroups: [
          ['invocations', 'invocation'],
          ['execution', 'duration', 'ms'],
          ['memory', 'memoria'],
          ['concurrency', 'provisioned concurrency'],
        ],
        minimumConceptMatches: 3,
        expectedPartNumbers: ['B90617', 'B90618'],
        minPartMatches: 1,
      }),
    },
    {
      id: 'network_firewall_composition',
      weight: 6,
      factory: () => ({
        prompt: "Cuales son los SKU's requeridos en una quote de OCI Network Firewall?",
        expectedFamily: 'network_firewall',
        conceptGroups: [
          ['firewall', 'firewalls'],
          ['data processed', 'gb'],
        ],
        expectedPartNumbers: ['B95403', 'B95404'],
        minPartMatches: 2,
      }),
    },
    {
      id: 'waf_composition',
      weight: 6,
      factory: () => ({
        prompt: "Cuales son los SKU's requeridos en una quote de Web Application Firewall?",
        expectedFamily: 'security_waf',
        conceptGroups: [
          ['instances', 'instance'],
          ['requests', 'request volume'],
        ],
        expectedPartNumbers: ['B94579', 'B94277'],
        minPartMatches: 2,
      }),
    },
    {
      id: 'base_db_inputs',
      weight: 6,
      factory: () => ({
        prompt: 'What inputs do I need before quoting Base Database Service?',
        expectedFamily: 'database_base_db',
        conceptGroups: [
          ['byol', 'license included'],
          ['ocpu', 'ocpus'],
          ['storage'],
        ],
        expectedPartNumbers: ['B90570', 'B90573', 'B111584'],
        minPartMatches: 1,
      }),
    },
    {
      id: 'lakehouse_composition',
      weight: 5,
      factory: () => ({
        prompt: "Cuales son los SKU's requeridos en una quote de Autonomous AI Lakehouse?",
        expectedFamily: 'database_autonomous_dw',
        conceptGroups: [
          ['byol', 'license included'],
          ['ecpu', 'ecpus'],
          ['storage'],
        ],
        expectedPartNumbers: ['B95701', 'B95703', 'B95706'],
        minPartMatches: 2,
      }),
    },
    {
      id: 'exascale_composition',
      weight: 5,
      factory: () => ({
        prompt: "Cuales son los SKU's requeridos en una quote de Exadata Exascale?",
        expectedFamily: 'database_exadata_exascale',
        conceptGroups: [
          ['ecpu', 'ecpus'],
          ['storage', 'filesystem'],
          ['license included', 'byol'],
        ],
        expectedPartNumbers: ['B109356', 'B107951', 'B107952'],
        minPartMatches: 2,
      }),
    },
    {
      id: 'health_checks_billing',
      weight: 5,
      factory: () => ({
        prompt: 'How is OCI Health Checks billed for 12 endpoints?',
        expectedFamily: 'edge_health_checks',
        acceptableFamilies: ['edge_health_checks'],
        conceptGroups: [
          ['endpoints', 'endpoint'],
          ['per month', 'monthly'],
        ],
        expectedPartNumbers: ['B90323', 'B90325'],
        minPartMatches: 1,
      }),
    },
    {
      id: 'health_checks_inputs',
      weight: 5,
      factory: () => ({
        prompt: 'What inputs do I need before quoting Health Checks in OCI?',
        expectedFamily: 'edge_health_checks',
        acceptableFamilies: ['edge_health_checks'],
        conceptGroups: [
          ['endpoints', 'endpoint'],
          ['health checks', 'health check'],
        ],
      }),
    },
    {
      id: 'api_gateway_billing',
      weight: 4,
      factory: () => ({
        prompt: 'How is API Gateway billed in OCI?',
        expectedFamily: 'apigw',
        acceptableFamilies: ['apigw'],
        conceptGroups: [
          ['api calls', 'calls'],
          ['gateway'],
        ],
        expectedPartNumbers: ['B92072'],
        minPartMatches: 1,
      }),
    },
    {
      id: 'fastconnect_options',
      weight: 4,
      factory: () => ({
        prompt: 'What options do I have before quoting OCI FastConnect?',
        expectedFamily: 'network_fastconnect',
        acceptableFamilies: ['network_fastconnect'],
        conceptGroups: [
          ['1 gbps', '10 gbps', '100 gbps', '400 gbps'],
          ['port hour', 'bandwidth', 'gbps'],
        ],
        minimumConceptMatches: 1,
      }),
    },
    {
      id: 'monitoring_billing',
      weight: 3,
      factory: () => ({
        prompt: 'How is OCI Monitoring billed?',
        expectedFamily: 'observability_monitoring',
        acceptableFamilies: ['observability_monitoring'],
        conceptGroups: [
          ['requests', 'datapoints', 'metric data'],
          ['ingestion', 'retrieval'],
        ],
        minimumConceptMatches: 1,
      }),
    },
    {
      id: 'notifications_https_billing',
      weight: 3,
      factory: () => ({
        prompt: 'How is Notifications HTTPS Delivery billed?',
        expectedFamily: 'observability_notifications_https',
        acceptableFamilies: ['observability_notifications_https'],
        conceptGroups: [
          ['delivery', 'deliveries'],
          ['https'],
        ],
      }),
    },
    {
      id: 'email_delivery_billing',
      weight: 3,
      factory: () => ({
        prompt: 'How is Email Delivery billed?',
        expectedFamily: 'operations_email_delivery',
        acceptableFamilies: ['operations_email_delivery'],
        conceptGroups: [
          ['emails', 'email'],
          ['per month', 'sent'],
        ],
      }),
    },
    {
      id: 'analytics_cloud_billing',
      weight: 3,
      factory: (rand) => ({
        prompt: pick(rand, [
          'How is Oracle Analytics Cloud Professional billed?',
          'How is Oracle Analytics Cloud Enterprise billed?',
        ]),
        expectedFamily: 'analytics_oac_professional',
        acceptableFamilies: ['analytics_oac_professional', 'analytics_oac_enterprise'],
        conceptGroups: [
          ['professional', 'enterprise', 'users'],
          ['users', 'user count'],
        ],
        minimumConceptMatches: 1,
      }),
    },
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

function countConceptMatches(text, conceptGroups) {
  const source = normalizeLabel(text);
  const results = [];
  for (const group of conceptGroups || []) {
    const matched = group.some((needle) => source.includes(normalizeLabel(needle)));
    results.push({
      group,
      matched,
    });
  }
  return results;
}

function validateQuality(result, scenario) {
  const errors = [];
  const warnings = [];
  const payload = result.payload || {};
  const family = String(payload.contextPackSummary?.family?.id || payload.intent?.serviceFamily || '');
  const message = String(payload.message || '');
  const partNumbersInMessage = extractPartNumbers(message);
  const acceptableFamilies = Array.isArray(scenario.acceptableFamilies) && scenario.acceptableFamilies.length
    ? scenario.acceptableFamilies
    : [scenario.expectedFamily];
  const familyMatched = acceptableFamilies.includes(family);
  const conceptResults = countConceptMatches(message, scenario.conceptGroups || []);
  const conceptMatches = conceptResults.filter((item) => item.matched).length;
  const minimumConceptMatches = Number.isFinite(Number(scenario.minimumConceptMatches))
    ? Number(scenario.minimumConceptMatches)
    : conceptResults.length;
  const expectedPartNumbers = Array.isArray(scenario.expectedPartNumbers) ? scenario.expectedPartNumbers : [];
  const minPartMatches = Number.isFinite(Number(scenario.minPartMatches))
    ? Number(scenario.minPartMatches)
    : expectedPartNumbers.length;
  const partMatches = expectedPartNumbers.filter((part) => partNumbersInMessage.includes(part)).length;
  const notQuoteLike = !/deterministic oci quotation|monthly total is \*\*?\$|line items/i.test(message);

  if (result.status !== 200) errors.push(`HTTP ${result.status}`);
  if (!payload.ok) errors.push(`payload.ok=false (${payload.error || 'unknown error'})`);
  if (payload.mode !== 'answer') errors.push(`expected mode=answer but got ${payload.mode || 'unknown'}`);
  if (String(payload.intent?.route || '') !== 'product_discovery') {
    errors.push(`expected intent.route=product_discovery but got ${payload.intent?.route || 'unknown'}`);
  }
  if (payload.intent?.shouldQuote !== false) {
    errors.push(`expected intent.shouldQuote=false but got ${String(payload.intent?.shouldQuote)}`);
  }
  if (!familyMatched) {
    errors.push(`expected family ${acceptableFamilies.join(' or ')} but got ${family || 'none'}`);
  }
  if (conceptMatches < minimumConceptMatches) {
    errors.push(`expected at least ${minimumConceptMatches} concept groups but matched ${conceptMatches}`);
  }
  if (expectedPartNumbers.length && partMatches < minPartMatches) {
    warnings.push(`expected at least ${minPartMatches} part numbers but found ${partMatches}`);
  }
  if (!notQuoteLike) warnings.push('response looked like a quote instead of guided discovery');

  let score = 0;
  if (result.status === 200 && payload.ok) score += 0.15;
  if (payload.mode === 'answer') score += 0.15;
  if (String(payload.intent?.route || '') === 'product_discovery' && payload.intent?.shouldQuote === false) score += 0.2;
  if (familyMatched) score += 0.2;
  if (conceptResults.length) {
    score += 0.25 * (conceptMatches / conceptResults.length);
  } else {
    score += 0.25;
  }
  if (expectedPartNumbers.length) {
    score += 0.05 * Math.min(1, partMatches / Math.max(1, minPartMatches));
  } else {
    score += 0.05;
  }

  return {
    pass: errors.length === 0 && score >= PASS_SCORE,
    score: Number(score.toFixed(4)),
    errors,
    warnings,
    family,
    conceptMatches,
    conceptTotal: conceptResults.length,
    conceptResults,
    partNumbersInMessage,
    partMatches,
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
  let totalScore = 0;
  const clientId = `assistant-quality-${options.seed}`;

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

      const evaluation = validateQuality(result, scenario);
      totalScore += evaluation.score;
      const stat = templateStats.get(scenario.templateId) || { total: 0, failed: 0, scoreSum: 0 };
      stat.total += 1;
      stat.scoreSum += evaluation.score;
      if (!evaluation.pass) {
        stat.failed += 1;
        failures.push({
          id: scenario.id,
          templateId: scenario.templateId,
          prompt: scenario.prompt,
          score: evaluation.score,
          errors: evaluation.errors,
          warnings: evaluation.warnings,
          family: evaluation.family,
          conceptMatches: evaluation.conceptMatches,
          conceptTotal: evaluation.conceptTotal,
          partNumbersInMessage: evaluation.partNumbersInMessage,
          messagePreview: String(result.payload?.message || '').slice(0, 700),
        });
      }
      templateStats.set(scenario.templateId, stat);
      completed += 1;
      if (completed % 25 === 0 || completed === sequence.length) {
        process.stdout.write(`Completed ${completed}/${sequence.length} quality checks. Failures so far: ${failures.length}. Avg score: ${(totalScore / completed).toFixed(4)}. Throttled retries: ${throttledRetries}\n`);
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
      averageScore: stat.total ? Number((stat.scoreSum / stat.total).toFixed(4)) : 0,
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
    averageScore: sequence.length ? Number((totalScore / sequence.length).toFixed(4)) : 0,
    baseUrl: options.baseUrl,
    failures,
    stats,
    passScore: PASS_SCORE,
    generatedAt: new Date().toISOString(),
  };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const reportPath = options.report || path.join('/tmp', `assistant-quality-${options.seed}-${Date.now()}.json`);
  const report = await runSequence(options);
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);

  console.log('\nAssistant quality summary');
  console.log(`- Base URL: ${report.baseUrl}`);
  console.log(`- Seed: ${report.seed}`);
  console.log(`- Count: ${report.count}`);
  console.log(`- Average score: ${report.averageScore}`);
  console.log(`- Failures: ${report.failures.length}`);
  console.log(`- Throttled retries: ${report.throttledRetries}`);
  console.log(`- Report: ${reportPath}`);

  const topFailures = report.stats
    .filter((item) => item.failed > 0)
    .sort((a, b) => b.failed - a.failed)
    .slice(0, 10);
  if (topFailures.length) {
    console.log('- Weak templates:');
    for (const item of topFailures) {
      console.log(`  - ${item.templateId}: ${item.failed}/${item.total} failed, avg score ${item.averageScore}`);
    }
  }

  if (report.failures.length) {
    console.log('\nSample quality failures:');
    for (const failure of report.failures.slice(0, 10)) {
      console.log(`- ${failure.templateId}`);
      console.log(`  Prompt: ${failure.prompt}`);
      console.log(`  Score: ${failure.score}`);
      console.log(`  Errors: ${failure.errors.join(' | ')}`);
      if (failure.warnings.length) console.log(`  Warnings: ${failure.warnings.join(' | ')}`);
      console.log(`  Family: ${failure.family || 'none'} | Concepts: ${failure.conceptMatches}/${failure.conceptTotal}`);
    }
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
