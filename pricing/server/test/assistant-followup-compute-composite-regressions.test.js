'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadAssistantWithStubs, buildIndex, assertWithin } = require('./assistant-test-helpers');

test('session follow-up ignores unsupported BYOL license flips for Block Volume quotes', async () => {
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
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'BYOL',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Block Volume with 400 GB and 30 VPUs',
        label: 'OCI Block Volume',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  assert.equal(reply.sessionContext.lastQuote.source, 'Quote OCI Block Volume with 400 GB and 30 VPUs');
});

test('session follow-up can change VPU count in the active Block Volume quote', async () => {
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
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '20 VPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Block Volume with 400 GB and 30 VPUs',
        label: 'OCI Block Volume',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b20 VPUs\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b30 VPUs\b/i);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
});

test('session follow-up reuses the active quote source for short instance overrides', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_waf',
    serviceName: 'Web Application Firewall',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'y con 2 instancias?',
    sessionContext: {
      lastQuote: {
        source: 'Quote Web Application Firewall with 1 instance and 25000000 requests per month',
        label: 'Web Application Firewall',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94579/);
  assert.match(reply.sessionContext.lastQuote.source, /2 instancias|2 instances/i);
});

test('route-driven quote follow-up reuses the active quote source for longer workbook-style VPU changes', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    route: 'quote_followup',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'SI cambiamos el block storage a 20VPU\'s como se veria este quote?',
    assumptions: [],
    serviceFamily: 'block_volume',
    serviceName: 'Block Volume',
    extractedInputs: { storageGb: 340, vpuPerGb: 20 },
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: 'SI cambiamos el block storage a 20VPU\'s como se veria este quote?',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'SI cambiamos el block storage a 20VPU\'s como se veria este quote?',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM with 340 GB Block Storage and 30 VPUs',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91962/);
  assert.match(reply.sessionContext.lastQuote.source, /20\s*VPU/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /30\s*VPU/i);
});

test('session follow-up can switch the active workbook-origin quote shape while keeping sizing and block storage', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'VM.Standard.E4.Flex',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B93113/);
  assert.match(reply.message, /B93114/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E4\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
});

test('session follow-up can switch workbook-origin shape and VPU in one step while keeping sizing and block storage', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'VM.Standard.E5.Flex with 30 VPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 30 VPUs/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /20\s*VPU/i);
});

test('session follow-up keeps shared fastconnect and monitoring services when workbook-origin shape and VPU change', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'VM.Standard.E5.Flex with 30 VPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 30 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /20\s*VPU/i);
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90926/);
});

test('session follow-up keeps shared load balancer and dns services when workbook-origin shape and VPU change', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'VM.Standard.E5.Flex with 30 VPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 30 VPUs plus Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /20\s*VPU/i);
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B88525/);
});

test('session follow-up keeps shared load balancer and monitoring services when workbook-origin shape and VPU change', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'VM.Standard.E5.Flex with 30 VPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 30 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /20\s*VPU/i);
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90926/);
});

test('session follow-up can apply preemptible to an active workbook-origin compute quote while keeping block storage', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm',
    serviceName: 'Virtual Machine',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const baseline = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM with 340 GB Block Storage and 20 VPUs',
    sessionContext: {},
  });

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'preemptible',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM with 340 GB Block Storage and 20 VPUs',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bpreemptible\b/i);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.ok(Number(reply.quote.totals.monthly) < Number(baseline.quote.totals.monthly));
});

test('session follow-up can switch workbook-origin shape and apply preemptible in one step while keeping block storage', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm',
    serviceName: 'Virtual Machine',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const baseline = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote VM.Standard.E4.Flex 2 OCPUs 8 GB RAM with 340 GB Block Storage and 20 VPUs',
    sessionContext: {},
  });

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'VM.Standard.E4.Flex preemptible',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM with 340 GB Block Storage and 20 VPUs',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E4\.Flex 2 OCPUs 8 GB RAM with 340 GB Block Storage and 20 VPUs preemptible/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.match(reply.message, /B93113/);
  assert.match(reply.message, /B93114/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.ok(Number(reply.quote.totals.monthly) < Number(baseline.quote.totals.monthly));
});

test('session follow-up can switch RVTools-origin shape and VPU in one step while keeping vmware sizing', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Use VM.Standard.E5.Flex with 30 VPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 30 VPUs/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /20\s*VPU/i);
});

test('session follow-up can switch RVTools-origin shape and apply preemptible in one step while keeping vmware sizing', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const baseline = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote VM.Standard.E4.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs',
    sessionContext: {},
  });

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Use VM.Standard.E4.Flex preemptible',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E4\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs preemptible/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.match(reply.message, /B93113/);
  assert.match(reply.message, /B93114/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.ok(Number(reply.quote.totals.monthly) < Number(baseline.quote.totals.monthly));
});

test('session follow-up can switch the active quote currency with a minimal currency-only answer', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm',
    serviceName: 'Virtual Machine',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'MXN',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM',
        label: 'Virtual Machine',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote.totals.currencyCode, 'MXN');
  assert.equal(reply.sessionContext.lastQuote.currencyCode, 'MXN');
  assert.match(reply.sessionContext.lastQuote.source, /\bMXN\b/i);
  assert.match(reply.message, /MX\$/);
});

test('session follow-up can apply preemptible to the active compute quote with a minimal answer', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm',
    serviceName: 'Virtual Machine',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const baseline = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM',
    sessionContext: {},
  });
  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'preemptible',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM',
        label: 'Virtual Machine',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bpreemptible\b/i);
  assert.ok(Number(reply.quote.totals.monthly) < Number(baseline.quote.totals.monthly));
});

test('session follow-up can append instance count to the active compute quote when it was previously omitted', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm',
    serviceName: 'Virtual Machine',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '3 instances',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM',
        label: 'Virtual Machine',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b3 instances\b/i);
  const line = reply.quote.lineItems.find((item) => Number(item.instances) === 3);
  assert.ok(line);
});

test('session follow-up can apply a burstable baseline to the active compute quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm',
    serviceName: 'Virtual Machine',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const baseline = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM',
    sessionContext: {},
  });
  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'burstable baseline 0.5',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM',
        label: 'Virtual Machine',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bburstable baseline 0\.5\b/i);
  assert.ok(Number(reply.quote.totals.monthly) < Number(baseline.quote.totals.monthly));
});

test('session follow-up can apply capacity reservation utilization to the active compute quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm',
    serviceName: 'Virtual Machine',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const baseline = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM',
    sessionContext: {},
  });
  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'capacity reservation 0.7',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM',
        label: 'Virtual Machine',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bcapacity reservation 0\.7\b/i);
  assert.ok(Number(reply.quote.totals.monthly) < Number(baseline.quote.totals.monthly));
});

test('session follow-up can apply capacity reservation utilization to an active workbook-origin compute quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm',
    serviceName: 'Virtual Machine',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const baseline = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM with 340 GB Block Storage and 20 VPUs',
    sessionContext: {},
  });

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'capacity reservation 0.7',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM with 340 GB Block Storage and 20 VPUs',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bcapacity reservation 0\.7\b/i);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.ok(Number(reply.quote.totals.monthly) < Number(baseline.quote.totals.monthly));
});

