'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadAssistantWithStubs, buildIndex, extendIndexWithProducts, product, payg } = require('./assistant-test-helpers');

test('license follow-up keeps Oracle Integration Cloud Enterprise context', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'integration_oic_enterprise',
    serviceName: 'Oracle Integration Cloud Enterprise',
    extractedInputs: { instances: 1 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const conversation = [
    { role: 'user', content: 'Quote Oracle Integration Cloud Enterprise, 1 instance, 744h/month' },
    { role: 'assistant', content: 'Do you want Oracle Integration Cloud Enterprise as BYOL or License Included?' },
    { role: 'user', content: 'BYOL' },
    { role: 'assistant', content: 'I prepared a deterministic OCI quotation for `Oracle Integration Cloud Enterprise`.' },
  ];

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation,
    userText: 'Now do it with license included',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /Oracle Integration Cloud Enterprise/);
  assert.match(reply.message, /B89640/);
  assert.doesNotMatch(reply.message, /B110464/);
});

test('oracle integration cloud standard asks for license choice and quotes the selected variant', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'integration_oic_standard',
    serviceName: 'Oracle Integration Cloud Standard',
    extractedInputs: { instances: 1 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const clarify = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Oracle Integration Cloud Standard, 1 instance, 744h/month',
  });
  assert.equal(clarify.ok, true);
  assert.equal(clarify.mode, 'clarification');
  assert.match(clarify.message, /BYOL or License Included/i);

  const quote = await respondToAssistant({
    cfg: {},
    index,
    conversation: [
      { role: 'user', content: 'Quote Oracle Integration Cloud Standard, 1 instance, 744h/month' },
      { role: 'assistant', content: clarify.message },
    ],
    userText: 'License Included',
  });
  assert.equal(quote.ok, true);
  assert.equal(quote.mode, 'quote');
  assert.match(quote.message, /B89639/);
  assert.doesNotMatch(quote.message, /B89643/);
});

test('oracle analytics cloud professional users quote does not force unnecessary license clarification', async () => {
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
    extractedInputs: { users: 25 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Oracle Analytics Cloud Professional 25 users',
  });
  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B92682/);
  assert.doesNotMatch(reply.message, /BYOL or License Included/i);
});

test('oracle analytics cloud professional ocpu quote still asks for license mode and honors BYOL', async () => {
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
    extractedInputs: { ocpus: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const clarify = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Oracle Analytics Cloud Professional 2 OCPUs',
  });
  assert.equal(clarify.ok, true);
  assert.equal(clarify.mode, 'clarification');
  assert.match(clarify.message, /BYOL or License Included/i);

  const quote = await respondToAssistant({
    cfg: {},
    index,
    conversation: [
      { role: 'user', content: 'Quote Oracle Analytics Cloud Professional 2 OCPUs' },
      { role: 'assistant', content: clarify.message },
    ],
    userText: 'BYOL',
  });
  assert.equal(quote.ok, true);
  assert.equal(quote.mode, 'quote');
  assert.match(quote.message, /B89636/);
  assert.doesNotMatch(quote.message, /B89630/);
});

test('session follow-up can switch the active OIC Standard quote from license included to BYOL', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'integration_oic_standard',
    serviceName: 'Oracle Integration Cloud Standard',
    extractedInputs: { instances: 1 },
    confidence: 0.9,
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
        source: 'Quote Oracle Integration Cloud Standard License Included 1 instance 744h/month',
        label: 'Oracle Integration Cloud Standard',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  assert.match(reply.message, /B89643/);
  assert.doesNotMatch(reply.message, /B89639/);
});

