'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const indexPath = path.join(ROOT, 'index.js');
const genaiPath = path.join(ROOT, 'genai.js');
const authPath = path.join(ROOT, 'auth.js');
const sessionStorePath = path.join(ROOT, 'session-store.js');
const metricsPath = path.join(ROOT, 'metrics.js');
const { loadAssistantWithStubs, buildIndex } = require('./assistant-test-helpers');

async function withEnv(overrides, fn) {
  const previous = {};
  for (const [key, value] of Object.entries(overrides)) {
    previous[key] = process.env[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }

  try {
    return await fn();
  } finally {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

function clearServerModules() {
  delete require.cache[indexPath];
  delete require.cache[genaiPath];
  delete require.cache[authPath];
  delete require.cache[sessionStorePath];
  delete require.cache[metricsPath];
}

function createTempSessionStore() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pricing-m10-'));
  return {
    tempDir,
    storePath: path.join(tempDir, 'session-store.json'),
  };
}

function loadServerWithGenAIStub(stub = {}) {
  clearServerModules();

  require.cache[genaiPath] = {
    id: genaiPath,
    filename: genaiPath,
    loaded: true,
    exports: {
      loadGenAISettings: () => ({
        region: 'us-chicago-1',
        compartmentId: 'ocid1.compartment.oc1..example',
        modelId: 'ocid1.generativeaimodel.oc1..example',
        profile: 'DEFAULT',
        defaultProfile: 'narrative',
      }),
      runChat: async () => ({ data: { text: 'ok' } }),
      extractChatText: (payload) => String(payload?.text || ''),
      ...stub,
    },
  };

  return require(indexPath);
}

async function withListeningServer(app, run) {
  const server = await new Promise((resolve, reject) => {
    const instance = app.listen(0, '127.0.0.1', (error) => {
      if (error) reject(error);
      else resolve(instance);
    });
  });

  try {
    const address = server.address();
    return await run(`http://127.0.0.1:${address.port}`);
  } finally {
    await new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  }
}

async function withFreshMetricsServer(envOverrides, stub, run) {
  const { tempDir, storePath } = createTempSessionStore();
  const env = {
    OCI_USER: 'ocid1.user.oc1..example',
    OCI_TENANCY: 'ocid1.tenancy.oc1..example',
    OCI_FINGERPRINT: 'aa:bb:cc:dd',
    OCI_PRIVATE_KEY: '-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----',
    OCI_GENAI_MODEL: 'ocid1.generativeaimodel.oc1..example',
    OCI_COMPARTMENT: 'ocid1.compartment.oc1..example',
    PRICING_SESSION_STORE_DIR: tempDir,
    PRICING_SESSION_STORE_PATH: storePath,
    PRICING_SHARED_API_KEY: 'shared-secret',
    ...envOverrides,
  };

  return withEnv(env, async () => {
    const metrics = require(metricsPath);
    metrics.resetMetrics();
    const { app } = loadServerWithGenAIStub(stub);
    const sessionStore = require(sessionStorePath);

    try {
      return await withListeningServer(app, run);
    } finally {
      await sessionStore.shutdown();
      clearServerModules();
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });
}

function restoreCacheEntry(modulePath, entry) {
  if (entry) require.cache[modulePath] = entry;
  else delete require.cache[modulePath];
}

async function withMockedGenAISdk(run) {
  const commonModulePath = require.resolve('oci-common', { paths: [ROOT] });
  const sdkModulePath = require.resolve('oci-generativeaiinference', { paths: [ROOT] });
  const previousCommon = require.cache[commonModulePath];
  const previousSdk = require.cache[sdkModulePath];
  delete require.cache[genaiPath];

  const recordedRequests = [];

  class FakeAuthenticationDetailsProvider {}
  class FakeGenerativeAiInferenceClient {
    constructor() {
      this.endpoint = '';
      this.regionId = '';
    }

    async chat({ chatDetails }) {
      recordedRequests.push(chatDetails);
      return {
        data: {
          chatResult: {
            chatResponse: {
              choices: [
                {
                  message: {
                    content: [{ text: 'mocked response' }],
                  },
                },
              ],
              usage: {
                promptTokens: 11,
                completionTokens: 7,
                totalTokens: 18,
              },
            },
          },
        },
      };
    }
  }

  require.cache[commonModulePath] = {
    id: commonModulePath,
    filename: commonModulePath,
    loaded: true,
    exports: {
      SimpleAuthenticationDetailsProvider: FakeAuthenticationDetailsProvider,
    },
  };

  require.cache[sdkModulePath] = {
    id: sdkModulePath,
    filename: sdkModulePath,
    loaded: true,
    exports: {
      GenerativeAiInferenceClient: FakeGenerativeAiInferenceClient,
      models: {
        GenericChatRequest: { apiFormat: 'GENERIC' },
        OnDemandServingMode: { servingType: 'ON_DEMAND' },
        SystemMessage: { role: 'SYSTEM' },
        TextContent: { type: 'TEXT' },
        ImageContent: { type: 'IMAGE' },
        ImageUrl: { Detail: { Auto: 'AUTO' } },
      },
    },
  };

  try {
    return await run(require(genaiPath), recordedRequests);
  } finally {
    delete require.cache[genaiPath];
    restoreCacheEntry(commonModulePath, previousCommon);
    restoreCacheEntry(sdkModulePath, previousSdk);
  }
}

test('metrics endpoint returns HTTP 200 and exposes Prometheus counter names without auth by default', async () => {
  await withFreshMetricsServer({}, {}, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/metrics`);
    const body = await response.text();

    assert.equal(response.status, 200);
    assert.match(response.headers.get('content-type') || '', /^text\/plain/);
    assert.match(body, /# HELP genai_calls_total /);
    assert.match(body, /# TYPE genai_calls_total counter/);
    assert.match(body, /# HELP assistant_requests_total /);
    assert.match(body, /# HELP quote_resolution_path /);
  });
});

test('assistant requests increment assistant metrics and quote resolution path counters', async () => {
  const { resetMetrics, renderPrometheusMetrics } = require(metricsPath);
  resetMetrics();

  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    route: 'quote_request',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {
      shape: 'VM.Standard.E4.Flex',
      ocpus: 4,
      memoryGb: 16,
      capacityGb: 200,
    },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: {
      action: 'quote',
      targetType: 'service',
      domain: 'compute',
      candidateFamilies: ['compute_flex'],
      missingInputs: [],
      useDeterministicEngine: true,
    },
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote VM.Standard.E4.Flex with 4 OCPUs, 16 GB RAM, and 200 GB block storage',
  });
  const metrics = renderPrometheusMetrics();

  assert.equal(reply.ok, true);
  assert.match(metrics, /assistant_requests_total\{outcome="quote"\} 1/);
  assert.match(metrics, /quote_resolution_path\{path="fast_path"\} 1/);
});

test('genai calls record SDK token counts in observability metrics instead of estimating', async () => {
  const { resetMetrics, renderPrometheusMetrics } = require(metricsPath);
  resetMetrics();

  await withMockedGenAISdk(async ({ runChat }, recordedRequests) => {
    const response = await runChat({
      cfg: {
        tenancy: 'ocid1.tenancy.oc1..example',
        user: 'ocid1.user.oc1..example',
        fingerprint: 'aa:bb:cc:dd',
        privateKeyPem: '-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----',
        compartment: 'ocid1.compartment.oc1..example',
        modelId: 'ocid1.generativeaimodel.oc1..example',
        endpoint: 'https://inference.generativeai.us-chicago-1.oci.oraclecloud.com',
        defaultProfile: 'narrative',
      },
      systemPrompt: 'You are helpful.',
      messages: [{ role: 'user', content: 'hello' }],
      profile: 'narrative',
    });
    const metrics = renderPrometheusMetrics();

    assert.ok(response?.data);
    assert.equal(recordedRequests.length, 1);
    assert.match(metrics, /genai_calls_total\{call_type="narrative"\} 1/);
    assert.match(metrics, /genai_tokens_input_total\{call_type="narrative"\} 11/);
    assert.match(metrics, /genai_tokens_output_total\{call_type="narrative"\} 7/);
    assert.match(metrics, /genai_latency_ms_bucket\{call_type="narrative",le="\+Inf"\} 1/);
  });
});
