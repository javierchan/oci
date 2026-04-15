'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const { resolveAssistantSessionContext } = require(path.join(ROOT, 'index.js'));

test('assistant session context ignores request-body state when a valid stored session exists', () => {
  const storedSessionContext = {
    lastQuote: { source: 'trusted server state' },
    workbookContext: { fileName: 'trusted.xlsx' },
  };
  const spoofedRequestBodyContext = {
    lastQuote: { source: 'spoofed client state' },
    workbookContext: { fileName: 'spoofed.xlsx' },
  };

  const resolved = resolveAssistantSessionContext(
    { sessionContext: storedSessionContext },
    spoofedRequestBodyContext,
  );

  assert.deepEqual(resolved, storedSessionContext);
  assert.notDeepEqual(resolved, spoofedRequestBodyContext);
});
