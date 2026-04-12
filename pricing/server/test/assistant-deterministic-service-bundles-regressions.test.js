'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const { loadAssistantWithStubs, buildIndex, assertWithin } = require('./assistant-test-helpers');

const ROOT = path.resolve(__dirname, '..');

test('assistant keeps monitoring retrieval in observability bundles with https delivery', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Monitoring Ingestion 7500000 datapoints plus Monitoring Retrieval 12000000 datapoints plus HTTPS Delivery 5000000 delivery operations. Explain how OCI measures the main billing dimensions.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90925/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B90940/);
});

test('assistant keeps fleet application management and email delivery in mixed operations bundles', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Fleet Application Management 20 managed resources plus OCI Batch 15 jobs plus Notifications Email Delivery 250000 emails per month. Explain how OCI measures the main billing dimensions.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B110475/);
  assert.match(reply.message, /B112107/);
  assert.match(reply.message, /B90941/);
});

test('assistant keeps IAM SMS in mixed notifications delivery bundles', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Notifications HTTPS Delivery 3000000 delivery operations plus Notifications Email Delivery 250000 emails per month plus IAM SMS 12 SMS messages. Explain how OCI measures the main billing dimensions.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90940/);
  assert.match(reply.message, /B90941/);
  assert.match(reply.message, /B93496/);
});

test('assistant keeps DNS in mixed email delivery and health checks bundles', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Notifications Email Delivery 100000 emails per month plus DNS 2000000 queries per month plus Health Checks 5 endpoints. Explain how OCI measures the main billing dimensions.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90941/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.message, /B90325/);
});

test('assistant keeps API Gateway in functions and dns bundles', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Functions 2000000 invocations per month 2000 ms per invocation 256 MB memory plus API Gateway 5000000 API calls per month plus DNS 5000000 queries per month. Explain how OCI measures the main billing dimensions.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90617/);
  assert.match(reply.message, /B90618/);
  assert.match(reply.message, /B92072/);
  assert.match(reply.message, /B88525/);
});

test('assistant keeps threat intelligence in mixed ai and dns bundles', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Generative AI Vector Store Retrieval 5000 requests plus OCI Generative AI Web Search 12000 requests plus Oracle Threat Intelligence Service 100 API calls plus DNS 1000000 queries per month. Explain how OCI measures the main billing dimensions.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B112416/);
  assert.match(reply.message, /B111973/);
  assert.match(reply.message, /B94173/);
  assert.match(reply.message, /B88525/);
});

test('quote narrative drops conflicting usage assumptions from GenAI when deterministic hours differ', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [
      'Region is not specified, assuming a standard region',
      'Usage is not specified, assuming 730 hours/month',
    ],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {
      ocpus: 4,
      memoryGb: 16,
      capacityGb: 200,
      shapeSeries: 'E4.FLEX',
    },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote E4.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.doesNotMatch(reply.message, /730 hours\/month/);
});

test('quote narrative drops non-verifiable model assumptions for plain text requests', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [
      'Linux OS',
      'US region',
      '1 year commitment',
      'no additional storage performance',
    ],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {
      ocpus: 4,
      memoryGb: 16,
      capacityGb: 200,
      shapeSeries: 'E4.FLEX',
    },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote E4.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.doesNotMatch(reply.message, /Linux OS/);
  assert.doesNotMatch(reply.message, /US region/);
  assert.doesNotMatch(reply.message, /1 year commitment/);
  assert.doesNotMatch(reply.message, /no additional storage performance/);
});

