'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  shouldForceQuoteFollowUpRoute,
  applyQuoteFollowUpIntentOverride,
} = require(path.join(ROOT, 'quote-followup-intent.js'));

test('quote follow-up intent forces route for short active-quote mutations', () => {
  const result = shouldForceQuoteFollowUpRoute({
    sessionContext: {
      lastQuote: {
        source: 'Quote Flexible Load Balancer 100 Mbps',
      },
    },
    userText: '250 Mbps',
    isSessionQuoteFollowUp: () => true,
  });

  assert.equal(result, true);
});

test('quote follow-up intent does not force route for discovery-style active-quote questions', () => {
  const result = shouldForceQuoteFollowUpRoute({
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E4.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs',
      },
    },
    userText: 'Only OCPU, no disk, no memory?',
    isSessionQuoteFollowUp: () => true,
  });

  assert.equal(result, false);
});

test('quote follow-up intent override sets quote-followup route and modify-quote plan', () => {
  const nextIntent = applyQuoteFollowUpIntentOverride({
    route: 'general_answer',
    intent: 'answer',
    shouldQuote: false,
    quotePlan: { domain: 'compute' },
  });

  assert.equal(nextIntent.route, 'quote_followup');
  assert.equal(nextIntent.intent, 'quote');
  assert.equal(nextIntent.shouldQuote, true);
  assert.equal(nextIntent.quotePlan.action, 'modify_quote');
  assert.equal(nextIntent.quotePlan.targetType, 'quote');
  assert.equal(nextIntent.quotePlan.useDeterministicEngine, true);
  assert.equal(nextIntent.quotePlan.domain, 'compute');
});
