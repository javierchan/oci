'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const assistantPath = path.join(ROOT, 'assistant.js');
const intentPath = path.join(ROOT, 'intent-extractor.js');
const genaiPath = path.join(ROOT, 'genai.js');
const { normalizeCatalog } = require(path.join(ROOT, 'catalog.js'));

function loadAssistantWithStubs(intentResolver) {
  delete require.cache[assistantPath];
  delete require.cache[intentPath];
  delete require.cache[genaiPath];

  require.cache[intentPath] = {
    id: intentPath,
    filename: intentPath,
    loaded: true,
    exports: {
      analyzeIntent: async (_cfg, _conversation, text) => intentResolver(String(text || '')),
      analyzeImageIntent: async (_cfg, text) => intentResolver(String(text || '')),
    },
  };

  require.cache[genaiPath] = {
    id: genaiPath,
    filename: genaiPath,
    loaded: true,
    exports: {
      runChat: async () => ({ data: {} }),
      extractChatText: () => '',
      loadGenAISettings: () => ({}),
    },
  };

  return require(assistantPath);
}

function metric(id, displayName, unitDisplayName = '') {
  return { id, displayName, unitDisplayName };
}

function payg(value, rangeMin, rangeMax) {
  const tier = {
    model: 'PAY_AS_YOU_GO',
    value,
  };
  if (rangeMin !== undefined) tier.rangeMin = rangeMin;
  if (rangeMax !== undefined) tier.rangeMax = rangeMax;
  return tier;
}

function product({
  partNumber,
  displayName,
  serviceCategoryDisplayName,
  metricId,
  pricetype = 'HOUR',
  usdPrices = [payg(1)],
}) {
  return {
    partNumber,
    displayName,
    serviceCategoryDisplayName,
    metricId,
    pricetype,
    currencyCodeLocalizations: [
      {
        currencyCode: 'USD',
        prices: usdPrices,
      },
    ],
  };
}