test('session follow-up can switch workbook-origin shape and apply capacity reservation in one step while keeping block storage', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm',
    serviceName: 'Virtual Machine',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const baseline = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote VM.Standard.E5.Flex 2 OCPUs 8 GB RAM with 340 GB Block Storage and 20 VPUs',
    sessionContext: {},
  });

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'VM.Standard.E5.Flex capacity reservation 0.7',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM with 340 GB Block Storage and 20 VPUs',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 2 OCPUs 8 GB RAM with 340 GB Block Storage and 20 VPUs capacity reservation 0\.7/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.ok(Number(reply.quote.totals.monthly) < Number(baseline.quote.totals.monthly));
});

test('session follow-up keeps shared load balancer and health checks when workbook-origin shape and capacity reservation change', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'VM.Standard.E5.Flex capacity reservation 0.7',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Health Checks 5 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus (?:OCI )?Health Checks 5 endpoints capacity reservation 0\.7/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90325/);
});

test('session follow-up replaces an existing capacity reservation utilization instead of duplicating it', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm',
    serviceName: 'Virtual Machine',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'capacity reservation 0.7',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 2 OCPUs 8 GB RAM capacity reservation 1.0',
        label: 'Virtual Machine',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bcapacity reservation 0\.7\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bcapacity reservation 1\.0\b/i);
});

test('session follow-up can switch RVTools-origin shape and apply capacity reservation in one step while keeping vmware sizing', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const baseline = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote VM.Standard.E5.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs',
    sessionContext: {},
  });

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Use VM.Standard.E5.Flex capacity reservation 0.7',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs capacity reservation 0\.7/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.ok(Number(reply.quote.totals.monthly) < Number(baseline.quote.totals.monthly));
});

test('session follow-up keeps shared fastconnect and monitoring services when RVTools-origin shape and capacity reservation change', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Use VM.Standard.E5.Flex capacity reservation 0.7',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints capacity reservation 0\.7/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90926/);
});

test('session follow-up keeps shared fastconnect and monitoring services when RVTools-origin shape and preemptible change', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Use VM.Standard.E5.Flex preemptible',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints preemptible/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90926/);
});

test('session follow-up keeps shared load balancer and dns services when RVTools-origin shape and capacity reservation change', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Use VM.Standard.E5.Flex capacity reservation 0.7',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month capacity reservation 0\.7/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B88525/);
});

test('session follow-up keeps shared load balancer and monitoring services when RVTools-origin shape and capacity reservation change', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Use VM.Standard.E5.Flex capacity reservation 0.7',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints capacity reservation 0\.7/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex/i);
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90926/);
});

test('session follow-up can remove fastconnect from an active workbook-origin mixed quote source', async () => {
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
    userText: 'sin FastConnect',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.doesNotMatch(reply.message, /B88326/);
  assert.doesNotMatch(reply.message, /B88525/);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /FastConnect/i);
});

test('session follow-up can remove monitoring retrieval from an active RVTools-origin mixed quote source', async () => {
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
    userText: 'sin Monitoring Retrieval',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval/i);
});

test('session follow-up can remove monitoring retrieval from an active workbook-origin mixed quote source', async () => {
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
    userText: 'sin Monitoring Retrieval',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval/i);
});

test('session follow-up can replace fastconnect with dns in an active workbook-origin mixed quote source', async () => {
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
    userText: 'cambia FastConnect por DNS 5000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.message, /B90926/);
  assert.doesNotMatch(reply.message, /B88326/);
  assert.match(reply.sessionContext.lastQuote.source, /DNS 5000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /FastConnect/i);
});

test('session follow-up can replace fastconnect with dns in an active RVTools-origin mixed quote source', async () => {
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
    userText: 'cambia FastConnect por DNS 5000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.message, /B90926/);
  assert.doesNotMatch(reply.message, /B88326/);
  assert.match(reply.sessionContext.lastQuote.source, /DNS 5000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /FastConnect/i);
});

test('session follow-up can replace monitoring retrieval with health checks in an active RVTools-origin mixed quote source', async () => {
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
    userText: 'cambia Monitoring Retrieval por Health Checks 10 endpoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /Health Checks 10 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval/i);
});

test('session follow-up can replace monitoring retrieval with health checks in an active workbook-origin mixed quote source', async () => {
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
    userText: 'cambia Monitoring Retrieval por Health Checks 10 endpoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /Health Checks 10 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval/i);
});

test('session follow-up can replace monitoring retrieval with monitoring ingestion in an active RVTools-origin mixed quote source', async () => {
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
    userText: 'cambia Monitoring Retrieval por Monitoring Ingestion 2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90925/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /FastConnect 10 Gbps plus Monitoring Ingestion 2500000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can replace monitoring retrieval with monitoring ingestion in an active workbook-origin mixed quote source', async () => {
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
    userText: 'cambia Monitoring Retrieval por Monitoring Ingestion 2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90925/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /FastConnect 10 Gbps plus Monitoring Ingestion 2500000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can replace DNS with health checks in an active RVTools-origin mixed edge quote source', async () => {
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
    userText: 'cambia DNS por Health Checks 10 endpoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus (?:OCI )?Health Checks 10 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /DNS 5000000 queries/i);
});

test('session follow-up can replace DNS with health checks in an active workbook-origin mixed edge quote source', async () => {
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
    userText: 'cambia DNS por Health Checks 10 endpoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus (?:OCI )?Health Checks 10 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /DNS 5000000 queries/i);
});

test('session follow-up can replace health checks with dns in an active workbook-origin mixed observability quote source', async () => {
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
    userText: 'cambia Health Checks por DNS 5000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus Health Checks 10 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B88525/);
  assert.doesNotMatch(reply.message, /B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus (?:OCI )?DNS 5000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Health Checks 10 endpoints/i);
});

test('session follow-up can replace health checks with dns in an active RVTools-origin mixed observability quote source', async () => {
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
    userText: 'cambia Health Checks por DNS 5000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus Health Checks 10 endpoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B88525/);
  assert.doesNotMatch(reply.message, /B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus (?:OCI )?DNS 5000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Health Checks 10 endpoints/i);
});

test('session follow-up can change dns query volume in an active workbook-origin mixed observability quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'OCI DNS',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus (?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /5000000 queries per month/i);
});

test('session follow-up can change dns query volume in an active RVTools-origin mixed observability quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'OCI DNS',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus (?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /5000000 queries per month/i);
});

test('session follow-up can remove DNS from an active workbook-origin mixed observability quote source', async () => {
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
    userText: 'sin DNS',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.doesNotMatch(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /DNS/i);
});

test('session follow-up can remove DNS from an active RVTools-origin mixed observability quote source', async () => {
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
    userText: 'sin DNS',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.doesNotMatch(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /DNS/i);
});

