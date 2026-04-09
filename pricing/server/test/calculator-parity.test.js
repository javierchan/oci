'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const { normalizeCatalog } = require(path.join(ROOT, 'catalog.js'));
const { quoteFromPrompt } = require(path.join(ROOT, 'quotation-engine.js'));

function metric(id, displayName, unitDisplayName = '') {
  return { id, displayName, unitDisplayName };
}

function payg(value, rangeMin, rangeMax) {
  const tier = { model: 'PAY_AS_YOU_GO', value };
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

function buildCalculatorIndex() {
  return normalizeCatalog({
    'metrics.json': {
      items: [
        metric('m-ocpu-hour', 'OCPU Per Hour'),
        metric('m-gpu-hour', 'GPU Per Hour'),
        metric('m-gb-hour', 'Gigabytes Per Hour'),
        metric('m-capacity-month', 'Gigabyte Storage Capacity Per Month'),
        metric('m-performance-month', 'Performance Units Per Gigabyte Per Month'),
        metric('m-port-hour', 'Port Hour'),
        metric('m-million-requests', 'Million Requests'),
        metric('m-million-queries', '1,000,000 Queries'),
        metric('m-thousand-emails', '1,000 Emails Sent'),
        metric('m-million-api-calls', '1,000,000 API Calls'),
        metric('m-functions-exec', '10,000 GB Memory Seconds'),
        metric('m-functions-inv', '1,000,000 Invocations'),
        metric('m-datapoints-million', '1,000,000 Datapoints'),
        metric('m-delivery-million', '1,000,000 Delivery Operations'),
        metric('m-managed-resource-month', 'Managed Resource Per Month'),
        metric('m-each', 'Each'),
        metric('m-endpoints-month', 'Endpoints Per Month'),
        metric('m-requests-thousand-plain', '1000 Requests'),
        metric('m-sms-each', '1 SMS Message Sent'),
        metric('m-transactions-thousand', '1,000 Transactions'),
        metric('m-transactions-ten-thousand', '10,000 Transactions'),
        metric('m-training-hour', 'Training Hour'),
        metric('m-transcription-hour', 'Transcription Hour'),
        metric('m-media-minute', 'Media Minute'),
        metric('m-processed-video-minute', 'Processed Video Minute'),
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
          partNumber: 'B94176',
          displayName: 'Compute - Standard - X9 - OCPU',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.04)],
        }),
        product({
          partNumber: 'B94177',
          displayName: 'Compute - Standard - X9 - Memory',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-gb-hour',
          usdPrices: [payg(0.0015)],
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
          partNumber: 'B88326',
          displayName: 'OCI - FastConnect 10 Gbps',
          serviceCategoryDisplayName: 'Networking - FastConnect',
          metricId: 'm-port-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(1.275)],
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
          metricId: 'm-million-requests',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0016)],
        }),
        product({
          partNumber: 'B88525',
          displayName: 'OCI DNS - Queries',
          serviceCategoryDisplayName: 'Networking - DNS',
          metricId: 'm-million-queries',
          pricetype: 'MONTH',
          usdPrices: [payg(0.85)],
        }),
        product({
          partNumber: 'B90941',
          displayName: 'OCI Notifications - Email Delivery',
          serviceCategoryDisplayName: 'Notifications - Email Delivery',
          metricId: 'm-thousand-emails',
          pricetype: 'MONTH',
          usdPrices: [payg(2)],
        }),
        product({
          partNumber: 'B92072',
          displayName: 'API Gateway - 1,000,000 API Calls',
          serviceCategoryDisplayName: 'Application Development - API Management',
          metricId: 'm-million-api-calls',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(3)],
        }),
        product({
          partNumber: 'B95403',
          displayName: 'Network Firewall Instance',
          serviceCategoryDisplayName: 'Network Firewall',
          metricId: 'm-port-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(2.75)],
        }),
        product({
          partNumber: 'B95404',
          displayName: 'Network Firewall Data Processing',
          serviceCategoryDisplayName: 'Network Firewall',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0, 0, 10240), payg(0.01, 10240, null)],
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
          partNumber: 'B89057',
          displayName: 'File Storage - Storage',
          serviceCategoryDisplayName: 'Storage - File Storage',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.3)],
        }),
        product({
          partNumber: 'B109546',
          displayName: 'File Storage Service - High Performance Mount Target',
          serviceCategoryDisplayName: 'Storage - File Storage',
          metricId: 'm-performance-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.3)],
        }),
        product({
          partNumber: 'B90617',
          displayName: 'Oracle Functions - Execution Time',
          serviceCategoryDisplayName: 'Application Development - Serverless',
          metricId: 'm-functions-exec',
          pricetype: 'MONTH',
          usdPrices: [payg(0, 0, 40), payg(0.1417, 40)],
        }),
        product({
          partNumber: 'B90618',
          displayName: 'Oracle Functions - Invocations',
          serviceCategoryDisplayName: 'Application Development - Serverless',
          metricId: 'm-functions-inv',
          pricetype: 'MONTH',
          usdPrices: [payg(0, 0, 2), payg(0.2, 2)],
        }),
        product({
          partNumber: 'B89639',
          displayName: 'Oracle Integration Cloud Service - Standard | 5K Messages Per Hour',
          serviceCategoryDisplayName: 'Application Integration - OIC',
          metricId: 'm-port-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.6452)],
        }),
        product({
          partNumber: 'B89643',
          displayName: 'Oracle Integration Cloud Service - Standard - BYOL',
          serviceCategoryDisplayName: 'Application Integration - OIC',
          metricId: 'm-port-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.3226)],
        }),
        product({
          partNumber: 'B89640',
          displayName: 'Oracle Integration Cloud Service - Enterprise',
          serviceCategoryDisplayName: 'Application Integration - OIC',
          metricId: 'm-port-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(1.2903)],
        }),
        product({
          partNumber: 'B89644',
          displayName: 'Oracle Integration Cloud Service - Enterprise - BYOL',
          serviceCategoryDisplayName: 'Application Integration - OIC',
          metricId: 'm-port-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.3226)],
        }),
        product({
          partNumber: 'B89636',
          displayName: 'Oracle Analytics Cloud - Professional - BYOL - OCPU',
          serviceCategoryDisplayName: 'Analytics - Analytics Cloud',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.3226)],
        }),
        product({
          partNumber: 'B92682',
          displayName: 'Oracle Analytics Cloud - Professional - Users',
          serviceCategoryDisplayName: 'Analytics - Analytics Cloud',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(16)],
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
          partNumber: 'B95701',
          displayName: 'Oracle Autonomous AI Lakehouse - ECPU',
          serviceCategoryDisplayName: 'Database - Autonomous AI Database',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.336)],
        }),
        product({
          partNumber: 'B95703',
          displayName: 'Oracle Autonomous AI Lakehouse - ECPU -BYOL',
          serviceCategoryDisplayName: 'Database - Autonomous AI Database',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.0807)],
        }),
        product({
          partNumber: 'B95702',
          displayName: 'Oracle Autonomous AI Transaction Processing - ECPU',
          serviceCategoryDisplayName: 'Database - Autonomous AI Database',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.336)],
        }),
        product({
          partNumber: 'B95704',
          displayName: 'Oracle Autonomous AI Transaction Processing - ECPU - BYOL',
          serviceCategoryDisplayName: 'Database - Autonomous AI Database',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.0807)],
        }),
        product({
          partNumber: 'B95706',
          displayName: 'Oracle Autonomous AI Database Storage for Transaction Processing',
          serviceCategoryDisplayName: 'Database - Autonomous AI Database',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.1156)],
        }),
        product({
          partNumber: 'B90570',
          displayName: 'Oracle Base Database Service - Enterprise',
          serviceCategoryDisplayName: 'Database - Base Database Service - Virtual Machine',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.4301)],
        }),
        product({
          partNumber: 'B90573',
          displayName: 'Oracle Base Database Service - BYOL',
          serviceCategoryDisplayName: 'Database - Base Database Service - Virtual Machine',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.1935)],
        }),
        product({
          partNumber: 'B111584',
          displayName: 'Oracle Base Database Service - Database Storage',
          serviceCategoryDisplayName: 'Database - Base Database Service - Virtual Machine',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0595)],
        }),
        product({
          partNumber: 'B109356',
          displayName: 'Oracle Exadata Exascale Database ECPU',
          serviceCategoryDisplayName: 'Exadata Database Service ECPUs',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.336)],
        }),
        product({
          partNumber: 'B107951',
          displayName: 'Oracle Exadata Exascale VM Filesystem Storage',
          serviceCategoryDisplayName: 'Exadata Exascale Infrastructure',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0425)],
        }),
        product({
          partNumber: 'B88592',
          displayName: 'Exadata Database OCPU - Dedicated Infrastructure',
          serviceCategoryDisplayName: 'Exadata Database Service OCPUs',
          metricId: 'm-ocpu-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(1.3441)],
        }),
        product({
          partNumber: 'B90777',
          displayName: 'Exadata Database Cloud Service - Base System',
          serviceCategoryDisplayName: 'Exadata Cloud Infrastructure Base System',
          metricId: 'm-port-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(10.7527)],
        }),
        product({
          partNumber: 'B91632',
          displayName: 'Data Safe for Database Cloud Service - Databases',
          serviceCategoryDisplayName: 'Security - Data Safe',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0)],
        }),
        product({
          partNumber: 'B92733',
          displayName: 'Data Safe for On-Premises Databases & Databases on Compute',
          serviceCategoryDisplayName: 'Security - Data Safe',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(200, 0, 100), payg(150, 100, 300), payg(100, 300, 500), payg(50, 500, null)],
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
          partNumber: 'B90325',
          displayName: 'OCI - Health Checks - Premium',
          serviceCategoryDisplayName: 'Edge Services',
          metricId: 'm-endpoints-month',
          pricetype: 'MONTH',
          usdPrices: [payg(1.3)],
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
          partNumber: 'B93496',
          displayName: 'OCI IAM - SMS',
          serviceCategoryDisplayName: 'Identity and Access Management - SMS',
          metricId: 'm-sms-each',
          pricetype: 'MONTH',
          usdPrices: [payg(0.02)],
        }),
        product({
          partNumber: 'B93004',
          displayName: 'OCI Notifications - SMS Outbound - Country Zone 1',
          serviceCategoryDisplayName: 'Notifications - SMS Delivery',
          metricId: 'm-sms-each',
          pricetype: 'MONTH',
          usdPrices: [payg(0, 0, 100), payg(0.015, 100, null)],
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
          partNumber: 'B94173',
          displayName: 'Oracle Threat Intelligence Service',
          serviceCategoryDisplayName: 'Security - Threat Intelligence',
          metricId: 'm-requests-thousand-plain',
          pricetype: 'MONTH',
          usdPrices: [payg(0.6)],
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
          metricId: 'm-gb-hour',
          pricetype: 'HOUR',
          usdPrices: [payg(0.0084)],
        }),
        product({
          partNumber: 'B94977',
          displayName: 'Vision - Custom Training',
          serviceCategoryDisplayName: 'Oracle Cloud Infrastructure - Vision - Custom Training',
          metricId: 'm-training-hour',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(1.47)],
        }),
        product({
          partNumber: 'B94896',
          displayName: 'Speech',
          serviceCategoryDisplayName: 'Speech',
          metricId: 'm-transcription-hour',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(0.016)],
        }),
        product({
          partNumber: 'B94973',
          displayName: 'Vision - Image Analysis',
          serviceCategoryDisplayName: 'Oracle Cloud Infrastructure - Vision',
          metricId: 'm-transactions-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(0, 0, 5), payg(0.25, 5, null)],
        }),
        product({
          partNumber: 'B94974',
          displayName: 'Vision - OCR',
          serviceCategoryDisplayName: 'Oracle Cloud Infrastructure - Vision',
          metricId: 'm-transactions-thousand',
          pricetype: 'MONTH',
          usdPrices: [payg(0, 0, 5), payg(1, 5, null)],
        }),
        product({
          partNumber: 'B95282',
          displayName: 'Media Services - Media Flow - Standard - H264 - HD - Below 30fps',
          serviceCategoryDisplayName: 'Media Services - Media Flow - Quality - H264 - HD - Below 30fps',
          metricId: 'm-media-minute',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(0.006)],
        }),
        product({
          partNumber: 'B110617',
          displayName: 'OCI - Vision - Stored Video Analysis',
          serviceCategoryDisplayName: 'OCI - Vision - Stored Video Analysis',
          metricId: 'm-processed-video-minute',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(0.003)],
        }),
        product({
          partNumber: 'B111539',
          displayName: 'OCI - Vision - Stream Video Analysis',
          serviceCategoryDisplayName: 'OCI - Vision - Stream Video Analysis',
          metricId: 'm-processed-video-minute',
          pricetype: 'PER-ITEM',
          usdPrices: [payg(0.15)],
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
          partNumber: 'B110475',
          displayName: 'OCI Fleet Application Management Service',
          serviceCategoryDisplayName: 'Fleet Application Management',
          metricId: 'm-managed-resource-month',
          pricetype: 'MONTH',
          usdPrices: [payg(7)],
        }),
        product({
          partNumber: 'B91627',
          displayName: 'Oracle Cloud Infrastructure - Object Storage Requests',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-requests-thousand-plain',
          pricetype: 'MONTH',
          usdPrices: [payg(0, 0, 5), payg(0.0034, 5, null)],
        }),
        product({
          partNumber: 'B91633',
          displayName: 'Archive Storage',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0, 0, 10), payg(0.0026, 10, null)],
        }),
        product({
          partNumber: 'B93000',
          displayName: 'Infrequent Access Storage',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0, 0, 10), payg(0.01, 10, null)],
        }),
        product({
          partNumber: 'B93001',
          displayName: 'Infrequent Access Retrieval',
          serviceCategoryDisplayName: 'Storage - Object Storage',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0, 0, 10), payg(0.01, 10, null)],
        }),
        product({
          partNumber: 'B88513',
          displayName: 'Compute - Bare Metal Standard - X7',
          serviceCategoryDisplayName: 'Compute - Bare Metal',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.06375)],
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
      ],
    },
    'productpresets.json': { items: [] },
  });
}

