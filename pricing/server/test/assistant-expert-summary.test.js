'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadAssistantWithStubs, buildIndex, assertWithin } = require('./assistant-test-helpers');

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

