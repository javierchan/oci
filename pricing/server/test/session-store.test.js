'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const sessionStore = require(path.join(ROOT, 'session-store.js'));

test('session store isolates sessions by client id', () => {
  const clientA = `test_client_a_${Date.now()}`;
  const clientB = `test_client_b_${Date.now()}`;
  const sessionA = sessionStore.createSession(clientA, 'A');
  const sessionB = sessionStore.createSession(clientB, 'B');

  sessionStore.appendMessage(clientA, sessionA.id, { role: 'user', content: 'hello a' });
  sessionStore.appendMessage(clientB, sessionB.id, { role: 'user', content: 'hello b' });
  sessionStore.updateSessionState(clientA, sessionA.id, {
    workbookContext: { fileName: 'a.xlsx', shapeName: 'VM.Standard3.Flex' },
    sessionContext: { currentIntent: 'workbook_quote' },
  });

  const loadedA = sessionStore.getSession(clientA, sessionA.id);
  const loadedB = sessionStore.getSession(clientB, sessionB.id);

  assert.equal(loadedA.messages.length, 1);
  assert.equal(loadedB.messages.length, 1);
  assert.equal(loadedA.messages[0].content, 'hello a');
  assert.equal(loadedB.messages[0].content, 'hello b');
  assert.equal(loadedA.workbookContext.fileName, 'a.xlsx');
  assert.equal(loadedB.workbookContext, null);
  assert.equal(sessionStore.getSession(clientA, sessionB.id), null);
  assert.equal(sessionStore.getSession(clientB, sessionA.id), null);
});

test('session store increments version and rejects stale writes when expectedVersion is supplied', () => {
  const clientId = `test_client_version_${Date.now()}`;
  const session = sessionStore.createSession(clientId, 'Versioned');
  assert.equal(session.version, 1);

  const afterMessage = sessionStore.appendMessage(
    clientId,
    session.id,
    { role: 'user', content: 'hello versioned' },
    { expectedVersion: 1 },
  );
  assert.equal(afterMessage.version, 2);

  const conflict = sessionStore.updateSessionState(
    clientId,
    session.id,
    { sessionContext: { foo: 'bar' } },
    { expectedVersion: 1 },
  );
  assert.equal(conflict.conflict, true);
  assert.equal(conflict.session.version, 2);
  assert.equal(conflict.session.sessionContext, null);
});

test('session store keeps an isolated bounded event log per session', () => {
  const clientId = `test_client_events_${Date.now()}`;
  const session = sessionStore.createSession(clientId, 'Events');

  sessionStore.appendEvent(clientId, session.id, {
    type: 'assistant_reply',
    data: { route: 'product_discovery', topic: 'vm_shapes' },
  });

  const loaded = sessionStore.getSession(clientId, session.id);
  assert.equal(Array.isArray(loaded.events), true);
  assert.equal(loaded.events.length, 1);
  assert.match(loaded.events[0].id, /^evt_/);
  assert.equal(loaded.events[0].type, 'assistant_reply');
  assert.equal(loaded.events[0].data.route, 'product_discovery');
});

test('session store compacts adjacent duplicate messages with identical role and content', () => {
  const clientId = `test_client_compact_${Date.now()}`;
  const session = sessionStore.createSession(clientId, 'Compact');

  sessionStore.appendMessage(clientId, session.id, { role: 'user', content: 'duplicate question' });
  sessionStore.appendMessage(clientId, session.id, { role: 'user', content: 'duplicate question' });
  sessionStore.appendMessage(clientId, session.id, { role: 'assistant', content: 'single answer' });
  sessionStore.appendMessage(clientId, session.id, { role: 'assistant', content: 'single answer' });

  const loaded = sessionStore.getSession(clientId, session.id);
  assert.equal(loaded.messages.length, 2);
  assert.equal(loaded.messages[0].role, 'user');
  assert.equal(loaded.messages[0].content, 'duplicate question');
  assert.equal(loaded.messages[1].role, 'assistant');
  assert.equal(loaded.messages[1].content, 'single answer');
});
