'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const { buildRegistryQuery } = require(path.join(__dirname, '..', 'request-query-helpers.js'));

test('buildRegistryQuery expands OIC shorthand and strips measured quantity tokens', () => {
  const query = buildRegistryQuery('Quote OIC Standard 2 instances 744h/month plus 10k queries');
  assert.equal(query, 'Oracle Integration Cloud Standard 2 instances 744h/month plus 10k queries');
});

test('buildRegistryQuery removes monthly wording and punctuation noise', () => {
  const query = buildRegistryQuery('Quote FastConnect, 10 Gbps, monthly');
  assert.equal(query, 'FastConnect');
});