function assertWithin(actual, expected, tolerance = 0.05) {
  assert.ok(Math.abs(Number(actual) - Number(expected)) <= tolerance, `${actual} was not within ${tolerance} of ${expected}`);
}

test('calculator parity: VM.Standard3.Flex 1 OCPU 8 GB plus 200 GB block at 10 VPU stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard3.Flex 1 OCPU 8 GB RAM with 200 GB Block Storage and 10 VPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 47.19);
  assert.match(quote.markdown, /B94176/);
  assert.match(quote.markdown, /B94177/);
  assert.match(quote.markdown, /B91961/);
  assert.match(quote.markdown, /B91962/);
});

test('calculator parity: VM.Standard3.Flex 28 OCPUs 256 GB plus 121 GB block at 30 VPU stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard3.Flex 28 OCPUs 256 GB RAM with 121 GB Block Storage and 30 VPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1128.23);
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B91962');
  assert.ok(performanceLine);
  assertWithin(performanceLine.monthly, 6.171);
});

test('calculator parity: VM.Standard3.Flex 28 OCPUs 512 GB plus 6279 GB block at 30 VPU stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard3.Flex 28 OCPUs 512 GB RAM with 6279 GB Block Storage and 30 VPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1885.01);
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B91962');
  assert.ok(performanceLine);
  assertWithin(performanceLine.monthly, 320.23, 0.1);
});

