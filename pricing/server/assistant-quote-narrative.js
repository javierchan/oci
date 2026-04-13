'use strict';

const { inferConsumptionPattern, explainConsumptionPattern } = require('./consumption-model');

function inferQuoteTechnologyProfile(quote) {
  const request = quote?.request || {};
  const lineItems = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const blob = [
    request?.source || '',
    request?.serviceFamily || '',
    request?.metadata?.inventorySource || '',
    ...lineItems.map((line) => `${line.service || ''} ${line.product || ''} ${line.metric || ''}`),
  ].join('\n').toLowerCase();

  if (request?.metadata?.inventorySource === 'rvtools' || /\bvmware\b|\brvtools\b/.test(blob)) {
    return {
      key: 'vmware-migration',
      role: 'OCI VMware migration specialist',
      name: 'VMware migration to OCI',
      focus: 'right-sizing, VMware vCPU to OCI OCPU normalization, exclusion of platform VMs, and follow-up items such as Windows licensing',
    };
  }
  const storageSignalCount = [
    /\bfile storage\b/.test(blob),
    /\bobject storage\b/.test(blob),
    /\bblock volume\b/.test(blob),
  ].filter(Boolean).length;
  const edgeSignalCount = [
    /\bdns\b/.test(blob),
    /\bload balancer\b/.test(blob),
    /\bfastconnect\b/.test(blob),
    /\bnetwork firewall\b/.test(blob),
    /\bwaf\b|\bweb application firewall\b/.test(blob),
  ].filter(Boolean).length;

  const scoreMonthly = (patterns) => lineItems.reduce((sum, line) => {
    const lineBlob = `${line.service || ''} ${line.product || ''} ${line.metric || ''}`.toLowerCase();
    if (patterns.some((pattern) => pattern.test(lineBlob))) return sum + Number(line.monthly || 0);
    return sum;
  }, 0);

  const networkPatterns = [/\bfastconnect\b/, /\bload balancer\b/, /\bdns\b/, /\bnetwork firewall\b/, /\bwaf\b|\bweb application firewall\b/];
  const databasePatterns = [/\bautonomous\b/, /\bdatabase\b/, /\bexadata\b/, /\bdata safe\b/];
  const serverlessAiPatterns = [/\bfunctions\b/, /\bgenerative ai\b/, /\bvector store\b/, /\bweb search\b/, /\bagents\b/, /\bapi gateway\b/];
  const analyticsPatterns = [/\bintegration cloud\b/, /\banalytics cloud\b/, /\bdata integration\b/];
  const observabilityPatterns = [/\bmonitoring\b/, /\blog analytics\b/, /\bnotifications\b/, /\bhealth checks\b/];
  const operationsPatterns = [/\bfleet application management\b/, /\boci batch\b/, /\bbatch\b/, /\bemail delivery\b/, /\biam sms\b/];
  const computeStoragePatterns = [/\bcompute\b/, /\bflex\b/, /\bocpu\b/, /\bram\b/, /\bblock volume\b/, /\bobject storage\b/, /\bfile storage\b/];

  const databaseMonthly = scoreMonthly(databasePatterns);
  const networkMonthly = scoreMonthly(networkPatterns);
  const serverlessAiMonthly = scoreMonthly(serverlessAiPatterns);
  const analyticsMonthly = scoreMonthly(analyticsPatterns);
  const observabilityMonthly = scoreMonthly(observabilityPatterns);
  const operationsMonthly = scoreMonthly(operationsPatterns);
  const computeStorageMonthly = scoreMonthly(computeStoragePatterns);
  const totalMonthly = lineItems.reduce((sum, line) => sum + Number(line.monthly || 0), 0) || 0;
  const maxDomainShare = totalMonthly > 0
    ? Math.max(
      networkMonthly,
      databaseMonthly,
      serverlessAiMonthly,
      analyticsMonthly,
      observabilityMonthly + operationsMonthly,
      computeStorageMonthly,
    ) / totalMonthly
    : 0;
  const signalDomainCount = [
    networkPatterns.some((pattern) => pattern.test(blob)),
    databasePatterns.some((pattern) => pattern.test(blob)),
    serverlessAiPatterns.some((pattern) => pattern.test(blob)),
    analyticsPatterns.some((pattern) => pattern.test(blob)),
    observabilityPatterns.some((pattern) => pattern.test(blob)),
    operationsPatterns.some((pattern) => pattern.test(blob)),
    computeStoragePatterns.some((pattern) => pattern.test(blob)),
  ].filter(Boolean).length;

  const hasAnalyticsSignals = analyticsPatterns.filter((pattern) => pattern.test(blob)).length >= 2;
  const hasDatabaseSignals = databasePatterns.some((pattern) => pattern.test(blob));
  const hasObservabilitySignals = observabilityPatterns.filter((pattern) => pattern.test(blob)).length >= 2;
  const hasOperationsSignals = operationsPatterns.filter((pattern) => pattern.test(blob)).length >= 2;

  if (signalDomainCount >= 5 && maxDomainShare <= 0.75) {
    return {
      key: 'solutions-architecture',
      role: 'OCI solutions architect',
      name: 'OCI multi-service architecture',
      focus: 'cross-domain cost drivers across compute, storage, networking, database, observability, and platform services, plus which components are foundational versus workload-specific',
    };
  }

  if (hasDatabaseSignals && totalMonthly > 0 && databaseMonthly / totalMonthly >= 0.35) {
    return {
      key: 'database',
      role: 'OCI database architect',
      name: 'OCI database platform',
      focus: 'license model, compute plus storage composition, and prerequisites or infrastructure components that may sit outside the direct metered lines',
    };
  }
  if (hasObservabilitySignals && totalMonthly > 0 && observabilityMonthly / totalMonthly >= 0.2 && operationsMonthly / totalMonthly < 0.15) {
    return {
      key: 'observability',
      role: 'OCI observability architect',
      name: 'OCI observability and notifications',
      focus: 'ingestion, retrieval, storage-unit, and delivery-operation metrics across monitoring, log analytics, and notifications',
    };
  }
  if (hasOperationsSignals && totalMonthly > 0 && (operationsMonthly / totalMonthly >= 0.15 || (observabilityMonthly + operationsMonthly) / totalMonthly >= 0.3)) {
    return {
      key: 'operations-platform',
      role: 'OCI operations and platform services architect',
      name: 'OCI operations and platform services',
      focus: 'counted operational units, observability storage and retrieval metrics, and which lines are free-tier versus usage-bearing',
    };
  }
  if (hasAnalyticsSignals && totalMonthly > 0 && analyticsMonthly / totalMonthly >= 0.25) {
    return {
      key: 'analytics-integration',
      role: 'OCI analytics and integration architect',
      name: 'OCI analytics and integration services',
      focus: 'user, OCPU/ECPU, data processed, and storage-unit metrics, plus BYOL versus License Included where applicable',
    };
  }
  if (storageSignalCount >= 2 && edgeSignalCount <= 2) {
    return {
      key: 'compute-storage',
      role: 'OCI compute and storage architect',
      name: 'OCI compute and storage platform',
      focus: 'shape selection, OCPU and memory sizing, attached storage assumptions, and whether usage is capacity-driven or hourly',
    };
  }
  const profiles = [
    {
      key: 'network-security',
      role: 'OCI networking and security architect',
      name: 'OCI networking and edge security',
      focus: 'port-hour, bandwidth, request, and processed-data dimensions, plus which components are fixed versus usage-driven',
      patterns: [/\bfastconnect\b/, /\bload balancer\b/, /\bdns\b/, /\bnetwork firewall\b/, /\bwaf\b|\bweb application firewall\b/],
    },
    {
      key: 'database',
      role: 'OCI database architect',
      name: 'OCI database platform',
      focus: 'license model, compute plus storage composition, and prerequisites or infrastructure components that may sit outside the direct metered lines',
      patterns: [/\bautonomous\b/, /\bdatabase\b/, /\bexadata\b/, /\bdata safe\b/],
    },
    {
      key: 'serverless-ai',
      role: 'OCI serverless and AI architect',
      name: 'OCI serverless and AI services',
      focus: 'request volume, execution sizing, token or transaction metrics, and when a service is dedicated versus serverless',
      patterns: [/\bfunctions\b/, /\bgenerative ai\b/, /\bvector store\b/, /\bweb search\b/, /\bagents\b/],
    },
    {
      key: 'operations-platform',
      role: 'OCI operations and platform services architect',
      name: 'OCI operations and platform services',
      focus: 'counted operational units such as jobs, managed resources, and delivery volumes, plus which lines are free-tier versus usage-bearing',
      patterns: [/\bfleet application management\b/, /\boci batch\b/, /\bbatch\b/, /\bemail delivery\b/],
    },
    {
      key: 'observability',
      role: 'OCI observability architect',
      name: 'OCI observability and notifications',
      focus: 'ingestion, retrieval, storage-unit, and delivery-operation metrics across monitoring, log analytics, and notifications',
      patterns: [/\bmonitoring\b/, /\blog analytics\b/, /\bnotifications\b/, /\bhealth checks\b/],
    },
    {
      key: 'analytics-integration',
      role: 'OCI analytics and integration architect',
      name: 'OCI analytics and integration services',
      focus: 'user, OCPU/ECPU, data processed, and storage-unit metrics, plus BYOL versus License Included where applicable',
      patterns: [/\bintegration cloud\b/, /\banalytics cloud\b/, /\bdata integration\b/],
    },
    {
      key: 'ai-media',
      role: 'OCI AI and media services architect',
      name: 'OCI AI and media services',
      focus: 'training-hour, transcription-hour, and processed-minute metrics across OCI AI and media pipelines',
      patterns: [/\bvision\b/, /\bspeech\b/, /\bmedia flow\b/, /\bprocessed video\b/],
    },
    {
      key: 'compute-storage',
      role: 'OCI compute and storage architect',
      name: 'OCI compute and storage platform',
      focus: 'shape selection, OCPU and memory sizing, attached storage assumptions, and whether usage is capacity-driven or hourly',
      patterns: [/\bcompute\b/, /\bflex\b/, /\bocpu\b/, /\bram\b/, /\bblock volume\b/, /\bobject storage\b/, /\bfile storage\b/],
    },
  ];
  const scored = profiles
    .map((profile) => ({
      profile,
      score: profile.patterns.reduce((sum, pattern) => sum + (pattern.test(blob) ? 1 : 0), 0),
    }))
    .sort((a, b) => b.score - a.score);
  if (scored[0]?.score > 0) return scored[0].profile;
  return {
    key: 'general',
    role: 'OCI pricing specialist',
    name: 'General OCI pricing',
    focus: 'the main billable dimensions, assumptions, and follow-up checks that a customer should validate before taking the estimate as final',
  };
}

