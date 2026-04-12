'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  buildEarlyAssistantReply,
  parseRegionAnswer,
} = require(path.join(ROOT, 'early-assistant-replies.js'));

test('early assistant replies detect greeting prompts', () => {
  const reply = buildEarlyAssistantReply({
    conversation: [],
    userText: 'hola',
  });

  assert.ok(reply);
  assert.equal(reply.mode, 'answer');
  assert.match(reply.message, /Puedo ayudarte a cotizar servicios de OCI/i);
});

test('early assistant replies answer FastConnect confidence follow-ups deterministically', () => {
  const reply = buildEarlyAssistantReply({
    conversation: [{ role: 'user', content: 'Quote OCI FastConnect 1 Gbps' }],
    userText: 'are you sure?',
  });

  assert.ok(reply);
  assert.equal(reply.mode, 'answer');
  assert.match(reply.message, /precio de FastConnect/i);
});

test('early assistant replies answer FastConnect region follow-ups deterministically', () => {
  const reply = buildEarlyAssistantReply({
    conversation: [{ role: 'user', content: 'Quote OCI FastConnect 1 Gbps' }],
    userText: 'Queretaro',
  });

  assert.ok(reply);
  assert.equal(reply.mode, 'answer');
  assert.match(reply.message, /mx-queretaro-1/i);
});

test('early assistant replies parse supported OCI regions', () => {
  assert.deepEqual(parseRegionAnswer('Queretaro'), {
    code: 'mx-queretaro-1',
    label: 'Mexico Central (Queretaro)',
  });
  assert.deepEqual(parseRegionAnswer('Monterrey'), {
    code: 'mx-monterrey-1',
    label: 'Mexico Northeast (Monterrey)',
  });
  assert.equal(parseRegionAnswer('Ashburn'), null);
});