test('session follow-up can switch the active OIC Standard quote from BYOL to license included', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'integration_oic_standard',
    serviceName: 'Oracle Integration Cloud Standard',
    extractedInputs: { instances: 1 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'License Included',
    sessionContext: {
      lastQuote: {
        source: 'Quote Oracle Integration Cloud Standard BYOL 1 instance 744h/month',
        label: 'Oracle Integration Cloud Standard',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  assert.match(reply.message, /B89639/);
  assert.doesNotMatch(reply.message, /B89643/);
});

test('session follow-up can switch the active Base Database quote from license included to BYOL while keeping edition and storage', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
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
        source: 'Quote OCI Base Database Service Enterprise License Included 8 OCPUs, 2000 GB storage',
        label: 'Base Database Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bEnterprise\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b2000 GB storage\b/i);
  assert.match(reply.message, /B90573/);
  assert.match(reply.message, /B111584/);
  assert.doesNotMatch(reply.message, /B90570/);
});

test('session follow-up can change OCPU count in the active Base Database quote while keeping license mode and storage', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '16 OCPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Base Database Service Enterprise BYOL 8 OCPUs, 2000 GB storage',
        label: 'Base Database Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b16 OCPUs\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b8 OCPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b2000 GB storage\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B90573');
  const storage = reply.quote.lineItems.find((item) => item.partNumber === 'B111584');
  assert.ok(compute);
  assert.ok(storage);
  assert.equal(compute.quantity, 16);
  assert.equal(storage.quantity, 2000);
});

test('session follow-up can change storage in the active Base Database quote while keeping edition and sizing', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '3000 GB storage',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Base Database Service Enterprise License Included 8 OCPUs, 2000 GB storage',
        label: 'Base Database Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b3000 GB storage\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b2000 GB storage\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b8 OCPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B90570');
  const storage = reply.quote.lineItems.find((item) => item.partNumber === 'B111584');
  assert.ok(compute);
  assert.ok(storage);
  assert.equal(compute.quantity, 8);
  assert.equal(storage.quantity, 3000);
});

test('session follow-up can change edition in the active Base Database quote while keeping license mode, sizing, and storage', async () => {
  const index = buildIndex();
  extendIndexWithProducts(index, [
    product({
      partNumber: 'B90569',
      displayName: 'Base Database Service Standard - License Included',
      serviceCategoryDisplayName: 'Database - Base Database Service',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.28)],
    }),
  ]);
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Standard',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Base Database Service Enterprise License Included 8 OCPUs, 2000 GB storage',
        label: 'Base Database Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bStandard\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bEnterprise\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b8 OCPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b2000 GB storage\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B90569');
  const storage = reply.quote.lineItems.find((item) => item.partNumber === 'B111584');
  assert.ok(compute);
  assert.ok(storage);
  assert.equal(compute.quantity, 8);
  assert.equal(storage.quantity, 2000);
});

test('session follow-up can change compute mode from OCPUs to ECPUs in the active Base Database quote while keeping edition, license mode, and storage', async () => {
  const index = buildIndex();
  extendIndexWithProducts(index, [
    product({
      partNumber: 'B111586',
      displayName: 'Base Database Service Enterprise - ECPU - License Included',
      serviceCategoryDisplayName: 'Database - Base Database Service',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.19)],
    }),
  ]);
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '12 ECPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Base Database Service Enterprise License Included 8 OCPUs, 2000 GB storage',
        label: 'Base Database Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b12 ECPUs\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b8 OCPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bEnterprise\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b2000 GB storage\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B111586');
  const storage = reply.quote.lineItems.find((item) => item.partNumber === 'B111584');
  assert.ok(compute);
  assert.ok(storage);
  assert.equal(compute.quantity, 12);
  assert.equal(storage.quantity, 2000);
});

test('session follow-up can switch the active Base Database ECPU quote from license included to BYOL while keeping edition and storage', async () => {
  const index = buildIndex();
  extendIndexWithProducts(index, [
    product({
      partNumber: 'B111586',
      displayName: 'Base Database Service Enterprise - ECPU - License Included',
      serviceCategoryDisplayName: 'Database - Base Database Service',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.19)],
    }),
    product({
      partNumber: 'B111588',
      displayName: 'Base Database Service - ECPU - BYOL',
      serviceCategoryDisplayName: 'Database - Base Database Service',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.11)],
    }),
  ]);
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
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
        source: 'Quote OCI Base Database Service Enterprise License Included 12 ECPUs, 2000 GB storage',
        label: 'Base Database Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bEnterprise\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b12 ECPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b2000 GB storage\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B111588');
  const storage = reply.quote.lineItems.find((item) => item.partNumber === 'B111584');
  assert.ok(compute);
  assert.ok(storage);
  assert.equal(compute.quantity, 12);
  assert.equal(storage.quantity, 2000);
});