test('calculator parity: VM.Standard3.Flex 28 OCPUs 512 GB without attached storage stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard3.Flex 28 OCPUs 512 GB RAM 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1404.67, 0.1);
  assert.equal(quote.lineItems.some((line) => line.partNumber === 'B91961'), false);
  assert.equal(quote.lineItems.some((line) => line.partNumber === 'B91962'), false);
});

test('calculator parity: block volume only 6279 GB at 10 VPU stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Block Volume 6279 GB with 10 VPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 266.83, 0.1);
  const storageLine = quote.lineItems.find((line) => line.partNumber === 'B91961');
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B91962');
  assert.ok(storageLine);
  assert.ok(performanceLine);
  assertWithin(storageLine.monthly, 160.11, 0.1);
  assertWithin(performanceLine.monthly, 106.74, 0.1);
});

test('calculator parity: block volume only 6279 GB at 20 VPU stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Block Volume 6279 GB with 20 VPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 373.53, 0.1);
  const storageLine = quote.lineItems.find((line) => line.partNumber === 'B91961');
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B91962');
  assert.ok(storageLine);
  assert.ok(performanceLine);
  assertWithin(storageLine.monthly, 160.11, 0.1);
  assertWithin(performanceLine.monthly, 213.49, 0.1);
});

test('calculator parity: block volume only 6279 GB at 30 VPU stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Block Volume 6279 GB with 30 VPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 480.34, 0.1);
  const storageLine = quote.lineItems.find((line) => line.partNumber === 'B91961');
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B91962');
  assert.ok(storageLine);
  assert.ok(performanceLine);
  assertWithin(storageLine.monthly, 160.11, 0.1);
  assertWithin(performanceLine.monthly, 320.23, 0.1);
});