test('large composite bundles explain OCI measurement by billing dimension instead of only by SKU', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote a global customer platform with 4x E4.Flex 4 OCPUs 32 GB RAM, 2x E5.Flex 8 OCPUs 64 GB RAM, Flexible Load Balancer 500 Mbps, Block Volume 3000 GB with 20 VPUs, File Storage 10 TB and 10 performance units per GB per month, Object Storage 30 TB per month, Web Application Firewall 3 instances and 100000000 requests per month, Network Firewall 2 firewalls and 20000 GB data processed per month, FastConnect 10 Gbps, DNS 10000000 queries per month, Health Checks 10 endpoints, Oracle Integration Cloud Enterprise License Included 3 instances 744h/month, Oracle Analytics Cloud Enterprise 75 users, Base Database Service Enterprise License Included 8 OCPUs and 2000 GB storage, Data Safe for Database Cloud Service 6 databases, Log Analytics active storage 1000 GB per month, and Log Analytics archival storage 4000 GB per month. Explain how OCI measures the main billing dimensions.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /How OCI measures this:/);
  assert.match(reply.message, /Compute-style charges are driven by provisioned CPU, memory, or execution usage over time/i);
  assert.match(reply.message, /Storage-style charges are driven by provisioned or retained capacity/i);
  assert.match(reply.message, /Transaction and request charges are volume-based/i);
  assert.match(reply.message, /Network charges are driven by provisioned connectivity, bandwidth configuration, or request\/query volume depending on the service/i);
  assert.doesNotMatch(reply.message, /B93113 - Compute - Standard - E4 - OCPU is billed by OCPU-hour/i);
});

test('explicit flex VM with block storage keeps both compute and block volume lines', () => {
  const index = buildIndex();
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));

  const quote = quoteFromPrompt(
    index,
    'Quote E4.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage',
  );

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B93113/);
  assert.match(quote.markdown, /B93114/);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
});

test('direct object storage quote resolves to storage SKU instead of requests SKU', () => {
  const index = buildIndex();
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));

  const quote = quoteFromPrompt(
    index,
    'Quote Object Storage 5 TB per month',
  );

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B91628/);
  assert.doesNotMatch(quote.markdown, /B91627/);
});

test('direct flexible load balancer quote includes base and bandwidth lines', () => {
  const index = buildIndex();
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));

  const quote = quoteFromPrompt(
    index,
    'Quote Flexible Load Balancer 100 Mbps per month',
  );

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B93030/);
  assert.match(quote.markdown, /B93031/);
});

test('direct block volume quote keeps storage and performance lines instead of throwing', () => {
  const index = buildIndex();
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));

  const quote = quoteFromPrompt(
    index,
    'Quote Block Volume 400 GB with 30 VPUs',
  );

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
});

test('assistant explains FastConnect consumption in quote narratives', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_fastconnect',
    serviceName: 'OCI FastConnect',
    extractedInputs: { bandwidthGbps: 10 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const response = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote FastConnect 10 Gbps',
  });

  assert.equal(response.ok, true);
  assert.equal(response.mode, 'quote');
  assert.match(response.message, /How OCI measures this:/);
  assert.match(response.message, /billed by port-hour/i);
});

test('assistant explains Block Volume storage and performance consumption in quote narratives', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'storage_block',
    serviceName: 'OCI Block Volume',
    extractedInputs: { capacityGb: 400, vpuPerGb: 30 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const response = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Block Volume 400 GB with 30 VPUs',
  });

  assert.equal(response.ok, true);
  assert.equal(response.mode, 'quote');
  assert.match(response.message, /How OCI measures this:/);
  assert.match(response.message, /billed by provisioned storage capacity in GB-month/i);
  assert.match(response.message, /performance units per GB-month/i);
});

test('log analytics archival storage uses archival SKU and documents the storage-unit inference', () => {
  const index = buildIndex();
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));

  const quote = quoteFromPrompt(
    index,
    'Quote Log Analytics archival storage 600 GB per month',
  );

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B92809/);
  assert.doesNotMatch(quote.markdown, /B95634/);
  assert.match((quote.warnings || []).join('\n'), /infers 1 storage unit = 300 GB/i);
});

test('assistant preserves archival variant when canonicalizing log analytics requests', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_log_analytics',
    serviceName: 'OCI Log Analytics',
    extractedInputs: { capacityGb: 600 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Log Analytics archival storage 600 GB per month',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B92809/);
  assert.doesNotMatch(reply.message, /B95634/);
});

