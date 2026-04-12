'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const { reconcilePostIntentFollowUp } = require(path.join(ROOT, 'post-intent-followup.js'));

test('post-intent follow-up merges short contextual follow-ups into reformulated and normalized request', () => {
  const result = reconcilePostIntentFollowUp({
    intent: {
      reformulatedRequest: '20 VPUs',
      normalizedRequest: '20 VPUs',
    },
    effectiveUserText: 'Quote OCI Block Volume with 400 GB and 20 VPUs',
    userText: '20 VPUs',
    contextualFollowUp: true,
    conversation: [],
    initialFlexComparison: null,
    extractFlexComparisonContext: () => null,
  });

  assert.equal(result.mergedContextualFollowUp, true);
  assert.equal(result.intent.reformulatedRequest, 'Quote OCI Block Volume with 400 GB and 20 VPUs');
  assert.equal(result.intent.normalizedRequest, 'Quote OCI Block Volume with 400 GB and 20 VPUs');
});

test('post-intent follow-up normalizes existing reformulated request for contextual follow-ups even when nothing merged', () => {
  const result = reconcilePostIntentFollowUp({
    intent: {
      reformulatedRequest: 'SI cambiamos el block storage a 20VPU\'s como se veria este quote?',
      normalizedRequest: '',
    },
    effectiveUserText: 'SI cambiamos el block storage a 20VPU\'s como se veria este quote?',
    userText: 'SI cambiamos el block storage a 20VPU\'s como se veria este quote?',
    contextualFollowUp: true,
    conversation: [],
    initialFlexComparison: null,
    extractFlexComparisonContext: () => null,
  });

  assert.equal(result.mergedContextualFollowUp, false);
  assert.equal(result.intent.normalizedRequest, 'SI cambiamos el block storage a 20VPU\'s como se veria este quote?');
});

test('post-intent follow-up resolves flex comparison from post-intent prompt when needed', () => {
  const result = reconcilePostIntentFollowUp({
    intent: {
      reformulatedRequest: 'Compare VM.Standard.E4.Flex vs VM.Standard.E5.Flex capacity reservation',
      normalizedRequest: '',
    },
    effectiveUserText: '0.7',
    userText: '0.7',
    contextualFollowUp: true,
    conversation: [{ role: 'user', content: 'compare shapes' }],
    initialFlexComparison: null,
    extractFlexComparisonContext: (_conversation, _userText, fallbackPrompt) => ({
      basePrompt: fallbackPrompt,
      modifierKind: 'capacity-reservation',
    }),
  });

  assert.ok(result.postIntentFlexComparison);
  assert.equal(result.postIntentFlexComparison.basePrompt, 'Compare VM.Standard.E4.Flex vs VM.Standard.E5.Flex capacity reservation');
});