test('calculator parity: object storage 20 TB per month stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Object Storage 20 TB per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 522.24, 0.1);
  const storageLine = quote.lineItems.find((line) => line.partNumber === 'B91628');
  assert.ok(storageLine);
  assertWithin(storageLine.monthly, 522.24, 0.1);
});

test('calculator parity: file storage 5 TB at 10 performance units stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote File Storage 5 TB and 10 performance units per GB per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 16896, 0.1);
  const storageLine = quote.lineItems.find((line) => line.partNumber === 'B89057');
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B109546');
  assert.ok(storageLine);
  assert.ok(performanceLine);
  assertWithin(storageLine.monthly, 1536, 0.1);
  assertWithin(performanceLine.monthly, 15360, 0.1);
});

test('calculator parity: Oracle Integration Cloud Standard license included 2 instances stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Oracle Integration Cloud Standard License Included 2 instances 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 960.0576, 0.1);
  const line = quote.lineItems.find((item) => item.partNumber === 'B89639');
  assert.ok(line);
  assertWithin(line.monthly, 960.0576, 0.1);
});

test('calculator parity: Oracle Integration Cloud Standard BYOL 2 instances stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Oracle Integration Cloud Standard BYOL 2 instances 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 480.0288, 0.1);
  const line = quote.lineItems.find((item) => item.partNumber === 'B89643');
  assert.ok(line);
  assertWithin(line.monthly, 480.0288, 0.1);
});

test('calculator parity: Oracle Integration Cloud Enterprise license included 2 instances stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Oracle Integration Cloud Enterprise License Included 2 instances 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1919.9664, 0.1);
  const line = quote.lineItems.find((item) => item.partNumber === 'B89640');
  assert.ok(line);
  assertWithin(line.monthly, 1919.9664, 0.1);
});

test('calculator parity: Oracle Integration Cloud Enterprise BYOL 2 instances stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Oracle Integration Cloud Enterprise BYOL 2 instances 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 480.0288, 0.1);
  const line = quote.lineItems.find((item) => item.partNumber === 'B89644');
  assert.ok(line);
  assertWithin(line.monthly, 480.0288, 0.1);
});

test('calculator parity: Oracle Analytics Cloud Professional 25 users stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Oracle Analytics Cloud Professional 25 users');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 400, 0.1);
  const line = quote.lineItems.find((item) => item.partNumber === 'B92682');
  assert.ok(line);
  assertWithin(line.monthly, 400, 0.1);
});

test('calculator parity: Oracle Analytics Cloud Professional BYOL 2 OCPUs stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Oracle Analytics Cloud Professional BYOL 2 OCPUs 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 480.0288, 0.1);
  const line = quote.lineItems.find((item) => item.partNumber === 'B89636');
  assert.ok(line);
  assertWithin(line.monthly, 480.0288, 0.1);
});

test('calculator parity: Oracle Analytics Cloud Enterprise 50 users stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Oracle Analytics Cloud Enterprise 50 users');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 4000, 0.1);
  const line = quote.lineItems.find((item) => item.partNumber === 'B92683');
  assert.ok(line);
  assertWithin(line.monthly, 4000, 0.1);
});

test('calculator parity: Base Database Service Enterprise License Included 4 OCPUs and 1000 GB storage stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Base Database Service Enterprise License Included 4 OCPUs and 1000 GB storage');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1339.4776, 0.1);
  const compute = quote.lineItems.find((item) => item.partNumber === 'B90570');
  const storage = quote.lineItems.find((item) => item.partNumber === 'B111584');
  assert.ok(compute);
  assert.ok(storage);
  assertWithin(compute.monthly, 1279.9776, 0.1);
  assertWithin(storage.monthly, 59.5, 0.1);
});

test('calculator parity: Base Database Service Enterprise BYOL 4 OCPUs and 1000 GB storage stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Base Database Service Enterprise BYOL 4 OCPUs and 1000 GB storage');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 635.356, 0.1);
  const compute = quote.lineItems.find((item) => item.partNumber === 'B90573');
  const storage = quote.lineItems.find((item) => item.partNumber === 'B111584');
  assert.ok(compute);
  assert.ok(storage);
  assertWithin(compute.monthly, 575.856, 0.1);
  assertWithin(storage.monthly, 59.5, 0.1);
});

test('calculator parity: Autonomous AI Lakehouse License Included 2 ECPUs and 100 GB storage stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Autonomous AI Lakehouse License Included 2 ECPUs and 100 GB storage per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 511.528, 0.1);
  const compute = quote.lineItems.find((item) => item.partNumber === 'B95701');
  const storage = quote.lineItems.find((item) => item.partNumber === 'B95706');
  assert.ok(compute);
  assert.ok(storage);
  assertWithin(compute.monthly, 499.968, 0.1);
  assertWithin(storage.monthly, 11.56, 0.1);
});

test('calculator parity: Autonomous AI Lakehouse BYOL 2 ECPUs and 100 GB storage stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Autonomous AI Lakehouse BYOL 2 ECPUs and 100 GB storage per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 131.6416, 0.1);
  const compute = quote.lineItems.find((item) => item.partNumber === 'B95703');
  const storage = quote.lineItems.find((item) => item.partNumber === 'B95706');
  assert.ok(compute);
  assert.ok(storage);
  assertWithin(compute.monthly, 120.0816, 0.1);
  assertWithin(storage.monthly, 11.56, 0.1);
});

