'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const indexPath = path.join(ROOT, 'index.js');
const genaiPath = path.join(ROOT, 'genai.js');
const sessionStorePath = path.join(ROOT, 'session-store.js');
const { GenAIError } = require(path.join(ROOT, 'errors.js'));

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
  delete require.cache[sessionStorePath];
}

function createTempSessionStore() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pricing-http-errors-'));
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
    const baseUrl = `http://127.0.0.1:${address.port}`;
    return await run(baseUrl);
  } finally {
    await new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  }
}

async function postJson(baseUrl, route, body, headers = {}) {
  const response = await fetch(`${baseUrl}${route}`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(body),
  });

  return {
    status: response.status,
    json: await response.json(),
  };
}

async function withFreshServer(stub, run) {
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

test('chat endpoint returns HTTP 503 with GENAI_UNAVAILABLE when GenAI fails', async () => {
  await withFreshServer({
    runChat: async () => {
      throw new GenAIError('Upstream OCI GenAI outage.', {
        code: 'GENAI_UNAVAILABLE',
        httpStatus: 503,
      });
    },
  }, async (baseUrl) => {
    const result = await postJson(baseUrl, '/api/chat', {
      messages: [{ role: 'user', content: 'hello' }],
    });

    assert.equal(result.status, 503);
    assert.equal(result.json.ok, false);
    assert.equal(result.json.code, 'GENAI_UNAVAILABLE');
    assert.equal(result.json.message, 'Upstream OCI GenAI outage.');
  });
});

test('session message endpoint returns HTTP 409 with SESSION_CONFLICT on stale writes', async () => {
  await withFreshServer({}, async (baseUrl) => {
    const created = await postJson(baseUrl, '/api/sessions', { title: 'Conflict test' });
    assert.equal(created.status, 200);
    assert.equal(created.json.ok, true);

    const conflict = await postJson(baseUrl, `/api/sessions/${created.json.session.id}/messages`, {
      role: 'user',
      content: 'stale write',
      expectedVersion: created.json.session.version + 99,
    });

    assert.equal(conflict.status, 409);
    assert.equal(conflict.json.ok, false);
    assert.equal(conflict.json.code, 'SESSION_CONFLICT');
    assert.equal(conflict.json.message, 'Session version conflict.');
    assert.ok(conflict.json.session);
  });
});

test('error responses do not leak Node.js stack traces to clients', async () => {
  await withFreshServer({
    runChat: async () => {
      const error = new Error('simulated internal failure');
      error.stack = 'Error: simulated internal failure\n    at dangerousFn (/tmp/server.js:10:3)';
      throw error;
    },
  }, async (baseUrl) => {
    const result = await postJson(baseUrl, '/api/chat', {
      messages: [{ role: 'user', content: 'hello' }],
    });

    assert.equal(result.status, 500);
    assert.equal(result.json.ok, false);
    assert.equal(result.json.code, 'INTERNAL_ERROR');
    assert.equal(result.json.message, 'Internal server error.');
    assert.doesNotMatch(JSON.stringify(result.json), /dangerousFn|\/tmp\/server\.js|stack|at\s+\w+/i);
  });
});
