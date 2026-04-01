'use strict';

const SERVICE_FAMILIES = [
  {
    id: 'compute_vm_generic',
    canonical: 'OCI Compute Virtual Machine',
    domain: 'compute',
    resolver: 'compute_vm_generic',
    aliases: [/\bvirtual machine\b/i, /\bcompute instance\b/i, /\bvm instance\b/i, /\bvm\b/i],
    clarifyRequired: ['ocpus', 'memoryGb', 'shapeSeries'],
    clarificationQuestion: 'Which OCI VM shape should I use for that machine? For Intel, common options are `E4.Flex` or `E5.Flex`. Once you pick the shape, I can combine it with the attached Block Volume sizing.',
    rescueInputs: [],
  },
  {
    id: 'storage_block',
    canonical: 'OCI Block Volume',
    domain: 'storage',
    resolver: 'block_volume',
    aliases: [/\bblock volumes?\b/i, /\bblock storage\b/i],
    rescueInputs: ['capacityGb'],
    buildRequest(inputs = {}) {
      const gb = numberLike(inputs.capacityGb);
      const vpu = numberLike(inputs.vpuPerGb);
      if (gb && vpu) return `Quote OCI Block Volume with ${gb} GB and ${vpu} VPUs`;
      if (gb) return `Quote OCI Block Volume with ${gb} GB`;
      return 'Quote OCI Block Volume';
    },
  },
  {
    id: 'storage_file',
    canonical: 'OCI File Storage',
    domain: 'storage',
    resolver: 'file_storage',
    aliases: [/\bfile storage\b/i, /\boci file storage\b/i],
    rescueInputs: ['capacityGb'],
    buildRequest(inputs = {}) {
      const gb = numberLike(inputs.capacityGb);
      const vpu = numberLike(inputs.vpuPerGb);
      const parts = ['Quote OCI File Storage'];
      if (gb) parts.push(`with ${gb} GB`);
      if (vpu) parts.push(`${vpu} performance units per GB`);
      return parts.join(', ');
    },
  },
  {
    id: 'network_fastconnect',
    canonical: 'OCI FastConnect',
    domain: 'network',
    resolver: 'fastconnect',
    aliases: [/\bfast\s*connect\b/i, /\bfastconnect\b/i],
    rescueInputs: ['bandwidthGbps'],
    buildRequest(inputs = {}, semantic = {}) {
      const gbps = numberLike(inputs.bandwidthGbps);
      if (!gbps) return 'Quote OCI FastConnect';
      return semantic?.annualRequested
        ? `Quote OCI FastConnect ${gbps} Gbps annually`
        : `Quote OCI FastConnect ${gbps} Gbps`;
    },
  },
  {
    id: 'network_firewall',
    canonical: 'OCI Network Firewall',
    domain: 'network',
    resolver: 'network_firewall',
    aliases: [/\bnetwork firewall\b/i, /\boci network firewall\b/i],
    rescueInputs: ['firewallInstances', 'dataProcessedGb'],
    clarifyRequired: ['firewallInstances', 'dataProcessedGb'],
    clarificationQuestion: 'How many Network Firewall instances do you need and how many GB of data will be processed per month?',
    buildRequest(inputs = {}) {
      const instances = numberLike(inputs.firewallInstances);
      const dataGb = numberLike(inputs.dataProcessedGb);
      const parts = ['Quote OCI Network Firewall'];
      if (instances) parts.push(`with ${instances} firewall instances`);
      if (dataGb) parts.push(`${dataGb} GB of data processed per month`);
      return parts.join(', ');
    },
  },
  {
    id: 'observability_log_analytics',
    canonical: 'OCI Log Analytics',
    domain: 'observability',
    resolver: 'log_analytics',
    aliases: [/\blog(?:ging)? analytics\b/i, /\boci log analytics\b/i],
    rescueInputs: ['capacityGb'],
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const gb = numberLike(inputs.capacityGb);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const archivalRequested = /\barchiv(?:e|al)\b/i.test(source);
      const parts = [archivalRequested ? 'Quote OCI Log Analytics Archival Storage' : 'Quote OCI Log Analytics Active Storage'];
      if (gb) parts.push(`with ${gb} GB per month`);
      return parts.join(', ');
    },
  },
  {
    id: 'security_data_safe',
    canonical: 'OCI Data Safe',
    domain: 'security',
    resolver: 'data_safe',
    aliases: [/\bdata safe\b/i, /\boci data safe\b/i],
    rescueAnyInputs: ['quantity'],
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const count = numberLike(inputs.quantity);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const onPremises = /\bon-?prem(?:ises)?\b|\bdatabases? on compute\b|\btarget databases?\b/i.test(source);
      const dbCloud = /\bdatabase cloud service\b/i.test(source);
      const parts = [onPremises
        ? 'Quote Data Safe for On-Premises Databases'
        : dbCloud
          ? 'Quote Data Safe for Database Cloud Service'
          : 'Quote OCI Data Safe'];
      if (count) parts.push(onPremises ? `${count} target databases` : `${count} databases`);
      return parts.join(' ');
    },
  },
  {
    id: 'devops_batch',
    canonical: 'OCI Batch',
    domain: 'devops',
    resolver: 'batch',
    aliases: [/\boci batch\b/i, /\bbatch\b/i],
    rescueAnyInputs: ['quantity'],
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.quantity);
      const parts = ['Quote OCI Batch'];
      if (count) parts.push(`${count} jobs`);
      return parts.join(' ');
    },
  },
  {
    id: 'ai_agents_data_ingestion',
    canonical: 'OCI Generative AI Agents - Data Ingestion',
    domain: 'analytics',
    resolver: 'ai_agents_data_ingestion',
    aliases: [/\bgenerative ai agents\b[^\n]*\bdata ingestion\b/i, /\bagents data ingestion\b/i],
    rescueAnyInputs: ['requestCount'],
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote OCI Generative AI Agents Data Ingestion'];
      if (count) parts.push(`${count} transactions`);
      return parts.join(' ');
    },
  },
  {
    id: 'ai_memory_ingestion',
    canonical: 'OCI Generative AI - Memory Ingestion',
    domain: 'analytics',
    resolver: 'ai_memory_ingestion',
    aliases: [/\bmemory ingestion\b/i, /\bgenerative ai\b[^\n]*\bmemory ingestion\b/i],
    rescueAnyInputs: ['requestCount'],
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote OCI Generative AI Memory Ingestion'];
      if (count) parts.push(`${count} events`);
      return parts.join(' ');
    },
  },
  {
    id: 'ai_rerank_dedicated',
    canonical: 'OCI Generative AI - Cohere Rerank - Dedicated',
    domain: 'analytics',
    aliases: [/\bcohere rerank\b/i, /\brerank\b/i],
    clarifyRequired: ['serviceHours'],
    clarificationQuestion: 'The current OCI catalog exposes Cohere Rerank as a dedicated Cluster Hour service. How many cluster-hours per month should I quote?',
    buildRequest(inputs = {}) {
      const hours = numberLike(inputs.serviceHours);
      const parts = ['Quote OCI Generative AI - Cohere Rerank - Dedicated'];
      if (hours) parts.push(`${hours} hours`);
      return parts.join(', ');
    },
  },
  {
    id: 'database_autonomous_tp',
    canonical: 'OCI Autonomous AI Transaction Processing',
    domain: 'database',
    resolver: 'autonomous_tp',
    aliases: [/\bautonomous(?: ai)? transaction processing\b/i, /\batp\b/i],
    rescueInputs: ['capacityGb', 'ecpus'],
    requireLicenseChoice: true,
    licenseClarificationQuestion: 'Do you want Autonomous AI Transaction Processing as BYOL or License Included?',
    clarificationQuestion: 'How many ECPUs and how many GB of storage do you need for Autonomous AI Transaction Processing?',
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const ecpus = numberLike(inputs.ecpus);
      const gb = numberLike(inputs.capacityGb);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const licenseMode = detectLicenseMode(source);
      const parts = ['Quote OCI Autonomous AI Transaction Processing'];
      if (licenseMode === 'byol') parts.push('BYOL');
      if (licenseMode === 'license-included') parts.push('License Included');
      if (ecpus) parts.push(`${ecpus} ECPUs`);
      if (gb) parts.push(`${gb} GB storage`);
      return parts.join(', ');
    },
  },
  {
    id: 'database_autonomous_dw',
    canonical: 'OCI Autonomous AI Lakehouse',
    domain: 'database',
    resolver: 'autonomous_dw',
    aliases: [/\bautonomous(?: ai)? lakehouse\b/i, /\bautonomous data warehouse\b/i, /\badw\b/i],
    rescueInputs: ['capacityGb', 'ecpus'],
    requireLicenseChoice: true,
    licenseClarificationQuestion: 'Do you want Autonomous AI Lakehouse as BYOL or License Included?',
    clarificationQuestion: 'How many ECPUs and how many GB of storage do you need for Autonomous AI Lakehouse?',
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const ecpus = numberLike(inputs.ecpus);
      const gb = numberLike(inputs.capacityGb);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const licenseMode = detectLicenseMode(source);
      const parts = ['Quote OCI Autonomous AI Lakehouse'];
      if (licenseMode === 'byol') parts.push('BYOL');
      if (licenseMode === 'license-included') parts.push('License Included');
      if (ecpus) parts.push(`${ecpus} ECPUs`);
      if (gb) parts.push(`${gb} GB storage`);
      return parts.join(', ');
    },
  },
  {
    id: 'database_base_db',
    canonical: 'OCI Base Database Service',
    domain: 'database',
    resolver: 'base_database',
    aliases: [/\bbase database service\b/i, /\bbase db\b/i],
    rescueInputs: ['capacityGb', 'databaseEdition'],
    rescueAnyInputs: ['ocpus', 'ecpus'],
    requireLicenseChoice: true,
    licenseClarificationQuestion: 'Do you want Base Database Service as BYOL or License Included?',
    clarificationQuestion: 'Which Base Database Service edition do you need, how many OCPUs or ECPUs, and how many GB of storage?',
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const edition = String(inputs.databaseEdition || '').trim();
      const ocpus = numberLike(inputs.ocpus);
      const ecpus = numberLike(inputs.ecpus);
      const gb = numberLike(inputs.capacityGb);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const licenseMode = detectLicenseMode(source);
      const parts = ['Quote OCI Base Database Service'];
      if (edition) parts.push(edition);
      if (licenseMode === 'byol') parts.push('BYOL');
      if (licenseMode === 'license-included') parts.push('License Included');
      if (ocpus) parts.push(`${ocpus} OCPUs`);
      if (ecpus) parts.push(`${ecpus} ECPUs`);
      if (gb) parts.push(`${gb} GB storage`);
      return parts.join(', ');
    },
  },
  {
    id: 'database_cloud_service',
    canonical: 'OCI Database Cloud Service',
    domain: 'database',
    resolver: 'database_cloud_service',
    aliases: [/\bdatabase cloud service\b/i, /\boracle database cloud service\b/i],
    rescueInputs: ['databaseEdition'],
    rescueAnyInputs: ['ocpus'],
    requireLicenseChoice: true,
    licenseClarificationQuestion: 'Do you want Database Cloud Service as BYOL or License Included?',
    clarificationQuestion: 'Which Database Cloud Service edition do you need and how many OCPUs?',
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const edition = String(inputs.databaseEdition || '').trim();
      const ocpus = numberLike(inputs.ocpus);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const licenseMode = detectLicenseMode(source);
      const parts = ['Quote OCI Database Cloud Service'];
      if (edition) parts.push(edition);
      if (licenseMode === 'byol') parts.push('BYOL');
      if (licenseMode === 'license-included') parts.push('License Included');
      if (ocpus) parts.push(`${ocpus} OCPUs`);
      return parts.join(', ');
    },
  },
  {
    id: 'database_exadata_exascale',
    canonical: 'OCI Exadata Exascale Database',
    domain: 'database',
    resolver: 'exadata_exascale',
    aliases: [/\bexadata exascale\b/i],
    rescueInputs: ['ecpus', 'capacityGb', 'databaseStorageModel'],
    requireLicenseChoice: true,
    licenseClarificationQuestion: 'Do you want Exadata Exascale Database as BYOL or License Included?',
    clarificationQuestion: 'For Exadata Exascale, how many ECPUs, how many GB of storage, and do you want smart database storage or filesystem storage?',
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const ecpus = numberLike(inputs.ecpus);
      const gb = numberLike(inputs.capacityGb);
      const storageModel = String(inputs.databaseStorageModel || '').trim();
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const licenseMode = detectLicenseMode(source);
      const parts = ['Quote OCI Exadata Exascale Database'];
      if (licenseMode === 'byol') parts.push('BYOL');
      if (licenseMode === 'license-included') parts.push('License Included');
      if (ecpus) parts.push(`${ecpus} ECPUs`);
      if (gb) parts.push(`${gb} GB storage`);
      if (storageModel) parts.push(storageModel);
      return parts.join(', ');
    },
  },
  {
    id: 'database_exadata_dedicated',
    canonical: 'OCI Exadata Dedicated Infrastructure Database',
    domain: 'database',
    resolver: 'exadata_dedicated',
    aliases: [/\bdedicated infrastructure exadata\b/i, /\bexadata dedicated infrastructure\b/i],
    rescueAnyInputs: ['ocpus', 'ecpus'],
    requireLicenseChoice: true,
    licenseClarificationQuestion: 'Do you want Exadata Dedicated Infrastructure Database as BYOL or License Included?',
    clarificationQuestion: 'How many OCPUs or ECPUs do you need for Exadata Dedicated Infrastructure Database?',
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const ocpus = numberLike(inputs.ocpus);
      const ecpus = numberLike(inputs.ecpus);
      const infraShape = String(inputs.exadataInfraShape || '').trim();
      const infraGeneration = String(inputs.exadataInfraGeneration || '').trim();
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const licenseMode = detectLicenseMode(source);
      const parts = ['Quote OCI Exadata Dedicated Infrastructure Database'];
      if (licenseMode === 'byol') parts.push('BYOL');
      if (licenseMode === 'license-included') parts.push('License Included');
      if (ocpus) parts.push(`${ocpus} OCPUs`);
      if (ecpus) parts.push(`${ecpus} ECPUs`);
      if (infraShape) {
        const shapeText = infraGeneration ? `${infraShape} ${infraGeneration}` : infraShape;
        parts.push(`on ${shapeText}`);
      }
      return parts.join(', ');
    },
  },
  {
    id: 'database_exadata_cloud_customer',
    canonical: 'OCI Exadata Cloud@Customer Database',
    domain: 'database',
    resolver: 'exadata_cloud_customer',
    aliases: [/\bexadata cloud@customer\b/i, /\bexadata cloud at customer\b/i, /\bcloud@customer exadata\b/i],
    rescueAnyInputs: ['ocpus', 'ecpus'],
    requireLicenseChoice: true,
    licenseClarificationQuestion: 'Do you want Exadata Cloud@Customer Database as BYOL or License Included?',
    clarificationQuestion: 'How many OCPUs or ECPUs do you need for Exadata Cloud@Customer Database?',
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const ocpus = numberLike(inputs.ocpus);
      const ecpus = numberLike(inputs.ecpus);
      const infraShape = String(inputs.exadataInfraShape || '').trim();
      const infraGeneration = String(inputs.exadataInfraGeneration || '').trim();
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const licenseMode = detectLicenseMode(source);
      const parts = ['Quote OCI Exadata Cloud@Customer Database'];
      if (licenseMode === 'byol') parts.push('BYOL');
      if (licenseMode === 'license-included') parts.push('License Included');
      if (ocpus) parts.push(`${ocpus} OCPUs`);
      if (ecpus) parts.push(`${ecpus} ECPUs`);
      if (infraShape) {
        const shapeText = infraGeneration ? `${infraShape} ${infraGeneration}` : infraShape;
        parts.push(`on ${shapeText}`);
      }
      return parts.join(', ');
    },
  },
  {
    id: 'analytics_oac_professional',
    canonical: 'Oracle Analytics Cloud Professional',
    domain: 'analytics',
    resolver: 'oac_professional',
    aliases: [/\boracle analytics cloud professional\b/i, /\boac professional\b/i],
    rescueInputs: [],
    rescueAnyInputs: ['ocpus', 'users'],
    clarifyAnyInputs: ['ocpus', 'users'],
    requireLicenseChoice: true,
    licenseNotRequiredWhenAnyInputs: ['users'],
    licenseClarificationQuestion: 'Do you want Oracle Analytics Cloud Professional as BYOL or License Included?',
    clarificationQuestion: 'For Oracle Analytics Cloud Professional, should I quote named users or OCPUs, and what count should I use?',
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const ocpus = numberLike(inputs.ocpus);
      const users = numberLike(inputs.users);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const licenseMode = detectLicenseMode(source);
      const parts = ['Quote Oracle Analytics Cloud Professional'];
      if (licenseMode === 'byol') parts.push('BYOL');
      if (licenseMode === 'license-included') parts.push('License Included');
      if (ocpus) parts.push(`${ocpus} OCPUs`);
      if (users) parts.push(`${users} users`);
      return parts.join(', ');
    },
  },
  {
    id: 'analytics_oac_enterprise',
    canonical: 'Oracle Analytics Cloud Enterprise',
    domain: 'analytics',
    resolver: 'oac_enterprise',
    aliases: [/\boracle analytics cloud enterprise\b/i, /\boac enterprise\b/i],
    rescueInputs: [],
    rescueAnyInputs: ['ocpus', 'users'],
    clarifyAnyInputs: ['ocpus', 'users'],
    requireLicenseChoice: true,
    licenseNotRequiredWhenAnyInputs: ['users'],
    licenseClarificationQuestion: 'Do you want Oracle Analytics Cloud Enterprise as BYOL or License Included?',
    clarificationQuestion: 'For Oracle Analytics Cloud Enterprise, should I quote named users or OCPUs, and what count should I use?',
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const ocpus = numberLike(inputs.ocpus);
      const users = numberLike(inputs.users);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const licenseMode = detectLicenseMode(source);
      const parts = ['Quote Oracle Analytics Cloud Enterprise'];
      if (licenseMode === 'byol') parts.push('BYOL');
      if (licenseMode === 'license-included') parts.push('License Included');
      if (ocpus) parts.push(`${ocpus} OCPUs`);
      if (users) parts.push(`${users} users`);
      return parts.join(', ');
    },
  },
  {
    id: 'integration_oic_standard',
    canonical: 'Oracle Integration Cloud Standard',
    domain: 'integration',
    resolver: 'oic_standard',
    aliases: [/\boracle integration cloud(?: service)? standard\b/i, /\boic standard\b/i],
    rescueInputs: [],
    requireLicenseChoice: true,
    licenseClarificationQuestion: 'Do you want Oracle Integration Cloud Standard as BYOL or License Included?',
    clarificationQuestion: 'How many Oracle Integration Cloud Standard instances do you need?',
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const instances = numberLike(inputs.instances);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const licenseMode = detectLicenseMode(source);
      const parts = ['Quote Oracle Integration Cloud Standard'];
      if (licenseMode === 'byol') parts.push('BYOL');
      if (licenseMode === 'license-included') parts.push('License Included');
      if (instances) parts.push(`${instances} instances`);
      return parts.join(', ');
    },
  },
  {
    id: 'integration_oic_enterprise',
    canonical: 'Oracle Integration Cloud Enterprise',
    domain: 'integration',
    resolver: 'oic_enterprise',
    aliases: [/\boracle integration cloud(?: service)? enterprise\b/i, /\boic enterprise\b/i],
    rescueInputs: [],
    requireLicenseChoice: true,
    licenseClarificationQuestion: 'Do you want Oracle Integration Cloud Enterprise as BYOL or License Included?',
    clarificationQuestion: 'How many Oracle Integration Cloud Enterprise instances do you need?',
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const instances = numberLike(inputs.instances);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const licenseMode = detectLicenseMode(source);
      const parts = ['Quote Oracle Integration Cloud Enterprise'];
      if (licenseMode === 'byol') parts.push('BYOL');
      if (licenseMode === 'license-included') parts.push('License Included');
      if (instances) parts.push(`${instances} instances`);
      return parts.join(', ');
    },
  },
  {
    id: 'integration_data',
    canonical: 'OCI Data Integration',
    domain: 'integration',
    resolver: 'data_integration',
    aliases: [/\bdata integration\b/i, /\boci data integration\b/i],
    rescueInputs: [],
    clarifyRequired: [],
    buildRequest(inputs = {}) {
      const parts = ['Quote OCI Data Integration'];
      if (numberLike(inputs.workspaceCount)) parts.push(`workspace usage ${numberLike(inputs.workspaceCount)} workspace`);
      if (numberLike(inputs.dataProcessedGb)) parts.push(`${numberLike(inputs.dataProcessedGb)} GB processed per hour`);
      if (numberLike(inputs.executionHours)) parts.push(`${numberLike(inputs.executionHours)} execution hours per month`);
      return parts.join(', ');
    },
  },
  {
    id: 'security_waf',
    canonical: 'OCI Web Application Firewall',
    domain: 'security',
    resolver: 'waf',
    aliases: [/\bweb application firewall\b/i, /\bwaf\b/i],
    rescueInputs: ['wafInstances', 'requestCount'],
    clarifyRequired: ['wafInstances', 'requestCount'],
    clarificationQuestion: 'How many WAF instances or policies do you need, and how many incoming requests do you expect per month?',
    buildRequest(inputs = {}) {
      const instances = numberLike(inputs.wafInstances);
      const requests = numberLike(inputs.requestCount);
      const parts = ['Quote OCI Web Application Firewall'];
      if (instances) parts.push(`with ${instances} instances`);
      if (requests) parts.push(`${requests} requests per month`);
      return parts.join(', ');
    },
  },
  {
    id: 'serverless_functions',
    canonical: 'OCI Functions',
    domain: 'serverless',
    resolver: 'functions',
    aliases: [/\boracle functions\b/i, /\boci functions\b/i, /\bfunctions\b/i, /\bserverless\b/i],
    rescueInputs: ['executionMs', 'memoryMb'],
    rescueAnyInputs: ['invocationsPerMonth', 'invocationsPerDay'],
    buildRequest(inputs = {}) {
      const parts = ['Quote OCI Functions'];
      if (numberLike(inputs.invocationsPerMonth)) parts.push(`with ${numberLike(inputs.invocationsPerMonth)} invocations per month`);
      else if (numberLike(inputs.invocationsPerDay) && numberLike(inputs.daysPerMonth)) parts.push(`with ${numberLike(inputs.invocationsPerDay)} invocations per day and ${numberLike(inputs.daysPerMonth)} days/month`);
      if (numberLike(inputs.executionMs)) parts.push(`${numberLike(inputs.executionMs)} milliseconds execution time per invocation`);
      if (numberLike(inputs.memoryMb)) parts.push(`${numberLike(inputs.memoryMb)} MB memory`);
      if (numberLike(inputs.provisionedConcurrencyUnits)) parts.push(`${numberLike(inputs.provisionedConcurrencyUnits)} provisioned concurrency units`);
      return parts.join(', ');
    },
  },
  {
    id: 'network_load_balancer',
    canonical: 'OCI Load Balancer',
    domain: 'network',
    resolver: 'load_balancer',
    aliases: [/\bload balancer\b/i],
    rescueInputs: [],
  },
  {
    id: 'storage_object',
    canonical: 'OCI Object Storage',
    domain: 'storage',
    resolver: 'object_storage',
    aliases: [/\bobject storage\b/i],
    rescueInputs: [],
  },
  {
    id: 'compute_flex',
    canonical: 'OCI Compute Flex',
    domain: 'compute',
    resolver: 'compute_flex',
    aliases: [
      /\b(?:vm|bm)\.[a-z0-9.]+(?:\.flex|\.\d+)\b/i,
      /\b[ea]\d+\.flex\b/i,
      /\bvm\.standard2\.(?:1|2|4|8|16|24)\b/i,
    ],
    rescueInputs: [],
  },
];