test('calculator parity: Autonomous AI Transaction Processing License Included 2 ECPUs and 100 GB storage stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Autonomous AI Transaction Processing License Included 2 ECPUs and 100 GB storage per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 511.528, 0.1);
  const compute = quote.lineItems.find((item) => item.partNumber === 'B95702');
  const storage = quote.lineItems.find((item) => item.partNumber === 'B95706');
  assert.ok(compute);
  assert.ok(storage);
  assertWithin(compute.monthly, 499.968, 0.1);
  assertWithin(storage.monthly, 11.56, 0.1);
});

test('calculator parity: Autonomous AI Transaction Processing BYOL 2 ECPUs and 100 GB storage stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Autonomous AI Transaction Processing BYOL 2 ECPUs and 100 GB storage per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 131.6416, 0.1);
  const compute = quote.lineItems.find((item) => item.partNumber === 'B95704');
  const storage = quote.lineItems.find((item) => item.partNumber === 'B95706');
  assert.ok(compute);
  assert.ok(storage);
  assertWithin(compute.monthly, 120.0816, 0.1);
  assertWithin(storage.monthly, 11.56, 0.1);
});

test('calculator parity: Exadata Exascale License Included 4 ECPUs and 1000 GB filesystem storage stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Exadata Exascale License Included 4 ECPUs and 1000 GB filesystem storage');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1042.436, 0.1);
  const compute = quote.lineItems.find((item) => item.partNumber === 'B109356');
  const storage = quote.lineItems.find((item) => item.partNumber === 'B107951');
  assert.ok(compute);
  assert.ok(storage);
  assertWithin(compute.monthly, 999.936, 0.1);
  assertWithin(storage.monthly, 42.5, 0.1);
});

test('calculator parity: Exadata Dedicated Infrastructure License Included 4 OCPUs on base system stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Exadata Dedicated Infrastructure License Included 4 OCPUs on base system');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 12000.0504, 0.1);
  const compute = quote.lineItems.find((item) => item.partNumber === 'B88592');
  const infrastructure = quote.lineItems.find((item) => item.partNumber === 'B90777');
  assert.ok(compute);
  assert.ok(infrastructure);
  assertWithin(compute.monthly, 4000.0416, 0.1);
  assertWithin(infrastructure.monthly, 8000.0088, 0.1);
});

test('calculator parity: bare metal fixed-shape prompts resolve the bare metal SKU instead of a VM family', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote BM.Standard2.52 744h/month');
  const meteredQuote = quoteFromPrompt(index, 'Quote BM.Standard2.52 metered 744h/month');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B88513/);
  assert.doesNotMatch(quote.markdown, /B89137/);
  assertWithin(quote.totals.monthly, 2466.36, 0.2);

  assert.equal(meteredQuote.ok, true);
  assert.match(meteredQuote.markdown, /B89137/);
  assert.doesNotMatch(meteredQuote.markdown, /B88513/);
  assertWithin(meteredQuote.totals.monthly, 2901.6, 0.2);
});

test('calculator parity: Bare Metal Standard - X7 - Metered with 52 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Compute - Bare Metal Standard - X7 - Metered with 52 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B89137/);
  assertWithin(quote.totals.monthly, 2901.6, 0.05);
});

test('calculator parity: Bare Metal Dense I/O - X7 - Metered with 52 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Compute - Bare Metal Dense I/O - X7 - Metered with 52 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B89139/);
  assertWithin(quote.totals.monthly, 3327.168, 0.05);
});

test('calculator parity: Virtual Machine Standard - X7 - Metered with 8 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Compute - Virtual Machine Standard - X7 - Metered with 8 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B89135/);
  assertWithin(quote.totals.monthly, 327.36, 0.05);
});

test('calculator parity: Virtual Machine Standard - X5 with 8 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Compute - Virtual Machine Standard - X5 with 8 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B88511/);
  assertWithin(quote.totals.monthly, 267.84, 0.05);
});

test('calculator parity: Virtual Machine Standard - B1 with 4 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Compute - Virtual Machine Standard - B1 with 4 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B91120/);
  assertWithin(quote.totals.monthly, 59.52, 0.05);
});

test('calculator parity: Compute - Standard - E2 with 8 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Compute - Standard - E2 with 8 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B90425/);
  assertWithin(quote.totals.monthly, 184.512, 0.05);
});

test('calculator parity: OCI Compute - Windows OS with 8 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute - Windows OS with 8 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B88318/);
  assertWithin(quote.totals.monthly, 273.792, 0.05);
});

test('calculator parity: OCI Compute - Windows OS - Metered with 8 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute - Windows OS - Metered with 8 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B87674/);
  assertWithin(quote.totals.monthly, 309.504, 0.05);
});

test('calculator parity: OCI Compute - Microsoft SQL Enterprise with 8 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute - Microsoft SQL Enterprise with 8 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B91372/);
  assertWithin(quote.totals.monthly, 1845.12, 0.05);
});

test('calculator parity: OCI Compute - Microsoft SQL Standard with 8 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute - Microsoft SQL Standard with 8 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B91373/);
  assertWithin(quote.totals.monthly, 833.28, 0.05);
});

test('calculator parity: Virtual Machine Standard - X5 - Metered with 8 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Compute - Virtual Machine Standard - X5 - Metered with 8 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B89133/);
  assertWithin(quote.totals.monthly, 297.6, 0.05);
});