function buildIndex() {
  return normalizeCatalog({
    'metrics.json': {
      items: [
        metric('m-port-hour', 'Port Hour'),
        metric('m-msg-hour', '5K Messages Per Hour'),
        metric('m-ocpu-hour', 'OCPU Per Hour'),
        metric('m-gb-hour', 'Gigabyte RAM Per Hour'),
        metric('m-capacity-month', 'Gigabyte Storage Capacity Per Month'),
        metric('m-performance-month', 'Performance Units Per Gigabyte Per Month'),
        metric('m-queries-million', '1,000,000 Queries'),
        metric('m-emails-thousand', '1,000 Emails Sent'),
        metric('m-sms-each', '1 SMS Message Sent'),
        metric('m-transactions-thousand', '1,000 Transactions'),
        metric('m-transactions-ten-thousand', '10,000 Transactions'),
        metric('m-training-hour', 'Training Hour'),
        metric('m-transcription-hour', 'Transcription Hour'),
        metric('m-media-minute', 'Minute of Output Media Content'),
        metric('m-processed-video-minute', 'Processed Video Minute'),
        metric('m-each', 'Each'),
        metric('m-datapoints-million', 'Million Datapoints'),
        metric('m-delivery-million', 'Million Delivery Operations'),
        metric('m-endpoints-month', 'Endpoints Per Month'),
        metric('m-managed-resource-month', '1 Managed Resource Per Month'),
        metric('m-target-database-month', 'Target Database Per Month'),
        metric('m-events-thousand', '1000 Events'),
        metric('m-requests-thousand-plain', '1000 Requests'),
        metric('m-storage-hour', 'Gigabyte Storage Per Hour'),
        metric('m-functions-exec', '10,000 GB Memory-Seconds'),
        metric('m-functions-inv', '1MIL Function Invocations'),
      ],
    },
    'products.json': {
      items: [
        product({
          partNumber: 'B88325',
          displayName: 'OCI - FastConnect 1 Gbps',
          serviceCategoryDisplayName: 'Networking - FastConnect',
          metricId: 'm-port-hour',
          usdPrices: [payg(0.2125)],
        }),
        product({
          partNumber: 'B88326',
          displayName: 'OCI - FastConnect 10 Gbps',
          serviceCategoryDisplayName: 'Networking - FastConnect',
          metricId: 'm-port-hour',
          usdPrices: [payg(1.275)],
        }),
        product({
          partNumber: 'B93126',
          displayName: 'OCI - FastConnect 100 Gbps',
          serviceCategoryDisplayName: 'Networking - FastConnect',
          metricId: 'm-port-hour',
          usdPrices: [payg(10.75)],
        }),
        product({
          partNumber: 'B107975',
          displayName: 'OCI - FastConnect 400 Gbps',
          serviceCategoryDisplayName: 'Networking - FastConnect',
          metricId: 'm-port-hour',
          usdPrices: [payg(20)],
        }),
        product({
          partNumber: 'B90617',
          displayName: 'Oracle Functions - Execution Time',
          serviceCategoryDisplayName: 'Application Development - Serverless',
          metricId: 'm-functions-exec',
          pricetype: 'MONTH',
          usdPrices: [payg(0, 0, 40), payg(0.1417, 40, null)],
        }),
        product({
          partNumber: 'B90618',
          displayName: 'Oracle Functions - Invocations',
          serviceCategoryDisplayName: 'Application Development - Serverless',
          metricId: 'm-functions-inv',
          pricetype: 'MONTH',
          usdPrices: [payg(0, 0, 2), payg(0.2, 2, null)],
        }),
        product({
          partNumber: 'B91961',
          displayName: 'Storage - Block Volume - Storage',
          serviceCategoryDisplayName: 'Storage - Block Volumes',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0255)],
        }),
        product({
          partNumber: 'B91962',
          displayName: 'Storage - Block Volume - Performance Units',
          serviceCategoryDisplayName: 'Storage - Block Volumes',
          metricId: 'm-performance-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0017)],
        }),
        product({
          partNumber: 'B91628',
          displayName: 'Object Storage - Storage',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0255)],
        }),
        product({
          partNumber: 'B92599',
          displayName: 'OCI Data Integration - Data Processed',
          serviceCategoryDisplayName: 'Data Integration',
          metricId: 'm-capacity-month',
          pricetype: 'HOUR',
          usdPrices: [payg(0.04)],
        }),
        product({
          partNumber: 'B92809',
          displayName: 'OCI Log Analytics - Archival Storage',
          serviceCategoryDisplayName: 'Observability - Log Analytics',
          metricId: 'm-port-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.02)],
        }),
        product({
          partNumber: 'B95634',
          displayName: 'OCI Log Analytics - Active Storage',
          serviceCategoryDisplayName: 'Observability - Log Analytics',
          metricId: 'm-port-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.412)],
        }),
        product({
          partNumber: 'B94579',
          displayName: 'OCI Web Application Firewall - Instance',
          serviceCategoryDisplayName: 'Security - Web Application Firewall',
          metricId: 'm-port-hour',
          pricetype: 'MONTH',
          usdPrices: [payg(5)],
        }),
        product({
          partNumber: 'B94277',
          displayName: 'OCI Web Application Firewall - Requests',
          serviceCategoryDisplayName: 'Security - Web Application Firewall',
          metricId: 'm-port-hour',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0016)],
        }),
        product({
          partNumber: 'B95701',
          displayName: 'Oracle Autonomous AI Lakehouse - ECPU',
          serviceCategoryDisplayName: 'Database - Autonomous Database',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.336)],
        }),
        product({
          partNumber: 'B95703',
          displayName: 'Oracle Autonomous AI Lakehouse - ECPU - BYOL',
          serviceCategoryDisplayName: 'Database - Autonomous Database',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.0807)],
        }),
        product({
          partNumber: 'B95706',
          displayName: 'Oracle Autonomous Database Storage for Transaction Processing',
          serviceCategoryDisplayName: 'Database - Autonomous Database',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.1156)],
        }),
        product({
          partNumber: 'B109356',
          displayName: 'Oracle Exadata Exascale Database - ECPU - License Included',
          serviceCategoryDisplayName: 'Exadata Database Service',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.336)],
        }),
        product({
          partNumber: 'B107951',
          displayName: 'Oracle Exadata Exascale Filesystem Storage',
          serviceCategoryDisplayName: 'Exadata Database Service Storage',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0391)],
        }),
        product({
          partNumber: 'B88592',
          displayName: 'Exadata Dedicated Infrastructure Database - OCPU - License Included',
          serviceCategoryDisplayName: 'Exadata Dedicated Infrastructure Database',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(1.3441)],
        }),
        product({
          partNumber: 'B91363',
          displayName: 'Exadata Cloud@Customer Database - OCPU - License Included',
          serviceCategoryDisplayName: 'Exadata Cloud@Customer Database',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(1.3441)],
        }),
        product({
          partNumber: 'B96610',
          displayName: 'Exadata Cloud@Customer Base System X10M',
          serviceCategoryDisplayName: 'Exadata Infrastructure',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(1600)],
        }),
        product({
          partNumber: 'B90777',
          displayName: 'Exadata Dedicated Infrastructure Base System',
          serviceCategoryDisplayName: 'Exadata Infrastructure',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(560)],
        }),
        product({
          partNumber: 'B93030',
          displayName: 'Load Balancer Base',
          serviceCategoryDisplayName: 'Flexible Load Balancer',
          metricId: 'm-port-hour',
          pricetype: 'HOUR_UTILIZED',
          usdPrices: [payg(0, 0, 744), payg(0.008, 744, null)],
        }),
        product({
          partNumber: 'B93031',
          displayName: 'Load Balancer Bandwidth',
          serviceCategoryDisplayName: 'Flexible Load Balancer',
          metricId: 'm-port-hour',
          pricetype: 'HOUR_UTILIZED',
          usdPrices: [payg(0.00009)],
        }),
        product({
          partNumber: 'B89640',
          displayName: 'Oracle Integration Cloud Service - Enterprise | 5K Messages Per Hour',
          serviceCategoryDisplayName: 'Application Integration - OIC',
          metricId: 'm-msg-hour',
          usdPrices: [payg(1.2903)],
        }),
        product({
          partNumber: 'B89639',
          displayName: 'Oracle Integration Cloud Service - Standard | 5K Messages Per Hour',
          serviceCategoryDisplayName: 'Application Integration - OIC',
          metricId: 'm-msg-hour',
          usdPrices: [payg(0.6452)],
        }),
        product({
          partNumber: 'B89644',
          displayName: 'Oracle Integration Cloud Service - Enterprise - BYOL | 5K Messages Per Hour',
          serviceCategoryDisplayName: 'Application Integration - OIC',
          metricId: 'm-msg-hour',
          usdPrices: [payg(0.3226)],
        }),
        product({
          partNumber: 'B89643',
          displayName: 'Oracle Integration Cloud Service - Standard - BYOL | 20K Messages Per Hour',
          serviceCategoryDisplayName: 'Application Integration - OIC',
          metricId: 'm-msg-hour',
          usdPrices: [payg(0.1613)],
        }),
        product({
          partNumber: 'B88525',
          displayName: 'OCI DNS - Queries',
          serviceCategoryDisplayName: 'Networking - DNS',
          metricId: 'm-queries-million',
          pricetype: 'MONTH',
          usdPrices: [payg(0.85)],
        }),
        product({
          partNumber: 'B90941',
          displayName: 'OCI Notifications - Email Delivery',
          serviceCategoryDisplayName: 'Notifications - Email Delivery',
          metricId: 'm-emails-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(2)],
        }),
        product({
          partNumber: 'B93496',
          displayName: 'OCI IAM - SMS',
          serviceCategoryDisplayName: 'Identity and Access Management - SMS',
          metricId: 'm-sms-each',
          pricetype: 'MONTH',
          usdPrices: [payg(0.02)],
        }),
        product({
          partNumber: 'B93423',
          displayName: 'OCI AI Language - Pre-trained Inferencing',
          serviceCategoryDisplayName: 'OCI - AI Services - Language - Pre-trained Inferencing',
          metricId: 'm-transactions-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(0.5)],
        }),
        product({
          partNumber: 'B108077',
          displayName: 'OCI Generative AI - Large Cohere',
          serviceCategoryDisplayName: 'OCI Generative AI - Large Cohere',
          metricId: 'm-transactions-ten-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(1.5)],
        }),
        product({
          partNumber: 'B94977',
          displayName: 'Vision - Custom Training',
          serviceCategoryDisplayName: 'Oracle Cloud Infrastructure - Vision - Custom Training',
          metricId: 'm-training-hour',
          usdPrices: [payg(1.47)],
        }),
        product({
          partNumber: 'B94896',
          displayName: 'Speech',
          serviceCategoryDisplayName: 'Speech',
          metricId: 'm-transcription-hour',
          usdPrices: [payg(0.016)],
        }),
        product({
          partNumber: 'B95337',
          displayName: 'Media Services - Media Flow - Standard - H264 - HD - Above 30fps and Below 60fps',
          serviceCategoryDisplayName: 'Media Services - Media Flow - Quality - H264 - HD - Above 30fps and Below 60fps',
          metricId: 'm-media-minute',
          pricetype: 'MONTH',
          usdPrices: [payg(0.006)],
        }),
        product({
          partNumber: 'B95282',
          displayName: 'Media Services - Media Flow - Standard - H264 - HD - Below 30fps',
          serviceCategoryDisplayName: 'Media Services - Media Flow - Quality - H264 - HD - Below 30fps',
          metricId: 'm-media-minute',
          pricetype: 'MONTH',
          usdPrices: [payg(0.006)],
        }),
        product({
          partNumber: 'B110617',
          displayName: 'OCI - Vision - Stored Video Analysis',
          serviceCategoryDisplayName: 'OCI - Vision - Stored Video Analysis',
          metricId: 'm-processed-video-minute',
          pricetype: 'MONTH',
          usdPrices: [payg(0.003)],
        }),
        product({
          partNumber: 'B91632',
          displayName: 'Data Safe for Database Cloud Service - Databases',
          serviceCategoryDisplayName: 'Security - Data Safe',
          metricId: 'm-each',
          pricetype: 'MONTH',
          usdPrices: [payg(10)],
        }),
        product({
          partNumber: 'B92733',
          displayName: 'Data Safe for On-Premises Databases & Databases on Compute',
          serviceCategoryDisplayName: 'Security - Data Safe',
          metricId: 'm-target-database-month',
          pricetype: 'MONTH',
          usdPrices: [payg(20)],
        }),
        product({
          partNumber: 'B112107',
          displayName: 'OCI Batch',
          serviceCategoryDisplayName: 'OCI Batch',
          metricId: 'm-each',
          pricetype: 'MONTH',
          usdPrices: [payg(2)],
        }),
        product({
          partNumber: 'B90925',
          displayName: 'Monitoring - Ingestion',
          serviceCategoryDisplayName: 'Observability - Monitoring',
          metricId: 'm-datapoints-million',
          pricetype: 'MONTH',
          usdPrices: [payg(1.25)],
        }),
        product({
          partNumber: 'B90926',
          displayName: 'Monitoring - Retrieval',
          serviceCategoryDisplayName: 'Observability - Monitoring',
          metricId: 'm-datapoints-million',
          pricetype: 'MONTH',
          usdPrices: [payg(0.75)],
        }),
        product({
          partNumber: 'B90940',
          displayName: 'Notifications - HTTPS Delivery',
          serviceCategoryDisplayName: 'Observability - Notifications',
          metricId: 'm-delivery-million',
          pricetype: 'MONTH',
          usdPrices: [payg(4)],
        }),
        product({
          partNumber: 'B95485',
          displayName: 'OCI Full Stack Disaster Recovery Service',
          serviceCategoryDisplayName: 'OCI Full Stack Disaster Recovery Service',
          metricId: 'm-port-hour',
          usdPrices: [payg(0.0128)],
        }),
        product({
          partNumber: 'B110274',
          displayName: 'OCI Full Stack Disaster Recovery Service for Compute',
          serviceCategoryDisplayName: 'OCI Full Stack Disaster Recovery Service',
          metricId: 'm-port-hour',
          usdPrices: [payg(0.0056)],
        }),
        product({
          partNumber: 'B112110',
          displayName: 'OCI Full Stack Disaster Recovery Service for Oracle Integration Cloud',
          serviceCategoryDisplayName: 'OCI Full Stack Disaster Recovery Service',
          metricId: 'm-port-hour',
          usdPrices: [payg(0.192)],
        }),
        product({
          partNumber: 'B90325',
          displayName: 'OCI - Health Checks - Premium',
          serviceCategoryDisplayName: 'Edge Services',
          metricId: 'm-endpoints-month',
          pricetype: 'MONTH',
          usdPrices: [payg(1.3)],
        }),
        product({
          partNumber: 'B110475',
          displayName: 'OCI Fleet Application Management Service',
          serviceCategoryDisplayName: 'Fleet Application Management',
          metricId: 'm-managed-resource-month',
          pricetype: 'MONTH',
          usdPrices: [payg(7)],
        }),
        product({
          partNumber: 'B110463',
          displayName: 'OCI Generative AI Agents - Data Ingestion',
          serviceCategoryDisplayName: 'OCI Generative AI Agents',
          metricId: 'm-transactions-ten-thousand',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(0.0003)],
        }),
        product({
          partNumber: 'B112383',
          displayName: 'OCI Generative AI - Memory Ingestion',
          serviceCategoryDisplayName: 'OCI Generative AI - Search and Retrieval',
          metricId: 'm-events-thousand',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(0.05)],
        }),
        product({
          partNumber: 'B112384',
          displayName: 'OCI Generative AI - Memory Retention',
          serviceCategoryDisplayName: 'OCI Generative AI - Search and Retrieval',
          metricId: 'm-storage-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.01)],
        }),
        product({
          partNumber: 'B112416',
          displayName: 'OCI Generative AI - Vector Store Retrieval',
          serviceCategoryDisplayName: 'OCI Generative AI - Search and Retrieval',
          metricId: 'm-requests-thousand-plain',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(0.5)],
        }),
        product({
          partNumber: 'B111973',
          displayName: 'OCI Generative AI - Web Search',
          serviceCategoryDisplayName: 'OCI Generative AI - Search and Retrieval',
          metricId: 'm-requests-thousand-plain',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(10)],
        }),
        product({
          partNumber: 'B89630',
          displayName: 'Oracle Analytics Cloud - Professional - OCPU',
          serviceCategoryDisplayName: 'Analytics - Analytics Cloud',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.4)],
        }),
        product({
          partNumber: 'B89636',
          displayName: 'Oracle Analytics Cloud - Professional - BYOL - OCPU',
          serviceCategoryDisplayName: 'Analytics - Analytics Cloud',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.1)],
        }),
        product({
          partNumber: 'B92682',
          displayName: 'Oracle Analytics Cloud - Professional - Users',
          serviceCategoryDisplayName: 'Analytics - Analytics Cloud',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(60)],
        }),
        product({
          partNumber: 'B92683',
          displayName: 'Oracle Analytics Cloud - Enterprise - Users',
          serviceCategoryDisplayName: 'Analytics - Analytics Cloud',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(80)],
        }),
        product({
          partNumber: 'B95403',
          displayName: 'OCI Network Firewall - Instance',
          serviceCategoryDisplayName: 'Security - Network Firewall',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(1000)],
        }),
        product({
          partNumber: 'B95404',
          displayName: 'OCI Network Firewall - Data Processing',
          serviceCategoryDisplayName: 'Security - Network Firewall',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.1)],
        }),
        product({
          partNumber: 'B93113',
          displayName: 'Compute - Standard - E4 - OCPU',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.025)],
        }),
        product({
          partNumber: 'B93114',
          displayName: 'Compute - Standard - E4 - Memory',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-gb-hour',
          usdPrices: [payg(0.005)],
        }),
        product({
          partNumber: 'B97384',
          displayName: 'Compute - Standard - E5 - OCPU',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.03)],
        }),
        product({
          partNumber: 'B97385',
          displayName: 'Compute - Standard - E5 - Memory',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-gb-hour',
          usdPrices: [payg(0.006)],
        }),
        product({
          partNumber: 'B93297',
          displayName: 'Compute - Standard - A1 - OCPU',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR_UTILIZED',
          usdPrices: [payg(0, 0, 3000), payg(0.01, 3000, null)],
        }),
        product({
          partNumber: 'B93298',
          displayName: 'Compute - Standard - A1 - Memory',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-gb-hour',
          pricetype: 'HOUR_UTILIZED',
          usdPrices: [payg(0, 0, 18000), payg(0.0015, 18000, null)],
        }),
      ],
    },
    'productpresets.json': { items: [] },
  });
}

