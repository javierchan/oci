'use strict';

const SERVICE_FAMILIES = [
  {
    id: 'compute_vm_generic',
    canonical: 'OCI Compute Virtual Machine',
    domain: 'compute',
    resolver: 'compute_vm_generic',
    aliases: [/\bvirtual machines?(?:\s*\(instances\))?\b/i, /\bcompute instances?\b/i, /\bvm instances?\b/i, /\bvirtual machine\b/i, /\bcompute instance\b/i, /\bvm\b/i],
    clarifyRequired: ['ocpus', 'memoryGb', 'shapeSeries'],
    clarificationQuestion: 'Which OCI VM shape should I use for that machine? For Intel, common options are `E4.Flex` or `E5.Flex`. Once you pick the shape, I can combine it with the attached Block Volume sizing.',
    buildClarificationQuestion(inputs = {}) {
      const vendor = String(inputs.processorVendor || '').toLowerCase();
      if (vendor === 'amd') {
        return 'Which OCI AMD VM shape should I use for that machine? Common options are `VM.Standard.E4.Flex`, `VM.Standard.E5.Flex`, or `VM.Standard.E6.Flex`. If the workload needs local NVMe, `VM.DenseIO.E4.Flex` or `VM.DenseIO.E5.Flex` may fit better. Once you pick the shape, I can combine it with the attached Block Volume sizing.';
      }
      if (vendor === 'arm' || vendor === 'ampere') {
        return 'Which OCI Arm VM shape should I use for that machine? Common options are `VM.Standard.A1.Flex`, `VM.Standard.A2.Flex`, or `VM.Standard.A4.Flex`. Once you pick the shape, I can combine it with the attached Block Volume sizing.';
      }
      return 'Which OCI VM shape should I use for that machine? For Intel, common options are `VM.Standard3.Flex`, `VM.Optimized3.Flex`, or the fixed-shape family `VM.Standard2.x`. Once you pick the shape, I can combine it with the attached Block Volume sizing.';
    },
    rescueInputs: [],
  },
  {
    id: 'storage_block',
    canonical: 'OCI Block Volume',
    domain: 'storage',
    resolver: 'block_volume',
    aliases: [/\bblock volumes?\b/i, /\bblock storage\b/i],
    partNumbers: ['B91961', 'B91962'],
    rescueInputs: ['capacityGb', 'vpuPerGb'],
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*vpu'?s?\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*vpu'?s?\b/i,
        },
      ],
    },
    options: {
      measurementModes: ['storage capacity (GB)', 'VPU per GB'],
      variants: ['balanced performance', 'higher performance', 'ultra high performance'],
      storageModels: ['Block Volume'],
    },
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
    partNumbers: ['B89057', 'B109546'],
    rescueInputs: ['capacityGb', 'vpuPerGb'],
    options: {
      measurementModes: ['storage capacity (GB)', 'performance units per GB'],
      variants: ['file systems', 'performance units'],
      storageModels: ['File Storage'],
    },
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
    id: 'storage_object_requests',
    canonical: 'OCI Object Storage Requests',
    domain: 'storage',
    resolver: 'object_storage_requests',
    aliases: [/\bobject storage\b[^\n]*\brequests?\b/i, /\bobject storage requests?\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['requests per month'],
      variants: ['object storage requests'],
      storageModels: ['Object Storage'],
    },
    buildRequest(inputs = {}) {
      const requests = numberLike(inputs.requestCount);
      const parts = ['Quote Object Storage Requests'];
      if (requests) parts.push(`${requests} requests per month`);
      return parts.join(' ');
    },
  },
  {
    id: 'storage_archive',
    canonical: 'OCI Archive Storage',
    domain: 'storage',
    resolver: 'archive_storage',
    aliases: [/\barchive storage\b/i],
    rescueInputs: ['capacityGb'],
    options: {
      measurementModes: ['storage capacity (GB)', 'storage capacity (TB)'],
      variants: ['archive storage'],
      storageModels: ['Archive Storage'],
    },
    buildRequest(inputs = {}) {
      const gb = numberLike(inputs.capacityGb);
      const parts = ['Quote Archive Storage'];
      if (gb) parts.push(`${gb} GB per month`);
      return parts.join(' ');
    },
  },
  {
    id: 'storage_infrequent_access',
    canonical: 'OCI Infrequent Access Storage',
    domain: 'storage',
    resolver: 'infrequent_access_storage',
    aliases: [/\binfrequent access storage\b/i, /\binfrequent access\b/i],
    rescueAnyInputs: ['capacityGb', 'dataProcessedGb'],
    options: {
      measurementModes: ['storage capacity (GB)', 'storage capacity (TB)', 'retrieved data (GB)'],
      variants: ['infrequent access storage', 'data retrieval'],
      storageModels: ['Infrequent Access Storage'],
    },
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const gb = numberLike(inputs.capacityGb);
      const retrievalGb = numberLike(inputs.dataProcessedGb);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const wantsRetrieval = /\bretriev(?:al|ed)?\b/i.test(source);
      const parts = [wantsRetrieval ? 'Quote Infrequent Access Storage retrieval' : 'Quote Infrequent Access Storage'];
      if (wantsRetrieval && retrievalGb) parts.push(`${retrievalGb} GB per month`);
      else if (gb) parts.push(`${gb} GB per month`);
      return parts.join(' ');
    },
  },
  {
    id: 'network_fastconnect',
    canonical: 'OCI FastConnect',
    domain: 'network',
    resolver: 'fastconnect',
    aliases: [/\bfast\s*connect\b/i, /\bfastconnect\b/i],
    rescueInputs: ['bandwidthGbps'],
    followUpCapabilities: {
      compositeReplaceSource: true,
      compositeReplaceTarget: true,
    },
    followUpDirectives: {
      removeFromComposite: {
        detect: /\b(?:sin|without)\s+(?:oci\s+)?fast\s*connect\b|\b(?:sin|without)\s+fastconnect\b/i,
        segmentPattern: String.raw`(?:oci\s+)?fast\s*connect|fastconnect`,
      },
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*gbps\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*gbps\b/i,
        },
      ],
    },
    options: {
      measurementModes: ['bandwidth (Gbps)', 'port hours'],
      variants: ['1 Gbps', '10 Gbps', '100 Gbps'],
    },
    buildRequest(inputs = {}, semantic = {}) {
      const gbps = numberLike(inputs.bandwidthGbps);
      if (!gbps) return 'Quote OCI FastConnect';
      return semantic?.annualRequested
        ? `Quote OCI FastConnect ${gbps} Gbps annually`
        : `Quote OCI FastConnect ${gbps} Gbps`;
    },
  },
  {
    id: 'network_dns',
    canonical: 'OCI DNS',
    domain: 'network',
    resolver: 'dns',
    aliases: [/\bdns\b/i, /\boracle cloud infrastructure dns\b/i],
    followUpCapabilities: {
      compositeReplaceSource: true,
      compositeReplaceTarget: true,
    },
    followUpDirectives: {
      removeFromComposite: {
        detect: /\b(?:sin|without)\s+dns\b/i,
        segmentPattern: String.raw`dns`,
      },
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*queries?\b(?:\s+per\s+month)?/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*queries?\b(?:\s+per\s+month)?/i,
        },
      ],
    },
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['queries per month'],
    },
    buildRequest(inputs = {}) {
      const queries = numberLike(inputs.requestCount);
      const parts = ['Quote OCI DNS'];
      if (queries) parts.push(`${queries} queries per month`);
      return parts.join(' ');
    },
  },
  {
    id: 'network_firewall',
    canonical: 'OCI Network Firewall',
    domain: 'network',
    resolver: 'network_firewall',
    aliases: [/\bnetwork firewall\b/i, /\boci network firewall\b/i],
    partNumbers: ['B95403', 'B95404'],
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
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*firewalls?\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*firewalls?\b/i,
        },
      ],
    },
  },
  {
    id: 'observability_monitoring',
    canonical: 'OCI Monitoring',
    domain: 'observability',
    resolver: 'monitoring',
    aliases: [/\bmonitoring\b/i, /\boci monitoring\b/i],
    rescueAnyInputs: ['requestCount'],
    followUpCapabilities: {
      compositeReplaceSource: true,
      compositeReplaceTarget: true,
    },
    followUpDirectives: {
      removeFromComposite: {
        detect: /\b(?:sin|without)\s+(?:oci\s+)?monitoring(?:\s+(?:retrieval|ingestion))?\b/i,
        segmentPattern: String.raw`(?:oci\s+)?monitoring(?:\s+(?:retrieval|ingestion))?`,
      },
    },
    options: {
      measurementModes: ['datapoints', 'million datapoints'],
      variants: ['ingestion', 'retrieval'],
    },
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const count = numberLike(inputs.requestCount);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const retrieval = /\bretrieval\b/i.test(source);
      const parts = [retrieval ? 'Quote OCI Monitoring Retrieval' : 'Quote OCI Monitoring Ingestion'];
      if (count) parts.push(`${count} datapoints`);
      return parts.join(' ');
    },
  },
  {
    id: 'observability_notifications_https',
    canonical: 'OCI Notifications HTTPS Delivery',
    domain: 'observability',
    resolver: 'notifications_https',
    aliases: [/\bnotifications?\b[^\n]*\bhttps delivery\b/i, /\bhttps delivery\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['delivery operations'],
      variants: ['HTTPS delivery'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote Notifications HTTPS Delivery'];
      if (count) parts.push(`${count} delivery operations`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*delivery operations?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*delivery operations?\b/i,
        },
      ],
    },
  },
  {
    id: 'operations_email_delivery',
    canonical: 'OCI Notifications Email Delivery',
    domain: 'operations',
    resolver: 'email_delivery',
    aliases: [/\bnotifications?\b[^\n]*\bemail delivery\b/i, /\bemail delivery\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['emails per month'],
      variants: ['email delivery'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote Notifications Email Delivery'];
      if (count) parts.push(`${count} emails per month`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*emails?\b(?:\s+per\s+month)?/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*emails?\b(?:\s+per\s+month)?/i,
        },
      ],
    },
  },
  {
    id: 'operations_iam_sms',
    canonical: 'OCI IAM SMS',
    domain: 'operations',
    resolver: 'iam_sms',
    aliases: [/\biam sms\b/i, /\bsms messages?\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['messages'],
      variants: ['IAM SMS'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote IAM SMS'];
      if (count) parts.push(`${count} SMS messages`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*sms messages?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*sms messages?\b/i,
        },
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*messages?\b/i,
          apply(nextPrompt, sourceMatch) {
            const amount = String(sourceMatch || '').match(/\b\d[\d,]*(?:\.\d+)?\b/i)?.[0];
            if (!amount) return nextPrompt;
            if (/\b\d[\d,]*(?:\.\d+)?\s*sms messages?\b/i.test(nextPrompt)) {
              return nextPrompt.replace(/\b\d[\d,]*(?:\.\d+)?\s*sms messages?\b/i, `${amount} SMS messages`);
            }
            return nextPrompt.replace(/\b\d[\d,]*(?:\.\d+)?\s*messages?\b/i, `${amount} messages`);
          },
        },
      ],
    },
  },
  {
    id: 'operations_notifications_sms',
    canonical: 'OCI Notifications SMS Outbound',
    domain: 'operations',
    resolver: 'notifications_sms',
    aliases: [/\bnotifications?\b[^\n]*\bsms\b/i, /\bsms outbound\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['SMS messages'],
      variants: ['Country Zone 1', 'Country Zone 2', 'Country Zone 3', 'Country Zone 4', 'Country Zone 5'],
    },
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const count = numberLike(inputs.requestCount);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const zoneMatch = source.match(/\bcountry zone\s*([1-5])\b/i);
      const zone = zoneMatch ? zoneMatch[1] : '1';
      const parts = [`Quote Notifications SMS Outbound to Country Zone ${zone}`];
      if (count) parts.push(`${count} messages`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*messages?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*messages?\b/i,
        },
      ],
    },
  },
  {
    id: 'security_threat_intelligence',
    canonical: 'Oracle Threat Intelligence Service',
    domain: 'security',
    resolver: 'threat_intelligence',
    aliases: [/\bthreat intelligence\b/i, /\boracle threat intelligence service\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['API calls'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote Oracle Threat Intelligence Service'];
      if (count) parts.push(`${count} API calls`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*api calls?\b(?:\s+per\s+month)?/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*api calls?\b(?:\s+per\s+month)?/i,
        },
      ],
    },
  },
  {
    id: 'observability_log_analytics',
    canonical: 'OCI Log Analytics',
    domain: 'observability',
    resolver: 'log_analytics',
    aliases: [/\blog(?:ging)? analytics\b/i, /\boci log analytics\b/i],
    rescueInputs: ['capacityGb'],
    options: {
      measurementModes: ['active storage (GB)', 'archival storage (GB)'],
      storageModels: ['Active Storage', 'Archival Storage'],
    },
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
    options: {
      measurementModes: ['database count', 'target databases'],
      variants: ['Database Cloud Service', 'On-Premises Databases'],
    },
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
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*target\s+databases?\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*target\s+databases?\b/i,
        },
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*databases?\b/i,
          apply(nextPrompt, sourceMatch) {
            if (/\b\d+(?:\.\d+)?\s*target\s+databases?\b/i.test(nextPrompt)) {
              const amount = String(sourceMatch || '').match(/\b\d+(?:\.\d+)?\b/i)?.[0];
              if (!amount) return nextPrompt;
              return nextPrompt.replace(/\b\d+(?:\.\d+)?\s*target\s+databases?\b/i, `${amount} target databases`);
            }
            return nextPrompt.replace(/\b\d+(?:\.\d+)?\s*databases?\b/i, sourceMatch);
          },
        },
      ],
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
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*jobs?\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*jobs?\b/i,
        },
      ],
    },
  },
  {
    id: 'ops_fleet_application_management',
    canonical: 'OCI Fleet Application Management',
    domain: 'operations',
    resolver: 'fleet_application_management',
    aliases: [/\bfleet application management\b/i, /\boci fleet application management\b/i],
    rescueAnyInputs: ['quantity'],
    options: {
      measurementModes: ['managed resources per month'],
      variants: ['managed resources'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.quantity);
      const parts = ['Quote OCI Fleet Application Management'];
      if (count) parts.push(`${count} managed resources`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*managed resources?\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*managed resources?\b/i,
        },
      ],
    },
  },
  {
    id: 'ai_agents_data_ingestion',
    canonical: 'OCI Generative AI Agents - Data Ingestion',
    domain: 'analytics',
    resolver: 'ai_agents_data_ingestion',
    aliases: [/\bgenerative ai agents\b[^\n]*\bdata ingestion\b/i, /\bagents data ingestion\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['transactions'],
      variants: ['data ingestion'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote OCI Generative AI Agents Data Ingestion'];
      if (count) parts.push(`${count} transactions`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
        },
      ],
    },
  },
  {
    id: 'ai_language',
    canonical: 'OCI AI Language',
    domain: 'analytics',
    resolver: 'ai_language',
    aliases: [/\boci ai language\b/i, /\bai language\b/i, /\boracle ai language\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['transactions'],
      variants: ['pre-trained inferencing'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote OCI AI Language'];
      if (count) parts.push(`${count} transactions`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
        },
      ],
    },
  },
  {
    id: 'ai_vector_store_retrieval',
    canonical: 'OCI Generative AI - Vector Store Retrieval',
    domain: 'analytics',
    resolver: 'ai_vector_store_retrieval',
    aliases: [/\bvector store retrieval\b/i, /\bgenerative ai\b[^\n]*\bvector store\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['requests'],
      variants: ['vector store retrieval'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote OCI Generative AI Vector Store Retrieval'];
      if (count) parts.push(`${count} requests`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*requests?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*requests?\b/i,
        },
      ],
    },
  },
  {
    id: 'ai_web_search',
    canonical: 'OCI Generative AI - Web Search',
    domain: 'analytics',
    resolver: 'ai_web_search',
    aliases: [/\bweb search\b/i, /\bgenerative ai\b[^\n]*\bweb search\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['requests'],
      variants: ['web search'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote OCI Generative AI Web Search'];
      if (count) parts.push(`${count} requests`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*requests?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*requests?\b/i,
        },
      ],
    },
  },
  {
    id: 'ai_large_cohere',
    canonical: 'OCI Generative AI - Large Cohere',
    domain: 'analytics',
    resolver: 'ai_large_cohere',
    aliases: [/\blarge cohere\b/i, /\bgenerative ai\b[^\n]*\blarge cohere\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['transactions'],
      variants: ['large cohere'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote OCI Generative AI Large Cohere'];
      if (count) parts.push(`${count} transactions`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
        },
      ],
    },
  },
  {
    id: 'ai_small_cohere',
    canonical: 'OCI Generative AI - Small Cohere',
    domain: 'analytics',
    resolver: 'ai_small_cohere',
    aliases: [/\bsmall cohere\b/i, /\bgenerative ai\b[^\n]*\bsmall cohere\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['transactions'],
      variants: ['small cohere'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote OCI Generative AI Small Cohere'];
      if (count) parts.push(`${count} transactions`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
        },
      ],
    },
  },
  {
    id: 'ai_embed_cohere',
    canonical: 'OCI Generative AI - Embed Cohere',
    domain: 'analytics',
    resolver: 'ai_embed_cohere',
    aliases: [/\bembed cohere\b/i, /\bgenerative ai\b[^\n]*\bembed cohere\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['transactions'],
      variants: ['embed cohere'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote OCI Generative AI Embed Cohere'];
      if (count) parts.push(`${count} transactions`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
        },
      ],
    },
  },
  {
    id: 'ai_large_meta',
    canonical: 'OCI Generative AI - Large Meta',
    domain: 'analytics',
    resolver: 'ai_large_meta',
    aliases: [/\blarge meta\b/i, /\bgenerative ai\b[^\n]*\blarge meta\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['transactions'],
      variants: ['large meta'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote OCI Generative AI Large Meta'];
      if (count) parts.push(`${count} transactions`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
        },
      ],
    },
  },
  {
    id: 'ai_agents_knowledge_base_storage',
    canonical: 'OCI Generative AI Agents - Knowledge Base Storage',
    domain: 'analytics',
    resolver: 'ai_agents_knowledge_base_storage',
    aliases: [/\bknowledge base storage\b/i, /\bgenerative ai agents\b[^\n]*\bknowledge base storage\b/i],
    rescueInputs: ['capacityGb'],
    options: {
      measurementModes: ['storage per hour (GB)'],
      variants: ['knowledge base storage'],
    },
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const gb = numberLike(inputs.capacityGb);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const hours = numberLike(inputs.hoursPerMonth) || (/744/.test(source) ? 744 : null);
      const parts = ['Quote OCI Generative AI Agents Knowledge Base Storage'];
      if (gb) parts.push(`${gb} GB`);
      if (hours) parts.push(`for ${hours} hours`);
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
    quoteUnavailableMessage() {
      return [
        'The current OCI catalog loaded by this agent does not expose a direct quotable SKU for `OCI Generative AI - Memory Ingestion`.',
        'I can see related catalog entries such as `B110463` (`OCI Generative AI Agents - Data Ingestion`) and `B112384` (`OCI Generative AI - Memory Retention`), but I should not map your request to either one automatically.',
        'If you want, I can quote one of those related services explicitly or continue once Oracle exposes a direct Memory Ingestion SKU in the live catalog.',
      ].join('\n\n');
    },
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
    preQuoteClarification(inputs = {}, semantic = {}, fallbackText = '') {
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      if (!/\brerank\b/i.test(source)) return '';
      if (!/\btransactions?\b/i.test(source)) return '';
      if (/\bhours?\b|\bcluster-hours?\b/i.test(source)) return '';
      return this.clarificationQuestion;
    },
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
    partNumbers: ['B95701', 'B95703', 'B95706'],
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
    partNumbers: ['B90570', 'B90573', 'B111584'],
    rescueInputs: ['capacityGb', 'databaseEdition'],
    rescueAnyInputs: ['ocpus', 'ecpus'],
    requireLicenseChoice: true,
    options: {
      editions: ['Enterprise', 'Standard'],
      measurementModes: ['OCPUs', 'ECPUs', 'storage capacity (GB)'],
      variants: ['Enterprise edition', 'Standard edition'],
    },
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
    partNumbers: ['B109356', 'B107951', 'B107952'],
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
    rescueInputs: ['exadataInfraShape', 'exadataInfraGeneration'],
    rescueAnyInputs: ['ocpus', 'ecpus'],
    requireLicenseChoice: true,
    licenseClarificationQuestion: 'Do you want Exadata Dedicated Infrastructure Database as BYOL or License Included?',
    clarificationQuestion: 'For Exadata Dedicated Infrastructure Database, which infrastructure shape do you need (for example base system, quarter rack, half rack, or full rack), which generation (for example X11M, X10M, X9M, X8M, X8, or X7), and how many OCPUs or ECPUs should I quote?',
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
    rescueInputs: ['exadataInfraShape', 'exadataInfraGeneration'],
    rescueAnyInputs: ['ocpus', 'ecpus'],
    requireLicenseChoice: true,
    licenseClarificationQuestion: 'Do you want Exadata Cloud@Customer Database as BYOL or License Included?',
    clarificationQuestion: 'For Exadata Cloud@Customer Database, which infrastructure shape do you need (for example base system, quarter rack, half rack, or full rack), which generation (for example X11M, X10M, X9M, X8M, X8, or X7), and how many OCPUs or ECPUs should I quote?',
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
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*(?:users?|usuarios?)\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*(?:users?|usuarios?)\b/i,
        },
      ],
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
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*(?:users?|usuarios?)\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*(?:users?|usuarios?)\b/i,
        },
      ],
    },
  },
  {
    id: 'integration_oic_standard',
    canonical: 'Oracle Integration Cloud Standard',
    domain: 'integration',
    resolver: 'oic_standard',
    aliases: [/\boracle integration cloud(?: service)? standard\b/i, /\boic standard\b/i],
    partNumbers: ['B89639', 'B89643'],
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
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i,
        },
      ],
    },
  },
  {
    id: 'integration_oic_enterprise',
    canonical: 'Oracle Integration Cloud Enterprise',
    domain: 'integration',
    resolver: 'oic_enterprise',
    aliases: [/\boracle integration cloud(?: service)? enterprise\b/i, /\boic enterprise\b/i],
    partNumbers: ['B89640', 'B89644'],
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
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i,
        },
      ],
    },
  },
  {
    id: 'integration_oic',
    canonical: 'Oracle Integration Cloud',
    domain: 'integration',
    resolver: 'oic',
    aliases: [/\boracle integration cloud(?: service)?\b/i, /\boic\b/i],
    partNumbers: ['B89639', 'B89643', 'B89640', 'B89644'],
    clarificationQuestion: 'Should I use Oracle Integration Cloud Standard or Oracle Integration Cloud Enterprise?',
    requireLicenseChoice: true,
    licenseClarificationQuestion: 'Once the edition is selected, should I use Oracle Integration Cloud as BYOL or License Included?',
    options: {
      variants: ['Standard', 'Enterprise'],
      editions: ['Standard', 'Enterprise'],
      measurementModes: ['instance count'],
    },
    preQuoteClarification(inputs = {}, semantic = {}, fallbackText = '') {
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      if (!/\b(?:standard|enterprise)\b/i.test(source)) {
        return 'Should I use Oracle Integration Cloud Standard or Oracle Integration Cloud Enterprise? Once you pick the edition, I can also confirm BYOL or License Included and instance count if needed.';
      }
      return '';
    },
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const instances = numberLike(inputs.instances);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const licenseMode = detectLicenseMode(source);
      const parts = ['Quote Oracle Integration Cloud'];
      if (/\benterprise\b/i.test(source)) parts.push('Enterprise');
      else if (/\bstandard\b/i.test(source)) parts.push('Standard');
      if (licenseMode === 'byol') parts.push('BYOL');
      if (licenseMode === 'license-included') parts.push('License Included');
      if (instances) parts.push(`${instances} instances`);
      return parts.join(', ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i,
        },
      ],
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
    options: {
      measurementModes: ['workspace count', 'data processed per hour (GB)', 'execution hours per month'],
      variants: ['workspace usage', 'data processed'],
    },
    buildRequest(inputs = {}) {
      const parts = ['Quote OCI Data Integration'];
      if (numberLike(inputs.workspaceCount)) parts.push(`workspace usage ${numberLike(inputs.workspaceCount)} workspace`);
      if (numberLike(inputs.dataProcessedGb)) parts.push(`${numberLike(inputs.dataProcessedGb)} GB processed per hour`);
      if (numberLike(inputs.executionHours)) parts.push(`${numberLike(inputs.executionHours)} execution hours per month`);
      return parts.join(', ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*workspaces?\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*workspaces?\b/i,
        },
      ],
    },
  },
  {
    id: 'security_waf',
    canonical: 'OCI Web Application Firewall',
    domain: 'security',
    resolver: 'waf',
    aliases: [/\bweb application firewall\b/i, /\bwaf\b/i],
    partNumbers: ['B94579', 'B94277'],
    followUpCapabilities: {
      compositeReplaceSource: true,
      compositeReplaceTarget: true,
    },
    followUpDirectives: {
      removeFromComposite: {
        detect: /\b(?:sin|without)\s+(?:waf|web application firewall)\b/i,
        segmentPattern: String.raw`(?:waf|web application firewall)`,
      },
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i,
        },
      ],
    },
    rescueInputs: ['wafInstances', 'requestCount'],
    clarifyRequired: ['wafInstances', 'requestCount'],
    options: {
      measurementModes: ['WAF instances or policies', 'requests per month'],
      variants: ['instance count', 'request volume'],
    },
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
    partNumbers: ['B90617', 'B90618'],
    rescueInputs: ['executionMs', 'memoryMb'],
    rescueAnyInputs: ['invocationsPerMonth', 'invocationsPerDay'],
    options: {
      measurementModes: ['monthly invocations', 'execution time per invocation (ms)', 'memory (MB)', 'provisioned concurrency units'],
      variants: ['invocations', 'execution time', 'provisioned concurrency'],
    },
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
    id: 'apigw',
    canonical: 'OCI API Gateway',
    domain: 'appdev',
    resolver: 'api_gateway',
    aliases: [/\bapi gateway\b/i, /\boci api gateway\b/i],
    followUpCapabilities: {
      compositeReplaceSource: true,
      compositeReplaceTarget: true,
    },
    followUpDirectives: {
      removeFromComposite: {
        detect: /\b(?:sin|without)\s+api gateway\b/i,
        segmentPattern: String.raw`api gateway`,
      },
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*api calls?\b(?:\s+per\s+month)?/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*api calls?\b(?:\s+per\s+month)?/i,
        },
      ],
    },
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['API calls per month'],
      variants: ['gateway requests'],
    },
    buildRequest(inputs = {}) {
      const calls = numberLike(inputs.requestCount);
      const parts = ['Quote OCI API Gateway'];
      if (calls) parts.push(`${calls} API calls per month`);
      return parts.join(' ');
    },
  },
  {
    id: 'ai_vision_custom_training',
    canonical: 'OCI Vision - Custom Training',
    domain: 'analytics',
    resolver: 'vision_custom_training',
    aliases: [/\bvision\b[^\n]*\bcustom training\b/i, /\bcustom training\b/i],
    rescueAnyInputs: ['serviceHours'],
    options: {
      measurementModes: ['training hours'],
      variants: ['custom training'],
    },
    buildRequest(inputs = {}) {
      const hours = numberLike(inputs.serviceHours);
      const parts = ['Quote Vision Custom Training'];
      if (hours) parts.push(`${hours} training hours`);
      return parts.join(' ');
    },
  },
  {
    id: 'ai_vision_image_analysis',
    canonical: 'OCI Vision - Image Analysis',
    domain: 'analytics',
    resolver: 'vision_image_analysis',
    aliases: [/\bvision\b[^\n]*\bimage analysis\b/i, /\bimage analysis\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['transactions'],
      variants: ['image analysis'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote OCI Vision Image Analysis'];
      if (count) parts.push(`${count} transactions`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
        },
      ],
    },
  },
  {
    id: 'ai_vision_ocr',
    canonical: 'OCI Vision - OCR',
    domain: 'analytics',
    resolver: 'vision_ocr',
    aliases: [/\bvision\b[^\n]*\bocr\b/i, /\bocr\b/i],
    rescueAnyInputs: ['requestCount'],
    options: {
      measurementModes: ['transactions'],
      variants: ['OCR'],
    },
    buildRequest(inputs = {}) {
      const count = numberLike(inputs.requestCount);
      const parts = ['Quote OCI Vision OCR'];
      if (count) parts.push(`${count} transactions`);
      return parts.join(' ');
    },
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
          targetPattern: /\b\d[\d,]*(?:\.\d+)?\s*transactions?\b/i,
        },
      ],
    },
  },
  {
    id: 'ai_speech',
    canonical: 'OCI Speech',
    domain: 'analytics',
    resolver: 'speech',
    aliases: [/\bspeech\b/i, /\btranscription\b/i],
    rescueAnyInputs: ['serviceHours'],
    options: {
      measurementModes: ['transcription hours'],
      variants: ['speech transcription'],
    },
    buildRequest(inputs = {}) {
      const hours = numberLike(inputs.serviceHours);
      const parts = ['Quote Speech'];
      if (hours) parts.push(`${hours} transcription hours`);
      return parts.join(' ');
    },
  },
  {
    id: 'ai_vision_stream_video_analysis',
    canonical: 'OCI Vision - Stream Video Analysis',
    domain: 'analytics',
    resolver: 'vision_stream_video_analysis',
    aliases: [/\bstream video analysis\b/i, /\bvision\b[^\n]*\bstream video\b/i],
    rescueAnyInputs: ['minuteQuantity'],
    options: {
      measurementModes: ['processed video minutes'],
      variants: ['stream video analysis'],
    },
    buildRequest(inputs = {}) {
      const minutes = numberLike(inputs.minuteQuantity);
      const parts = ['Quote OCI Vision Stream Video Analysis'];
      if (minutes) parts.push(`${minutes} processed video minutes`);
      return parts.join(' ');
    },
  },
  {
    id: 'media_flow',
    canonical: 'OCI Media Flow',
    domain: 'media',
    resolver: 'media_flow',
    aliases: [/\bmedia flow\b/i, /\bmedia services\b[^\n]*\bmedia flow\b/i],
    rescueAnyInputs: ['minuteQuantity'],
    options: {
      measurementModes: ['output media minutes'],
      variants: ['HD below 30fps'],
    },
    buildRequest(inputs = {}, semantic = {}, fallbackText = '') {
      const minutes = numberLike(inputs.minuteQuantity);
      const source = `${semantic.reformulatedRequest || ''}\n${fallbackText || ''}`;
      const quality = /\bhd\b/i.test(source) ? 'HD ' : '';
      const frameRate = /\bbelow 30fps\b/i.test(source) ? 'below 30fps ' : '';
      const parts = [`Quote Media Flow ${quality}${frameRate}`.trim()];
      if (minutes) parts.push(`${minutes} minutes of output media content`);
      return parts.join(' ');
    },
  },
  {
    id: 'ai_vision_stored_video_analysis',
    canonical: 'OCI Vision - Stored Video Analysis',
    domain: 'analytics',
    resolver: 'vision_stored_video_analysis',
    aliases: [/\bstored video analysis\b/i, /\bvision\b[^\n]*\bstored video\b/i],
    rescueAnyInputs: ['minuteQuantity'],
    options: {
      measurementModes: ['processed video minutes'],
      variants: ['stored video analysis'],
    },
    buildRequest(inputs = {}) {
      const minutes = numberLike(inputs.minuteQuantity);
      const parts = ['Quote OCI Vision Stored Video Analysis'];
      if (minutes) parts.push(`${minutes} processed video minutes`);
      return parts.join(' ');
    },
  },
  {
    id: 'edge_health_checks',
    canonical: 'OCI Health Checks',
    domain: 'network',
    resolver: 'health_checks',
    aliases: [/\bhealth checks?\b/i, /\boci health checks?\b/i],
    followUpCapabilities: {
      compositeReplaceSource: true,
      compositeReplaceTarget: true,
    },
    followUpDirectives: {
      removeFromComposite: {
        detect: /\b(?:sin|without)\s+health checks?\b/i,
        segmentPattern: String.raw`health checks?`,
      },
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*endpoints?\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*endpoints?\b/i,
        },
      ],
    },
    rescueAnyInputs: ['quantity'],
    options: {
      measurementModes: ['endpoint count'],
      variants: ['endpoints'],
    },
    buildRequest(inputs = {}) {
      const endpoints = numberLike(inputs.quantity);
      const parts = ['Quote OCI Health Checks'];
      if (endpoints) parts.push(`${endpoints} endpoints`);
      return parts.join(' ');
    },
  },
  {
    id: 'network_load_balancer',
    canonical: 'OCI Load Balancer',
    domain: 'network',
    resolver: 'load_balancer',
    aliases: [/\bload balancer\b/i],
    partNumbers: ['B93030', 'B93031'],
    followUpCapabilities: {
      compositeReplaceSource: true,
      compositeReplaceTarget: true,
    },
    followUpDirectives: {
      removeFromComposite: {
        detect: /\b(?:sin|without)\s+(?:load balancer|lb)\b/i,
        segmentPattern: String.raw`(?:flexible\s+)?load balancer|\blb\b`,
      },
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*mbps\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*mbps\b/i,
        },
      ],
    },
    rescueInputs: ['bandwidthMbps'],
    options: {
      measurementModes: ['bandwidth (Mbps)', 'base capacity hours'],
      variants: ['Flexible Load Balancer'],
    },
    buildRequest(inputs = {}) {
      const mbps = numberLike(inputs.bandwidthMbps);
      const parts = ['Quote Flexible Load Balancer'];
      if (mbps) parts.push(`${mbps} Mbps`);
      return parts.join(' ');
    },
  },
  {
    id: 'storage_object',
    canonical: 'OCI Object Storage',
    domain: 'storage',
    resolver: 'object_storage',
    aliases: [/\bobject storage\b/i],
    rescueInputs: ['capacityGb'],
    options: {
      measurementModes: ['storage capacity (GB)', 'storage capacity (TB)'],
      variants: ['standard object storage'],
      storageModels: ['Object Storage'],
    },
    buildRequest(inputs = {}) {
      const gb = numberLike(inputs.capacityGb);
      const parts = ['Quote Object Storage'];
      if (gb) parts.push(`${gb} GB per month`);
      return parts.join(' ');
    },
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
    followUpDirectives: {
      replaceWithinActiveQuote: [
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i,
          apply(nextPrompt, sourceMatch) {
            const current = String(nextPrompt || '').trim();
            if (!current) return current;
            if (/\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i.test(current)) {
              return current.replace(/\b\d+(?:\.\d+)?\s*(?:instances?|instancias?)\b/i, sourceMatch);
            }
            return `${current} ${String(sourceMatch || '').trim()}`.trim();
          },
        },
        {
          sourcePattern: /\b\d+(?:\.\d+)?\s*vpu'?s?\b/i,
          targetPattern: /\b\d+(?:\.\d+)?\s*vpu'?s?\b/i,
        },
      ],
    },
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

