'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadAssistantWithStubs, buildIndex, assertWithin } = require('./assistant-test-helpers');

test('quote enrichment sanitizer drops numeric breakdowns and keeps technical considerations', () => {
  const { sanitizeQuoteEnrichment } = loadAssistantWithStubs(() => ({ intent: 'quote', reformulatedRequest: 'Quote WAF' }));
  const sanitized = sanitizeQuoteEnrichment([
    '## OCI Considerations for Web Application Firewall',
    '* WAF pricing has fixed instance and variable request dimensions.',
    '',
    '## Breakdown of Costs',
    '* 2 instances at $5 = $10',
    '* 25 million requests = $9',
    '',
    '## Migration Notes',
    '* Not applicable.',
  ].join('\n'));

  assert.match(sanitized, /## OCI Considerations/);
  assert.match(sanitized, /fixed instance and variable request dimensions/);
  assert.match(sanitized, /## Migration Notes/);
  assert.doesNotMatch(sanitized, /\$10|\$9|Breakdown of Costs/);
});

test('quote enrichment sanitizer drops migration notes when the quote is not from VMware or RVTools', () => {
  const { sanitizeQuoteEnrichment } = loadAssistantWithStubs(() => ({ intent: 'quote', reformulatedRequest: 'Quote Monitoring' }));
  const sanitized = sanitizeQuoteEnrichment([
    '## OCI Considerations',
    '* Monitoring and notifications are usage-driven.',
    '',
    '## Migration Notes',
    '* Review VMware platform VMs before migration.',
  ].join('\n'), { allowMigrationNotes: false });

  assert.match(sanitized, /## OCI Considerations/);
  assert.doesNotMatch(sanitized, /## Migration Notes|VMware platform VMs/);
});
