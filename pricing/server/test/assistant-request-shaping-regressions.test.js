'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadAssistantWithStubs, buildIndex } = require('./assistant-test-helpers');

test('assistant preserves the metered modifier when the intent model drops it from a bare metal prompt', async () => {
  const index = buildIndex();
  index.products.push({
    partNumber: 'B89137',
    displayName: 'Compute - Bare Metal Standard - X7 - Metered',
    fullDisplayName: 'B89137 - Compute - Bare Metal Standard - X7 - Metered',
    priceType: 'HOUR',
    serviceCategoryDisplayName: 'Compute - Bare Metal',
    metricId: 'm-ocpu-hour',
    metricDisplayName: 'OCPU Per Hour',
    metricUnitDisplayName: '',
    pricingByCurrency: { USD: [{ model: 'PAY_AS_YOU_GO', value: 0.075 }] },
    tiersByCurrency: { USD: [{ model: 'PAY_AS_YOU_GO', value: 0.075, rangeMin: null, rangeMax: null, rangeUnit: null }] },
  });
  index.productsByPartNumber.set('B89137', [index.products[index.products.length - 1]]);

  const { respondToAssistant } = loadAssistantWithStubs((_text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Quote BM.Standard2.52 744h/month',
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: 'Quote BM.Standard2.52 744h/month',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote BM.Standard2.52 metered 744h/month',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B89137/);
  assert.doesNotMatch(reply.message, /B88513/);
});

test('autonomous ai lakehouse asks for license choice and quotes compute plus storage', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_autonomous_dw',
    serviceName: 'Autonomous AI Lakehouse',
    extractedInputs: { ecpus: 2, capacityGb: 100 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const clarify = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Autonomous AI Lakehouse 2 ECPUs and 100 GB storage per month',
  });
  assert.equal(clarify.ok, true);
  assert.equal(clarify.mode, 'clarification');
  assert.match(clarify.message, /BYOL or License Included/i);

  const quote = await respondToAssistant({
    cfg: {},
    index,
    conversation: [
      { role: 'user', content: 'Quote Autonomous AI Lakehouse 2 ECPUs and 100 GB storage per month' },
      { role: 'assistant', content: clarify.message },
    ],
    userText: 'BYOL',
  });
  assert.equal(quote.ok, true);
  assert.equal(quote.mode, 'quote');
  assert.match(quote.message, /B95703/);
  assert.match(quote.message, /B95706/);
  assert.match(quote.message, /shared autonomous database storage SKU/i);
});

test('autonomous data warehouse alias resolves to autonomous ai lakehouse family', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_autonomous_dw',
    serviceName: 'Autonomous Data Warehouse',
    extractedInputs: { ecpus: 2, capacityGb: 100 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const quote = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Autonomous Data Warehouse License Included 2 ECPUs and 100 GB storage per month',
  });
  assert.equal(quote.ok, true);
  assert.equal(quote.mode, 'quote');
  assert.match(quote.message, /Autonomous AI Lakehouse|Autonomous Data Warehouse/i);
  assert.match(quote.message, /B95701/);
  assert.match(quote.message, /B95706/);
});

test('web application firewall quotes directly when generic instance count is present', async () => {
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
    extractedInputs: { instanceCount: 2, requestCount: 25000000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const quote = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Web Application Firewall with 2 instances and 25000000 requests per month',
  });
  assert.equal(quote.ok, true);
  assert.equal(quote.mode, 'quote');
  assert.match(quote.message, /B94579/);
  assert.match(quote.message, /B94277/);
  assert.match(quote.message, /\|\s*2\s*\|\s*1\s*\|\s*744\s*\|\s*1\s*\|\s*\$5\s*\|/);
});

test('web application firewall still quotes when explanation text is appended', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: true,
    clarificationQuestion: 'How many WAF instances or policies do you need, and how many incoming requests do you expect per month?',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_waf',
    serviceName: 'Web Application Firewall',
    extractedInputs: { instanceCount: 2, requestCount: 25000000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const quote = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Web Application Firewall with 2 instances and 25000000 requests per month. Explain how OCI measures it.',
  });
  assert.equal(quote.ok, true);
  assert.equal(quote.mode, 'quote');
  assert.match(quote.message, /B94579/);
  assert.match(quote.message, /B94277/);
});

test('web application firewall prefers the richer user prompt when the canonical request loses instance count', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Quote Web Application Firewall with 25000000 requests per month',
    assumptions: [],
    serviceFamily: 'security_waf',
    serviceName: 'Web Application Firewall',
    extractedInputs: { requestCount: 25000000, wafInstances: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: 'Quote Web Application Firewall with 25000000 requests per month',
  }));

  const quote = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Web Application Firewall with 2 instances and 25000000 requests per month. Explain how OCI measures it.',
  });
  assert.equal(quote.ok, true);
  assert.equal(quote.mode, 'quote');
  assert.match(quote.message, /Monthly total: \$10\.04/);
  assert.match(quote.message, /B94579/);
  assert.match(quote.message, /B94277/);
  assert.match(quote.message, /B94579[^]*\$10\.00\/month/);
});

test('exadata exascale canonical request keeps filesystem storage line', async () => {
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
    extractedInputs: { ecpus: 4, capacityGb: 1000, databaseStorageModel: 'filesystem storage' },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: 'Exadata Exascale with License Included, 4 ECPUs, 1000 GB storage',
  }));

  const quote = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Exadata Exascale License Included 4 ECPUs and 1000 GB filesystem storage',
  });
  assert.equal(quote.ok, true);
  assert.equal(quote.mode, 'quote');
  assert.match(quote.message, /B109356/);
  assert.match(quote.message, /B107951/);
});

test('exadata dedicated canonical request keeps base system infrastructure line', async () => {
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
    extractedInputs: { ocpus: 4, exadataInfraShape: 'base system' },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: 'Exadata Dedicated Infrastructure License Included with 4 OCPUs',
  }));

  const quote = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Exadata Dedicated Infrastructure License Included 4 OCPUs on base system',
  });
  assert.equal(quote.ok, true);
  assert.equal(quote.mode, 'quote');
  assert.match(quote.message, /B88592/);
  assert.match(quote.message, /B90777/);
});
