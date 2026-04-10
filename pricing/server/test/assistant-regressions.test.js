'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const assistantPath = path.join(ROOT, 'assistant.js');
const intentPath = path.join(ROOT, 'intent-extractor.js');
const genaiPath = path.join(ROOT, 'genai.js');
const { normalizeCatalog } = require(path.join(ROOT, 'catalog.js'));

function loadAssistantWithStubs(intentResolver, options = {}) {
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
      buildSessionContextBlock: () => '',
    },
  };

  require.cache[genaiPath] = {
    id: genaiPath,
    filename: genaiPath,
    loaded: true,
    exports: {
      runChat: async () => {
        if (options.throwGenAI) throw new Error('genai unavailable');
        return { data: { ...(options.genaiData || {}), text: options.genaiText || '' } };
      },
      extractChatText: (payload) => String(payload?.text || ''),
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
  currencyCodeLocalizations,
}) {
  return {
    partNumber,
    displayName,
    serviceCategoryDisplayName,
    metricId,
    pricetype,
    currencyCodeLocalizations: Array.isArray(currencyCodeLocalizations) && currencyCodeLocalizations.length
      ? currencyCodeLocalizations
      : [
        {
          currencyCode: 'USD',
          prices: usdPrices,
        },
      ],
  };
}

function assertWithin(actual, expected, tolerance = 0.05) {
  assert.ok(Math.abs(Number(actual) - Number(expected)) <= tolerance, `${actual} was not within ${tolerance} of ${expected}`);
}

function buildIndex() {
  return normalizeCatalog({
    'metrics.json': {
      items: [
        metric('m-port-hour', 'Port Hour'),
        metric('m-msg-hour', '5K Messages Per Hour'),
        metric('m-ocpu-hour', 'OCPU Per Hour'),
        metric('m-gpu-hour', 'GPU Per Hour'),
        metric('m-gb-hour', 'Gigabyte RAM Per Hour'),
        metric('m-capacity-month', 'Gigabyte Storage Capacity Per Month'),
        metric('m-performance-month', 'Performance Units Per Gigabyte Per Month'),
        metric('m-queries-million', '1,000,000 Queries'),
        metric('m-api-calls-million', '1,000,000 API Calls'),
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
          partNumber: 'B95909',
          displayName: 'OCI - Compute - GPU - A10',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(1.8)],
        }),
        product({
          partNumber: 'B95910',
          displayName: 'OCI - Compute - GPU - A100 - v2',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(2.4)],
        }),
        product({
          partNumber: 'B95911',
          displayName: 'OCI - Compute - GPU - E3',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(1.2)],
        }),
        product({
          partNumber: 'B95912',
          displayName: 'OCI - Compute - GPU - B200',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(6.2)],
        }),
        product({
          partNumber: 'B95913',
          displayName: 'OCI - Compute - GPU - GB200',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(7.1)],
        }),
        product({
          partNumber: 'B90398',
          displayName: 'OCI - Compute - HPC - X7',
          serviceCategoryDisplayName: 'Compute - HPC',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.3)],
        }),
        product({
          partNumber: 'B91130',
          displayName: 'Big Data Service - Compute - HPC',
          serviceCategoryDisplayName: 'Compute - HPC',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.33)],
        }),
        product({
          partNumber: 'B96531',
          displayName: 'OCI - Compute - HPC - E5',
          serviceCategoryDisplayName: 'Compute - HPC',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.27)],
        }),
        product({
          partNumber: 'B91120',
          displayName: 'Compute - Virtual Machine Standard - B1',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.02)],
        }),
        product({
          partNumber: 'B90425',
          displayName: 'Compute - Standard - E2',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.031)],
        }),
        product({
          partNumber: 'B88318',
          displayName: 'OCI Compute - Windows OS',
          serviceCategoryDisplayName: 'Compute - Guest OS',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.046)],
        }),
        product({
          partNumber: 'B87674',
          displayName: 'OCI Compute - Windows OS - Metered',
          serviceCategoryDisplayName: 'Compute - Guest OS',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.052)],
        }),
        product({
          partNumber: 'B91372',
          displayName: 'OCI Compute - Microsoft SQL Enterprise',
          serviceCategoryDisplayName: 'Compute - Marketplace OS',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.31)],
        }),
        product({
          partNumber: 'B91373',
          displayName: 'OCI Compute - Microsoft SQL Standard',
          serviceCategoryDisplayName: 'Compute - Marketplace OS',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.14)],
        }),
        product({
          partNumber: 'B91444',
          displayName: 'Compute - Virtual Machine Standard - E2 Micro - Free',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0)],
        }),
        product({
          partNumber: 'B110965',
          displayName: 'Oracle Compute Cloud@Customer - Compute - GPU.L40S',
          serviceCategoryDisplayName: 'Compute Cloud@Customer',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(3.5)],
        }),
        product({
          partNumber: 'B111454',
          displayName: 'Oracle Compute Cloud@Customer - Compute - GPU.L40S - Resource Commit',
          serviceCategoryDisplayName: 'Compute Cloud@Customer',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(0.6)],
        }),
        product({
          partNumber: 'B88511',
          displayName: 'Compute - Virtual Machine Standard - X5',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.045)],
        }),
        product({
          partNumber: 'B89133',
          displayName: 'Compute - Virtual Machine Standard - X5 - Metered',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.05)],
        }),
        product({
          partNumber: 'B89135',
          displayName: 'Compute - Virtual Machine Standard - X7 - Metered',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.055)],
        }),
        product({
          partNumber: 'B88515',
          displayName: 'Compute - Virtual Machine Dense I/O - X7',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.08)],
        }),
        product({
          partNumber: 'B89134',
          displayName: 'Compute - Virtual Machine Dense I/O - X5 - Metered',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.07)],
        }),
        product({
          partNumber: 'B89136',
          displayName: 'Compute - Virtual Machine Dense I/O - X7 - Metered',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.065)],
        }),
        product({
          partNumber: 'B89141',
          displayName: 'Compute - Bare Metal GPU Standard - X7 - Metered',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(3.2)],
        }),
        product({
          partNumber: 'B89137',
          displayName: 'Compute - Bare Metal Standard - X7 - Metered',
          serviceCategoryDisplayName: 'Compute - Bare Metal',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.075)],
        }),
        product({
          partNumber: 'B89139',
          displayName: 'Compute - Bare Metal Dense I/O - X7 - Metered',
          serviceCategoryDisplayName: 'Compute - Bare Metal',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.086)],
        }),
        product({
          partNumber: 'B88517',
          displayName: 'Compute - Bare Metal GPU Standard - X7',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(2.9)],
        }),
        product({
          partNumber: 'B88518',
          displayName: 'Compute - Virtual Machine GPU Standard - X7',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(2.7)],
        }),
        product({
          partNumber: 'B89734',
          displayName: 'Compute - GPU Standard - V2',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(2.2)],
        }),
        product({
          partNumber: 'B89735',
          displayName: 'Compute - GPU Standard - V2 - Metered',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(2.4)],
        }),
        product({
          partNumber: 'B98415',
          displayName: 'OCI - Compute - GPU - H100',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(4.8)],
        }),
        product({
          partNumber: 'B98416',
          displayName: 'OCI - Compute - GPU - L40S',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(3.6)],
        }),
        product({
          partNumber: 'B98417',
          displayName: 'OCI - Compute - GPU - H200',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(5.4)],
        }),
        product({
          partNumber: 'B98418',
          displayName: 'OCI - Compute - GPU - MI300X',
          serviceCategoryDisplayName: 'Compute - GPU',
          metricId: 'm-gpu-hour',
          usdPrices: [payg(4.2)],
        }),
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
          partNumber: 'B92072',
          displayName: 'API Gateway - 1,000,000 API Calls',
          serviceCategoryDisplayName: 'Application Development - API Management',
          metricId: 'm-api-calls-million',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(3)],
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
          partNumber: 'B92598',
          displayName: 'OCI Data Integration - Workspace Workspace',
          serviceCategoryDisplayName: 'Data Integration',
          metricId: 'm-port-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.16)],
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
          partNumber: 'B93004',
          displayName: 'OCI Notifications - SMS Outbound - Country Zone 1',
          serviceCategoryDisplayName: 'Notifications - SMS Delivery',
          metricId: 'm-sms-each',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(0.015)],
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
          partNumber: 'B108078',
          displayName: 'OCI Generative AI - Small Cohere',
          serviceCategoryDisplayName: 'OCI Generative AI - Small Cohere',
          metricId: 'm-transactions-ten-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0009)],
        }),
        product({
          partNumber: 'B108079',
          displayName: 'OCI Generative AI - Embed Cohere',
          serviceCategoryDisplayName: 'OCI Generative AI - Embed Cohere',
          metricId: 'm-transactions-ten-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(0.001)],
        }),
        product({
          partNumber: 'B108080',
          displayName: 'OCI Generative AI - Large Meta',
          serviceCategoryDisplayName: 'OCI Generative AI - Large Meta',
          metricId: 'm-transactions-ten-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0018)],
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
          partNumber: 'B94973',
          displayName: 'Vision - Image Analysis',
          serviceCategoryDisplayName: 'Oracle Cloud Infrastructure - Vision',
          metricId: 'm-transactions-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(0.25)],
        }),
        product({
          partNumber: 'B94974',
          displayName: 'Vision - OCR',
          serviceCategoryDisplayName: 'Oracle Cloud Infrastructure - Vision',
          metricId: 'm-transactions-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(1)],
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
          partNumber: 'B111539',
          displayName: 'OCI - Vision - Stream Video Analysis',
          serviceCategoryDisplayName: 'OCI - Vision - Stream Video Analysis',
          metricId: 'm-processed-video-minute',
          pricetype: 'MONTH',
          usdPrices: [payg(0.15)],
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
          partNumber: 'B110462',
          displayName: 'OCI Generative AI Agents - Knowledge Base Storage',
          serviceCategoryDisplayName: 'OCI Generative AI Agents',
          metricId: 'm-storage-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.0084)],
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
          partNumber: 'B91627',
          displayName: 'Oracle Cloud Infrastructure - Object Storage Requests',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-requests-thousand-plain',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(0.0034)],
        }),
        product({
          partNumber: 'B91633',
          displayName: 'Archive Storage',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(0.0026)],
        }),
        product({
          partNumber: 'B93000',
          displayName: 'Infrequent Access Storage',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(0.01)],
        }),
        product({
          partNumber: 'B93001',
          displayName: 'Infrequent Access Retrieval',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0), payg(0.01)],
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
          partNumber: 'B94173',
          displayName: 'Oracle Threat Intelligence Service',
          serviceCategoryDisplayName: 'Security - Threat Intelligence',
          metricId: 'm-each',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(0)],
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
          partNumber: 'B94176',
          displayName: 'Compute - Standard - X9 - OCPU',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          currencyCodeLocalizations: [
            { currencyCode: 'USD', prices: [payg(0.04)] },
            { currencyCode: 'MXN', prices: [payg(0.68)] },
          ],
        }),
        product({
          partNumber: 'B94177',
          displayName: 'Compute - Standard - X9 - Memory',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-gb-hour',
          currencyCodeLocalizations: [
            { currencyCode: 'USD', prices: [payg(0.0015)] },
            { currencyCode: 'MXN', prices: [payg(0.0255)] },
          ],
        }),
        product({
          partNumber: 'B93311',
          displayName: 'Compute - Optimized - X9 - OCPU',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.054)],
        }),
        product({
          partNumber: 'B93312',
          displayName: 'Compute - Optimized - X9 - Memory',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-gb-hour',
          usdPrices: [payg(0.0015)],
        }),
        product({
          partNumber: 'B88514',
          displayName: 'Compute - Virtual Machine Standard - X7',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.0638)],
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
          partNumber: 'B93121',
          displayName: 'Compute - Dense I/O - E4 - OCPU',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.025)],
        }),
        product({
          partNumber: 'B93122',
          displayName: 'Compute - Dense I/O - E4 - Memory',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-gb-hour',
          usdPrices: [payg(0.005)],
        }),
        product({
          partNumber: 'B93123',
          displayName: 'Compute - Dense I/O - E4 - NVMe',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-capacity-month',
          pricetype: 'HOUR',
          usdPrices: [payg(0.0612)],
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
        product({
          partNumber: 'B109529',
          displayName: 'Compute - Standard - A2 OCPU',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.014)],
        }),
        product({
          partNumber: 'B109530',
          displayName: 'Compute - Standard - A2 Memory',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-gb-hour',
          usdPrices: [payg(0.002)],
        }),
        product({
          partNumber: 'B112145',
          displayName: 'OCI - Compute - Standard - A4 - OCPU',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.02)],
        }),
        product({
          partNumber: 'B112146',
          displayName: 'OCI - Compute - Standard - A4 - Memory',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-gb-hour',
          usdPrices: [payg(0.002)],
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

test('general VM shape options question returns discovery guidance instead of a quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
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
  }), {
    genaiText: [
      'Sí. En `OCI VM Instances` las familias principales disponibles son:',
      '- `Intel x86`: `VM.Standard3.Flex`, `VM.Optimized3.Flex`, y la línea fija `VM.Standard2.x`.',
      '- `AMD x86`: `VM.Standard.E3.Flex`, `VM.Standard.E4.Flex`, `VM.Standard.E5.Flex`, `VM.Standard.E6.Flex`, y `VM.DenseIO.E4/E5.Flex`.',
      '- `Ampere Arm`: `VM.Standard.A1.Flex`, `VM.Standard.A2.Flex` y `VM.Standard.A4.Flex`.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Que opciones de Shape tenemos en Virtual Machines?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.match(reply.message, /VM\.Standard3\.Flex/i);
  assert.match(reply.message, /VM\.Standard\.E4\.Flex/i);
  assert.match(reply.message, /VM\.Standard\.A1\.Flex/i);
  assert.doesNotMatch(reply.message, /I prepared a deterministic OCI quotation/i);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.topic, 'vm_shapes');
});

