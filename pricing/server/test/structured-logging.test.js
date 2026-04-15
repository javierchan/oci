'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const { execFileSync } = require('node:child_process');

const { buildIndex, loadAssistantWithStubs } = require('./assistant-test-helpers');

const ROOT = path.resolve(__dirname, '..');
const loggerPath = path.join(ROOT, 'logger.js');

async function captureStdout(fn) {
  const writes = [];
  const originalWrite = process.stdout.write;
  process.stdout.write = function write(chunk, encoding, callback) {
    if (Buffer.isBuffer(chunk)) writes.push(chunk.toString('utf8'));
    else if (ArrayBuffer.isView(chunk)) writes.push(Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength).toString('utf8'));
    else writes.push(String(chunk));
    if (typeof encoding === 'function') encoding();
    if (typeof callback === 'function') callback();
    return true;
  };

  try {
    await fn();
    await new Promise((resolve) => setImmediate(resolve));
  } finally {
    process.stdout.write = originalWrite;
  }

  return writes.join('');
}

function withEnv(overrides, fn) {
  const previous = {};
  for (const [key, value] of Object.entries(overrides)) {
    previous[key] = process.env[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }

  try {
    return fn();
  } finally {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

function loadFreshLogger() {
  delete require.cache[loggerPath];
  return require(loggerPath);
}

test('logger writes human-readable output in development mode', async () => {
  const output = execFileSync(process.execPath, [
    '-e',
    `const { logger } = require(${JSON.stringify(loggerPath)}); logger.info({ event: 'logger.dev_mode', sample: true }, 'Dev log line');`,
  ], {
    env: {
      ...process.env,
      LOG_FORMAT: '',
      LOG_LEVEL: 'info',
      NODE_ENV: 'development',
    },
    encoding: 'utf8',
  });

  assert.match(output, /Dev log line/);
  assert.match(output, /event="logger\.dev_mode"/);
  assert.ok(!output.trim().startsWith('{'));
});

test('logger writes newline-delimited JSON when LOG_FORMAT=json', async () => {
  const output = execFileSync(process.execPath, [
    '-e',
    `const { logger } = require(${JSON.stringify(loggerPath)}); logger.info({ event: 'logger.json_mode', sample: true }, 'JSON log line');`,
  ], {
    env: {
      ...process.env,
      LOG_FORMAT: 'json',
      LOG_LEVEL: 'info',
      NODE_ENV: 'development',
    },
    encoding: 'utf8',
  });

  const parsed = JSON.parse(output.trim());
  assert.equal(parsed.msg, 'JSON log line');
  assert.equal(parsed.event, 'logger.json_mode');
  assert.equal(parsed.sample, true);
});

test('assistant request emits a parseable completion trace with routing and outcome fields', async () => {
  const output = await withEnv({
    LOG_FORMAT: 'json',
    LOG_LEVEL: 'debug',
    NODE_ENV: 'development',
  }, async () => {
    delete require.cache[loggerPath];
    const { buildRequestLogger, createTrace } = require(loggerPath);
    const { respondToAssistant } = loadAssistantWithStubs(() => ({
      route: 'quote_request',
      intent: 'quote',
      shouldQuote: true,
      needsClarification: false,
      clarificationQuestion: '',
      reformulatedRequest: 'Quote OCI FastConnect 10 Gbps',
      assumptions: [],
      serviceFamily: 'network_fastconnect',
      serviceName: 'OCI FastConnect',
      extractedInputs: { bandwidthGbps: 10 },
      annualRequested: false,
      quotePlan: {
        action: 'quote',
        targetType: 'service',
        domain: 'network',
        candidateFamilies: ['network_fastconnect'],
        missingInputs: [],
        useDeterministicEngine: true,
      },
    }));

    return captureStdout(async () => {
      const reply = await respondToAssistant({
        cfg: { modelId: 'test-model', compartment: 'ocid1.compartment.oc1..example' },
        index: buildIndex(),
        conversation: [],
        userText: 'Quote OCI FastConnect 10 Gbps',
        imageDataUrl: '',
        sessionContext: null,
        logger: buildRequestLogger({
          routeName: '/api/assistant',
          requestId: 'req_logging_test',
          clientId: 'customer-123',
          sessionId: 'ses_logging_test',
        }),
        trace: createTrace(),
      });

      assert.ok(reply.message);
    });
  });

  const lines = output
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('{') && line.endsWith('}'))
    .map((line) => JSON.parse(line));
  const completion = lines.find((entry) => entry.event === 'assistant.pipeline.complete');

  assert.ok(completion, 'expected assistant.pipeline.complete log entry');
  assert.equal(completion.route, 'quote_request');
  assert.equal(completion.serviceFamily, 'network_fastconnect');
  assert.equal(completion.shouldQuote, true);
  assert.equal(typeof completion.genaiCallCount, 'number');
  assert.ok(['early_exit', 'fast_path', 'full_pipeline'].includes(completion.routingPath));
  assert.ok(completion.quoteProduced || completion.clarificationTriggered || completion.outcome === 'answer');
});