function buildDeterministicExpertSummary(quote) {
  const profile = inferQuoteTechnologyProfile(quote);
  const totals = quote?.totals || {};
  const currencyCode = totals.currencyCode || 'USD';
  const lineItems = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const topDrivers = [...lineItems]
    .sort((a, b) => Number(b.monthly || 0) - Number(a.monthly || 0))
    .slice(0, 3);
  const sections = [];

  sections.push('## OCI Expert Summary');
  sections.push(`- Perspective: **${profile.role}**.`);
  sections.push(`- This estimate is centered on **${profile.name}** pricing.`);
  sections.push(`- Monthly total: ${formatMoney(totals.monthly, currencyCode)}. Annual total: ${formatMoney(totals.annual, currencyCode)}.`);
  sections.push(`- The quote contains ${lineItems.length} priced line${lineItems.length === 1 ? '' : 's'} derived from the OCI catalog and deterministic pricing rules.`);
  if (topDrivers.length) {
    sections.push(`- Main cost drivers: ${topDrivers.map((line) => `\`${line.partNumber}\` (${line.product}) = ${formatMoney(line.monthly, currencyCode)}/month`).join('; ')}.`);
  }

  return sections.join('\n');
}

function buildDeterministicConsiderationsFallback(quote, assumptions) {
  const profile = inferQuoteTechnologyProfile(quote);
  const sections = [];

  sections.push('## OCI Considerations');
  if (profile.key === 'vmware-migration') {
    sections.push('- Validate that non-migrated VMware platform VMs stay excluded from the target scope.');
    sections.push('- Review Windows workloads separately because OCI infrastructure pricing does not automatically include Microsoft licensing adjustments in this pass.');
  } else if (profile.key === 'network-security') {
    sections.push('- As an OCI networking/security review, validate throughput assumptions, request volumes, and whether the edge controls shown here align with the intended ingress and egress paths.');
    sections.push('- Review which lines are fixed monthly components versus variable traffic or request-driven charges.');
    sections.push('- Confirm whether the quoted edge/security services match the intended throughput and request profile.');
  } else if (profile.key === 'database') {
    sections.push('- As an OCI database review, validate the service architecture first: Base DB, Autonomous, and Exadata families have materially different operational and licensing behavior.');
    sections.push('- Confirm the intended license model before taking the quote as final if the family supports BYOL and License Included variants.');
    sections.push('- Review whether any deployment or infrastructure prerequisites sit outside the direct metered lines shown here.');
  } else if (profile.key === 'serverless-ai') {
    sections.push('- As an OCI serverless/AI review, validate whether the service is genuinely usage-driven or whether Oracle exposes it as a dedicated hourly construct in the live catalog.');
    sections.push('- Validate request volume and execution sizing because those two dimensions usually dominate the monthly result.');
    sections.push('- For dedicated AI services, confirm whether the catalog exposes the service as usage-based or hour-based before assuming a transactional quote.');
  } else if (profile.key === 'operations-platform') {
    sections.push('- As an OCI operations/platform services review, validate which lines are truly paid units versus free-tier operational counts.');
    sections.push('- Review whether the quoted counts match the intended managed-resource, job, or notification-delivery volumes for the target operating model.');
  } else if (profile.key === 'solutions-architecture') {
    sections.push('- As an OCI solutions-architecture review, validate the service boundaries first: this quote spans multiple OCI domains and should be checked as an integrated platform, not as a single-service estimate.');
    sections.push('- Review which lines are foundational platform components versus workload-specific consumption, because those categories usually drive optimization decisions differently.');
    sections.push('- Confirm the intended commercial model for each major domain, especially where user-based, request-based, and infrastructure-based pricing are mixed together.');
  } else if (profile.key === 'analytics-integration') {
    sections.push('- As an OCI analytics/integration review, verify which commercial unit actually applies: users, OCPUs/ECPUs, processed data, or storage units.');
    sections.push('- Confirm whether the service is billed by users, OCPUs/ECPUs, storage units, or data processed, because different variants in the same family bill differently.');
    sections.push('- Review BYOL versus License Included where the selected product family supports both modes.');
  } else if (profile.key === 'compute-storage') {
    sections.push('- As an OCI compute/storage review, validate shape family, OCPU-to-memory ratio, and whether block or object storage should be sized from provisioned capacity or observed consumption.');
    sections.push('- Review whether attached storage should remain block-based or whether file or object storage would better match the workload pattern.');
  } else {
    sections.push(`- Main OCI expert focus for this estimate: ${profile.focus}.`);
    if (assumptions.length) sections.push('- Validate the sizing assumptions before treating the quote as final.');
  }

  return sections.join('\n');
}

function formatMoney(value, currencyCode = 'USD') {
  const num = Number(value);
  if (!Number.isFinite(num)) return `${currencyCode} -`;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currencyCode,
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(num);
}

function buildConsumptionExplanation(quote) {
  const items = Array.isArray(quote?.lineItems) ? quote.lineItems : [];
  const patternEntries = [];
  const seenPatterns = new Set();
  for (const line of items) {
    const pattern = inferConsumptionPattern(line.metric, `${line.service} ${line.product}`);
    if (!pattern || pattern === 'unknown' || seenPatterns.has(pattern)) continue;
    seenPatterns.add(pattern);
    patternEntries.push({ pattern, line });
  }

  if (patternEntries.length <= 3 && items.length <= 6) {
    return patternEntries.map(({ pattern, line }) => {
      const text = explainConsumptionPattern(pattern, {
        displayName: line.product,
        fullDisplayName: line.product,
      });
      return text ? `- ${text}` : null;
    }).filter(Boolean);
  }

  const grouped = new Map();
  for (const line of items) {
    const pattern = inferConsumptionPattern(line.metric, `${line.service} ${line.product}`);
    const group = classifyConsumptionGroup(pattern, line);
    if (!grouped.has(group.key)) grouped.set(group.key, { ...group, examples: [], patterns: new Set() });
    const bucket = grouped.get(group.key);
    bucket.patterns.add(pattern);
    if (bucket.examples.length < 3) bucket.examples.push(line.product);
  }

  const priority = ['compute', 'storage', 'requests', 'users', 'platform', 'media', 'network', 'other'];
  return Array.from(grouped.values())
    .sort((a, b) => priority.indexOf(a.key) - priority.indexOf(b.key))
    .slice(0, 5)
    .map((group) => {
      const examples = Array.from(new Set(group.examples)).slice(0, 2).map((item) => `\`${item}\``).join(', ');
      return `- ${group.description}${examples ? ` Example lines: ${examples}.` : ''}`;
    });
}