function getServiceFamily(id) {
  return SERVICE_FAMILIES.find((item) => item.id === id) || null;
}

function inferServiceFamily(text, declaredFamily = '') {
  const family = String(declaredFamily || '').trim();
  if (family) return family;
  const source = String(text || '');
  const matched = SERVICE_FAMILIES.find((item) => item.aliases.some((pattern) => pattern.test(source)));
  return matched?.id || '';
}

function normalizeServiceAliases(text) {
  let out = String(text || '');
  for (const family of SERVICE_FAMILIES) {
    for (const pattern of family.aliases) {
      if (pattern.test(out)) {
        out = out.replace(pattern, family.canonical);
        break;
      }
    }
  }
  return out;
}

function buildCanonicalRequest(semantic = {}, fallbackText = '') {
  const familyId = inferServiceFamily(semantic.reformulatedRequest || fallbackText, semantic.serviceFamily);
  const family = getServiceFamily(familyId);
  if (family?.buildRequest) {
    return family.buildRequest(semantic.extractedInputs || {}, semantic, fallbackText);
  }
  return fallbackText || semantic.reformulatedRequest || '';
}

function shouldForceQuote(semantic = {}) {
  const family = getServiceFamily(semantic.serviceFamily);
  if (!family) return false;
  const inputs = semantic.extractedInputs || {};
  const required = (family.rescueInputs || []).every((key) => hasInputValue(inputs[key]));
  const any = !(family.rescueAnyInputs || []).length || family.rescueAnyInputs.some((key) => hasInputValue(inputs[key]));
  return required && any;
}