test('session follow-up can change monitoring datapoints in an active workbook-origin mixed observability-dns quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_monitoring',
    serviceName: 'OCI Monitoring',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 2500000 datapoints plus (?:OCI )?DNS 5000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can change monitoring datapoints in an active RVTools-origin mixed observability-dns quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_monitoring',
    serviceName: 'OCI Monitoring',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 2500000 datapoints plus (?:OCI )?DNS 5000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can replace monitoring retrieval with monitoring ingestion in an active workbook-origin mixed observability quote source', async () => {
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
    userText: 'cambia Monitoring Retrieval por Monitoring Ingestion 2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus Health Checks 10 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90925/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Ingestion 2500000 datapoints plus (?:OCI )?Health Checks 10 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can replace monitoring retrieval with monitoring ingestion in an active RVTools-origin mixed observability quote source', async () => {
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
    userText: 'cambia Monitoring Retrieval por Monitoring Ingestion 2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus Health Checks 10 endpoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90925/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Ingestion 2500000 datapoints plus (?:OCI )?Health Checks 10 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can remove monitoring retrieval from an active workbook-origin mixed observability quote source', async () => {
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
    userText: 'sin Monitoring Retrieval',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus Health Checks 10 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus (?:OCI )?Health Checks 10 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval/i);
});

test('session follow-up can remove health checks from an active RVTools-origin mixed observability quote source', async () => {
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
    userText: 'sin Health Checks',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus Health Checks 10 endpoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.doesNotMatch(reply.message, /B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Health Checks/i);
});

test('session follow-up can change monitoring datapoints in an active workbook-origin mixed observability quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_monitoring',
    serviceName: 'OCI Monitoring',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus Health Checks 10 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 2500000 datapoints plus (?:OCI )?Health Checks 10 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can change monitoring datapoints in an active RVTools-origin mixed observability quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_monitoring',
    serviceName: 'OCI Monitoring',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus Health Checks 10 endpoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 2500000 datapoints plus (?:OCI )?Health Checks 10 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can change fastconnect bandwidth in an active workbook-origin mixed quote source', async () => {
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
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '1 Gbps',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88325/);
  assert.match(reply.message, /B90926/);
  assert.doesNotMatch(reply.message, /B88326/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 1 Gbps plus Monitoring Retrieval 4000000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b10 Gbps\b/i);
});

test('session follow-up can change monitoring datapoints in an active workbook-origin mixed fastconnect quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_monitoring',
    serviceName: 'OCI Monitoring',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 2500000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can change monitoring datapoints in an active RVTools-origin mixed fastconnect quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_monitoring',
    serviceName: 'OCI Monitoring',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 2500000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can change fastconnect bandwidth in an active RVTools-origin mixed monitoring quote source', async () => {
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
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '1 Gbps',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88325/);
  assert.match(reply.message, /B90926/);
  assert.doesNotMatch(reply.message, /B88326/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 1 Gbps plus Monitoring Retrieval 4000000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b10 Gbps\b/i);
});

test('session follow-up can change dns query volume in an active workbook-origin mixed fastconnect observability quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'OCI DNS',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints plus (?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /5000000 queries per month/i);
});

test('session follow-up can change dns query volume in an active RVTools-origin mixed fastconnect observability quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'OCI DNS',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Monitoring Retrieval 4000000 datapoints plus (?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /5000000 queries per month/i);
});

test('session follow-up can change dns query volume in an active workbook-origin mixed fastconnect health-checks quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'OCI DNS',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Health Checks 5 endpoints plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90325/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps/i);
  assert.match(reply.sessionContext.lastQuote.source, /(?:OCI )?Health Checks 5 endpoints/i);
  assert.match(reply.sessionContext.lastQuote.source, /(?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /5000000 queries per month/i);
});

test('session follow-up can change dns query volume in an active RVTools-origin mixed fastconnect health-checks quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'OCI DNS',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Health Checks 5 endpoints plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90325/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps/i);
  assert.match(reply.sessionContext.lastQuote.source, /(?:OCI )?Health Checks 5 endpoints/i);
  assert.match(reply.sessionContext.lastQuote.source, /(?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /5000000 queries per month/i);
});

test('session follow-up can remove DNS from an active workbook-origin mixed fastconnect health-checks quote source', async () => {
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
    userText: 'sin DNS',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Health Checks 5 endpoints plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps/i);
  assert.match(reply.sessionContext.lastQuote.source, /(?:OCI )?Health Checks 5 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /DNS/i);
});

test('session follow-up can remove DNS from an active RVTools-origin mixed fastconnect health-checks quote source', async () => {
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
    userText: 'sin DNS',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Health Checks 5 endpoints plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps/i);
  assert.match(reply.sessionContext.lastQuote.source, /(?:OCI )?Health Checks 5 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /DNS/i);
});

test('session follow-up can change health checks endpoint count in an active RVTools-origin mixed fastconnect quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'health_checks',
    serviceName: 'Health Checks',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '8 endpoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Health Checks 5 endpoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus (?:OCI )?Health Checks 8 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b5 endpoints\b/i);
});

test('session follow-up can change health checks endpoint count in an active workbook-origin mixed fastconnect quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'health_checks',
    serviceName: 'Health Checks',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '8 endpoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Health Checks 5 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus (?:OCI )?Health Checks 8 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b5 endpoints\b/i);
});

test('session follow-up can remove health checks from an active workbook-origin mixed fastconnect quote source', async () => {
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
    userText: 'sin Health Checks',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Health Checks 5 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.doesNotMatch(reply.message, /B90323|B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Health Checks/i);
});

test('session follow-up can remove health checks from an active RVTools-origin mixed fastconnect quote source', async () => {
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
    userText: 'sin Health Checks',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Health Checks 5 endpoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.doesNotMatch(reply.message, /B90323|B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Health Checks/i);
});

test('session follow-up can replace health checks with DNS in an active RVTools-origin mixed fastconnect quote source', async () => {
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
    userText: 'cambia Health Checks por DNS 7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Health Checks 5 endpoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B88525/);
  assert.doesNotMatch(reply.message, /B90323|B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus (?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Health Checks 5 endpoints/i);
});

test('session follow-up can replace health checks with DNS in an active workbook-origin mixed fastconnect quote source', async () => {
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
    userText: 'cambia Health Checks por DNS 7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus Health Checks 5 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B88525/);
  assert.doesNotMatch(reply.message, /B90323|B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus (?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Health Checks 5 endpoints/i);
});

test('session follow-up can remove DNS from an active workbook-origin mixed fastconnect quote source', async () => {
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
    userText: 'sin DNS',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.doesNotMatch(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /DNS/i);
});

test('session follow-up can remove fastconnect from an active RVTools-origin mixed dns quote source', async () => {
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
    userText: 'sin FastConnect',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88525/);
  assert.doesNotMatch(reply.message, /B88325|B88326/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus (?:OCI )?DNS 5000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /FastConnect/i);
});

test('session follow-up can replace DNS with health checks in an active workbook-origin mixed fastconnect quote source', async () => {
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
    userText: 'cambia DNS por Health Checks 8 endpoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus (?:OCI )?Health Checks 8 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /DNS 5000000 queries/i);
});

test('session follow-up can change dns query volume in an active workbook-origin mixed fastconnect quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'OCI DNS',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus (?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /5000000 queries per month/i);
});