test('composite workload keeps block storage object storage and flexible load balancer lines together', () => {
  const index = buildIndex();
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));

  const quote = quoteFromPrompt(
    index,
    'Quote 3x E4.Flex 4 OCPUs 32 GB RAM + 500 GB Block Storage + 5 TB Object Storage + Flex Load Balancer 100 Mbps',
  );

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B93113/);
  assert.match(quote.markdown, /B93114/);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
  assert.match(quote.markdown, /B91628/);
  assert.match(quote.markdown, /B93030/);
  assert.match(quote.markdown, /B93031/);
});

test('assistant composes integration analytics and object storage bundles instead of collapsing to one family', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { instances: 2, users: 50, capacityGb: 5 * 1024 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote an integration and analytics bundle: Oracle Integration Cloud Enterprise License Included 2 instances 744h/month, Oracle Analytics Cloud Enterprise 50 users, Object Storage 5 TB per month',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B89640/);
  assert.match(reply.message, /B92683/);
  assert.match(reply.message, /B91628/);
  assertWithin(reply.quote.totals.monthly, 6050.5264, 0.05);
});

test('assistant composes secure edge bundles instead of keeping only load balancer lines', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { wafInstances: 2, requestCount: 50000000, firewallInstances: 2, dataProcessedGb: 10000, bandwidthGbps: 10 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote a secure edge workload: Web Application Firewall 2 instances and 50000000 requests per month, Network Firewall 2 firewalls and 10000 GB data processed per month, Flexible Load Balancer 100 Mbps, FastConnect 10 Gbps',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B94579/);
  assert.match(reply.message, /B94277/);
  assert.match(reply.message, /B95403/);
  assert.match(reply.message, /B95404/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B88326/);
  assertWithin(reply.quote.totals.monthly, 3965.376, 0.05);
});

test('assistant keeps DNS as a separate line in mixed edge-security bundles', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { firewallInstances: 2, dataProcessedGb: 20000, wafInstances: 2, requestCount: 60000000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Network Firewall 2 firewalls and 20000 GB data processed per month plus Web Application Firewall 2 instances and 60000000 requests per month plus DNS 5000000 queries per month. Explain how OCI measures the main billing dimensions.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B95403/);
  assert.match(reply.message, /B95404/);
  assert.match(reply.message, /B94579/);
  assert.match(reply.message, /B94277/);
  assert.match(reply.message, /B88525/);
});

test('direct OCI Functions quote resolves execution and invocation lines from ms per invocation wording', () => {
  const index = buildIndex();
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));

  const quote = quoteFromPrompt(
    index,
    'Quote OCI Functions 3100000 invocations per month 30000 ms per invocation 128 MB memory',
  );

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B90617/);
  assert.match(quote.markdown, /B90618/);
});

test('assistant composes serverless retrieval bundles with OCI Functions and generative ai request lines', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {
      requestCount: 12000,
      invocationsPerMonth: 3100000,
      executionMs: 30000,
      memoryMb: 128,
    },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote a serverless retrieval workload: OCI Functions 3100000 invocations per month 30000 ms per invocation 128 MB memory, OCI Generative AI Agents Data Ingestion 100000 transactions, OCI Generative AI Vector Store Retrieval 50000 requests, OCI Generative AI Web Search 12000 requests',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B90617/);
  assert.match(reply.message, /B90618/);
  assert.match(reply.message, /B110463/);
  assert.match(reply.message, /B112416/);
  assert.match(reply.message, /B111973/);
  assertWithin(reply.quote.totals.monthly, 304.28125, 0.05);
});

test('assistant composes plus-separated autonomous bundles instead of collapsing to one family', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Autonomous AI Lakehouse BYOL 8 ECPUs and 2000 GB storage per month plus Data Integration 500 GB processed per hour for 744h/month plus Object Storage 20 TB per month',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B95703/);
  assert.match(reply.message, /B95706/);
  assert.match(reply.message, /B92599/);
  assert.match(reply.message, /B91628/);
});