function getClarificationMessage(semantic = {}, fallbackText = '') {
  const familyId = semantic.serviceFamily || inferServiceFamily(semantic.reformulatedRequest || fallbackText, semantic.serviceFamily);
  const family = getServiceFamily(familyId);
  if (!family) return '';
  if (typeof family.buildClarificationQuestion === 'function') {
    return family.buildClarificationQuestion(semantic.extractedInputs || {}, semantic, fallbackText) || '';
  }
  return String(family.clarificationQuestion || '');
}

function getPreQuoteClarification(semantic = {}, fallbackText = '') {
  const familyId = semantic.serviceFamily || inferServiceFamily(semantic.reformulatedRequest || fallbackText, semantic.serviceFamily);
  const family = getServiceFamily(familyId);
  if (!family || typeof family.preQuoteClarification !== 'function') return '';
  return String(family.preQuoteClarification(semantic.extractedInputs || {}, semantic, fallbackText) || '').trim();
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

function supportsFollowUpCapability(familyId, capability, inputs = {}) {
  const family = getServiceFamily(familyId);
  if (!family) return false;
  if (family.followUpCapabilities && Object.prototype.hasOwnProperty.call(family.followUpCapabilities, capability)) {
    return family.followUpCapabilities[capability] === true;
  }
  if (capability === 'licenseMode') {
    if (!family.requireLicenseChoice || !family.licenseClarificationQuestion) return false;
    if (Array.isArray(family.licenseNotRequiredWhenAnyInputs) && family.licenseNotRequiredWhenAnyInputs.length) {
      const licenseOptional = family.licenseNotRequiredWhenAnyInputs.some((key) => hasInputValue(inputs[key]));
      if (licenseOptional) return false;
    }
    return true;
  }
  return false;
}

function getCompositeFollowUpRemovalRules() {
  return SERVICE_FAMILIES
    .filter((family) => family.followUpDirectives?.removeFromComposite)
    .map((family) => ({
      familyId: family.id,
      detect: family.followUpDirectives.removeFromComposite.detect,
      segmentPattern: family.followUpDirectives.removeFromComposite.segmentPattern,
    }));
}

function getActiveQuoteFollowUpReplacementRules(familyId) {
  const family = getServiceFamily(familyId);
  return Array.isArray(family?.followUpDirectives?.replaceWithinActiveQuote)
    ? family.followUpDirectives.replaceWithinActiveQuote.slice()
    : [];
}

function getFamiliesWithActiveQuoteFollowUpRules() {
  return SERVICE_FAMILIES
    .filter((family) => Array.isArray(family?.followUpDirectives?.replaceWithinActiveQuote) && family.followUpDirectives.replaceWithinActiveQuote.length > 0)
    .map((family) => family.id);
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
  getClarificationMessage,
  getPreQuoteClarification,
  shouldForceQuote,
  getMissingRequiredInputs,
  supportsFollowUpCapability,
  getCompositeFollowUpRemovalRules,
  getActiveQuoteFollowUpReplacementRules,
  getFamiliesWithActiveQuoteFollowUpRules,
  classifyDomain,
};
