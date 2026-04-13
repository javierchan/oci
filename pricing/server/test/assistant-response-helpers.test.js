'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const { buildServiceUnavailableMessage } = require(path.join(__dirname, '..', 'assistant-response-helpers.js'));

test('buildServiceUnavailableMessage includes the original request when present', () => {
  const message = buildServiceUnavailableMessage('Quote unknown OCI service');
  assert.match(message, /This OCI pricing guidance service is not available/);
  assert.match(message, /`Quote unknown OCI service`/);
  assert.match(message, /I prefer to stop here rather than return an unreliable answer or quote\./);
});

test('buildServiceUnavailableMessage stays safe when the user text is empty', () => {
  const message = buildServiceUnavailableMessage('');
  assert.match(message, /This OCI pricing guidance service is not available/);
  assert.doesNotMatch(message, /``/);
  assert.match(message, /current GenAI controller and structured pricing context/);
});
