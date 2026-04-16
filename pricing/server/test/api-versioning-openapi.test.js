'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const OpenAPISchemaValidator = require('openapi-schema-validator').default;

const SERVER_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(SERVER_ROOT, '..', '..');
const indexPath = path.join(SERVER_ROOT, 'index.js');
const sessionStorePath = path.join(SERVER_ROOT, 'session-store.js');
const specPath = path.join(REPO_ROOT, 'pricing', 'docs', 'openapi.yaml');

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

function clearServerModules() {
  delete require.cache[indexPath];
  delete require.cache[sessionStorePath];
}

function createTempSessionStore() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pricing-m8-'));
  return {
    tempDir,
    storePath: path.join(tempDir, 'session-store.json'),
  };
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

async function withFreshServer(run) {
  const { tempDir, storePath } = createTempSessionStore();
  const env = {
    PRICING_SESSION_STORE_DIR: tempDir,
    PRICING_SESSION_STORE_PATH: storePath,
  };

  return withEnv(env, async () => {
    clearServerModules();
    const { app } = require(indexPath);
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

test('openapi spec is present, validates as OpenAPI 3.1, and omits assistant sessionContext input', () => {
  assert.equal(fs.existsSync(specPath), true, 'expected pricing/docs/openapi.yaml to exist');

  const raw = fs.readFileSync(specPath, 'utf8');
  const document = JSON.parse(raw);
  const validator = new OpenAPISchemaValidator({ version: 3 });
  const result = validator.validate(document);

  assert.deepEqual(result.errors, []);
  assert.equal(document.openapi, '3.1.0');

  const documentedPaths = Object.keys(document.paths).sort();
  assert.deepEqual(documentedPaths, [
    '/assistant',
    '/catalog/reload',
    '/catalog/search',
    '/catalog/{file}',
    '/chat',
    '/coverage',
    '/excel/estimate',
    '/health',
    '/providers',
    '/quote',
    '/sessions',
    '/sessions/{id}',
    '/sessions/{id}/messages',
    '/sessions/{id}/quote-export',
    '/sessions/{id}/state',
  ]);

  const assistantSchema = document.components.schemas.AssistantRequest;
  assert.equal(Object.hasOwn(assistantSchema.properties, 'sessionContext'), false);
  assert.equal(assistantSchema.additionalProperties, false);
});

test('legacy GET routes redirect permanently to /api/v1 equivalents', async () => {
  await withFreshServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/providers`, {
      method: 'GET',
      redirect: 'manual',
    });

    assert.equal(response.status, 301);
    assert.equal(response.headers.get('location'), '/api/v1/providers');
  });
});

test('legacy POST routes preserve method semantics while redirecting to /api/v1 equivalents', async () => {
  await withFreshServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/assistant`, {
      method: 'POST',
      redirect: 'manual',
      headers: {
        'content-type': 'application/json',
      },
      body: JSON.stringify({ text: 'hello' }),
    });

    assert.equal(response.status, 307);
    assert.equal(response.headers.get('location'), '/api/v1/assistant');
  });
});

test('versioned routes are the canonical API surface', async () => {
  await withFreshServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/v1/providers`);
    const json = await response.json();

    assert.equal(response.status, 200);
    assert.equal(typeof json.oci.configured, 'boolean');
    assert.equal(typeof json.oci.region, 'string');
  });
});