test('session follow-up can change edition in the active Base Database ECPU quote while keeping license mode and storage', async () => {
  const index = buildIndex();
  extendIndexWithProducts(index, [
    product({
      partNumber: 'B111586',
      displayName: 'Base Database Service Enterprise - ECPU - License Included',
      serviceCategoryDisplayName: 'Database - Base Database Service',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.19)],
    }),
    product({
      partNumber: 'B111585',
      displayName: 'Base Database Service Standard - ECPU - License Included',
      serviceCategoryDisplayName: 'Database - Base Database Service',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.13)],
    }),
  ]);
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Standard',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Base Database Service Enterprise License Included 12 ECPUs, 2000 GB storage',
        label: 'Base Database Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bStandard\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bEnterprise\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b12 ECPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b2000 GB storage\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B111585');
  const storage = reply.quote.lineItems.find((item) => item.partNumber === 'B111584');
  assert.ok(compute);
  assert.ok(storage);
  assert.equal(compute.quantity, 12);
  assert.equal(storage.quantity, 2000);
});

test('session follow-up can change OCPU count in the active Database Cloud Service quote while keeping edition and license mode', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_cloud_service',
    serviceName: 'Database Cloud Service',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '12 OCPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Database Cloud Service Enterprise BYOL 8 OCPUs',
        label: 'Database Cloud Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b12 OCPUs\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b8 OCPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B88404');
  assert.ok(compute);
  assert.equal(compute.quantity, 12);
});

test('session follow-up can change edition in the active Database Cloud Service quote while keeping OCPU count and license mode', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_cloud_service',
    serviceName: 'Database Cloud Service',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Extreme Performance',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Database Cloud Service Enterprise License Included 8 OCPUs',
        label: 'Database Cloud Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bExtreme Performance\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bEnterprise\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b8 OCPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B88291');
  assert.ok(compute);
  assert.equal(compute.quantity, 8);
});

test('session follow-up can switch the active Database Cloud Service quote from license included to BYOL while keeping extreme performance edition and OCPU count', async () => {
  const index = buildIndex();
  extendIndexWithProducts(index, [
    product({
      partNumber: 'B88402',
      displayName: 'Database Cloud Service Extreme Performance - BYOL',
      serviceCategoryDisplayName: 'Database - Database Cloud Service',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.39)],
    }),
  ]);
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_cloud_service',
    serviceName: 'Database Cloud Service',
    extractedInputs: {},
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
        source: 'Quote OCI Database Cloud Service Extreme Performance License Included 8 OCPUs',
        label: 'Database Cloud Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bExtreme Performance\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b8 OCPUs\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B88402');
  assert.ok(compute);
  assert.equal(compute.quantity, 8);
});

test('session follow-up can change edition in the active Database Cloud Service quote from enterprise to standard while keeping license included and OCPU count', async () => {
  const index = buildIndex();
  extendIndexWithProducts(index, [
    product({
      partNumber: 'B88293',
      displayName: 'Database Cloud Service Standard - License Included',
      serviceCategoryDisplayName: 'Database - Database Cloud Service',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.31)],
    }),
  ]);
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_cloud_service',
    serviceName: 'Database Cloud Service',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Standard',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Database Cloud Service Enterprise License Included 8 OCPUs',
        label: 'Database Cloud Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bStandard\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bEnterprise\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b8 OCPUs\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B88293');
  assert.ok(compute);
  assert.equal(compute.quantity, 8);
});

test('session follow-up can change edition in the active Database Cloud Service quote from extreme performance BYOL to standard BYOL while keeping OCPU count', async () => {
  const index = buildIndex();
  extendIndexWithProducts(index, [
    product({
      partNumber: 'B88402',
      displayName: 'Database Cloud Service Extreme Performance - BYOL',
      serviceCategoryDisplayName: 'Database - Database Cloud Service',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.39)],
    }),
  ]);
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_cloud_service',
    serviceName: 'Database Cloud Service',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Standard',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Database Cloud Service Extreme Performance BYOL 8 OCPUs',
        label: 'Database Cloud Service',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bStandard\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bExtreme Performance\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b8 OCPUs\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B88404');
  assert.ok(compute);
  assert.equal(compute.quantity, 8);
});