test('session follow-up can change dns query volume in an active RVTools-origin mixed fastconnect quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'OCI DNS',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus FastConnect 10 Gbps plus (?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /5000000 queries per month/i);
});

test('session follow-up can change dns query volume in an active workbook-origin mixed edge quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'OCI DNS',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus (?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /5000000 queries per month/i);
});

test('session follow-up can change dns query volume in an active RVTools-origin mixed edge quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'OCI DNS',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus (?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /5000000 queries per month/i);
});

test('session follow-up can change health checks endpoint count in an active workbook-origin mixed observability quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'health_checks',
    serviceName: 'Health Checks',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '12 endpoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus Health Checks 10 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.message, /B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints plus (?:OCI )?Health Checks 12 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b10 endpoints\b/i);
});

test('session follow-up can change load balancer bandwidth in an active workbook-origin mixed health-checks quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_load_balancer',
    serviceName: 'OCI Load Balancer',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '150 Mbps',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Health Checks 5 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 150 Mbps plus (?:OCI )?Health Checks 5 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b100 Mbps\b/i);
});

test('session follow-up can change load balancer bandwidth in an active workbook-origin mixed monitoring quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_load_balancer',
    serviceName: 'OCI Load Balancer',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '150 Mbps',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 150 Mbps plus Monitoring Retrieval 4000000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b100 Mbps\b/i);
});

test('session follow-up can change load balancer bandwidth in an active RVTools-origin mixed monitoring quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_load_balancer',
    serviceName: 'OCI Load Balancer',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '150 Mbps',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 150 Mbps plus Monitoring Retrieval 4000000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b100 Mbps\b/i);
});

test('session follow-up can change monitoring datapoints in an active workbook-origin mixed load-balancer quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_monitoring',
    serviceName: 'OCI Monitoring',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 2500000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can change monitoring datapoints in an active RVTools-origin mixed load-balancer quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_monitoring',
    serviceName: 'OCI Monitoring',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 2500000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can remove monitoring retrieval from an active workbook-origin mixed load-balancer quote source', async () => {
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
    userText: 'sin Monitoring Retrieval',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval/i);
});

test('session follow-up can remove load balancer from an active RVTools-origin mixed monitoring quote source', async () => {
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
    userText: 'sin Load Balancer',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90926/);
  assert.doesNotMatch(reply.message, /B93030/);
  assert.doesNotMatch(reply.message, /B93031/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Monitoring Retrieval 4000000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Load Balancer/i);
});

