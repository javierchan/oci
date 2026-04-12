'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  extractInlineShapeSelection,
  extractLicenseModeDirective,
  extractProductContextFromAssistant,
  findPriorProductPrompt,
  isLicenseModeFollowUp,
  isSessionQuoteFollowUp,
  isShapeSelectionFollowUp,
  isShortClarificationAnswer,
  isShortContextualAnswer,
  lastConversationItems,
  mergeClarificationAnswer,
  normalizeLicenseModeText,
  replaceShapeInPrompt,
  stripQuotePrefix,
} = require(path.join(ROOT, 'clarification-followup.js'));

test('clarification follow-up detects short license-only answers', () => {
  assert.equal(isShortClarificationAnswer('BYOL'), true);
  assert.equal(isShortClarificationAnswer('con licencia incluida'), true);
  assert.equal(isShortClarificationAnswer('I need two instances'), false);
});

test('clarification follow-up detects broader license follow-ups', () => {
  assert.equal(isLicenseModeFollowUp('use bring your own license please'), true);
  assert.equal(isLicenseModeFollowUp('licencia incluida'), true);
  assert.equal(isLicenseModeFollowUp('monitoring retrieval 4M datapoints'), false);
});

test('clarification follow-up detects short contextual answers and shape selections', () => {
  assert.equal(isShortContextualAnswer('reserved'), true);
  assert.equal(isShortContextualAnswer('0.7'), true);
  assert.equal(isShortContextualAnswer('VM.Standard.E5.Flex'), true);
  assert.equal(isShapeSelectionFollowUp('VM.Standard.E5.Flex'), true);
  assert.equal(isShapeSelectionFollowUp('Compute and block storage'), false);
});

test('clarification follow-up tracks the latest assistant and user items', () => {
  const items = lastConversationItems([
    { role: 'user', content: 'Quote OIC Standard' },
    { role: 'assistant', content: 'Do you want Oracle Integration Cloud Standard as BYOL or License Included?' },
    { role: 'user', content: 'BYOL' },
  ]);

  assert.equal(items.lastAssistant.content, 'Do you want Oracle Integration Cloud Standard as BYOL or License Included?');
  assert.equal(items.lastUser.content, 'BYOL');
});

test('clarification follow-up extracts product context from assistant messages', () => {
  assert.equal(
    extractProductContextFromAssistant('Do you want Oracle Integration Cloud Standard as BYOL or License Included?'),
    'Oracle Integration Cloud Standard',
  );
  assert.equal(
    extractProductContextFromAssistant('I prepared a quotation for `OCI Block Volume`.'),
    'OCI Block Volume',
  );
});

test('clarification follow-up finds the prior product prompt before license-only answers', () => {
  const conversation = [
    { role: 'user', content: 'Quote Oracle Integration Cloud Standard' },
    { role: 'assistant', content: 'Do you want Oracle Integration Cloud Standard as BYOL or License Included?' },
    { role: 'user', content: 'BYOL' },
  ];

  assert.equal(findPriorProductPrompt(conversation), 'Quote Oracle Integration Cloud Standard');
});

test('clarification follow-up normalizes and extracts license directives', () => {
  assert.equal(normalizeLicenseModeText('bring your own license'), 'BYOL');
  assert.equal(normalizeLicenseModeText('licencia incluida'), 'License Included');
  assert.equal(extractLicenseModeDirective('please use BYOL'), 'BYOL');
  assert.equal(extractLicenseModeDirective('license included'), 'License Included');
  assert.equal(extractLicenseModeDirective('standard edition'), '');
});

test('clarification follow-up merges license-only answers back into the prior quote prompt', () => {
  const conversation = [
    { role: 'user', content: 'Quote Oracle Integration Cloud Standard' },
    { role: 'assistant', content: 'Do you want Oracle Integration Cloud Standard as BYOL or License Included?' },
  ];

  assert.equal(
    mergeClarificationAnswer(conversation, 'BYOL'),
    'Quote Oracle Integration Cloud Standard BYOL',
  );
});

test('clarification follow-up merges shape-only answers back into shape-clarification prompts', () => {
  const conversation = [
    { role: 'user', content: 'Quote 2 instances 8 ocpus 64 gb ram' },
    { role: 'assistant', content: 'Which OCI VM shape should I use for this quote?' },
  ];

  assert.equal(
    mergeClarificationAnswer(conversation, 'VM.Standard.E5.Flex'),
    'Quote 2 instances 8 ocpus 64 gb ram VM.Standard.E5.Flex',
  );
});

test('clarification follow-up detects session quote follow-up prompts conservatively', () => {
  assert.equal(isSessionQuoteFollowUp('add 2 instances'), true);
  assert.equal(isSessionQuoteFollowUp('capacity reservation 0.7'), true);
  assert.equal(isSessionQuoteFollowUp('VM.Standard.E5.Flex'), true);
  assert.equal(isSessionQuoteFollowUp('tell me about OIC billing dimensions in general'), false);
});

test('clarification follow-up strips quote prefixes and replaces inline shapes safely', () => {
  assert.equal(stripQuotePrefix('Quote FastConnect 10 Gbps'), 'FastConnect 10 Gbps');
  assert.equal(
    replaceShapeInPrompt('Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM', 'VM.Standard.E5.Flex'),
    'Quote VM.Standard.E5.Flex 4 OCPUs 16 GB RAM',
  );
  assert.equal(
    extractInlineShapeSelection('Use AMD with VM.Standard.E5.Flex and 20 VPUs'),
    'VM.Standard.E5.Flex',
  );
});
