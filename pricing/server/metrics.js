'use strict';

const HISTOGRAM_BUCKETS = [25, 50, 100, 250, 500, 1000, 2000, 5000];

const METRIC_DEFINITIONS = {
  genai_calls_total: {
    type: 'counter',
    help: 'Total GenAI calls by call type.',
    labelNames: ['call_type'],
  },
  genai_tokens_input_total: {
    type: 'counter',
    help: 'Total GenAI input tokens reported by the OCI SDK.',
    labelNames: ['call_type'],
  },
  genai_tokens_output_total: {
    type: 'counter',
    help: 'Total GenAI output tokens reported by the OCI SDK.',
    labelNames: ['call_type'],
  },
  genai_latency_ms: {
    type: 'histogram',
    help: 'GenAI call latency in milliseconds.',
    labelNames: ['call_type'],
    buckets: HISTOGRAM_BUCKETS,
  },
  assistant_requests_total: {
    type: 'counter',
    help: 'Total assistant requests by outcome.',
    labelNames: ['outcome'],
  },
  quote_resolution_path: {
    type: 'counter',
    help: 'Total quote resolution paths taken by the assistant.',
    labelNames: ['path'],
  },
};

function createCounterState() {
  return new Map();
}

function createHistogramState(buckets) {
  return {
    buckets,
    series: new Map(),
  };
}

function createMetricState() {
  return {
    genai_calls_total: createCounterState(),
    genai_tokens_input_total: createCounterState(),
    genai_tokens_output_total: createCounterState(),
    genai_latency_ms: createHistogramState(HISTOGRAM_BUCKETS),
    assistant_requests_total: createCounterState(),
    quote_resolution_path: createCounterState(),
  };
}

let state = createMetricState();

function escapePrometheusLabelValue(value) {
  return String(value ?? '')
    .replace(/\\/g, '\\\\')
    .replace(/\n/g, '\\n')
    .replace(/"/g, '\\"');
}

function normalizeLabels(labelNames, labels = {}) {
  const normalized = {};
  for (const name of labelNames) {
    normalized[name] = String(labels?.[name] ?? '');
  }
  return normalized;
}

function serializeLabels(labelNames, labels = {}) {
  return JSON.stringify(normalizeLabels(labelNames, labels));
}

function formatPrometheusLabels(labels = {}) {
  const pairs = Object.entries(labels);
  if (!pairs.length) return '';
  return `{${pairs.map(([key, value]) => `${key}="${escapePrometheusLabelValue(value)}"`).join(',')}}`;
}

function incCounter(name, labels = {}, value = 1) {
  const definition = METRIC_DEFINITIONS[name];
  if (!definition || definition.type !== 'counter') return;
  const amount = Number(value);
  if (!Number.isFinite(amount)) return;
  const key = serializeLabels(definition.labelNames, labels);
  const current = state[name].get(key) || 0;
  state[name].set(key, current + amount);
}

function observeHistogram(name, labels = {}, value = 0) {
  const definition = METRIC_DEFINITIONS[name];
  if (!definition || definition.type !== 'histogram') return;
  const amount = Number(value);
  if (!Number.isFinite(amount)) return;

  const normalizedLabels = normalizeLabels(definition.labelNames, labels);
  const key = JSON.stringify(normalizedLabels);
  let series = state[name].series.get(key);
  if (!series) {
    series = {
      labels: normalizedLabels,
      bucketCounts: definition.buckets.map(() => 0),
      count: 0,
      sum: 0,
    };
    state[name].series.set(key, series);
  }

  series.count += 1;
  series.sum += amount;
  definition.buckets.forEach((bucket, index) => {
    if (amount <= bucket) series.bucketCounts[index] += 1;
  });
}

function normalizeCallType(callType) {
  const source = String(callType || '').trim().toLowerCase();
  return source || 'narrative';
}

function normalizeAssistantOutcome(outcome) {
  const source = String(outcome || '').trim().toLowerCase();
  if (source === 'quote' || source === 'clarification' || source === 'discovery' || source === 'error') return source;
  return 'discovery';
}

function normalizeResolutionPath(pathName) {
  const source = String(pathName || '').trim().toLowerCase();
  if (source === 'full_pipeline') return 'intent_pipeline';
  if (source === 'fast_path' || source === 'early_exit' || source === 'intent_pipeline') return source;
  return '';
}

function recordGenAIMetrics({ callType, latencyMs = 0, inputTokens = 0, outputTokens = 0 }) {
  const normalizedCallType = normalizeCallType(callType);
  incCounter('genai_calls_total', { call_type: normalizedCallType }, 1);
  incCounter('genai_tokens_input_total', { call_type: normalizedCallType }, Number(inputTokens) || 0);
  incCounter('genai_tokens_output_total', { call_type: normalizedCallType }, Number(outputTokens) || 0);
  observeHistogram('genai_latency_ms', { call_type: normalizedCallType }, Number(latencyMs) || 0);
}

function recordAssistantRequestMetrics({ outcome, pathName }) {
  const normalizedOutcome = normalizeAssistantOutcome(outcome);
  incCounter('assistant_requests_total', { outcome: normalizedOutcome }, 1);
  const normalizedPath = normalizeResolutionPath(pathName);
  if (normalizedPath) incCounter('quote_resolution_path', { path: normalizedPath }, 1);
}

function renderCounter(name, definition, metricState) {
  const lines = [
    `# HELP ${name} ${definition.help}`,
    `# TYPE ${name} counter`,
  ];
  for (const [serializedLabels, value] of metricState.entries()) {
    lines.push(`${name}${formatPrometheusLabels(JSON.parse(serializedLabels))} ${value}`);
  }
  return lines.join('\n');
}

function renderHistogram(name, definition, metricState) {
  const lines = [
    `# HELP ${name} ${definition.help}`,
    `# TYPE ${name} histogram`,
  ];

  for (const series of metricState.series.values()) {
    const baseLabels = series.labels;
    let cumulative = 0;
    definition.buckets.forEach((bucket, index) => {
      cumulative = series.bucketCounts[index];
      lines.push(`${name}_bucket${formatPrometheusLabels({ ...baseLabels, le: String(bucket) })} ${cumulative}`);
    });
    lines.push(`${name}_bucket${formatPrometheusLabels({ ...baseLabels, le: '+Inf' })} ${series.count}`);
    lines.push(`${name}_sum${formatPrometheusLabels(baseLabels)} ${series.sum}`);
    lines.push(`${name}_count${formatPrometheusLabels(baseLabels)} ${series.count}`);
  }

  return lines.join('\n');
}

function renderPrometheusMetrics() {
  return Object.entries(METRIC_DEFINITIONS)
    .map(([name, definition]) => {
      if (definition.type === 'histogram') return renderHistogram(name, definition, state[name]);
      return renderCounter(name, definition, state[name]);
    })
    .join('\n\n')
    .concat('\n');
}

function resetMetrics() {
  state = createMetricState();
}

module.exports = {
  normalizeAssistantOutcome,
  normalizeCallType,
  normalizeResolutionPath,
  recordAssistantRequestMetrics,
  recordGenAIMetrics,
  renderPrometheusMetrics,
  resetMetrics,
};