test('calculator parity: Virtual Machine Dense I/O - X7 - Metered with 8 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Compute - Virtual Machine Dense I/O - X7 - Metered with 8 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B89136/);
  assertWithin(quote.totals.monthly, 386.88, 0.05);
});

test('calculator parity: Virtual Machine Dense I/O - X7 with 8 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Compute - Virtual Machine Dense I/O - X7 with 8 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B88515/);
  assertWithin(quote.totals.monthly, 476.16, 0.05);
});

test('calculator parity: Virtual Machine Dense I/O - X5 - Metered with 8 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Compute - Virtual Machine Dense I/O - X5 - Metered with 8 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assert.match(quote.markdown, /B89134/);
  assertWithin(quote.totals.monthly, 416.64, 0.05);
});

test('calculator parity: FastConnect 10 Gbps stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote FastConnect 10 Gbps');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 948.6, 0.1);
  assert.match(quote.markdown, /B88326/);
});

test('calculator parity: Flexible Load Balancer 200 Mbps stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Flexible Load Balancer 200 Mbps 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 13.392, 0.05);
  assert.match(quote.markdown, /B93030/);
  assert.match(quote.markdown, /B93031/);
});

test('calculator parity: WAF 2 instances and 25000000 requests stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Web Application Firewall with 2 instances and 25000000 requests per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 10.04, 0.05);
  assert.match(quote.markdown, /B94579/);
  assert.match(quote.markdown, /B94277/);
});

test('calculator parity: DNS 5000000 queries stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote DNS 5000000 queries per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 4.25, 0.05);
  assert.match(quote.markdown, /B88525/);
});

test('calculator parity: Email Delivery 100000 emails stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Email Delivery 100000 emails per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 200, 0.05);
  assert.match(quote.markdown, /B90941/);
});

test('calculator parity: API Gateway 5000000 API calls stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote API Gateway 5000000 API calls per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 15, 0.05);
  assert.match(quote.markdown, /B92072/);
});

test('calculator parity: Network Firewall 2 firewalls and 20000 GB processed stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Network Firewall 2 firewalls and 20000 GB data processed per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 4189.6, 0.1);
  const instanceLine = quote.lineItems.find((line) => line.partNumber === 'B95403');
  const dataLine = quote.lineItems.find((line) => line.partNumber === 'B95404');
  assert.ok(instanceLine);
  assert.ok(dataLine);
  assertWithin(instanceLine.monthly, 4092, 0.01);
  assertWithin(dataLine.monthly, 97.6, 0.1);
});

test('calculator parity: Data Safe for Database Cloud Service 3 databases stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Data Safe for Database Cloud Service 3 databases');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 0, 0.01);
  const line = quote.lineItems.find((item) => item.partNumber === 'B91632');
  assert.ok(line);
  assertWithin(line.monthly, 0, 0.01);
});

test('calculator parity: Data Safe for On-Premises Databases 2 target databases stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Data Safe for On-Premises Databases 2 target databases');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 400, 0.1);
  const line = quote.lineItems.find((item) => item.partNumber === 'B92733');
  assert.ok(line);
  assertWithin(line.monthly, 400, 0.1);
});

test('calculator parity: Monitoring Ingestion 2500000 datapoints stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Monitoring Ingestion 2500000 datapoints');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 3.125, 0.01);
  const line = quote.lineItems.find((item) => item.partNumber === 'B90925');
  assert.ok(line);
  assertWithin(line.monthly, 3.125, 0.01);
});

test('calculator parity: Monitoring Retrieval 4000000 datapoints stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Monitoring Retrieval 4000000 datapoints');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 3, 0.01);
  const line = quote.lineItems.find((item) => item.partNumber === 'B90926');
  assert.ok(line);
  assertWithin(line.monthly, 3, 0.01);
});

test('calculator parity: Notifications HTTPS Delivery 3000000 delivery operations stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Notifications HTTPS Delivery 3000000 delivery operations');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 12, 0.01);
  const line = quote.lineItems.find((item) => item.partNumber === 'B90940');
  assert.ok(line);
  assertWithin(line.monthly, 12, 0.01);
});

test('calculator parity: Log Analytics archival storage 600 GB per month stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Log Analytics archival storage 600 GB per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 29.76, 0.05);
  const line = quote.lineItems.find((item) => item.partNumber === 'B92809');
  assert.ok(line);
  assertWithin(line.monthly, 29.76, 0.05);
});

test('calculator parity: Log Analytics active storage 1200 GB per month stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Log Analytics active storage 1200 GB per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1215.8944, 0.1);
  const line = quote.lineItems.find((item) => item.partNumber === 'B95634');
  assert.ok(line);
  assertWithin(line.monthly, 1215.8944, 0.1);
});

test('calculator parity: OCI Functions 3100000 invocations 30000 ms 128 MB stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Functions 3100000 invocations per month 30000 ms per invocation 128 MB memory');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 159.27825, 0.05);
  const execution = quote.lineItems.find((item) => item.partNumber === 'B90617');
  const invocations = quote.lineItems.find((item) => item.partNumber === 'B90618');
  assert.ok(execution);
  assert.ok(invocations);
  assertWithin(execution.monthly, 159.05825, 0.05);
  assertWithin(invocations.monthly, 0.22, 0.01);
});

test('calculator parity: Fleet Application Management 5 managed resources stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Fleet Application Management 5 managed resources per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 35, 0.01);
  const line = quote.lineItems.find((item) => item.partNumber === 'B110475');
  assert.ok(line);
  assertWithin(line.monthly, 35, 0.01);
});