test('session follow-up can change instance count in the active OIC Standard quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'integration_oic_standard',
    serviceName: 'Oracle Integration Cloud Standard',
    extractedInputs: {},
    confidence: 0.9,
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
        source: 'Quote Oracle Integration Cloud Standard License Included 1 instance 744h/month',
        label: 'Oracle Integration Cloud Standard',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b3 instances\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b1 instance\b/i);
  assert.match(reply.message, /B89639/);
});

test('session follow-up can change instance count in the active OIC Enterprise quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'integration_oic_enterprise',
    serviceName: 'Oracle Integration Cloud Enterprise',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '4 instances',
    sessionContext: {
      lastQuote: {
        source: 'Quote Oracle Integration Cloud Enterprise License Included 2 instances 744h/month',
        label: 'Oracle Integration Cloud Enterprise',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b4 instances\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b2 instances\b/i);
  assert.ok(Array.isArray(reply.quote.lineItems));
  assert.ok(reply.quote.lineItems.length > 0);
  assert.match(reply.message, /B89640/);
});

test('session follow-up can switch the active OAC Professional OCPU quote from license included to BYOL', async () => {
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
    extractedInputs: {},
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
        source: 'Quote Oracle Analytics Cloud Professional License Included 2 OCPUs',
        label: 'Oracle Analytics Cloud Professional',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  assert.match(reply.message, /B89636/);
  assert.doesNotMatch(reply.message, /B89630/);
});

test('session follow-up can change OCPU count in the active OAC Professional OCPU quote', async () => {
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
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '4 OCPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote Oracle Analytics Cloud Professional BYOL 2 OCPUs',
        label: 'Oracle Analytics Cloud Professional',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b4 OCPUs\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b2 OCPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B89636');
  assert.ok(compute);
  assert.equal(compute.quantity, 4);
});

test('session follow-up can switch the active OAC Enterprise OCPU quote from BYOL to license included', async () => {
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
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'License Included',
    sessionContext: {
      lastQuote: {
        source: 'Quote Oracle Analytics Cloud Enterprise BYOL 4 OCPUs',
        label: 'Oracle Analytics Cloud Enterprise',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  assert.match(reply.message, /B89631/);
  assert.doesNotMatch(reply.message, /B89637/);
});

test('session follow-up can change OCPU count in the active OAC Enterprise OCPU quote', async () => {
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
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '6 OCPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote Oracle Analytics Cloud Enterprise License Included 4 OCPUs',
        label: 'Oracle Analytics Cloud Enterprise',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b6 OCPUs\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b4 OCPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B89631');
  assert.ok(compute);
  assert.equal(compute.quantity, 6);
});

test('session follow-up can switch the active Autonomous AI Lakehouse quote from BYOL to license included', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_autonomous_lakehouse',
    serviceName: 'Autonomous AI Lakehouse',
    extractedInputs: { ecpus: 2, storageGb: 100 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'License Included',
    sessionContext: {
      lastQuote: {
        source: 'Quote Autonomous AI Lakehouse BYOL 2 ECPUs and 100 GB storage per month',
        label: 'Autonomous AI Lakehouse',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bLicense Included\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bBYOL\b/i);
  assert.match(reply.message, /B95701/);
  assert.doesNotMatch(reply.message, /B95703/);
});

test('session follow-up can change OCPU count in the active Exadata Dedicated quote while keeping infrastructure shape', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_exadata_dedicated',
    serviceName: 'Exadata Dedicated Infrastructure',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '8 OCPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Exadata Dedicated Infrastructure Database License Included 4 OCPUs on base system',
        label: 'Exadata Dedicated Infrastructure',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b8 OCPUs\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b4 OCPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bon base system\b/i);
  assert.match(reply.message, /B88592/);
  assert.match(reply.message, /B90777/);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B88592');
  assert.ok(compute);
  assert.equal(compute.quantity, 8);
});

test('session follow-up can change ECPU count in the active Exadata Dedicated quote while keeping X11M infrastructure shape', async () => {
  const index = buildIndex();
  extendIndexWithProducts(index, [
    product({
      partNumber: 'B110631',
      displayName: 'Exadata Dedicated Infrastructure Database - ECPU - License Included',
      serviceCategoryDisplayName: 'Exadata Dedicated Infrastructure Database',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.336)],
    }),
    product({
      partNumber: 'B110627',
      displayName: 'Exadata Dedicated Infrastructure Database Server X11M',
      serviceCategoryDisplayName: 'Exadata Infrastructure',
      metricId: 'm-capacity-month',
      pricetype: 'MONTH',
      usdPrices: [payg(2200)],
    }),
  ]);
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_exadata_dedicated',
    serviceName: 'Exadata Dedicated Infrastructure',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '12 ECPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Exadata Dedicated Infrastructure Database License Included 8 ECPUs on database server X11M',
        label: 'Exadata Dedicated Infrastructure',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b12 ECPUs\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b8 ECPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bon database server X11M\b/i);
  assert.match(reply.message, /B110631/);
  assert.match(reply.message, /B110627/);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B110631');
  assert.ok(compute);
  assert.equal(compute.quantity, 12);
});