test('assistant composes exadata cloud customer bundles instead of collapsing to one service', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    normalizedRequest: text,
    assumptions: [],
    confidence: 0.9,
  }));
  const reply = await respondToAssistant({
    cfg: { ok: true },
    index,
    conversation: [],
    userText: 'Quote Exadata Cloud@Customer License Included 8 OCPUs on base system X10M plus Data Safe for Database Cloud Service 8 databases plus Log Analytics active storage 1000 GB per month',
    imageDataUrl: '',
  });
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B91363|B110663|B110627|B96610|B96611|B96615/);
  assert.match(reply.message, /B91632/);
  assert.match(reply.message, /B95634/);
});

test('assistant keeps deterministic bundle output when a mixed bundle includes base database plus integration and analytics lines', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    normalizedRequest: text,
    assumptions: [],
    confidence: 0.9,
  }));
  const reply = await respondToAssistant({
    cfg: { ok: true },
    index,
    conversation: [],
    userText: 'Quote Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage plus Oracle Integration Cloud Standard BYOL 2 instances for 744h/month plus Oracle Analytics Cloud Professional 100 users',
    imageDataUrl: '',
  });
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B90573/);
  assert.match(reply.message, /B111584/);
  assert.match(reply.message, /B89643/);
  assert.match(reply.message, /B92682/);
  assert.doesNotMatch(reply.message, /Could not deterministically quote segment: Quote Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage/);
});

test('assistant composes generative ai bundles even when all segments are in the same family', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    normalizedRequest: text,
    assumptions: [],
    confidence: 0.9,
  }));
  const reply = await respondToAssistant({
    cfg: { ok: true },
    index,
    conversation: [],
    userText: 'Quote OCI Generative AI Vector Store Retrieval 150000 requests plus OCI Generative AI Web Search 40000 requests plus OCI Generative AI Agents Data Ingestion 250000 transactions',
    imageDataUrl: '',
  });
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B112416/);
  assert.match(reply.message, /B111973/);
  assert.match(reply.message, /B110463/);
});

test('assistant normalizes abbreviated generative ai segments inside hybrid bundles', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    normalizedRequest: text,
    assumptions: [],
    confidence: 0.9,
  }));
  const reply = await respondToAssistant({
    cfg: { ok: true },
    index,
    conversation: [],
    userText: 'Quote Data Integration workspace usage 2 workspaces 744h/month plus Data Integration 150 GB processed per hour for 744h/month plus Oracle Integration Cloud Standard License Included 2 instances plus Generative AI Agents Data Ingestion 250000 transactions plus Vector Store Retrieval 80000 requests plus Web Search 30000 requests plus API Gateway 12000000 API calls/month plus Object Storage 12 TB/month plus Notifications Email Delivery 250000 emails/month. Also explain how OCI measures it.',
    imageDataUrl: '',
  });
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B110463/);
  assert.match(reply.message, /B112416/);
  assert.match(reply.message, /B111973/);
});

test('assistant keeps monitoring separate from log analytics archival in observability bundles', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    normalizedRequest: text,
    assumptions: [],
    confidence: 0.9,
  }));
  const reply = await respondToAssistant({
    cfg: { ok: true },
    index,
    conversation: [],
    userText: 'Quote Log Analytics active storage 1200 GB per month plus Log Analytics archival storage 4000 GB per month plus Monitoring Ingestion 7500000 datapoints',
    imageDataUrl: '',
  });
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B95634/);
  assert.match(reply.message, /B92809/);
  assert.match(reply.message, /B90925/);
});

test('assistant keeps active and archival log analytics lines when both are present in one mixed segment', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    normalizedRequest: text,
    assumptions: [],
    confidence: 0.9,
  }));
  const reply = await respondToAssistant({
    cfg: { ok: true },
    index,
    conversation: [],
    userText: 'Quote an enterprise stack with Log Analytics active 800 GB monthly, archival 2500 GB monthly, and Monitoring Ingestion 6000000 datapoints. Explain how OCI measures the main billing dimensions.',
    imageDataUrl: '',
  });
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B95634/);
  assert.match(reply.message, /B92809/);
  assert.match(reply.message, /B90925/);
});