test('calculator parity: OCI Batch 4 jobs stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Batch 4 jobs');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 8, 0.01);
  const line = quote.lineItems.find((item) => item.partNumber === 'B112107');
  assert.ok(line);
  assertWithin(line.monthly, 8, 0.01);
});

test('calculator parity: Health Checks 5 endpoints stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Health Checks 5 endpoints');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 6.5, 0.01);
  const line = quote.lineItems.find((item) => item.partNumber === 'B90325');
  assert.ok(line);
  assertWithin(line.monthly, 6.5, 0.01);
});

test('calculator parity: OCI Compute GPU - A10 with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute GPU - A10 with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 2678.4, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B95909');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 2678.4, 0.001);
});

test('calculator parity: OCI Compute GPU - A100 - v2 with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute GPU - A100 - v2 with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 3571.2, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B95910');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 3571.2, 0.001);
});

test('calculator parity: OCI Compute GPU - E3 with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute GPU - E3 with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1785.6, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B95911');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 1785.6, 0.001);
});

test('calculator parity: OCI Compute GPU - B200 with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute GPU - B200 with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 9225.6, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B95912');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 9225.6, 0.001);
});

test('calculator parity: OCI Compute GPU - GB200 with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute GPU - GB200 with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 10564.8, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B95913');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 10564.8, 0.001);
});

test('calculator parity: Big Data Service - Compute - HPC with 16 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Big Data Service - Compute - HPC with 16 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 3928.32, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B91130');
  assert.ok(line);
  assert.equal(line.quantity, 16);
  assertWithin(line.monthly, 3928.32, 0.001);
});

test('calculator parity: OCI Compute HPC - X7 with 52 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute HPC - X7 with 52 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 11606.4, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B90398');
  assert.ok(line);
  assert.equal(line.quantity, 52);
  assertWithin(line.monthly, 11606.4, 0.001);
});

test('calculator parity: OCI Compute HPC - E5 with 40 OCPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute HPC - E5 with 40 OCPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 8035.2, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B96531');
  assert.ok(line);
  assert.equal(line.quantity, 40);
  assertWithin(line.monthly, 8035.2, 0.001);
});

test('calculator parity: Bare Metal GPU Standard - X7 - Metered with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Bare Metal GPU Standard - X7 - Metered with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 4761.6, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B89141');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 4761.6, 0.001);
});

test('calculator parity: Bare Metal GPU Standard - X7 with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Bare Metal GPU Standard - X7 with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 4315.2, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B88517');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 4315.2, 0.001);
});

test('calculator parity: Virtual Machine GPU Standard - X7 with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Compute - Virtual Machine GPU Standard - X7 with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 4017.6, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B88518');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 4017.6, 0.001);
});

test('calculator parity: GPU Standard - V2 - Metered with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote GPU Standard - V2 - Metered with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 3571.2, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B89735');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 3571.2, 0.001);
});

test('calculator parity: GPU Standard - V2 with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote GPU Standard - V2 with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 3273.6, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B89734');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 3273.6, 0.001);
});

test('calculator parity: OCI Compute GPU - H100 with 4 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute GPU - H100 with 4 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 14284.8, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B98415');
  assert.ok(line);
  assert.equal(line.quantity, 4);
  assertWithin(line.monthly, 14284.8, 0.001);
});

test('calculator parity: OCI Compute GPU - L40S with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute GPU - L40S with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 5356.8, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B98416');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 5356.8, 0.001);
});

test('calculator parity: Oracle Compute Cloud@Customer - Compute - GPU.L40S with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Oracle Compute Cloud@Customer - Compute - GPU.L40S with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 5208, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B110965');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 5208, 0.001);
});

test('calculator parity: Oracle Compute Cloud@Customer - Compute - GPU.L40S - Resource Commit with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Oracle Compute Cloud@Customer - Compute - GPU.L40S - Resource Commit with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 892.8, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B111454');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 892.8, 0.001);
});

test('calculator parity: VM.Standard.E2.1.Micro with 1 OCPU for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote VM.Standard.E2.1.Micro with 1 OCPU for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 0, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B91444');
  assert.ok(line);
  assert.equal(line.quantity, 1);
  assertWithin(line.monthly, 0, 0.001);
});

test('calculator parity: OCI Compute GPU - H200 with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute GPU - H200 with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 8035.2, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B98417');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 8035.2, 0.001);
});

test('calculator parity: OCI Compute GPU - MI300X with 2 GPUs for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Compute GPU - MI300X with 2 GPUs for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 6249.6, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B98418');
  assert.ok(line);
  assert.equal(line.quantity, 2);
  assertWithin(line.monthly, 6249.6, 0.001);
});

test('calculator parity: Data Integration workspace usage 2 workspaces 744h/month stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Data Integration workspace usage 2 workspaces 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 238.08, 0.01);
  const line = quote.lineItems.find((item) => item.partNumber === 'B92598');
  assert.ok(line);
  assertWithin(line.monthly, 238.08, 0.01);
});

test('calculator parity: Data Integration 150 GB processed per hour for 744h/month stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Data Integration 150 GB processed per hour for 744h/month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 4464, 0.1);
  const line = quote.lineItems.find((item) => item.partNumber === 'B92599');
  assert.ok(line);
  assertWithin(line.monthly, 4464, 0.1);
});

test('calculator parity: OCI Generative AI Vector Store Retrieval 5000 requests stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Generative AI Vector Store Retrieval 5000 requests');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 2.5, 0.01);
  const line = quote.lineItems.find((item) => item.partNumber === 'B112416');
  assert.ok(line);
  assertWithin(line.monthly, 2.5, 0.01);
});

