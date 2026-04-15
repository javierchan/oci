'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const SERVER_ROOT = path.resolve(__dirname, '..');
const SESSION_STORE_MODULE = path.join(SERVER_ROOT, 'session-store.js');

function makeTempStorePaths() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pricing-session-store-'));
  return {
    tempDir,
    storePath: path.join(tempDir, 'session-store.json'),
  };
}

function runSessionStoreScenario({ env = {}, script }) {
  const output = execFileSync(process.execPath, ['-e', script], {
    cwd: SERVER_ROOT,
    env: {
      ...process.env,
      ...env,
      SESSION_STORE_MODULE,
    },
    encoding: 'utf8',
  }).trim();

  return output ? JSON.parse(output) : null;
}

test('session store coalesces concurrent writes without torn persisted state', () => {
  const { tempDir, storePath } = makeTempStorePaths();

  try {
    const result = runSessionStoreScenario({
      env: {
        PRICING_SESSION_STORE_DIR: tempDir,
        PRICING_SESSION_STORE_PATH: storePath,
      },
      script: `
        const fs = require('fs');
        const sessionStore = require(process.env.SESSION_STORE_MODULE);

        async function main() {
          const clientId = 'concurrent-client';
          const session = sessionStore.createSession(clientId, 'Concurrent');
          const writes = Array.from({ length: 25 }, (_, index) => Promise.resolve().then(() => {
            sessionStore.appendMessage(clientId, session.id, {
              role: 'user',
              content: 'message-' + index,
            });
          }));

          await Promise.all(writes);
          await sessionStore.flushPendingWrites();

          const persisted = JSON.parse(fs.readFileSync(process.env.PRICING_SESSION_STORE_PATH, 'utf8'));
          const client = persisted.clients[clientId];
          const storedSession = client.sessions.find((item) => item.id === session.id);

          console.log(JSON.stringify({
            messageCount: storedSession.messages.length,
            persistedCount: client.sessions.length,
            first: storedSession.messages[0].content,
            last: storedSession.messages[storedSession.messages.length - 1].content,
          }));

          await sessionStore.shutdown();
        }

        main().catch((error) => {
          console.error(error);
          process.exit(1);
        });
      `,
    });

    assert.equal(result.messageCount, 25);
    assert.equal(result.persistedCount, 1);
    assert.equal(result.first, 'message-0');
    assert.equal(result.last, 'message-24');
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test('session store prunes expired sessions during startup load', () => {
  const { tempDir, storePath } = makeTempStorePaths();
  const now = Date.now();

  fs.writeFileSync(storePath, JSON.stringify({
    clients: {
      'ttl-client': {
        sessions: [
          {
            id: 'expired-session',
            title: 'Expired',
            ts: now - (3 * 24 * 60 * 60 * 1000),
            updatedAt: now - (3 * 24 * 60 * 60 * 1000),
            version: 1,
            messages: [{ role: 'user', content: 'expired' }],
            events: [],
            sessionContext: { lastQuote: { source: 'expired source' } },
            workbookContext: null,
          },
          {
            id: 'active-session',
            title: 'Active',
            ts: now - (2 * 60 * 60 * 1000),
            updatedAt: now - (60 * 60 * 1000),
            version: 1,
            messages: [{ role: 'user', content: 'active' }],
            events: [],
            sessionContext: { lastQuote: { source: 'active source' } },
            workbookContext: null,
          },
        ],
      },
    },
  }, null, 2));

  try {
    const result = runSessionStoreScenario({
      env: {
        PRICING_SESSION_STORE_DIR: tempDir,
        PRICING_SESSION_STORE_PATH: storePath,
        PRICING_SESSION_TTL_DAYS: '1',
      },
      script: `
        const fs = require('fs');
        const sessionStore = require(process.env.SESSION_STORE_MODULE);

        async function main() {
          await sessionStore.flushPendingWrites();
          const sessions = sessionStore.listSessions('ttl-client');
          const persisted = JSON.parse(fs.readFileSync(process.env.PRICING_SESSION_STORE_PATH, 'utf8'));

          console.log(JSON.stringify({
            listedIds: sessions.map((item) => item.id),
            persistedIds: persisted.clients['ttl-client'].sessions.map((item) => item.id),
          }));

          await sessionStore.shutdown();
        }

        main().catch((error) => {
          console.error(error);
          process.exit(1);
        });
      `,
    });

    assert.deepEqual(result.listedIds, ['active-session']);
    assert.deepEqual(result.persistedIds, ['active-session']);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test('session store applies per-client LRU eviction using updatedAt recency', () => {
  const { tempDir, storePath } = makeTempStorePaths();

  try {
    const result = runSessionStoreScenario({
      env: {
        PRICING_SESSION_STORE_DIR: tempDir,
        PRICING_SESSION_STORE_PATH: storePath,
        PRICING_SESSION_MAX_PER_CLIENT: '2',
      },
      script: `
        const sessionStore = require(process.env.SESSION_STORE_MODULE);

        async function wait(ms) {
          await new Promise((resolve) => setTimeout(resolve, ms));
        }

        async function main() {
          const clientId = 'lru-client';
          const first = sessionStore.createSession(clientId, 'First');
          await wait(10);
          const second = sessionStore.createSession(clientId, 'Second');
          await wait(10);
          sessionStore.appendMessage(clientId, first.id, {
            role: 'user',
            content: 'refresh-first',
          });
          await wait(10);
          const third = sessionStore.createSession(clientId, 'Third');
          await sessionStore.flushPendingWrites();

          console.log(JSON.stringify({
            ids: sessionStore.listSessions(clientId).map((item) => item.id),
            firstId: first.id,
            secondId: second.id,
            thirdId: third.id,
          }));

          await sessionStore.shutdown();
        }

        main().catch((error) => {
          console.error(error);
          process.exit(1);
        });
      `,
    });

    assert.deepEqual(result.ids, [result.thirdId, result.firstId]);
    assert.equal(result.ids.includes(result.secondId), false);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});