test('vm shape comparison question uses product discovery with structured shape comparison context', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.92,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para un contexto general:',
      '- `VM.Standard3.Flex` es `Intel x86` general purpose.',
      '- `VM.Standard.E4.Flex` es `AMD x86` general purpose.',
      '- Ambas son `Flex`, así que aceptan `OCPU` y `memoria` definidos por el usuario.',
      '- En ambas familias `x86`, `1 OCPU = 2 vCPUs`.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Que diferencia hay entre VM.Standard3.Flex y VM.Standard.E4.Flex?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.topic, 'vm_shapes');
  assert.ok(Array.isArray(reply.sessionContext.lastContextPack.shapeComparison));
});

test('pricing model question for WAF uses product discovery with structured pricing dimensions', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
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
  }), {
    genaiText: [
      'En `OCI Web Application Firewall` el cobro principal se divide en dos dimensiones:',
      '- cargo fijo por instancia o policy',
      '- cargo variable por volumen de requests',
      'Para cotizar con precisión, normalmente necesitas cantidad de instancias y requests mensuales.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Como se cobra Web Application Firewall en OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'security_waf');
  assert.ok(Array.isArray(reply.sessionContext.lastContextPack.registryMatchNames));
  assert.match(reply.message, /instancia|policy|requests/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for DNS uses product discovery with structured pricing dimensions', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'DNS',
    extractedInputs: {},
    confidence: 0.92,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI DNS` el cobro se basa principalmente en el volumen de queries procesadas.',
      '- la dimension de cobro es queries por mes',
      '- para cotizar con precision, normalmente necesitas queries mensuales esperadas',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Como se cobra DNS en OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.ok(reply.sessionContext.lastContextPack.family);
  assert.match(reply.sessionContext.lastContextPack.family.id, /dns/i);
  assert.ok(Array.isArray(reply.sessionContext.lastContextPack.serviceContext?.pricingDimensions || []));
  assert.match(reply.message, /dns|queries/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for API Gateway uses product discovery with structured pricing dimensions', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'apigw',
    serviceName: 'API Gateway',
    extractedInputs: {},
    confidence: 0.92,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI API Gateway` el cobro principal se basa en volumen de API calls.',
      '- la unidad de cobro es bloques de llamadas API',
      '- para cotizar con precision, normalmente necesitas llamadas mensuales esperadas',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is API Gateway billed in OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.ok(reply.sessionContext.lastContextPack.family);
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'apigw');
  assert.ok(Array.isArray(reply.sessionContext.lastContextPack.serviceContext?.pricingDimensions || []));
  assert.match(reply.message, /api gateway|api calls/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Health Checks uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'edge_health_checks',
    serviceName: 'Health Checks',
    extractedInputs: {},
    confidence: 0.92,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Health Checks` el cobro se basa principalmente en la cantidad de endpoints monitoreados.',
      '- la unidad de cobro es endpoints por mes',
      '- para cotizar con precisión normalmente necesito el número de endpoints',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Health Checks billed in OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'edge_health_checks');
  assert.match(reply.message, /endpoints?/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('options discovery for Network Firewall uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_firewall',
    serviceName: 'Network Firewall',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Network Firewall` normalmente evaluas dos dimensiones principales:',
      '- instancias de firewall',
      '- data processed mensual',
      'Para cotizar, el sizing tipico pide cantidad de firewalls y GB procesados por mes.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What options do we have for Network Firewall in OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'network_firewall');
  assert.match(reply.message, /network firewall|instances|data processed|gb/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('licensing discovery question for Base Database uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Base Database Service`, la diferencia principal es el modelo de licenciamiento:',
      '- `BYOL`: reutilizas licencias Oracle elegibles que ya posees.',
      '- `License Included`: el precio del servicio incorpora la licencia correspondiente.',
      'Para una cotización exacta, además necesitas edición, OCPUs o ECPUs, y storage.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What is the difference between BYOL and License Included for Base Database Service?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'database_base_db');
  assert.match(reply.message, /BYOL/i);
  assert.match(reply.message, /License Included/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Object Storage uses product discovery with structured pricing dimensions', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'storage_object',
    serviceName: 'OCI Object Storage',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Object Storage` el cobro principal se basa en capacidad almacenada.',
      '- la dimensión principal es `GB-month` de storage',
      '- para una cotización básica normalmente basta con la capacidad mensual esperada',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Como se cobra Object Storage en OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'storage_object');
  assert.match(reply.message, /GB-month|capacidad/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for File Storage uses product discovery with structured pricing dimensions', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'storage_file',
    serviceName: 'OCI File Storage',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI File Storage` normalmente verás dos dimensiones relevantes:',
      '- capacidad provisionada en `GB-month`',
      '- performance units por `GB-month` cuando eliges un nivel de desempeño que las usa',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI File Storage billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'storage_file');
  assert.match(reply.message, /GB-month|performance units/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Load Balancer uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_load_balancer',
    serviceName: 'OCI Load Balancer',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Load Balancer` normalmente verás dos dimensiones de cobro:',
      '- capacidad base por hora',
      '- bandwidth en `Mbps-hour` para el throughput configurado',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Load Balancer billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'network_load_balancer');
  assert.match(reply.message, /bandwidth|Mbps-hour|capacidad base/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('sku composition question for Flexible Load Balancer stays in product discovery even if intent arrives as quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_load_balancer',
    serviceName: 'OCI Load Balancer',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para una quote de `Flexible Load Balancer` normalmente debes validar dos SKU principales:',
      '- capacidad base del load balancer',
      '- bandwidth configurado en `Mbps-hour`',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: "Cuales son los SKU's requeridos en una quote de Flexible Load Balancer?",
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'network_load_balancer');
  assert.match(reply.message, /bandwidth|capacidad base|SKU/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('options question for FastConnect uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_fastconnect',
    serviceName: 'OCI FastConnect',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI FastConnect` las opciones comunes se diferencian principalmente por ancho de banda.',
      '- variantes comunes: `1 Gbps`, `10 Gbps` y `100 Gbps`',
      '- la dimensión principal es el puerto por hora asociado al ancho de banda elegido',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What FastConnect options do we have?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'network_fastconnect');
  assert.match(reply.message, /1 Gbps|10 Gbps|100 Gbps/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Block Volume uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'storage_block',
    serviceName: 'OCI Block Volume',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Block Volume` normalmente verás dos dimensiones de cobro:',
      '- storage capacity en `GB-month`',
      '- `VPU per GB` cuando eliges niveles de desempeño que usan performance units',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Block Volume billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'storage_block');
  assert.match(reply.message, /GB-month|VPU per GB|performance units/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for OCI Functions uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'serverless_functions',
    serviceName: 'OCI Functions',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Functions` el cobro suele combinar varias dimensiones:',
      '- invocations mensuales',
      '- tiempo de ejecución por invocation',
      '- memoria asignada por invocation',
      '- y, si aplica, unidades de provisioned concurrency',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Functions billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'serverless_functions');
  assert.match(reply.message, /invocations|execution|memoria|memory|concurrency/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('prerequisite discovery for OCI Data Integration uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'integration_data',
    serviceName: 'OCI Data Integration',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para cotizar `OCI Data Integration` normalmente necesito saber:',
      '- si quieres `workspace usage`',
      '- si quieres `data processed`',
      '- la cantidad de workspaces o los GB procesados por hora',
      '- y las horas de ejecución mensuales si aplica',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What information do I need to quote OCI Data Integration?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'integration_data');
  assert.match(reply.message, /workspace|data processed|hours/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Data Safe on-prem uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_data_safe',
    serviceName: 'OCI Data Safe',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Data Safe` el cobro depende del alcance del servicio:',
      '- `Database Cloud Service` tiene su propia ruta',
      '- `On-Premises Databases` se mide por cantidad de target databases',
      'Para una cotización exacta necesito el tipo de despliegue y el número de databases objetivo.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Data Safe for On-Premises Databases billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'security_data_safe');
  assert.match(reply.message, /target databases|database cloud service|on-premises/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for OCI Monitoring uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
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
  }), {
    genaiText: [
      'En `OCI Monitoring` normalmente evalúas dos dimensiones:',
      '- `ingestion` de datapoints',
      '- `retrieval` de datapoints',
      'Para una cotización exacta necesito el volumen esperado de datapoints en la variante que quieras usar.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Monitoring billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'observability_monitoring');
  assert.match(reply.message, /ingestion|retrieval|datapoints/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Notifications HTTPS Delivery uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_notifications_https',
    serviceName: 'Notifications HTTPS Delivery',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `Notifications HTTPS Delivery` el cobro principal se basa en operaciones de entrega.',
      '- la unidad operativa es delivery operations',
      '- para una cotización exacta necesito el volumen mensual esperado',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Notifications HTTPS Delivery billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'observability_notifications_https');
  assert.match(reply.message, /delivery operations|https delivery/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Email Delivery uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'operations_email_delivery',
    serviceName: 'Email Delivery',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `Notifications Email Delivery` el cobro principal se basa en volumen de emails enviados.',
      '- la métrica operativa es emails por mes',
      '- para una cotización exacta necesito el volumen mensual esperado',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Email Delivery billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'operations_email_delivery');
  assert.match(reply.message, /emails per month|email delivery/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for IAM SMS uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'operations_iam_sms',
    serviceName: 'IAM SMS',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI IAM SMS` el cobro se basa en mensajes enviados.',
      '- la métrica operativa es messages',
      '- para una cotización exacta necesito la cantidad de mensajes del periodo',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is IAM SMS billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'operations_iam_sms');
  assert.match(reply.message, /messages|iam sms/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Oracle Threat Intelligence Service uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_threat_intelligence',
    serviceName: 'Oracle Threat Intelligence Service',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `Oracle Threat Intelligence Service` el cobro se basa en volumen de llamadas API.',
      '- la métrica operativa es API calls',
      '- para cotizar necesito el volumen esperado en el periodo',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Oracle Threat Intelligence Service billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'security_threat_intelligence');
  assert.match(reply.message, /api calls|threat intelligence/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Vector Store Retrieval uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ai_vector_store_retrieval',
    serviceName: 'Vector Store Retrieval',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Generative AI Vector Store Retrieval` el cobro se basa en requests.',
      '- la métrica operativa es requests',
      '- para cotizar necesito el volumen esperado en el periodo',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Generative AI Vector Store Retrieval billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'ai_vector_store_retrieval');
  assert.match(reply.message, /requests|vector store/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model questions for archive, infrequent access, AI variants, vision, and notifications SMS use structured family context instead of quote', async () => {
  const index = buildIndex();
  const cases = [
    ['How is Archive Storage billed?', 'storage_archive', 'Archive Storage', /archive|storage capacity/i, 'En `Archive Storage` el cobro se basa en storage capacity (GB) por mes.'],
    ['How is Infrequent Access Storage billed?', 'storage_infrequent_access', 'Infrequent Access Storage', /infrequent access|retrieval/i, 'En `Infrequent Access Storage` el cobro se basa en storage capacity (GB) y retrieval cuando aplica.'],
    ['How is OCI Generative AI Small Cohere billed?', 'ai_small_cohere', 'OCI Generative AI Small Cohere', /small cohere|transactions/i, 'En `OCI Generative AI Small Cohere` el cobro se basa en transactions.'],
    ['How is OCI Generative AI Embed Cohere billed?', 'ai_embed_cohere', 'OCI Generative AI Embed Cohere', /embed cohere|transactions/i, 'En `OCI Generative AI Embed Cohere` el cobro se basa en transactions.'],
    ['How is OCI Generative AI Large Meta billed?', 'ai_large_meta', 'OCI Generative AI Large Meta', /large meta|transactions/i, 'En `OCI Generative AI Large Meta` el cobro se basa en transactions.'],
    ['How is OCI Vision Image Analysis billed?', 'ai_vision_image_analysis', 'OCI Vision Image Analysis', /image analysis|transactions/i, 'En `OCI Vision Image Analysis` el cobro se basa en transactions.'],
    ['How is OCI Vision OCR billed?', 'ai_vision_ocr', 'OCI Vision OCR', /vision ocr|transactions/i, 'En `OCI Vision OCR` el cobro se basa en transactions.'],
    ['How is OCI Vision Stream Video Analysis billed?', 'ai_vision_stream_video_analysis', 'OCI Vision Stream Video Analysis', /stream video analysis|processed video/i, 'En `OCI Vision Stream Video Analysis` el cobro se basa en processed video minutes.'],
    ['How is OCI Notifications SMS billed?', 'operations_notifications_sms', 'OCI Notifications SMS', /notifications sms|messages/i, 'En `OCI Notifications SMS` el cobro se basa en messages.'],
  ];

  for (const [userText, serviceFamily, serviceName, expected, genaiText] of cases) {
    const { respondToAssistant } = loadAssistantWithStubs((text) => ({
      route: 'product_discovery',
      intent: 'discover',
      shouldQuote: false,
      needsClarification: false,
      clarificationQuestion: '',
      reformulatedRequest: text,
      assumptions: [],
      serviceFamily,
      serviceName,
      extractedInputs: {},
      confidence: 0.9,
      annualRequested: false,
      normalizedRequest: text,
    }), { genaiText });

    const reply = await respondToAssistant({
      cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
      index,
      conversation: [],
      userText,
    });

    assert.equal(reply.ok, true);
    assert.equal(reply.mode, 'answer');
    assert.equal(reply.intent.shouldQuote, false);
    assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
    assert.equal(reply.sessionContext.lastContextPack.family.id, serviceFamily);
    assert.match(reply.message, expected);
    assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
  }
});

test('pricing model question for Vision Custom Training uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ai_vision_custom_training',
    serviceName: 'Vision Custom Training',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `Vision Custom Training` el cobro se basa en training hours.',
      '- la métrica operativa es training hours',
      '- para cotizar necesito el número de horas de entrenamiento',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Vision Custom Training billed in OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'ai_vision_custom_training');
  assert.match(reply.message, /training hours|vision/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Fleet Application Management uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ops_fleet_application_management',
    serviceName: 'Fleet Application Management',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Fleet Application Management` el cobro se basa en managed resources.',
      '- la métrica operativa es managed resources por mes',
      '- para cotizar necesito la cantidad de recursos administrados',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Fleet Application Management billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'ops_fleet_application_management');
  assert.match(reply.message, /managed resources|fleet/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model questions for storage, AI variants, vision, and notifications use structured family context instead of quote', async () => {
  const index = buildIndex();
  const cases = [
    {
      userText: 'How is Archive Storage billed?',
      serviceFamily: 'storage_archive',
      serviceName: 'Archive Storage',
      expected: /archive|storage capacity/i,
      genaiText: 'En `Archive Storage` el cobro se basa en storage capacity (GB) por mes.',
    },
    {
      userText: 'How is Infrequent Access Storage billed?',
      serviceFamily: 'storage_infrequent_access',
      serviceName: 'Infrequent Access Storage',
      expected: /infrequent access|storage capacity/i,
      genaiText: 'En `Infrequent Access Storage` el cobro se basa en storage capacity (GB) y retrieval cuando aplica.',
    },
    {
      userText: 'How is OCI Generative AI Small Cohere billed?',
      serviceFamily: 'ai_small_cohere',
      serviceName: 'OCI Generative AI Small Cohere',
      expected: /small cohere|transactions/i,
      genaiText: 'En `OCI Generative AI Small Cohere` el cobro se basa en transactions.',
    },
    {
      userText: 'How is OCI Generative AI Embed Cohere billed?',
      serviceFamily: 'ai_embed_cohere',
      serviceName: 'OCI Generative AI Embed Cohere',
      expected: /embed cohere|transactions/i,
      genaiText: 'En `OCI Generative AI Embed Cohere` el cobro se basa en transactions.',
    },
    {
      userText: 'How is OCI Generative AI Large Meta billed?',
      serviceFamily: 'ai_large_meta',
      serviceName: 'OCI Generative AI Large Meta',
      expected: /large meta|transactions/i,
      genaiText: 'En `OCI Generative AI Large Meta` el cobro se basa en transactions.',
    },
    {
      userText: 'How is OCI Vision Image Analysis billed?',
      serviceFamily: 'ai_vision_image_analysis',
      serviceName: 'OCI Vision Image Analysis',
      expected: /image analysis|transactions/i,
      genaiText: 'En `OCI Vision Image Analysis` el cobro se basa en transactions.',
    },
    {
      userText: 'How is OCI Vision OCR billed?',
      serviceFamily: 'ai_vision_ocr',
      serviceName: 'OCI Vision OCR',
      expected: /vision ocr|transactions/i,
      genaiText: 'En `OCI Vision OCR` el cobro se basa en transactions.',
    },
    {
      userText: 'How is OCI Vision Stream Video Analysis billed?',
      serviceFamily: 'ai_vision_stream_video_analysis',
      serviceName: 'OCI Vision Stream Video Analysis',
      expected: /stream video analysis|processed video/i,
      genaiText: 'En `OCI Vision Stream Video Analysis` el cobro se basa en processed video minutes.',
    },
    {
      userText: 'How is OCI Notifications SMS billed?',
      serviceFamily: 'operations_notifications_sms',
      serviceName: 'OCI Notifications SMS',
      expected: /notifications sms|messages/i,
      genaiText: 'En `OCI Notifications SMS` el cobro se basa en messages.',
    },
  ];

  for (const item of cases) {
    const { respondToAssistant } = loadAssistantWithStubs((text) => ({
      route: 'product_discovery',
      intent: 'discover',
      shouldQuote: false,
      needsClarification: false,
      clarificationQuestion: '',
      reformulatedRequest: text,
      assumptions: [],
      serviceFamily: item.serviceFamily,
      serviceName: item.serviceName,
      extractedInputs: {},
      confidence: 0.9,
      annualRequested: false,
      normalizedRequest: text,
    }), {
      genaiText: item.genaiText,
    });

    const reply = await respondToAssistant({
      cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
      index,
      conversation: [],
      userText: item.userText,
    });

    assert.equal(reply.ok, true);
    assert.equal(reply.mode, 'answer');
    assert.equal(reply.intent.shouldQuote, false);
    assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
    assert.equal(reply.sessionContext.lastContextPack.family.id, item.serviceFamily);
    assert.match(reply.message, item.expected);
    assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
  }
});

test('pricing model question for OCI AI Language uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ai_language',
    serviceName: 'OCI AI Language',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI AI Language` el cobro se basa en transactions.',
      '- la métrica operativa es transactions',
      '- para una cotización exacta necesito el volumen transaccional esperado',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI AI Language billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'ai_language');
  assert.match(reply.message, /transactions|ai language/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('prerequisite discovery for Oracle Integration Cloud Standard uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
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
  }), {
    genaiText: [
      'Para cotizar `Oracle Integration Cloud Standard` normalmente necesito:',
      '- el modelo de licenciamiento: `BYOL` o `License Included`',
      '- la cantidad de instancias',
      '- y, si aplica en tu caso, cualquier aclaración de moneda o periodo',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What information do I need to quote Oracle Integration Cloud Standard?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'integration_oic_standard');
  assert.match(reply.message, /BYOL/i);
  assert.match(reply.message, /License Included/i);
  assert.match(reply.message, /instancias|instances/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Oracle Analytics Cloud Professional uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'analytics_oac_professional',
    serviceName: 'Oracle Analytics Cloud Professional',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `Oracle Analytics Cloud Professional` el modelo depende de cómo lo cotices:',
      '- por `users` cuando eliges named users',
      '- por `OCPU-hour` cuando lo cotizas por capacidad de cómputo',
      'Si lo haces por OCPUs, también importa el modo de licenciamiento.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Oracle Analytics Cloud Professional billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'analytics_oac_professional');
  assert.match(reply.message, /users/i);
  assert.match(reply.message, /OCPU/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Oracle Analytics Cloud Enterprise uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'analytics_oac_enterprise',
    serviceName: 'Oracle Analytics Cloud Enterprise',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `Oracle Analytics Cloud Enterprise` el modelo depende de cómo lo cotices:',
      '- por `users` cuando eliges named users',
      '- por `OCPU-hour` cuando lo cotizas por capacidad',
      '- y para OCPUs sí importa el modo `BYOL` o `License Included`',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Oracle Analytics Cloud Enterprise billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'analytics_oac_enterprise');
  assert.match(reply.message, /users/i);
  assert.match(reply.message, /OCPU/i);
  assert.match(reply.message, /BYOL|License Included/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('prerequisite discovery for Base Database Service uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para cotizar `Base Database Service` normalmente necesito:',
      '- la edición, por ejemplo `Enterprise` o `Standard`',
      '- si será `BYOL` o `License Included`',
      '- la capacidad de cómputo, en `OCPU` o `ECPU` según el caso',
      '- y el storage en GB',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What information do I need to quote Base Database Service?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'database_base_db');
  assert.match(reply.message, /Enterprise|Standard/i);
  assert.match(reply.message, /BYOL|License Included/i);
  assert.match(reply.message, /OCPU|ECPU/i);
  assert.match(reply.message, /storage/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('options discovery for Exadata Dedicated Infrastructure uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_exadata_dedicated',
    serviceName: 'Exadata Dedicated Infrastructure Database',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para `Exadata Dedicated Infrastructure Database`, las opciones principales incluyen:',
      '- `BYOL` o `License Included`',
      '- capacidad en `OCPU` o `ECPU`',
      '- y formas de infraestructura como `Base System`',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Que opciones tenemos para Exadata Dedicated Infrastructure?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'database_exadata_dedicated');
  assert.ok(reply.sessionContext.lastContextPack.family.options.infrastructureShapes.includes('Base System'));
  assert.match(reply.message, /BYOL|License Included/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('required-input question for Health Checks stays in product discovery even when intent arrives as quote_request', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'edge_health_checks',
    serviceName: 'Health Checks',
    extractedInputs: {},
    confidence: 0.78,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'network', useDeterministicEngine: true },
  }), {
    genaiText: [
      'Para cotizar `OCI Health Checks` normalmente necesito:',
      '- cantidad de `endpoints`',
      '- confirmar si buscas guidance o una cotización directa',
      'El cobro principal se basa en endpoints monitoreados.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What inputs do I need before quoting Health Checks in OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'edge_health_checks');
  assert.match(reply.message, /Health Checks|endpoints/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('required-input question for Base Database stays in product discovery even when intent arrives as quote_request', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.79,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'database', useDeterministicEngine: true },
  }), {
    genaiText: [
      'Para cotizar `Base Database Service` normalmente necesito:',
      '- edición, por ejemplo `Enterprise` o `Standard`',
      '- `BYOL` o `License Included`',
      '- capacidad en `OCPU` o `ECPU`',
      '- `storage` en GB',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What inputs do I need before quoting Base Database Service?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'database_base_db');
  assert.match(reply.message, /Enterprise|Standard/i);
  assert.match(reply.message, /BYOL|License Included/i);
  assert.match(reply.message, /OCPU|ECPU/i);
  assert.match(reply.message, /storage/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('active quote conceptual compute composition question answers instead of mutating the quote', async () => {
  const index = buildIndex();
  const activeQuoteSource = 'Quote VM.Standard.E4.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs';
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_followup',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Virtual Machine Flex',
    extractedInputs: { ocpus: 4, memoryGb: 16, storageGb: 200, vpuPerGb: 20 },
    confidence: 0.74,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'modify_quote', targetType: 'quote', domain: 'compute', useDeterministicEngine: true },
  }), {
    genaiText: [
      'For a `Virtual Machine Flex` quote, the main components are usually:',
      '- `OCPUs` for compute',
      '- `memory` in GB when the shape is flexible',
      '- optional `Block Storage` and its `VPU` performance level when attached',
      'So no, it is not usually just OCPU unless you intentionally exclude storage and memory from the request.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Only OCPU, no disk, no memory?',
    sessionContext: {
      lastQuote: {
        source: activeQuoteSource,
        label: 'Virtual Machine Flex',
        serviceFamily: 'compute_flex',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'compute_flex');
  assert.equal(reply.sessionContext.lastQuote.source, activeQuoteSource);
  assert.match(reply.message, /OCPU|memory|Block Storage|VPU/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('active quote SKU requirement question answers instead of mutating the quote', async () => {
  const index = buildIndex();
  const activeQuoteSource = 'Quote VM.Standard.E4.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs';
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_followup',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Virtual Machine Flex',
    extractedInputs: { ocpus: 4, memoryGb: 16, storageGb: 200, vpuPerGb: 20 },
    confidence: 0.76,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'modify_quote', targetType: 'quote', domain: 'compute', useDeterministicEngine: true },
  }), {
    genaiText: [
      'To quote a `Virtual Machine Flex` stack you normally need the compute and attached component SKUs separated by billing dimension:',
      '- compute `OCPU` SKU',
      '- memory `GB-hour` SKU for Flex memory',
      '- optional `Block Storage` capacity SKU',
      '- optional `VPU` performance SKU',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Which SKUs are required to quote a Virtual Machine instance and its components?',
    sessionContext: {
      lastQuote: {
        source: activeQuoteSource,
        label: 'Virtual Machine Flex',
        serviceFamily: 'compute_flex',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'compute_flex');
  assert.equal(reply.sessionContext.lastQuote.source, activeQuoteSource);
  assert.match(reply.message, /SKU|OCPU|memory|Block Storage|VPU/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('billing question for Health Checks with explicit endpoint count stays in discovery instead of being top-service quoted', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 12 },
    confidence: 0.77,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'network', useDeterministicEngine: true },
  }), {
    genaiText: [
      'For `OCI Health Checks`, the main billing dimension is the number of monitored `endpoints` per month.',
      '- with `12 endpoints`, the quantity informs the explanation',
      '- but this is still a pricing-model answer, not a deterministic quote request by itself',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Health Checks billed for 12 endpoints?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'edge_health_checks');
  assert.match(reply.message, /Health Checks|endpoints/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing-dimensions explanation for FastConnect with explicit bandwidth stays in discovery instead of being top-service quoted', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { bandwidthGbps: 10 },
    confidence: 0.78,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'network', useDeterministicEngine: true },
  }), {
    genaiText: [
      'For `OCI FastConnect`, the main billing unit is the selected port bandwidth per hour.',
      '- `10 Gbps` is one of the standard bandwidth options',
      '- this prompt is asking for pricing dimensions, not for a deterministic quote output',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Explain OCI FastConnect pricing dimensions for 10 Gbps.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'network_fastconnect');
  assert.match(reply.message, /FastConnect|10 Gbps|bandwidth/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('explicit GPU compute quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - A10 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B95909');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 2678.4, 0.001);
});

test('explicit GPU A100 v2 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - A100 - v2 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B95910');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 3571.2, 0.001);
});

test('explicit GPU E3 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - E3 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B95911');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 1785.6, 0.001);
});

test('explicit GPU B200 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - B200 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B95912');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 9225.6, 0.001);
});

test('explicit GPU GB200 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - GB200 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B95913');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 10564.8, 0.001);
});

test('explicit Big Data Service HPC quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 16 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Big Data Service - Compute - HPC with 16 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B91130');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 16);
  assertWithin(reply.quote?.totals?.monthly, 3928.32, 0.001);
});

test('HPC compute quote with node wording still resolves deterministically through the matched OCPU SKU', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute HPC - X7 with 2 nodes for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /not available yet/i);
  assert.match(reply.message, /OCI Compute HPC - X7/i);
});

test('explicit HPC compute quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 52 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute HPC - X7 with 52 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B90398');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 52);
  assertWithin(reply.quote?.totals?.monthly, 11606.4, 0.001);
});

test('explicit HPC E5 compute quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 40 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute HPC - E5 with 40 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B96531');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 40);
  assertWithin(reply.quote?.totals?.monthly, 8035.2, 0.001);
});

test('explicit bare metal GPU metered quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Bare Metal GPU Standard - X7 - Metered with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89141');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 4761.6, 0.001);
});

test('explicit bare metal standard x7 metered quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 52 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Bare Metal Standard - X7 - Metered with 52 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89137');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 52);
  assertWithin(reply.quote?.totals?.monthly, 2901.6, 0.001);
});

test('explicit bare metal dense i/o x7 metered quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 52 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Bare Metal Dense I/O - X7 - Metered with 52 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89139');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 52);
  assertWithin(reply.quote?.totals?.monthly, 3327.168, 0.001);
});

test('explicit vm standard x7 metered quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Standard - X7 - Metered with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89135');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 327.36, 0.001);
});

test('explicit vm standard x5 quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Standard - X5 with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B88511');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 267.84, 0.001);
});

test('explicit vm standard B1 quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 4 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Standard - B1 with 4 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B91120');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 4);
  assertWithin(reply.quote?.totals?.monthly, 59.52, 0.001);
});

test('explicit standard E2 quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Standard - E2 with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B90425');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 184.512, 0.001);
});

test('explicit vm standard x5 metered quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Standard - X5 - Metered with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89133');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 297.6, 0.001);
});

test('explicit vm dense i/o x7 metered quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Dense I/O - X7 - Metered with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89136');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 386.88, 0.001);
});

test('explicit vm dense i/o x7 quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Dense I/O - X7 with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B88515');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 476.16, 0.001);
});

test('explicit vm dense i/o x5 metered quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { ocpus: 8 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine Dense I/O - X5 - Metered with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89134');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 8);
  assertWithin(reply.quote?.totals?.monthly, 416.64, 0.001);
});

test('explicit bare metal GPU quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Bare Metal GPU Standard - X7 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B88517');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 4315.2, 0.001);
});

test('explicit vm gpu standard x7 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Compute - Virtual Machine GPU Standard - X7 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B88518');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 4017.6, 0.001);
});

test('explicit GPU Standard V2 metered quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote GPU Standard - V2 - Metered with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89735');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 3571.2, 0.001);
});

test('explicit GPU Standard V2 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote GPU Standard - V2 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B89734');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 3273.6, 0.001);
});

test('explicit GPU H100 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - H100 with 4 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B98415');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 4);
  assertWithin(reply.quote?.totals?.monthly, 14284.8, 0.001);
});

test('explicit GPU L40S quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - L40S with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B98416');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 5356.8, 0.001);
});

test('explicit GPU H200 quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - H200 with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B98417');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 8035.2, 0.001);
});

test('explicit GPU MI300X quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 2 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute GPU - MI300X with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B98418');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 2);
  assertWithin(reply.quote?.totals?.monthly, 6249.6, 0.001);
});

test('legacy fixed VM alias quote resolves to the mapped fixed-shape SKU when deterministic coverage exists', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote VM.Standard1.4 for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /not available yet/i);
  assert.match(reply.message, /Virtual Machine Standard - X5/i);
});

test('legacy DenseIO VM alias quote resolves to the mapped fixed-shape SKU when deterministic coverage exists', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote VM.DenseIO2.8 for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /not available yet/i);
  assert.match(reply.message, /Virtual Machine Dense I\/O - X7/i);
});

test('metered legacy DenseIO VM alias quote resolves to the mapped metered SKU when deterministic coverage exists', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote VM.DenseIO2.8 metered for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /not available yet/i);
  assert.match(reply.message, /Virtual Machine Dense I\/O - X7 \(Metered\)/i);
  assert.match(reply.message, /VM\.DenseIO\.E4\.Flex/i);
});

test('explicit E2 micro quote with OCPU units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote VM.Standard.E2.1.Micro with 1 OCPU for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.equal(reply.quote?.ok, true);
  assert.equal(reply.quote?.lineItems?.[0]?.partNumber, 'B91444');
  assert.equal(reply.quote?.lineItems?.[0]?.quantity, 1);
  assertWithin(reply.quote?.totals?.monthly, 0, 0.001);
  assert.doesNotMatch(reply.message, /Full Stack Disaster Recovery/i);
});

test('unsupported Windows OS compute quote returns safe unavailability instead of an unreliable quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute - Windows OS for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /not available yet/i);
  assert.match(reply.message, /Windows OS/i);
  assert.match(reply.message, /Guest OS licensing lines/i);
  assert.match(reply.message, /Quote the underlying OCI compute shape separately/i);
});

test('explicit Windows OS compute quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute - Windows OS with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B88318/);
  assert.match(reply.message, /\$273\.79/);
});

test('unsupported metered Windows OS compute quote keeps metered licensing guidance', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Windows OS - Metered for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /Windows OS - Metered/i);
  assert.match(reply.message, /Metered guest OS licensing lines/i);
});

test('explicit metered Windows OS compute quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute - Windows OS - Metered with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B87674/);
  assert.match(reply.message, /\$309\.50/);
});

test('explicit Microsoft SQL Enterprise quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute - Microsoft SQL Enterprise with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91372/);
  assert.match(reply.message, /\$1,845\.12/);
});

test('explicit Microsoft SQL Standard quote with OCPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote OCI Compute - Microsoft SQL Standard with 8 OCPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B91373/);
  assert.match(reply.message, /\$833\.28/);
});

test('unsupported Cloud@Customer GPU quote returns safe unavailability with public-region alternatives', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote GPU.L40S on Compute Cloud@Customer for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.match(reply.message, /not available yet/i);
  assert.match(reply.message, /Cloud@Customer/i);
  assert.match(reply.message, /VM\.Standard\.E5\.Flex/i);
});

test('explicit Cloud@Customer GPU quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Oracle Compute Cloud@Customer - Compute - GPU.L40S with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B110965/);
  assert.match(reply.message, /\$5,208\.00/);
});

test('explicit Cloud@Customer GPU resource commit quote with GPU-hour units resolves deterministically', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
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
    quotePlan: { action: 'quote', targetType: 'service', domain: 'compute', useDeterministicEngine: true },
  }));

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Quote Oracle Compute Cloud@Customer - Compute - GPU.L40S - Resource Commit with 2 GPUs for 744 hours',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B111454/);
  assert.match(reply.message, /\$892\.80/);
});

test('prerequisite discovery for Oracle Integration Cloud Enterprise uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
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
  }), {
    genaiText: [
      'Para cotizar `Oracle Integration Cloud Enterprise` normalmente necesito:',
      '- el modelo de licenciamiento: `BYOL` o `License Included`',
      '- la cantidad de instancias',
      '- y cualquier aclaración adicional de moneda o periodo si quieres una presentación distinta del quote estándar',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What information do I need to quote Oracle Integration Cloud Enterprise?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'integration_oic_enterprise');
  assert.match(reply.message, /BYOL/i);
  assert.match(reply.message, /License Included/i);
  assert.match(reply.message, /instances|instancias/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('generic OIC SKU composition question uses structured discovery instead of a deterministic quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'integration_oic',
    serviceName: 'Oracle Integration Cloud',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para una quote de `Oracle Integration Cloud` primero debes definir la edición:',
      '- `Standard` o `Enterprise`',
      '- luego el modelo `BYOL` o `License Included`',
      '- y finalmente la cantidad de instancias',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: "Cuales son los SKU's requeridos en una quote de OIC?",
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'integration_oic');
  assert.match(reply.message, /Standard/i);
  assert.match(reply.message, /Enterprise/i);
  assert.match(reply.message, /BYOL|License Included/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('general discovery request returns service unavailable instead of inventing a quote when genai fails', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.6,
    annualRequested: false,
    normalizedRequest: text,
  }), { throwGenAI: true });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Que opciones de Shape tenemos en Virtual Machines?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.match(reply.message, /not available/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
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

test('memory ingestion unresolved quote uses family metadata instead of a hardcoded assistant branch', async () => {
  const unresolvedIndex = normalizeCatalog({
    'metrics.json': {
      items: [
        metric('m-transactions-ten-thousand', '10,000 Transactions'),
        metric('m-storage-hour', 'Gigabyte Storage Per Hour'),
      ],
    },
    'products.json': {
      items: [
        product({
          partNumber: 'B110463',
          displayName: 'OCI Generative AI Agents - Data Ingestion',
          serviceCategoryDisplayName: 'OCI Generative AI Agents',
          metricId: 'm-transactions-ten-thousand',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(0.0003)],
        }),
        product({
          partNumber: 'B112384',
          displayName: 'OCI Generative AI - Memory Retention',
          serviceCategoryDisplayName: 'OCI Generative AI - Search and Retrieval',
          metricId: 'm-storage-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.01)],
        }),
      ],
    },
    'productpresets.json': { items: [] },
  });

  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ai_memory_ingestion',
    serviceName: 'OCI Generative AI - Memory Ingestion',
    extractedInputs: { requestCount: 2000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: {
      action: 'quote',
      targetType: 'service',
      domain: 'analytics',
      candidateFamilies: ['ai_memory_ingestion'],
      missingInputs: [],
      useDeterministicEngine: true,
    },
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index: unresolvedIndex,
    conversation: [],
    userText: 'Quote OCI Generative AI Memory Ingestion 2000 events',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote_unresolved');
  assert.match(reply.message, /does not expose a direct quotable SKU/i);
  assert.match(reply.message, /B110463/);
  assert.match(reply.message, /B112384/);
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
  assert.match(reply.message, /VM\.Standard\.E4\.Flex/);
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
  assert.match(reply.message, /VM\.Standard\.A1\.Flex/);
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
      { role: 'assistant', content: 'Which OCI VM shape should I use for that machine? For Intel, common options are `VM.Standard3.Flex`, `VM.Optimized3.Flex`, or the fixed-shape family `VM.Standard2.x`. Once you pick the shape, I can combine it with the attached Block Volume sizing.' },
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

test('VM.Standard3.Flex quote resolves to X9 compute plus block volume', async () => {
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard3.Flex 1 OCPU 8 GB RAM with 200 GB Block Storage 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B94176/);
  assert.match(quote.markdown, /B94177/);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
});

test('Standard3.Flex alias quote resolves to X9 compute plus block volume', async () => {
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote Standard3.Flex 1 OCPU 8 GB RAM with 200 GB Block Storage 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B94176/);
  assert.match(quote.markdown, /B94177/);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
});

test('VM.Optimized3.Flex quote resolves to optimized X9 compute', async () => {
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Optimized3.Flex 2 OCPUs 16 GB RAM 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B93311/);
  assert.match(quote.markdown, /B93312/);
});

test('Optimized3.Flex alias quote resolves to optimized X9 compute', async () => {
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote Optimized3.Flex 2 OCPUs 16 GB RAM 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B93311/);
  assert.match(quote.markdown, /B93312/);
});

test('VM.Standard2 fixed shape quote uses fixed X7 sizing even without explicit memory', async () => {
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard2.4 with 200 GB Block Storage');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B88514/);
  assert.match(quote.markdown, /\|\s*4\s*\|/);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
});

test('Standard2.4 alias quote uses fixed X7 sizing even without explicit memory', async () => {
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote Standard2.4 with 200 GB Block Storage');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B88514/);
  assert.match(quote.markdown, /\|\s*4\s*\|/);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
});

test('DenseIO.E4.Flex alias quote resolves to dense I/O compute lines', async () => {
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote DenseIO.E4.Flex 2 OCPUs 16 GB RAM 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B93121/);
  assert.match(quote.markdown, /B93122/);
});

test('VM.Standard.A2.Flex quote resolves to A2 compute lines', async () => {
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard.A2.Flex 1 OCPU 6 GB RAM 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B109529/);
  assert.match(quote.markdown, /B109530/);
});

test('VM.Standard.A4.Flex quote resolves to A4 compute lines', async () => {
  const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));
  const index = buildIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard.A4.Flex 2 OCPUs 12 GB RAM 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B112145/);
  assert.match(quote.markdown, /B112146/);
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

test('deterministic expert summary prefers analytics and integration perspective when those lines dominate an AI search bundle', () => {
  const { buildDeterministicExpertSummary } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    reformulatedRequest: 'Quote Oracle Integration Cloud Standard License Included 3 instances plus Oracle Analytics Cloud Professional 40 users plus OCI Generative AI Agents Data Ingestion 500000 transactions plus OCI Generative AI Vector Store Retrieval 120000 requests plus OCI Generative AI Web Search 25000 requests plus API Gateway 9000000 API calls plus Object Storage 15 TB per month',
    assumptions: [],
    extractedInputs: {},
  }));

  const summary = buildDeterministicExpertSummary({
    ok: true,
    request: { source: 'Quote Oracle Integration Cloud Standard License Included 3 instances plus Oracle Analytics Cloud Professional 40 users plus OCI Generative AI Agents Data Ingestion 500000 transactions plus OCI Generative AI Vector Store Retrieval 120000 requests plus OCI Generative AI Web Search 25000 requests plus API Gateway 9000000 API calls plus Object Storage 15 TB per month' },
    resolution: { label: 'Composite OCI workload' },
    totals: { monthly: 2808.5264, annual: 33702.3168, currencyCode: 'USD' },
    lineItems: [
      { partNumber: 'B89639', product: 'Oracle Integration Cloud Standard - License Included', monthly: 1440.0864 },
      { partNumber: 'B92682', product: 'Oracle Analytics Cloud Professional - Users', monthly: 640 },
      { partNumber: 'B110463', product: 'OCI Generative AI Agents - Data Ingestion', monthly: 250 },
      { partNumber: 'B112416', product: 'OCI Generative AI - Vector Store Retrieval', monthly: 60 },
      { partNumber: 'B111973', product: 'OCI Generative AI - Web Search', monthly: 250 },
      { partNumber: 'B92072', product: 'API Gateway - 1,000,000 API Calls', monthly: 27 },
      { partNumber: 'B91628', product: 'Object Storage - Storage', monthly: 141.44 },
    ],
  });

  assert.match(summary, /OCI analytics and integration architect/);
  assert.doesNotMatch(summary, /OCI serverless and AI architect/);
});

test('deterministic expert summary prefers database perspective when database lines dominate an edge bundle', () => {
  const { buildDeterministicExpertSummary } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    reformulatedRequest: 'Quote Exadata Dedicated Infrastructure License Included 8 OCPUs on base system plus Network Firewall 2 firewalls and 5000 GB data processed per month plus Flexible Load Balancer 300 Mbps plus FastConnect 10 Gbps plus DNS 4000000 queries per month plus Data Safe for Database Cloud Service 3 databases',
    assumptions: [],
    extractedInputs: {},
  }));

  const summary = buildDeterministicExpertSummary({
    ok: true,
    request: { source: 'Quote Exadata Dedicated Infrastructure License Included 8 OCPUs on base system plus Network Firewall 2 firewalls and 5000 GB data processed per month plus Flexible Load Balancer 300 Mbps plus FastConnect 10 Gbps plus DNS 4000000 queries per month plus Data Safe for Database Cloud Service 3 databases' },
    resolution: { label: 'Composite OCI workload' },
    totals: { monthly: 21065.668, annual: 252788.016, currencyCode: 'USD' },
    lineItems: [
      { partNumber: 'B88592', product: 'Exadata Dedicated Infrastructure Database - OCPU - License Included', monthly: 8000.0832 },
      { partNumber: 'B90777', product: 'Exadata Dedicated Infrastructure - Base System', monthly: 12000.0096 },
      { partNumber: 'B95403', product: 'Network Firewall Instance', monthly: 160 },
      { partNumber: 'B95404', product: 'Network Firewall Data Processing', monthly: 840 },
      { partNumber: 'B93030', product: 'Load Balancer Base', monthly: 0 },
      { partNumber: 'B93031', product: 'Load Balancer Bandwidth', monthly: 19.278 },
      { partNumber: 'B88326', product: 'OCI - FastConnect 10 Gbps', monthly: 948.6 },
      { partNumber: 'B88525', product: 'Networking - DNS', monthly: 3.4 },
      { partNumber: 'B91632', product: 'Data Safe for Database Cloud Service', monthly: 94.2972 },
    ],
  });

  assert.match(summary, /OCI database architect/);
  assert.doesNotMatch(summary, /OCI networking and security architect/);
});

test('deterministic expert summary prefers solutions architect perspective for heavily mixed bundles', () => {
  const { buildDeterministicExpertSummary } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    reformulatedRequest: 'Quote a global customer platform with compute, storage, edge, analytics, integration, database, and observability services',
    assumptions: [],
    extractedInputs: {},
  }));

  const summary = buildDeterministicExpertSummary({
    ok: true,
    request: { source: 'Quote a global customer platform with compute, storage, edge, analytics, integration, database, and observability services' },
    resolution: { label: 'Composite OCI workload' },
    totals: { monthly: 53976.6978, annual: 647720.3736, currencyCode: 'USD' },
    lineItems: [
      { partNumber: 'B93113', product: 'Compute OCPU', monthly: 1200 },
      { partNumber: 'B89057', product: 'File Storage - Storage', monthly: 3072 },
      { partNumber: 'B94579', product: 'OCI Web Application Firewall - Instance', monthly: 10 },
      { partNumber: 'B89640', product: 'Oracle Integration Cloud Enterprise', monthly: 2880 },
      { partNumber: 'B92683', product: 'Oracle Analytics Cloud Enterprise - Users', monthly: 6000 },
      { partNumber: 'B90570', product: 'Base Database Service Enterprise - License Included', monthly: 2678.4 },
      { partNumber: 'B95634', product: 'OCI Log Analytics - Active Storage', monthly: 1475.6 },
      { partNumber: 'B109546', product: 'File Storage Service - High Performance Mount Target', monthly: 30720 },
      { partNumber: 'B95404', product: 'Network Firewall Data Processing', monthly: 3360 },
    ],
  });

  assert.match(summary, /OCI solutions architect/);
  assert.doesNotMatch(summary, /OCI analytics and integration architect/);
});

test('deterministic expert summary prefers observability perspective over database when observability services dominate a mixed operations bundle', () => {
  const { buildDeterministicExpertSummary } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    reformulatedRequest: 'Quote an enterprise operations and observability fabric with monitoring, log analytics, notifications, fleet, batch, data safe, and threat intelligence',
    assumptions: [],
    extractedInputs: {},
  }));

  const summary = buildDeterministicExpertSummary({
    ok: true,
    request: { source: 'Quote an enterprise operations and observability fabric with monitoring, log analytics, notifications, fleet, batch, data safe, and threat intelligence' },
    resolution: { label: 'Composite OCI workload' },
    totals: { monthly: 3836.78, annual: 46041.36, currencyCode: 'USD' },
    lineItems: [
      { partNumber: 'B90925', product: 'Monitoring Ingestion', monthly: 300 },
      { partNumber: 'B90926', product: 'Monitoring Retrieval', monthly: 720 },
      { partNumber: 'B90940', product: 'Notifications HTTPS Delivery', monthly: 6 },
      { partNumber: 'B90941', product: 'Notifications Email Delivery', monthly: 9.84 },
      { partNumber: 'B93496', product: 'IAM SMS', monthly: 20 },
      { partNumber: 'B110475', product: 'Fleet Application Management', monthly: 0 },
      { partNumber: 'B112107', product: 'OCI Batch', monthly: 0 },
      { partNumber: 'B95634', product: 'OCI Log Analytics - Active Storage', monthly: 1847.2 },
      { partNumber: 'B92809', product: 'OCI Log Analytics - Archival Storage', monthly: 248 },
      { partNumber: 'B92733', product: 'Data Safe for On-Premises Databases', monthly: 660 },
      { partNumber: 'B94173', product: 'Oracle Threat Intelligence Service', monthly: 0 },
      { partNumber: 'B88525', product: 'Networking - DNS', monthly: 5.1 },
    ],
  });

  assert.match(summary, /OCI observability architect/);
  assert.doesNotMatch(summary, /OCI database architect/);
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