test('calculator parity: OCI Generative AI Web Search 12000 requests stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Generative AI Web Search 12000 requests');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 120, 0.01);
  const line = quote.lineItems.find((item) => item.partNumber === 'B111973');
  assert.ok(line);
  assertWithin(line.monthly, 120, 0.01);
});

test('calculator parity: OCI Generative AI Agents Data Ingestion 100000 transactions stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Generative AI Agents Data Ingestion 100000 transactions');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 0.003, 0.0001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B110463');
  assert.ok(line);
  assertWithin(line.monthly, 0.003, 0.0001);
});

test('calculator parity: OCI Generative AI Small Cohere 50000 transactions stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Generative AI Small Cohere 50000 transactions');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 0.0045, 0.0001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B108078');
  assert.ok(line);
  assertWithin(line.monthly, 0.0045, 0.0001);
});

test('calculator parity: OCI Generative AI Embed Cohere 50000 transactions stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Generative AI Embed Cohere 50000 transactions');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 0.005, 0.0001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B108079');
  assert.ok(line);
  assertWithin(line.monthly, 0.005, 0.0001);
});

test('calculator parity: OCI Generative AI Large Meta 50000 transactions stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Generative AI Large Meta 50000 transactions');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 0.009, 0.0001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B108080');
  assert.ok(line);
  assertWithin(line.monthly, 0.009, 0.0001);
});

test('calculator parity: OCI Generative AI knowledge base storage 50 GB for 744 hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Generative AI knowledge base storage 50 GB for 744 hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 312.48, 0.01);
  const line = quote.lineItems.find((item) => item.partNumber === 'B110462');
  assert.ok(line);
  assertWithin(line.monthly, 312.48, 0.01);
});

test('calculator parity: Vision Custom Training 10 training hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Vision Custom Training 10 training hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 14.7, 0.01);
  const line = quote.lineItems.find((item) => item.partNumber === 'B94977');
  assert.ok(line);
  assertWithin(line.monthly, 14.7, 0.01);
});

test('calculator parity: Speech 3 transcription hours stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Speech 3 transcription hours');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 0.048, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B94896');
  assert.ok(line);
  assertWithin(line.monthly, 0.048, 0.001);
});

test('calculator parity: OCI Vision Image Analysis 10000 transactions stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Vision Image Analysis 10000 transactions');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1.25, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B94973');
  assert.ok(line);
  assertWithin(line.monthly, 1.25, 0.001);
});

test('calculator parity: OCI Vision OCR 10000 transactions stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Vision OCR 10000 transactions');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 5, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B94974');
  assert.ok(line);
  assertWithin(line.monthly, 5, 0.001);
});

test('calculator parity: Media Flow HD below 30fps 120 minutes stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Media Flow HD below 30fps 120 minutes of output media content');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 0.72, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B95282');
  assert.ok(line);
  assertWithin(line.monthly, 0.72, 0.001);
});

test('calculator parity: OCI Vision Stored Video Analysis 90 processed video minutes stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Vision Stored Video Analysis 90 processed video minutes');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 0.27, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B110617');
  assert.ok(line);
  assertWithin(line.monthly, 0.27, 0.001);
});

test('calculator parity: OCI Vision Stream Video Analysis 90 processed video minutes stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Vision Stream Video Analysis 90 processed video minutes');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 13.5, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B111539');
  assert.ok(line);
  assertWithin(line.monthly, 13.5, 0.001);
});

test('calculator parity: IAM SMS 12 messages stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote IAM SMS 12 SMS messages');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 0.24, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B93496');
  assert.ok(line);
  assertWithin(line.monthly, 0.24, 0.001);
});

test('calculator parity: OCI AI Language 2500 transactions stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI AI Language 2500 transactions');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1.25, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B93423');
  assert.ok(line);
  assertWithin(line.monthly, 1.25, 0.001);
});

test('calculator parity: Oracle Threat Intelligence Service 2000 API calls stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Oracle Threat Intelligence Service 2000 API calls');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 1.2, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B94173');
  assert.ok(line);
  assertWithin(line.monthly, 1.2, 0.001);
});

test('calculator parity: Notifications SMS Outbound to Country Zone 1 100 messages stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Notifications SMS Outbound to Country Zone 1 100 messages');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 0, 0.0001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B93004');
  assert.ok(line);
  assertWithin(line.monthly, 0, 0.0001);
});

test('calculator parity: Archive Storage 5 TB per month stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Archive Storage 5 TB per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 13.286, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B91633');
  assert.ok(line);
  assertWithin(line.monthly, 13.286, 0.001);
});

test('calculator parity: Infrequent Access Storage 10 TB per month stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Infrequent Access Storage 10 TB per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 102.3, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B93000');
  assert.ok(line);
  assertWithin(line.monthly, 102.3, 0.001);
});

test('calculator parity: Infrequent Access Storage retrieval 500 GB per month stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Infrequent Access Storage retrieval 500 GB per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 4.9, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B93001');
  assert.ok(line);
  assertWithin(line.monthly, 4.9, 0.001);
});

test('calculator parity: Object Storage Requests 100000 requests per month stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote Object Storage Requests 100000 requests per month');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 0.017, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B91627');
  assert.ok(line);
  assertWithin(line.monthly, 0.017, 0.001);
});

test('calculator parity: OCI Generative AI Large Cohere 25000 transactions stays aligned', () => {
  const index = buildCalculatorIndex();
  const quote = quoteFromPrompt(index, 'Quote OCI Generative AI Large Cohere 25000 transactions');

  assert.equal(quote.ok, true);
  assertWithin(quote.totals.monthly, 3.75, 0.001);
  const line = quote.lineItems.find((item) => item.partNumber === 'B108077');
  assert.ok(line);
  assertWithin(line.monthly, 3.75, 0.001);
});