test('session follow-up can switch the active Exadata Dedicated quote infrastructure shape from database server X11M to storage server X11M', async () => {
  const index = buildIndex();
  extendIndexWithProducts(index, [
    product({
      partNumber: 'B110631',
      displayName: 'Exadata Dedicated Infrastructure Database - ECPU - License Included',
      serviceCategoryDisplayName: 'Exadata Dedicated Infrastructure Database',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.336)],
    }),
    product({
      partNumber: 'B110627',
      displayName: 'Exadata Dedicated Infrastructure Database Server X11M',
      serviceCategoryDisplayName: 'Exadata Infrastructure',
      metricId: 'm-capacity-month',
      pricetype: 'MONTH',
      usdPrices: [payg(2200)],
    }),
    product({
      partNumber: 'B110629',
      displayName: 'Exadata Dedicated Infrastructure Storage Server X11M',
      serviceCategoryDisplayName: 'Exadata Infrastructure',
      metricId: 'm-capacity-month',
      pricetype: 'MONTH',
      usdPrices: [payg(1800)],
    }),
  ]);
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_exadata_dedicated',
    serviceName: 'Exadata Dedicated Infrastructure',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'on storage server X11M',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Exadata Dedicated Infrastructure Database License Included 8 ECPUs on database server X11M',
        label: 'Exadata Dedicated Infrastructure',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bon storage server X11M\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bon database server X11M\b/i);
  assert.match(reply.message, /B110631/);
  assert.match(reply.message, /B110629/);
  assert.doesNotMatch(reply.message, /B110627/);
});

test('session follow-up can change ECPU count in the active Exadata Exascale quote while keeping storage model and size', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_exadata_exascale',
    serviceName: 'Exadata Exascale',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '8 ECPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Exadata Exascale Database License Included 4 ECPUs 1000 GB storage filesystem storage',
        label: 'Exadata Exascale',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b8 ECPUs\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b4 ECPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b1000 GB storage\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /filesystem storage/i);
  assert.match(reply.message, /B109356/);
  assert.match(reply.message, /B107951/);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B109356');
  assert.ok(compute);
  assert.equal(compute.quantity, 8);
});

test('session follow-up can change storage size in the active Exadata Exascale quote while keeping ecpus and storage model', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_exadata_exascale',
    serviceName: 'Exadata Exascale',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '1500 GB storage',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Exadata Exascale Database BYOL 4 ECPUs 1000 GB storage filesystem storage',
        label: 'Exadata Exascale',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b1500 GB storage\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b1000 GB storage\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b4 ECPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /filesystem storage/i);
  assert.match(reply.message, /B109357/);
  assert.match(reply.message, /B107951/);
  const storage = reply.quote.lineItems.find((item) => item.partNumber === 'B107951');
  assert.ok(storage);
  assert.equal(storage.quantity, 1500);
});

test('session follow-up can switch the active Exadata Exascale quote storage model from filesystem to smart database storage', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_exadata_exascale',
    serviceName: 'Exadata Exascale',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'smart database storage',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Exadata Exascale Database License Included 4 ECPUs 1000 GB storage filesystem storage',
        label: 'Exadata Exascale',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /smart database storage/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /filesystem storage/i);
  assert.match(reply.message, /B109356/);
  assert.match(reply.message, /B107952/);
  assert.doesNotMatch(reply.message, /B107951/);
});