test('session follow-up can replace monitoring retrieval with health checks in an active workbook-origin mixed load-balancer quote source', async () => {
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
    userText: 'cambia Monitoring Retrieval por Health Checks 10 endpoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90323|B90325/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus (?:OCI )?Health Checks 10 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can replace monitoring retrieval with monitoring ingestion in an active workbook-origin mixed load-balancer quote source', async () => {
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
    userText: 'cambia Monitoring Retrieval por Monitoring Ingestion 2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90925/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Ingestion 2500000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can replace monitoring retrieval with monitoring ingestion in an active RVTools-origin mixed load-balancer quote source', async () => {
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
    userText: 'cambia Monitoring Retrieval por Monitoring Ingestion 2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Retrieval 4000000 datapoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B90925/);
  assert.doesNotMatch(reply.message, /B90926/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Monitoring Ingestion 2500000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
});

test('session follow-up can remove load balancer from an active workbook-origin mixed health-checks quote source', async () => {
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
    userText: 'sin Load Balancer',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Health Checks 5 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B93030/);
  assert.doesNotMatch(reply.message, /B93031/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus (?:OCI )?Health Checks 5 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Load Balancer/i);
});

test('session follow-up can remove load balancer from an active RVTools-origin mixed health-checks quote source', async () => {
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
    userText: 'sin Load Balancer',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Health Checks 5 endpoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B93030/);
  assert.doesNotMatch(reply.message, /B93031/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus (?:OCI )?Health Checks 5 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Load Balancer/i);
});

test('session follow-up can remove health checks from an active RVTools-origin mixed load-balancer quote source', async () => {
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
    userText: 'sin Health Checks',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Health Checks 5 endpoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.doesNotMatch(reply.message, /B90323|B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Health Checks/i);
});

test('session follow-up can remove health checks from an active workbook-origin mixed load-balancer quote source', async () => {
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
    userText: 'sin Health Checks',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Health Checks 5 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.doesNotMatch(reply.message, /B90323|B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Health Checks/i);
});

test('session follow-up can replace health checks with DNS in an active workbook-origin mixed load-balancer quote source', async () => {
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
    userText: 'cambia Health Checks por DNS 7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Health Checks 5 endpoints',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B88525/);
  assert.doesNotMatch(reply.message, /B90323|B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus (?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Health Checks 5 endpoints/i);
});

test('session follow-up can replace health checks with DNS in an active RVTools-origin mixed load-balancer quote source', async () => {
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
    userText: 'cambia Health Checks por DNS 7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus Health Checks 5 endpoints',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.match(reply.message, /B88525/);
  assert.doesNotMatch(reply.message, /B90323|B90325/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus (?:OCI )?DNS 7000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Health Checks 5 endpoints/i);
});

test('session follow-up can remove DNS from an active workbook-origin mixed load-balancer quote source', async () => {
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
    userText: 'sin DNS',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard.E5.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month',
        label: 'Excel quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B97384/);
  assert.match(reply.message, /B97385/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.doesNotMatch(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard\.E5\.Flex 8 OCPUs 64 GB RAM with 300 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /DNS/i);
});

test('session follow-up can remove DNS from an active RVTools-origin mixed load-balancer quote source', async () => {
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
    userText: 'sin DNS',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.doesNotMatch(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /DNS/i);
});

test('session follow-up can remove load balancer from an active RVTools-origin mixed dns quote source', async () => {
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
    userText: 'sin Load Balancer',
    sessionContext: {
      lastQuote: {
        source: 'Quote VM.Standard3.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month',
        label: 'RVTools quotation',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94176/);
  assert.match(reply.message, /B94177/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
  assert.match(reply.message, /B88525/);
  assert.doesNotMatch(reply.message, /B93030/);
  assert.doesNotMatch(reply.message, /B93031/);
  assert.match(reply.sessionContext.lastQuote.source, /VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs plus (?:OCI )?DNS 5000000 queries per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Load Balancer/i);
});

test('session follow-up can remove WAF from the active composite quote source', async () => {
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
    userText: 'sin WAF',
    sessionContext: {
      lastQuote: {
        source: 'Quote Web Application Firewall with 2 instances and 50000000 requests per month plus DNS 5000000 queries per month',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B88525/);
  assert.doesNotMatch(reply.message, /B94579/);
  assert.doesNotMatch(reply.message, /B94277/);
});

test('session follow-up can remove DNS from the active composite quote source', async () => {
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
    userText: 'sin DNS',
    sessionContext: {
      lastQuote: {
        source: 'Quote Web Application Firewall with 2 instances and 50000000 requests per month plus DNS 5000000 queries per month plus Flexible Load Balancer 100 Mbps',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94579/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.doesNotMatch(reply.message, /B88525/);
});

test('session follow-up can remove load balancer from the active composite quote source', async () => {
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
    userText: 'sin Load Balancer',
    sessionContext: {
      lastQuote: {
        source: 'Quote Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month plus Web Application Firewall with 2 instances and 50000000 requests per month',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B88525/);
  assert.match(reply.message, /B94579/);
  assert.doesNotMatch(reply.message, /B93030/);
  assert.doesNotMatch(reply.message, /B93031/);
});

test('session follow-up can remove load balancer from the active composite quote source with LB shorthand', async () => {
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
    userText: 'sin LB',
    sessionContext: {
      lastQuote: {
        source: 'Quote Flexible Load Balancer 100 Mbps plus DNS 5000000 queries per month plus Web Application Firewall with 2 instances and 50000000 requests per month',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B88525/);
  assert.match(reply.message, /B94579/);
  assert.doesNotMatch(reply.message, /B93030/);
  assert.doesNotMatch(reply.message, /B93031/);
});

test('session follow-up can remove health checks from the active composite quote source', async () => {
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
    userText: 'sin Health Checks',
    sessionContext: {
      lastQuote: {
        source: 'Quote Health Checks 5 endpoints plus DNS 5000000 queries per month plus Web Application Firewall with 2 instances and 50000000 requests per month',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B88525/);
  assert.match(reply.message, /B94579/);
  assert.match(reply.message, /B94277/);
  assert.doesNotMatch(reply.message, /B90323|B90325/);
});

test('session follow-up can remove API Gateway from the active composite quote source', async () => {
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
    userText: 'sin API Gateway',
    sessionContext: {
      lastQuote: {
        source: 'Quote API Gateway 5000000 API calls per month plus DNS 5000000 queries per month plus Flexible Load Balancer 100 Mbps',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B88525/);
  assert.match(reply.message, /B93030/);
  assert.match(reply.message, /B93031/);
  assert.doesNotMatch(reply.message, /B92072/);
});

test('session follow-up can remove Data Safe from an active mixed database quote source', async () => {
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
    userText: 'sin Data Safe',
    sessionContext: {
      lastQuote: {
        source: 'Quote Exadata Cloud@Customer License Included 8 OCPUs on base system X10M plus Data Safe for Database Cloud Service 8 databases plus Log Analytics active storage 1000 GB per month',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91363|B110663|B110627|B96610|B96611|B96615/);
  assert.match(reply.message, /B95634/);
  assert.doesNotMatch(reply.message, /B91632|B92733/);
  assert.match(reply.sessionContext.lastQuote.source, /Exadata Cloud@Customer/i);
  assert.match(reply.sessionContext.lastQuote.source, /Log Analytics active storage 1000 GB per month/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Data Safe/i);
});

test('session follow-up can remove Log Analytics from an active mixed database quote source', async () => {
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
    userText: 'sin Log Analytics',
    sessionContext: {
      lastQuote: {
        source: 'Quote Exadata Cloud@Customer License Included 8 OCPUs on base system X10M plus Data Safe for Database Cloud Service 8 databases plus Log Analytics active storage 1000 GB per month',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91363|B110663|B110627|B96610|B96611|B96615/);
  assert.match(reply.message, /B91632/);
  assert.doesNotMatch(reply.message, /B95634|B92809/);
  assert.match(reply.sessionContext.lastQuote.source, /Exadata Cloud@Customer/i);
  assert.match(reply.sessionContext.lastQuote.source, /Data Safe for Database Cloud Service 8 databases/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Log Analytics/i);
});

test('session follow-up can remove OIC Standard from an active mixed platform quote source', async () => {
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
    userText: 'sin OIC Standard',
    sessionContext: {
      lastQuote: {
        source: 'Quote Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage plus Oracle Integration Cloud Standard BYOL 2 instances for 744h/month plus Oracle Analytics Cloud Professional 100 users',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90573/);
  assert.match(reply.message, /B111584/);
  assert.match(reply.message, /B92682/);
  assert.doesNotMatch(reply.message, /B89639|B89643/);
  assert.match(reply.sessionContext.lastQuote.source, /Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage/i);
  assert.match(reply.sessionContext.lastQuote.source, /Oracle Analytics Cloud Professional 100 users/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Oracle Integration Cloud Standard|OIC Standard/i);
});

test('session follow-up can remove OAC Professional from an active mixed platform quote source', async () => {
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
    userText: 'sin OAC Professional',
    sessionContext: {
      lastQuote: {
        source: 'Quote Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage plus Oracle Integration Cloud Standard BYOL 2 instances for 744h/month plus Oracle Analytics Cloud Professional 100 users',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90573/);
  assert.match(reply.message, /B111584/);
  assert.match(reply.message, /B89643/);
  assert.doesNotMatch(reply.message, /B92681|B92682/);
  assert.match(reply.sessionContext.lastQuote.source, /Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage/i);
  assert.match(reply.sessionContext.lastQuote.source, /Oracle Integration Cloud Standard BYOL 2 instances/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Oracle Analytics Cloud Professional|OAC Professional/i);
});

test('session follow-up can replace OIC Standard with OIC Enterprise in an active mixed platform quote source', async () => {
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
    userText: 'cambia OIC Standard por OIC Enterprise BYOL 2 instances',
    sessionContext: {
      lastQuote: {
        source: 'Quote Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage plus Oracle Integration Cloud Standard BYOL 2 instances for 744h/month plus Oracle Analytics Cloud Professional 100 users',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90573/);
  assert.match(reply.message, /B111584/);
  assert.match(reply.message, /B89644/);
  assert.match(reply.message, /B92682/);
  assert.doesNotMatch(reply.message, /B89639|B89643/);
  assert.match(reply.sessionContext.lastQuote.source, /Oracle Integration Cloud Enterprise,\s*BYOL,\s*2 instances/i);
  assert.match(reply.sessionContext.lastQuote.source, /Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage/i);
  assert.match(reply.sessionContext.lastQuote.source, /Oracle Analytics Cloud Professional 100 users/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Oracle Integration Cloud Standard|OIC Standard/i);
});

test('session follow-up can replace OAC Professional with OAC Enterprise in an active mixed platform quote source', async () => {
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
    userText: 'cambia OAC Professional por OAC Enterprise 100 users',
    sessionContext: {
      lastQuote: {
        source: 'Quote Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage plus Oracle Integration Cloud Standard BYOL 2 instances for 744h/month plus Oracle Analytics Cloud Professional 100 users',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90573/);
  assert.match(reply.message, /B111584/);
  assert.match(reply.message, /B89643/);
  assert.match(reply.message, /B92683/);
  assert.doesNotMatch(reply.message, /B92681|B92682/);
  assert.match(reply.sessionContext.lastQuote.source, /Oracle Analytics Cloud Enterprise,\s*100 users/i);
  assert.match(reply.sessionContext.lastQuote.source, /Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage/i);
  assert.match(reply.sessionContext.lastQuote.source, /Oracle Integration Cloud Standard BYOL 2 instances/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Oracle Analytics Cloud Professional|OAC Professional/i);
});

test('session follow-up can replace OIC Enterprise with OIC Standard in an active mixed platform quote source', async () => {
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
    userText: 'cambia OIC Enterprise por OIC Standard BYOL 2 instances',
    sessionContext: {
      lastQuote: {
        source: 'Quote Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage plus Oracle Integration Cloud Enterprise BYOL 2 instances plus Oracle Analytics Cloud Enterprise 100 users',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90573/);
  assert.match(reply.message, /B111584/);
  assert.match(reply.message, /B89643/);
  assert.match(reply.message, /B92683/);
  assert.doesNotMatch(reply.message, /B89640|B89644/);
  assert.match(reply.sessionContext.lastQuote.source, /Oracle Integration Cloud Standard,\s*BYOL,\s*2 instances/i);
  assert.match(reply.sessionContext.lastQuote.source, /Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage/i);
  assert.match(reply.sessionContext.lastQuote.source, /Oracle Analytics Cloud Enterprise 100 users/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Oracle Integration Cloud Enterprise|OIC Enterprise/i);
});

test('session follow-up can replace OAC Enterprise with OAC Professional in an active mixed platform quote source', async () => {
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
    userText: 'cambia OAC Enterprise por OAC Professional 100 users',
    sessionContext: {
      lastQuote: {
        source: 'Quote Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage plus Oracle Integration Cloud Enterprise BYOL 2 instances plus Oracle Analytics Cloud Enterprise 100 users',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90573/);
  assert.match(reply.message, /B111584/);
  assert.match(reply.message, /B89644/);
  assert.match(reply.message, /B92682/);
  assert.doesNotMatch(reply.message, /B92683/);
  assert.match(reply.sessionContext.lastQuote.source, /Oracle Analytics Cloud Professional,\s*100 users/i);
  assert.match(reply.sessionContext.lastQuote.source, /Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage/i);
  assert.match(reply.sessionContext.lastQuote.source, /Oracle Integration Cloud Enterprise BYOL 2 instances/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Oracle Analytics Cloud Enterprise,\s*100 users|OAC Enterprise/i);
});

test('session follow-up can replace DNS with Health Checks in the active composite quote source', async () => {
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
    userText: 'cambia DNS por Health Checks 10 endpoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote Web Application Firewall with 2 instances and 50000000 requests per month plus DNS 5000000 queries per month',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94579/);
  assert.match(reply.message, /B90325/);
  assert.doesNotMatch(reply.message, /B88525/);
  assert.match(reply.sessionContext.lastQuote.source, /Health Checks 10 endpoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /DNS 5000000 queries/i);
});

test('session follow-up ignores unsupported composite replacements outside the declared family capability matrix', async () => {
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
    userText: 'cambia DNS por Block Volume 400 GB with 20 VPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote Web Application Firewall with 2 instances and 50000000 requests per month plus DNS 5000000 queries per month',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94579/);
  assert.match(reply.message, /B88525/);
  assert.doesNotMatch(reply.message, /B91961|B91962/);
  assert.match(reply.sessionContext.lastQuote.source, /DNS 5000000 queries/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Block Volume 400 GB/i);
});

test('session follow-up can change firewall count in the active network firewall quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_network_firewall',
    serviceName: 'Network Firewall',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '3 firewalls',
    sessionContext: {
      lastQuote: {
        source: 'Quote Network Firewall 2 firewalls and 20000 GB data processed per month',
        label: 'Network Firewall',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b3 firewalls\b/i);
  const instanceLine = reply.quote.lineItems.find((item) => item.partNumber === 'B95403');
  assert.ok(instanceLine);
  assert.equal(Number(instanceLine.quantity), 3);
});

test('session follow-up can change endpoint count in the active health checks quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'health_checks',
    serviceName: 'Health Checks',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '10 endpoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote Health Checks 5 endpoints',
        label: 'Health Checks',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b10 endpoints\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B90325');
  assert.ok(line);
  assert.equal(Number(line.quantity), 10);
});

test('session follow-up can change bandwidth in the active FastConnect quote', async () => {
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
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '1 Gbps',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI FastConnect 10 Gbps',
        label: 'OCI FastConnect',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b1 Gbps\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b10 Gbps\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B88325');
  assert.ok(line);
});

test('session follow-up can change bandwidth in the active load balancer quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_load_balancer',
    serviceName: 'OCI Load Balancer',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '250 Mbps',
    sessionContext: {
      lastQuote: {
        source: 'Quote Flexible Load Balancer 100 Mbps',
        label: 'Flexible Load Balancer',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b250 Mbps\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b100 Mbps\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B93031');
  assert.ok(line);
});

test('session follow-up can change database count in the active data safe quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_data_safe',
    serviceName: 'Data Safe',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '5 databases',
    sessionContext: {
      lastQuote: {
        source: 'Quote Data Safe for On-Premises Databases 2 target databases',
        label: 'Data Safe',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b5 (?:target )?databases\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B92733');
  assert.ok(line);
  assert.equal(Number(line.quantity), 5);
});

test('session follow-up can switch the active data safe quote from Database Cloud Service to On-Premises while keeping database count', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_data_safe',
    serviceName: 'Data Safe',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'On-Premises Databases 3 target databases',
    sessionContext: {
      lastQuote: {
        source: 'Quote Data Safe for Database Cloud Service 3 databases',
        label: 'Data Safe',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /On-Premises Databases 3 target databases/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Database Cloud Service 3 databases/i);
  assert.match(reply.message, /B92733/);
  assert.doesNotMatch(reply.message, /B91632/);
});

test('session follow-up can switch the active data safe quote from On-Premises to Database Cloud Service while keeping database count', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_data_safe',
    serviceName: 'Data Safe',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Database Cloud Service 3 databases',
    sessionContext: {
      lastQuote: {
        source: 'Quote Data Safe for On-Premises Databases 3 target databases',
        label: 'Data Safe',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /Database Cloud Service 3 databases/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /On-Premises Databases 3 target databases/i);
  assert.match(reply.message, /B91632/);
  assert.doesNotMatch(reply.message, /B92733/);
});

test('session follow-up can switch the active log analytics quote from active to archival storage while keeping capacity', async () => {
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
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'archival storage 600 GB per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Log Analytics Active Storage with 600 GB per month',
        label: 'OCI Log Analytics',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /Archival Storage/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b600 GB per month\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Active Storage/i);
  assert.match(reply.message, /B92809/);
  assert.doesNotMatch(reply.message, /B95634/);
});

test('session follow-up can switch the active log analytics quote from archival to active storage while keeping capacity', async () => {
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
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'active storage 600 GB per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Log Analytics Archival Storage with 600 GB per month',
        label: 'OCI Log Analytics',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /Active Storage/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b600 GB per month\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Archival Storage/i);
  assert.match(reply.message, /B95634/);
  assert.doesNotMatch(reply.message, /B92809/);
});

test('session follow-up can switch the active monitoring quote from ingestion to retrieval while keeping datapoints', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_monitoring',
    serviceName: 'OCI Monitoring',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'retrieval 4000000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Monitoring Ingestion 2500000 datapoints',
        label: 'OCI Monitoring',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Ingestion 2500000 datapoints/i);
  assert.match(reply.message, /B90926/);
  assert.doesNotMatch(reply.message, /B90925/);
});

test('session follow-up can switch the active monitoring quote from retrieval to ingestion while keeping datapoints', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_monitoring',
    serviceName: 'OCI Monitoring',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'ingestion 2500000 datapoints',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Monitoring Retrieval 4000000 datapoints',
        label: 'OCI Monitoring',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /Monitoring Ingestion 2500000 datapoints/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /Monitoring Retrieval 4000000 datapoints/i);
  assert.match(reply.message, /B90925/);
  assert.doesNotMatch(reply.message, /B90926/);
});

test('session follow-up can switch data safe variant inside an active mixed database quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_data_safe',
    serviceName: 'Data Safe',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'On-Premises Databases 8 target databases',
    sessionContext: {
      lastQuote: {
        source: 'Quote Exadata Cloud@Customer License Included 8 OCPUs on base system X10M plus Data Safe for Database Cloud Service 8 databases plus Log Analytics active storage 1000 GB per month',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91363|B110663|B110627|B96610|B96611|B96615/);
  assert.match(reply.message, /B92733/);
  assert.match(reply.message, /B95634/);
  assert.doesNotMatch(reply.message, /B91632/);
  assert.match(reply.sessionContext.lastQuote.source, /On-Premises Databases 8 target databases/i);
  assert.match(reply.sessionContext.lastQuote.source, /Log Analytics active storage 1000 GB per month/i);
  assert.match(reply.sessionContext.lastQuote.source, /Exadata Cloud@Customer/i);
});

test('session follow-up can switch data safe variant back inside an active mixed database quote source', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_data_safe',
    serviceName: 'Data Safe',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Database Cloud Service 8 databases',
    sessionContext: {
      lastQuote: {
        source: 'Quote Exadata Cloud@Customer License Included 8 OCPUs on base system X10M plus Data Safe for On-Premises Databases 8 target databases plus Log Analytics active storage 1000 GB per month',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91363|B110663|B110627|B96610|B96611|B96615/);
  assert.match(reply.message, /B91632/);
  assert.match(reply.message, /B95634/);
  assert.doesNotMatch(reply.message, /B92733/);
  assert.match(reply.sessionContext.lastQuote.source, /Database Cloud Service 8 databases/i);
  assert.match(reply.sessionContext.lastQuote.source, /Log Analytics active storage 1000 GB per month/i);
  assert.match(reply.sessionContext.lastQuote.source, /Exadata Cloud@Customer/i);
});

test('session follow-up can switch log analytics variant inside an active mixed database quote source', async () => {
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
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'archival storage 1000 GB per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote Exadata Cloud@Customer License Included 8 OCPUs on base system X10M plus Data Safe for Database Cloud Service 8 databases plus Log Analytics active storage 1000 GB per month',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91363|B110663|B110627|B96610|B96611|B96615/);
  assert.match(reply.message, /B91632/);
  assert.match(reply.message, /B92809/);
  assert.doesNotMatch(reply.message, /B95634/);
  assert.match(reply.sessionContext.lastQuote.source, /Log Analytics Archival Storage/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b1000 GB per month\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /Data Safe for Database Cloud Service 8 databases/i);
  assert.match(reply.sessionContext.lastQuote.source, /Exadata Cloud@Customer/i);
});

test('session follow-up can switch log analytics variant back inside an active mixed database quote source', async () => {
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
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'active storage 1000 GB per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote Exadata Cloud@Customer License Included 8 OCPUs on base system X10M plus Data Safe for Database Cloud Service 8 databases plus Log Analytics Archival Storage with 1000 GB per month',
        label: 'Composite OCI workload',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91363|B110663|B110627|B96610|B96611|B96615/);
  assert.match(reply.message, /B91632/);
  assert.match(reply.message, /B95634/);
  assert.doesNotMatch(reply.message, /B92809/);
  assert.match(reply.sessionContext.lastQuote.source, /Log Analytics Active Storage/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b1000 GB per month\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /Data Safe for Database Cloud Service 8 databases/i);
  assert.match(reply.sessionContext.lastQuote.source, /Exadata Cloud@Customer/i);
});

test('session follow-up can change workspace count in the active data integration quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'data_integration',
    serviceName: 'Data Integration',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '3 workspaces',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Data Integration workspace usage 2 workspaces 744h/month',
        label: 'Data Integration',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b3 workspaces\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B92598');
  assert.ok(line);
  assert.equal(Number(line.quantity), 3);
});

test('session follow-up can change managed resource count in the active fleet quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'operations_platform',
    serviceName: 'Fleet Application Management',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '8 managed resources',
    sessionContext: {
      lastQuote: {
        source: 'Quote Fleet Application Management 5 managed resources per month',
        label: 'Fleet Application Management',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b8 managed resources\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B110475');
  assert.ok(line);
  assert.equal(Number(line.quantity), 8);
});

test('session follow-up can change query volume in the active DNS quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'networking',
    serviceName: 'OCI DNS',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '7000000 queries per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI DNS 5000000 queries per month',
        label: 'OCI DNS',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b7000000 queries per month\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B88525');
  assert.ok(line);
});

test('session follow-up can change API call volume in the active API Gateway quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'networking',
    serviceName: 'API Gateway',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '12000000 API calls per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote API Gateway 5000000 API calls per month',
        label: 'API Gateway',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b12000000 API calls per month\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B92072');
  assert.ok(line);
});

test('session follow-up can change email volume in the active Email Delivery quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'operations_email_delivery',
    serviceName: 'Email Delivery',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '250000 emails per month',
    sessionContext: {
      lastQuote: {
        source: 'Quote Email Delivery 100000 emails per month',
        label: 'Email Delivery',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b250000 emails per month\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B90941');
  assert.ok(line);
});

test('session follow-up can change delivery operations in the active HTTPS Delivery quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_notifications_https',
    serviceName: 'Notifications HTTPS Delivery',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '8000000 delivery operations',
    sessionContext: {
      lastQuote: {
        source: 'Quote Notifications HTTPS Delivery 3000000 delivery operations',
        label: 'Notifications HTTPS Delivery',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b8000000 delivery operations\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B90940');
  assert.ok(line);
});

test('session follow-up can change SMS volume in the active IAM SMS quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'operations_iam_sms',
    serviceName: 'IAM SMS',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '50 SMS messages',
    sessionContext: {
      lastQuote: {
        source: 'Quote IAM SMS 12 SMS messages',
        label: 'IAM SMS',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b50 SMS messages\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B93496');
  assert.ok(line);
});

test('session follow-up can change generic message volume in the active IAM SMS quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'operations_iam_sms',
    serviceName: 'IAM SMS',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '65 messages',
    sessionContext: {
      lastQuote: {
        source: 'Quote IAM SMS 12 SMS messages',
        label: 'IAM SMS',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b65 SMS messages\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B93496');
  assert.ok(line);
});

test('session follow-up can change job count in the active OCI Batch quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'devops_batch',
    serviceName: 'OCI Batch',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '12 jobs',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Batch 4 jobs',
        label: 'OCI Batch',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b12 jobs\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B112107');
  assert.ok(line);
});

test('session follow-up can change transaction volume in the active AI Language quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ai_language',
    serviceName: 'OCI AI Language',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '10000 transactions',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI AI Language 2500 transactions',
        label: 'OCI AI Language',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b10000 transactions\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B93423');
  assert.ok(line);
});

[
  {
    name: 'OCI Generative AI Agents Data Ingestion',
    familyId: 'ai_agents_data_ingestion',
    followUpText: '750000 transactions',
    initialSource: 'Quote OCI Generative AI Agents Data Ingestion 250000 transactions',
    expectedSource: /\b750000 transactions\b/i,
    partNumber: 'B110463',
  },
  {
    name: 'OCI Generative AI Large Cohere',
    familyId: 'ai_large_cohere',
    followUpText: '90000 transactions',
    initialSource: 'Quote OCI Generative AI Large Cohere 50000 transactions',
    expectedSource: /\b90000 transactions\b/i,
    partNumber: 'B108077',
  },
  {
    name: 'OCI Generative AI Small Cohere',
    familyId: 'ai_small_cohere',
    followUpText: '120000 transactions',
    initialSource: 'Quote OCI Generative AI Small Cohere 50000 transactions',
    expectedSource: /\b120000 transactions\b/i,
    partNumber: 'B108078',
  },
  {
    name: 'OCI Generative AI Embed Cohere',
    familyId: 'ai_embed_cohere',
    followUpText: '150000 transactions',
    initialSource: 'Quote OCI Generative AI Embed Cohere 50000 transactions',
    expectedSource: /\b150000 transactions\b/i,
    partNumber: 'B108079',
  },
  {
    name: 'OCI Generative AI Large Meta',
    familyId: 'ai_large_meta',
    followUpText: '110000 transactions',
    initialSource: 'Quote OCI Generative AI Large Meta 50000 transactions',
    expectedSource: /\b110000 transactions\b/i,
    partNumber: 'B108080',
  },
  {
    name: 'OCI Vision Image Analysis',
    familyId: 'ai_vision_image_analysis',
    followUpText: '12000 transactions',
    initialSource: 'Quote OCI Vision Image Analysis 6000 transactions',
    expectedSource: /\b12000 transactions\b/i,
    partNumber: 'B94973',
  },
  {
    name: 'OCI Vision OCR',
    familyId: 'ai_vision_ocr',
    followUpText: '14000 transactions',
    initialSource: 'Quote OCI Vision OCR 6000 transactions',
    expectedSource: /\b14000 transactions\b/i,
    partNumber: 'B94974',
  },
].forEach(({ name, familyId, followUpText, initialSource, expectedSource, partNumber }) => {
  test(`session follow-up can change transaction volume in the active ${name} quote`, async () => {
    const index = buildIndex();
    const { respondToAssistant } = loadAssistantWithStubs((text) => ({
      intent: 'quote',
      shouldQuote: true,
      needsClarification: false,
      clarificationQuestion: '',
      reformulatedRequest: text,
      assumptions: [],
      serviceFamily: familyId,
      serviceName: name,
      extractedInputs: {},
      confidence: 0.95,
      annualRequested: false,
      normalizedRequest: text,
    }));

    const reply = await respondToAssistant({
      cfg: {},
      index,
      conversation: [],
      userText: followUpText,
      sessionContext: {
        lastQuote: {
          source: initialSource,
          label: name,
        },
      },
    });

    assert.equal(reply.ok, true);
    assert.equal(reply.mode, 'quote');
    assert.match(reply.sessionContext.lastQuote.source, expectedSource);
    const line = reply.quote.lineItems.find((item) => item.partNumber === partNumber);
    assert.ok(line);
  });
});

test('session follow-up can change request volume in the active Vector Store Retrieval quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ai_vector_store_retrieval',
    serviceName: 'OCI Generative AI Vector Store Retrieval',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '18000 requests',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Generative AI Vector Store Retrieval 5000 requests',
        label: 'OCI Generative AI Vector Store Retrieval',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b18000 requests\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B112416');
  assert.ok(line);
});

test('session follow-up can change request volume in the active Web Search quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ai_web_search',
    serviceName: 'OCI Generative AI Web Search',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '25000 requests',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Generative AI Web Search 12000 requests',
        label: 'OCI Generative AI Web Search',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b25000 requests\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B111973');
  assert.ok(line);
});

test('session follow-up can change API call volume in the active Threat Intelligence quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_threat_intelligence',
    serviceName: 'Oracle Threat Intelligence Service',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '2500 API calls',
    sessionContext: {
      lastQuote: {
        source: 'Quote Oracle Threat Intelligence Service 100 API calls',
        label: 'Oracle Threat Intelligence Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b2500 API calls\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B94173');
  assert.ok(line);
});

test('session follow-up can change message volume in the active Notifications SMS Outbound quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'operations_notifications_sms',
    serviceName: 'OCI Notifications SMS Outbound',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '350 messages',
    sessionContext: {
      lastQuote: {
        source: 'Quote Notifications SMS Outbound to Country Zone 1 100 messages',
        label: 'OCI Notifications SMS Outbound',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b350 messages\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bCountry Zone 1\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B93004');
  assert.ok(line);
});

test('session follow-up can change named user count in the active OAC Enterprise quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'analytics_oac_enterprise',
    serviceName: 'Oracle Analytics Cloud Enterprise',
    extractedInputs: { users: 80 },
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '80 users',
    sessionContext: {
      lastQuote: {
        source: 'Quote Oracle Analytics Cloud Enterprise 50 users',
        label: 'Oracle Analytics Cloud Enterprise',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b80 users\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B92683');
  assert.ok(line);
});

test('session follow-up can change named user count in the active OAC Professional quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'analytics_oac_professional',
    serviceName: 'Oracle Analytics Cloud Professional',
    extractedInputs: { users: 40 },
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '40 users',
    sessionContext: {
      lastQuote: {
        source: 'Quote Oracle Analytics Cloud Professional 25 users',
        label: 'Oracle Analytics Cloud Professional',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b40 users\b/i);
  const line = reply.quote.lineItems.find((item) => item.partNumber === 'B92682');
  assert.ok(line);
});