function classifyConsumptionGroup(pattern, line) {
  const serviceBlob = `${line?.service || ''} ${line?.product || ''}`.toLowerCase();
  if (['ocpu-hour', 'ecpu-hour', 'memory-gb-hour', 'functions-gb-memory-seconds', 'functions-invocations-million'].includes(pattern)) {
    return {
      key: 'compute',
      description: 'Compute-style charges are driven by provisioned CPU, memory, or execution usage over time. For hourly SKUs the requested size is multiplied by monthly hours; for serverless functions OCI separately charges execution memory-seconds and invocation volume.',
    };
  }
  if (['capacity-gb-month', 'performance-units-per-gb-month', 'log-analytics-storage-unit-month'].includes(pattern)) {
    return {
      key: 'storage',
      description: 'Storage-style charges are driven by provisioned or retained capacity. OCI bills GB-month, performance density, or storage-unit constructs depending on the storage service.',
    };
  }
  if (['requests', 'count-each', 'data-processed-gb-month', 'data-processed-gb-hour'].includes(pattern)) {
    return {
      key: 'requests',
      description: 'Transaction and request charges are volume-based. The agent converts API calls, requests, processed traffic, deliveries, or counted items into the billing unit defined by each SKU.',
    };
  }
  if (pattern === 'users-per-month') {
    return {
      key: 'users',
      description: 'User-based charges are billed directly from the active user count per month rather than from hourly uptime.',
    };
  }
  if (['workspace-hour', 'execution-hour-utilized', 'generic-hourly', 'generic-monthly', 'utilized-hour'].includes(pattern)) {
    return {
      key: 'platform',
      description: 'Platform-service charges use service-specific hourly or monthly units such as workspaces, execution hours, or dedicated service hours, depending on the SKU metric.',
    };
  }
  if (pattern === 'media-output-minute') {
    return {
      key: 'media',
      description: 'Media and AI pipeline charges are billed from directly consumed training hours, transcription hours, or processed/output media minutes.',
    };
  }
  if (['port-hour', 'load-balancer-hour', 'bandwidth-mbps-hour'].includes(pattern) || /\bfastconnect\b|\bload balancer\b|\bdns\b|\bhealth checks?\b/.test(serviceBlob)) {
    return {
      key: 'network',
      description: 'Network charges are driven by provisioned connectivity, bandwidth configuration, or request/query volume depending on the service.',
    };
  }
  return {
    key: 'other',
    description: 'Some lines use OCI service-specific billing units that are quoted directly from the catalog metric attached to the SKU.',
  };
}

module.exports = {
  buildConsumptionExplanation,
  buildDeterministicConsiderationsFallback,
  buildDeterministicExpertSummary,
  classifyConsumptionGroup,
  formatMoney,
  inferQuoteTechnologyProfile,
};