test('session follow-up can change OCPU count in the active Exadata Cloud@Customer quote while keeping infrastructure shape', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_exadata_cloud_customer',
    serviceName: 'Exadata Cloud@Customer',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '12 OCPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Exadata Cloud@Customer Database BYOL 8 OCPUs on base system X10M',
        label: 'Exadata Cloud@Customer',
        serviceFamily: 'database_exadata_cloud_customer',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b12 OCPUs\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b8 OCPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bon base system X10M\b/i);
  assert.match(reply.message, /B91364/);
  assert.match(reply.message, /B96610/);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B91364');
  assert.ok(compute);
  assert.equal(compute.quantity, 12);
});

test('session follow-up can change ECPU count in the active Exadata Cloud@Customer quote while keeping infrastructure shape', async () => {
  const index = buildIndex();
  extendIndexWithProducts(index, [
    product({
      partNumber: 'B110663',
      displayName: 'Exadata Cloud@Customer Database - ECPU - BYOL',
      serviceCategoryDisplayName: 'Exadata Cloud@Customer Database',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.168)],
    }),
  ]);
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_exadata_cloud_customer',
    serviceName: 'Exadata Cloud@Customer',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: '16 ECPUs',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Exadata Cloud@Customer Database BYOL 8 ECPUs on base system X10M',
        label: 'Exadata Cloud@Customer',
        serviceFamily: 'database_exadata_cloud_customer',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\b16 ECPUs\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\b8 ECPUs\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\bon base system X10M\b/i);
  assert.match(reply.message, /B110663/);
  assert.match(reply.message, /B96610/);
  const compute = reply.quote.lineItems.find((item) => item.partNumber === 'B110663');
  assert.ok(compute);
  assert.equal(compute.quantity, 16);
});

test('session follow-up can switch the active Exadata Cloud@Customer quote infrastructure shape from base system X10M to database server X10M', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_exadata_cloud_customer',
    serviceName: 'Exadata Cloud@Customer',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'on database server X10M',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Exadata Cloud@Customer Database License Included 8 OCPUs on base system X10M',
        label: 'Exadata Cloud@Customer',
        serviceFamily: 'database_exadata_cloud_customer',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bon database server X10M\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bon base system X10M\b/i);
  assert.match(reply.message, /B91363/);
  assert.match(reply.message, /B96611/);
  assert.doesNotMatch(reply.message, /B96610/);
});

test('session follow-up can switch the active Exadata Cloud@Customer quote infrastructure shape from database server X10M to expansion rack X10M while keeping ECPU compute', async () => {
  const index = buildIndex();
  extendIndexWithProducts(index, [
    product({
      partNumber: 'B110662',
      displayName: 'Exadata Cloud@Customer Database - ECPU - License Included',
      serviceCategoryDisplayName: 'Exadata Cloud@Customer Database',
      metricId: 'm-ocpu-hour',
      usdPrices: [payg(0.336)],
    }),
    product({
      partNumber: 'B96615',
      displayName: 'Exadata Cloud@Customer Expansion Rack X10M',
      serviceCategoryDisplayName: 'Exadata Infrastructure',
      metricId: 'm-capacity-month',
      pricetype: 'MONTH',
      usdPrices: [payg(1300)],
    }),
  ]);
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_exadata_cloud_customer',
    serviceName: 'Exadata Cloud@Customer',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'on expansion rack X10M',
    sessionContext: {
      lastQuote: {
        source: 'Quote OCI Exadata Cloud@Customer Database License Included 8 ECPUs on database server X10M',
        label: 'Exadata Cloud@Customer',
        serviceFamily: 'database_exadata_cloud_customer',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.sessionContext.lastQuote.source, /\bon expansion rack X10M\b/i);
  assert.doesNotMatch(reply.sessionContext.lastQuote.source, /\bon database server X10M\b/i);
  assert.match(reply.sessionContext.lastQuote.source, /\b8 ECPUs\b/i);
  assert.match(reply.message, /B110662/);
  assert.match(reply.message, /B96615/);
  assert.doesNotMatch(reply.message, /B96611/);
});