test('catalog listing returns FastConnect SKUs without asking for region', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'What FastConnect options are available in the catalog? List all SKUs with hourly prices.',
    assumptions: [],
    serviceFamily: 'network_fastconnect',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: 'Quote OCI FastConnect',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'What FastConnect options are available in the catalog? List all SKUs with hourly prices.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.match(reply.message, /B88325/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B93126/);
  assert.doesNotMatch(reply.message, /what region|which region|tell me the region|please provide the region/i);
});

test('dns queries quote resolves through generic request-volume pattern', async () => {
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
    extractedInputs: { requestCount: 5000000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI DNS 5000000 queries per month',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B88525/);
  assert.match(reply.message, /How OCI measures this:/);
});

test('dns queries quote still resolves correctly when the user appends an explanation request', async () => {
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
    extractedInputs: { requestCount: 5000000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote DNS 5000000 queries per month. Explain how OCI measures the main billing dimensions.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B88525/);
  assert.doesNotMatch(reply.message, /Exadata Cloud@Customer|B110663/);
});

test('email delivery quote resolves through generic request-volume pattern', async () => {
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
    extractedInputs: { requestCount: 25000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Email Delivery 25000 emails per month',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90941/);
});

test('iam sms quote resolves direct per-message pricing', async () => {
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
    extractedInputs: { requestCount: 12 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote IAM SMS 12 SMS messages',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B93496/);
});

test('transaction-based ai quote handles 10,000-transaction metrics', async () => {
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
    extractedInputs: { requestCount: 50000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Generative AI Large Cohere 50000 transactions',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B108077/);
});

test('vision custom training bills direct training hours instead of multiplying by monthly uptime', async () => {
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
    extractedInputs: { serviceHours: 10 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Vision Custom Training 10 training hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94977/);
  assert.match(reply.message, /\$14\.7\b/);
});

test('speech bills direct transcription hours instead of default monthly uptime', async () => {
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
    extractedInputs: { serviceHours: 3 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Speech 3 transcription hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B94896/);
  assert.match(reply.message, /\$0\.048\b/);
});

test('media flow prompt prefers the exact below-30fps variant and bills explicit minutes', async () => {
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
    extractedInputs: { minuteQuantity: 120 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Media Flow HD below 30fps 120 minutes of output media content',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B95282/);
  assert.match(reply.message, /\$0\.72\b/);
});

test('stored video analysis bills explicit processed video minutes', async () => {
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
    extractedInputs: { minuteQuantity: 90 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Vision Stored Video Analysis 90 processed video minutes',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B110617/);
  assert.match(reply.message, /\$0\.27\b/);
});

test('data safe each-metric quote uses explicit database count instead of defaulting to one', async () => {
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
    extractedInputs: { quantity: 3 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Data Safe for Database Cloud Service 3 databases',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91632/);
  assert.match(reply.message, /\$30\b/);
});

test('each-metric quote uses explicit job count for OCI Batch instead of defaulting to one', async () => {
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
    extractedInputs: { quantity: 4 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Batch 4 jobs',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B112107/);
  assert.match(reply.message, /\$8\b/);
});

test('monitoring datapoints quote converts datapoints into million-datapoint units', async () => {
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
    extractedInputs: { requestCount: 2500000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Monitoring Ingestion 2500000 datapoints',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90925/);
  assert.match(reply.message, /\$3\.125\b/);
});

test('https delivery quote converts delivery operations into million-operation units', async () => {
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
    extractedInputs: { requestCount: 3000000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Notifications HTTPS Delivery 3000000 delivery operations',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90940/);
  assert.match(reply.message, /\$12\b/);
});

test('fleet application management uses managed resource count directly', async () => {
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
    extractedInputs: { quantity: 5 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Fleet Application Management 5 managed resources per month',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B110475/);
  assert.match(reply.message, /\$35\b/);
});

test('data safe on-prem uses target database count directly', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_data_safe',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Data Safe for On-Premises Databases 2 target databases',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B92733/);
  assert.match(reply.message, /\$40\b/);
});

test('registry-backed request-volume quote overrides weak clarification from the intent model', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: true,
    clarificationQuestion: 'What is the average size of each event in MB?',
    reformulatedRequest: 'OCI Generative AI Memory Ingestion for 2000 events',
    assumptions: [],
    serviceFamily: 'ai_generative',
    serviceName: 'oci_generative_ai',
    extractedInputs: { requestCount: 2000 },
    confidence: 0.8,
    annualRequested: false,
    normalizedRequest: 'Quote OCI Generative AI Memory Ingestion 2000 events',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Generative AI Memory Ingestion 2000 events',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B112383/);
  assert.doesNotMatch(reply.message, /B112384/);
  assert.doesNotMatch(reply.message, /average size of each event in MB/i);
});

test('vector store retrieval converts 1000-request metrics without requiring commas in the metric name', async () => {
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
    extractedInputs: { requestCount: 5000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Generative AI Vector Store Retrieval 5000 requests',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B112416/);
  assert.match(reply.message, /\$2\.5\b/);
});

test('web search converts 1000-request metrics without requiring commas in the metric name', async () => {
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
    extractedInputs: { requestCount: 12000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Generative AI Web Search 12000 requests',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B111973/);
  assert.match(reply.message, /\$120\b/);
});

test('generic rerank transaction prompt asks for dedicated cluster-hours instead of inventing a transactional quote', async () => {
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
    extractedInputs: { requestCount: 25000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI Generative AI Cohere Rerank 25000 transactions',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'clarification');
  assert.match(reply.message, /cluster-hours/i);
  assert.doesNotMatch(reply.message, /B111015/);
});

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

test('flex comparison follow-ups produce a comparison table instead of collapsing to one shape', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm_generic',
    serviceName: '',
    extractedInputs: {
      ocpus: 4,
      memoryGb: 16,
      capacityGb: 200,
      processorVendor: 'intel',
    },
    confidence: 0.8,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const conversation = [
    {
      role: 'user',
      content: 'Compare E4.Flex vs E5.Flex vs A1.Flex for 8 OCPUs 128 GB RAM, 744h, with and without Capacity Reservation',
    },
    {
      role: 'assistant',
      content: 'For the Flex shape comparison, what capacity reservation utilization should I use: for example `1.0`, `0.7`, or `0.5`?',
    },
    { role: 'user', content: '1.0' },
    {
      role: 'assistant',
      content: 'For the non-capacity-reservation side of the comparison, should I use `On demand` pricing?',
    },
  ];

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation,
    userText: 'On demand',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /\| Shape \| On-demand \$\/Mo \| Capacity Reservation \$\/Mo \|/);
  assert.match(reply.message, /\| E4\.FLEX \|/);
  assert.match(reply.message, /\| E5\.FLEX \|/);
  assert.match(reply.message, /\| A1\.FLEX \|/);
  assert.doesNotMatch(reply.message, /API Gateway/i);
});

test('generic intel VM request asks for shape clarification instead of quoting block storage only', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_vm_generic',
    serviceName: '',
    extractedInputs: {
      ocpus: 4,
      memoryGb: 16,
      capacityGb: 200,
      processorVendor: 'intel',
    },
    confidence: 0.8,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Dame el quote para una virtual machine con procesador intel, 4 OCPUs, 16 GB RAM, 200 GB Block Storage',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'clarification');
  assert.match(reply.message, /which oci vm shape/i);
  assert.doesNotMatch(reply.message, /OCI Block Volume/i);
});

test('generic AMD VM request asks for AMD flex shape clarification instead of falling back to unresolved prose', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'explain',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: '',
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.2,
    annualRequested: false,
    normalizedRequest: '',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Dame el quote de una VM AMD con 8 OCPUs, 32 GB RAM y 1 TB de block storage',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'clarification');
  assert.match(reply.message, /amd vm shape/i);
  assert.match(reply.message, /E4\.Flex/);
});

test('generic Arm VM request asks for A1 flex clarification instead of Intel options', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'explain',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: '',
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.2,
    annualRequested: false,
    normalizedRequest: '',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Dame un quote de una virtual machine arm con 2 OCPUs, 12 GB RAM y 100 GB Block Storage',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'clarification');
  assert.match(reply.message, /arm vm shape/i);
  assert.match(reply.message, /A1\.Flex/);
  assert.doesNotMatch(reply.message, /For Intel/i);
});

test('generic intel VM shape follow-up keeps prior sizing and attached block storage', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'E4.Flex',
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Oracle Compute Cloud',
    extractedInputs: {
      ocpus: 4,
      memoryGb: 16,
      capacityGb: 200,
      shapeSeries: 'E4.FLEX',
      processorVendor: 'intel',
    },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: 'E4.Flex',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [
      { role: 'user', content: 'Dame el quote para una virtual machine con procesador intel, 4 OCPUs, 16 GB RAM, 200 GB Block Storage' },
      { role: 'assistant', content: 'Which OCI VM shape should I use for that machine? For Intel, common options are `E4.Flex` or `E5.Flex`. Once you pick the shape, I can combine it with the attached Block Volume sizing.' },
    ],
    userText: 'E4.Flex',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B93113/);
  assert.match(reply.message, /B93114/);
  assert.match(reply.message, /B91961/);
  assert.match(reply.message, /B91962/);
});

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

test('assistant keeps deterministic bundle output even when a base db sub-segment remains unresolved inside a mixed bundle', async () => {
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
  assert.match(reply.message, /B89643/);
  assert.match(reply.message, /B92682/);
  assert.match(reply.message, /Could not deterministically quote segment: Quote Base Database Service Enterprise BYOL 8 OCPUs and 2000 GB storage/);
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

test('deterministic expert summary anchors cost drivers to quoted line items', () => {
  const { buildDeterministicExpertSummary } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    reformulatedRequest: 'Quote Web Application Firewall with 2 instances and 25000000 requests per month',
    serviceFamily: 'security_waf',
    assumptions: [],
    extractedInputs: { wafInstances: 2, requestCount: 25000000 },
  }));

  const summary = buildDeterministicExpertSummary({
    ok: true,
    request: { source: 'Quote Web Application Firewall with 2 instances and 25000000 requests per month' },
    resolution: { label: 'OCI Web Application Firewall' },
    totals: { monthly: 14, annual: 168, currencyCode: 'USD' },
    lineItems: [
      { partNumber: 'B94579', product: 'OCI Web Application Firewall - Instance', monthly: 10 },
      { partNumber: 'B94277', product: 'OCI Web Application Firewall - Requests', monthly: 4 },
    ],
  });

  assert.match(summary, /Monthly total: \$14\.00/);
  assert.match(summary, /B94579/);
  assert.match(summary, /B94277/);
  assert.doesNotMatch(summary, /potential miscalculation|discrepanc/i);
});

test('deterministic expert summary prefers compute and storage perspective for storage-heavy bundles with a load balancer', () => {
  const { buildDeterministicExpertSummary } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    reformulatedRequest: 'Quote File Storage 10 TB and 20 performance units per GB per month plus Object Storage 5 TB per month plus Flexible Load Balancer 100 Mbps',
    assumptions: [],
    extractedInputs: {},
  }));

  const summary = buildDeterministicExpertSummary({
    ok: true,
    request: { source: 'Quote File Storage 10 TB and 20 performance units per GB per month plus Object Storage 5 TB per month plus Flexible Load Balancer 100 Mbps' },
    resolution: { label: 'Composite OCI workload' },
    totals: { monthly: 64649.001, annual: 775788.012, currencyCode: 'USD' },
    lineItems: [
      { partNumber: 'B109546', product: 'File Storage Service - High Performance Mount Target', monthly: 61440 },
      { partNumber: 'B89057', product: 'File Storage - Storage', monthly: 3072 },
      { partNumber: 'B91628', product: 'Object Storage - Storage', monthly: 130.305 },
      { partNumber: 'B93030', product: 'Load Balancer Base', monthly: 0 },
      { partNumber: 'B93031', product: 'Load Balancer Bandwidth', monthly: 6.696 },
    ],
  });

  assert.match(summary, /OCI compute and storage architect/);
});