test('assistant recognizes LB and OIC abbreviations in large architecture bundles without merging away load balancer or health checks', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    normalizedRequest: text,
    assumptions: [],
    confidence: 0.9,
  }));
  const reply = await respondToAssistant({
    cfg: { ok: false },
    index,
    conversation: [],
    userText: 'Need a consolidated OCI estimate for an enterprise stack: 3 E4.Flex VMs 4 OCPU 32GB RAM, 2 E5.Flex VMs 8 OCPU 64GB, LB 300 Mbps, block volume 4 TB 20 VPU, object storage 15 TB, WAF 2 instances 75000000 requests monthly, network firewall 2 firewalls 12000 GB processed monthly, dns 7000000 queries, health checks 8 endpoints, OIC enterprise license included 2 instances 744h, analytics cloud enterprise 60 users, base database service enterprise LI 6 OCPU and 1500 GB storage, log analytics active 800 GB monthly, archival 2500 GB monthly. Explain how OCI measures the main billing dimensions.',
    imageDataUrl: '',
  });
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90323|B90325/);
  assert.match(reply.message, /B89640/);
  assert.match(reply.message, /B95634/);
  assert.match(reply.message, /B92809/);
});

test('assistant composes observability bundles with monitoring retrieval and notifications instead of drifting to unrelated services', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    normalizedRequest: text,
    assumptions: [],
    confidence: 0.9,
  }));
  const reply = await respondToAssistant({
    cfg: { ok: true },
    index,
    conversation: [],
    userText: 'Quote a mixed observability stack with Monitoring Ingestion 2500000 datapoints, Monitoring Retrieval 4000000 datapoints, Notifications HTTPS Delivery 3000000 delivery operations, and Log Analytics archival storage 600 GB per month. Explain how OCI measures the main billing dimensions.',
    imageDataUrl: '',
  });
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B90925/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B90940/);
  assert.match(reply.message, /B92809/);
  assert.doesNotMatch(reply.message, /Full Stack Disaster Recovery/i);
  assert.match(reply.message, /OCI observability architect/);
  assertWithin(reply.quote.totals.monthly, 47.885, 0.05);
});

test('assistant strips fabric-style narrative prefixes before quoting observability and operations bundles', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    normalizedRequest: text,
    assumptions: [],
    confidence: 0.9,
  }));
  const reply = await respondToAssistant({
    cfg: { ok: true },
    index,
    conversation: [],
    userText: 'Quote an enterprise operations and security fabric with Monitoring Ingestion 12000000 datapoints, Monitoring Retrieval 20000000 datapoints, Log Analytics active storage 2000 GB per month, Log Analytics archival storage 7000 GB per month, Notifications HTTPS Delivery 8000000 delivery operations, Notifications Email Delivery 1000000 emails per month, IAM SMS 5000 messages, Fleet Application Management 80 managed resources, OCI Batch 200 jobs, Oracle Threat Intelligence Service 2000 API calls, DNS 10000000 queries per month, Health Checks 25 endpoints, and Network Firewall 1 firewall with 2000 GB data processed per month. Explain how OCI measures the main billing dimensions.',
    imageDataUrl: '',
  });
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B90925/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B95634/);
  assert.match(reply.message, /B92809/);
  assert.match(reply.message, /B95403/);
  assert.match(reply.message, /B95404/);
  assert.doesNotMatch(reply.message, /B110662/);
});

test('assistant composes vision speech and media flow bundles instead of collapsing to media flow only', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    normalizedRequest: text,
    assumptions: [],
    confidence: 0.9,
  }));
  const reply = await respondToAssistant({
    cfg: { ok: true },
    index,
    conversation: [],
    userText: 'Quote Vision Custom Training 12 training hours plus Speech 40 transcription hours plus Media Flow HD below 30fps 5000 processed video minutes. Explain how OCI measures the main billing dimensions.',
    imageDataUrl: '',
  });
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Composite OCI workload/);
  assert.match(reply.message, /B94977/);
  assert.match(reply.message, /B94896/);
  assert.match(reply.message, /B95282/);
  assert.match(reply.message, /OCI AI and media services architect/);
});
