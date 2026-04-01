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
