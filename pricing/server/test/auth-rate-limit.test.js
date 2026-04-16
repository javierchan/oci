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
}

function createTempSessionStore() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pricing-m9-'));
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

async function requestJson(baseUrl, route, { method = 'GET', body = undefined, headers = {}, redirect = 'follow' } = {}) {
  const response = await fetch(`${baseUrl}${route}`, {
    method,
    redirect,
    headers: {
      ...(body ? { 'content-type': 'application/json' } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  return {
    status: response.status,
    headers: response.headers,
    json: await response.json(),
  };
}

async function withFreshServer(envOverrides, stub, run) {
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

test('catalog reload rejects missing and incorrect shared API keys', async () => {
  await withFreshServer({}, {}, async (baseUrl) => {
    const missing = await requestJson(baseUrl, '/api/catalog/reload', {
      method: 'POST',
      body: {},
    });
    assert.equal(missing.status, 401);
    assert.equal(missing.json.code, 'AUTH_UNAUTHORIZED');

    const incorrect = await requestJson(baseUrl, '/api/catalog/reload', {
      method: 'POST',
      body: {},
      headers: {
        'x-api-key': 'wrong-secret',
      },
    });
    assert.equal(incorrect.status, 401);
    assert.equal(incorrect.json.code, 'AUTH_UNAUTHORIZED');
  });
});

test('providers endpoint omits sensitive OCI identity fields', async () => {
  await withFreshServer({}, {}, async (baseUrl) => {
    const result = await requestJson(baseUrl, '/api/providers');

    assert.equal(result.status, 200);
    assert.equal(typeof result.json.oci.ok, 'boolean');
    assert.equal(Object.hasOwn(result.json.oci, 'tenancy'), false);
    assert.equal(Object.hasOwn(result.json.oci, 'fingerprint'), false);
    assert.equal(Object.hasOwn(result.json.oci, 'privateKeyPem'), false);
    assert.equal(Object.hasOwn(result.json.oci, 'user'), false);
  });
});

test('chat endpoint returns 429 with Retry-After when configured RPM is exceeded', async () => {
  await withFreshServer({
    PRICING_RATE_LIMIT_RPM: '2',
  }, {}, async (baseUrl) => {
    const headers = {
      'x-client-id': 'rate-limit-client',
    };
    const payload = {
      messages: [{ role: 'user', content: 'hello' }],
    };

    const first = await requestJson(baseUrl, '/api/v1/chat', {
      method: 'POST',
      body: payload,
      headers,
    });
    const second = await requestJson(baseUrl, '/api/v1/chat', {
      method: 'POST',
      body: payload,
      headers,
    });
    const third = await requestJson(baseUrl, '/api/v1/chat', {
      method: 'POST',
      body: payload,
      headers,
    });

    assert.equal(first.status, 200);
    assert.equal(second.status, 200);
    assert.equal(third.status, 429);
    assert.equal(third.json.code, 'RATE_LIMITED');
    assert.equal(third.headers.get('retry-after'), third.json.retryAfter?.toString());
    assert.ok(Number.parseInt(third.headers.get('retry-after'), 10) >= 1);
  });
});