test('deterministic expert summary prefers operations platform perspective for fleet batch and email delivery bundles', () => {
  const { buildDeterministicExpertSummary } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    reformulatedRequest: 'Quote Fleet Application Management 20 managed resources plus OCI Batch 15 jobs plus Notifications Email Delivery 250000 emails per month',
    assumptions: [],
    extractedInputs: {},
  }));

  const summary = buildDeterministicExpertSummary({
    ok: true,
    request: { source: 'Quote Fleet Application Management 20 managed resources plus OCI Batch 15 jobs plus Notifications Email Delivery 250000 emails per month' },
    resolution: { label: 'Composite OCI workload' },
    totals: { monthly: 4.98, annual: 59.76, currencyCode: 'USD' },
    lineItems: [
      { partNumber: 'B110475', product: 'B110475 - OCI Fleet Application Management Service', monthly: 0 },
      { partNumber: 'B112107', product: 'B112107 - OCI Batch', monthly: 0 },
      { partNumber: 'B90941', product: 'B90941 - Notifications - Email Delivery', monthly: 4.98 },
    ],
  });

  assert.match(summary, /OCI operations and platform services architect/);
  assert.doesNotMatch(summary, /OCI observability architect/);
});

test('deterministic expert summary prefers compute and storage perspective for storage-heavy bundles even when dns and load balancer are present', () => {
  const { buildDeterministicExpertSummary } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    reformulatedRequest: 'Quote File Storage 2 TB and 5 performance units per GB per month plus Object Storage 10 TB per month plus DNS 5000000 queries per month plus Flexible Load Balancer 50 Mbps',
    assumptions: [],
    extractedInputs: {},
  }));

  const summary = buildDeterministicExpertSummary({
    ok: true,
    request: { source: 'Quote File Storage 2 TB and 5 performance units per GB per month plus Object Storage 10 TB per month plus DNS 5000000 queries per month plus Flexible Load Balancer 50 Mbps' },
    resolution: { label: 'Composite OCI workload' },
    totals: { monthly: 3954.491, annual: 47453.892, currencyCode: 'USD' },
    lineItems: [
      { partNumber: 'B89057', product: 'File Storage - Storage', monthly: 614.4 },
      { partNumber: 'B109546', product: 'File Storage Service - High Performance Mount Target', monthly: 3072 },
      { partNumber: 'B91628', product: 'Object Storage - Storage', monthly: 260.61 },
      { partNumber: 'B88525', product: 'Networking - DNS', monthly: 4.25 },
      { partNumber: 'B93031', product: 'Load Balancer Bandwidth', monthly: 3.231 },
    ],
  });

  assert.match(summary, /OCI compute and storage architect/);
  assert.doesNotMatch(summary, /OCI networking and security architect/);
});

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
