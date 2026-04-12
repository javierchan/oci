'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  applySessionFollowUpDirective,
  getActiveQuoteFamilyContext,
  mergeSessionQuoteFollowUp,
  mergeSessionQuoteFollowUpByRoute,
  preserveCriticalPromptModifiers,
} = require(path.join(ROOT, 'session-quote-followup.js'));

test('session quote follow-up helper swaps flex shapes while preserving attached block storage', () => {
  const nextPrompt = applySessionFollowUpDirective(
    'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 100 GB Block Volume',
    'VM.Standard.E5.Flex',
    {
      activeFamily: {
        familyId: 'compute_flex',
        parsed: { ocpus: 4, memoryGb: 16, storageGb: 100 },
      },
    },
  );

  assert.match(nextPrompt, /VM\.Standard\.E5\.Flex/i);
  assert.match(nextPrompt, /100 GB Block Volume/i);
  assert.doesNotMatch(nextPrompt, /VM\.Standard3\.Flex/i);
});

test('session quote follow-up helper removes composite services without dropping the rest of the quote', () => {
  const nextPrompt = applySessionFollowUpDirective(
    'Quote Oracle Integration Cloud Standard 1 instance plus Flexible Load Balancer 10 Mbps',
    'sin LB',
    {
      activeFamily: {
        familyId: 'integration_oic_standard',
        parsed: { instances: 1 },
      },
    },
  );

  assert.match(nextPrompt, /Oracle Integration Cloud Standard/i);
  assert.doesNotMatch(nextPrompt, /Load Balancer/i);
});

test('session quote follow-up helper replaces supported sibling services inside composite quotes', () => {
  const nextPrompt = applySessionFollowUpDirective(
    'Quote Base Database Service Enterprise License Included 2 OCPUs plus Oracle Integration Cloud Standard 1 instance',
    'cambia OIC Standard por OIC Enterprise',
    {
      activeFamily: {
        familyId: 'database_base',
        parsed: { ocpus: 2, licenseModel: 'License Included' },
      },
      followUpFamilyId: 'integration_oic_enterprise',
    },
  );

  assert.match(nextPrompt, /Base Database Service Enterprise/i);
  assert.match(nextPrompt, /Oracle Integration Cloud Enterprise/i);
  assert.doesNotMatch(nextPrompt, /Oracle Integration Cloud Standard/i);
});

test('session quote follow-up helper keeps composite context when monitoring retrieval switches to ingestion', () => {
  const nextPrompt = applySessionFollowUpDirective(
    'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
    'cambia Monitoring Retrieval por Monitoring Ingestion 2500000 datapoints',
    {
      activeFamily: {
        familyId: 'compute_flex',
        parsed: { ocpus: 4, memoryGb: 16, storageGb: 200, vpus: 20 },
      },
      followUpFamilyId: 'observability_monitoring',
    },
  );

  assert.match(nextPrompt, /VM\.Standard3\.Flex/i);
  assert.match(nextPrompt, /FastConnect 10 Gbps/i);
  assert.match(nextPrompt, /Monitoring Ingestion 2500000 datapoints/i);
  assert.doesNotMatch(nextPrompt, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session quote follow-up helper prefers inferred compute_flex family over generic stored family ids', () => {
  const activeFamily = getActiveQuoteFamilyContext({
    lastQuote: {
      serviceFamily: 'compute_vm_generic',
      source: 'Quote VM.Standard.E5.Flex 4 OCPUs 16 GB RAM',
    },
  });

  assert.equal(activeFamily.familyId, 'compute_flex');
  assert.equal(activeFamily.parsed.ocpus, 4);
});

test('session quote follow-up helper merges route-driven quote follow-ups only for quote_followup routes', () => {
  const sessionContext = {
    lastQuote: {
      serviceFamily: 'compute_flex',
      source: 'Quote VM.Standard.E5.Flex 4 OCPUs 16 GB RAM',
    },
  };

  const merged = mergeSessionQuoteFollowUpByRoute(
    sessionContext,
    { route: 'quote_followup', serviceFamily: 'compute_flex' },
    'capacity reservation 0.7',
  );
  const ignored = mergeSessionQuoteFollowUpByRoute(
    sessionContext,
    { route: 'product_discovery', serviceFamily: 'compute_flex' },
    'capacity reservation 0.7',
  );

  assert.match(merged, /capacity reservation 0\.7/i);
  assert.equal(ignored, '');
});

test('session quote follow-up helper preserves critical prompt modifiers from the reference prompt', () => {
  assert.equal(
    preserveCriticalPromptModifiers('Quote OCI Data Integration 2 workspaces', 'Quote OCI Data Integration metered 2 workspaces'),
    'Quote OCI Data Integration 2 workspaces metered',
  );
});

test('session quote follow-up helper leaves discovery-style questions untouched', () => {
  const nextPrompt = mergeSessionQuoteFollowUp(
    {
      lastQuote: {
        serviceFamily: 'integration_oic_standard',
        source: 'Quote Oracle Integration Cloud Standard 1 instance',
      },
    },
    'What inputs do I need before quoting OIC?',
  );

  assert.equal(nextPrompt, 'What inputs do I need before quoting OIC?');
});

test('session quote follow-up helper normalizes short prefixed answers before mutating the active quote', () => {
  const nextPrompt = mergeSessionQuoteFollowUp(
    {
      lastQuote: {
        serviceFamily: 'storage_block_volume',
        source: 'Quote OCI Block Volume 1000 GB and 10 VPUs',
      },
    },
    'y 20 VPUs',
  );

  assert.match(nextPrompt, /20 VPUs/i);
  assert.doesNotMatch(nextPrompt, /\b10 VPUs\b/i);
});