function getMissingRequiredInputs(semantic = {}) {
  const family = getServiceFamily(semantic.serviceFamily);
  if (!family) return [];
  const required = family.clarifyRequired || family.rescueInputs || [];
  const inputs = semantic.extractedInputs || {};
  const missing = required.filter((key) => !hasInputValue(inputs[key]));
  if (missing.length) return missing;
  if (Array.isArray(family.clarifyAnyInputs) && family.clarifyAnyInputs.length) {
    const hasAny = family.clarifyAnyInputs.some((key) => hasInputValue(inputs[key]));
    if (!hasAny) return family.clarifyAnyInputs.slice();
  }
  return [];
}

function classifyDomain(name) {
  const source = String(name || '');
  const matched = SERVICE_FAMILIES.find((item) => item.aliases.some((pattern) => pattern.test(source)));
  return matched?.domain || null;
}

function numberLike(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function detectLicenseMode(source) {
  const text = String(source || '');
  if (/\bbyol\b|\bbring your own license\b/i.test(text)) return 'byol';
  if (/\blicense included\b|\binclude license\b|\bcon licencia incluida\b|\blicencia incluida\b/i.test(text)) return 'license-included';
  return '';
}

function hasInputValue(value) {
  if (typeof value === 'string') return value.trim().length > 0;
  return numberLike(value) !== null;
}

module.exports = {
  SERVICE_FAMILIES,
  getServiceFamily,
  inferServiceFamily,
  normalizeServiceAliases,
  buildCanonicalRequest,
  shouldForceQuote,
  getMissingRequiredInputs,
  classifyDomain,
};
