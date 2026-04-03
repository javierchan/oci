'use strict';

const { searchProducts, searchServiceRegistry } = require('./catalog');
const { getServiceFamily, getMissingRequiredInputs } = require('./service-families');
const { VM_SHAPES, listFlexShapesByVendor, findVmShapeByText } = require('./vm-shapes');

function summarizeSessionContext(sessionContext) {
  if (!sessionContext || typeof sessionContext !== 'object') return null;
  const workbook = sessionContext.workbookContext && typeof sessionContext.workbookContext === 'object'
    ? sessionContext.workbookContext
    : null;
  const lastQuote = sessionContext.lastQuote && typeof sessionContext.lastQuote === 'object'
    ? sessionContext.lastQuote
    : null;
  return {
    currentIntent: sessionContext.currentIntent || '',
    sessionSummary: sessionContext.sessionSummary || '',
    workbook: workbook ? {
      fileName: workbook.fileName || '',
      sourcePlatform: workbook.sourcePlatform || '',
      processorVendor: workbook.processorVendor || '',
      shapeName: workbook.shapeName || '',
      vpuPerGb: Number.isFinite(Number(workbook.vpuPerGb)) ? Number(workbook.vpuPerGb) : null,
    } : null,
    lastQuote: lastQuote ? {
      label: lastQuote.label || '',
      serviceFamily: lastQuote.serviceFamily || '',
      shapeName: lastQuote.shapeName || '',
      monthly: Number.isFinite(Number(lastQuote.monthly)) ? Number(lastQuote.monthly) : null,
      currencyCode: lastQuote.currencyCode || 'USD',
      lineItemCount: Number.isFinite(Number(lastQuote.lineItemCount)) ? Number(lastQuote.lineItemCount) : null,
      partNumbers: Array.isArray(lastQuote.partNumbers) ? lastQuote.partNumbers.slice(0, 12) : [],
    } : null,
  };
}

function buildVmShapeContext() {
  const intelFixed = (VM_SHAPES || [])
    .filter((shape) => shape.kind === 'fixed' && String(shape.vendor || '').toLowerCase() === 'intel' && /^VM\./i.test(String(shape.shapeName || '')))
    .map((shape) => ({
      shapeName: shape.shapeName,
      kind: shape.kind,
      fixedOcpus: Number(shape.fixedOcpus),
      fixedMemoryGb: Number(shape.fixedMemoryGb),
    }));

  return {
    topic: 'vm_shapes',
    coreRules: {
      x86OcpuToVcpuRatio: '1 OCPU = 2 vCPUs',
      ampereOcpuToVcpuRatio: '1 OCPU = 1 vCPU',
      fixedVsFlex: 'Fixed shapes have predefined CPU and memory. Flex shapes accept user-defined OCPU and memory.',
    },
    families: {
      intel: {
        flex: listFlexShapesByVendor('intel').map((shape) => shape.shapeName),
        fixed: intelFixed,
      },
      amd: {
        flex: listFlexShapesByVendor('amd').map((shape) => shape.shapeName),
      },
      ampere: {
        flex: listFlexShapesByVendor('ampere').map((shape) => shape.shapeName),
      },
    },
  };
}

function extractVmShapeMentions(text) {
  const source = String(text || '');
  if (!source) return [];
  const mentions = [];
  const normalizedSource = source.toUpperCase();
  for (const shape of VM_SHAPES || []) {
    const candidates = Array.isArray(shape.aliases) && shape.aliases.length
      ? shape.aliases
      : [shape.shapeName];
    const matched = candidates.some((candidate) => {
      const raw = String(candidate || '').toUpperCase();
      return raw && normalizedSource.includes(raw);
    });
    if (matched) {
      mentions.push(String(shape.shapeName || '').toUpperCase());
    }
  }
  const shorthand = findVmShapeByText(source);
  if (shorthand?.shapeName) mentions.push(String(shorthand.shapeName).toUpperCase());
  return Array.from(new Set(mentions)).slice(0, 6);
}

function pickRelevantServices(index, userText, intent) {
  const registryMatches = searchServiceRegistry(index.serviceRegistry, userText, 5);
  const products = searchProducts(index, userText, 8);
  const family = getServiceFamily(intent?.serviceFamily || '');
  const missingInputs = family ? getMissingRequiredInputs(intent) : [];
  return {
    registryMatches: registryMatches.map((service) => ({
      name: service.name,
      domain: service.domain,
      coverageLevel: service.coverageLevel,
      requiredInputs: service.requiredInputs || [],
      patterns: service.patterns || [],
      partNumbers: (service.partNumbers || []).slice(0, 8),
    })),
    products: products.map((product) => ({
      partNumber: product.partNumber,
      displayName: product.displayName,
      serviceCategoryDisplayName: product.serviceCategoryDisplayName,
      metricDisplayName: product.metricDisplayName,
      priceType: product.priceType,
    })),
    family: family ? {
      id: family.id,
      canonical: family.canonical,
      domain: family.domain,
      resolver: family.resolver || '',
      aliases: Array.isArray(family.aliases) ? family.aliases.map((pattern) => String(pattern)).slice(0, 8) : [],
      clarifyRequired: family.clarifyRequired || family.rescueInputs || [],
      clarificationQuestion: family.clarificationQuestion || '',
      requireLicenseChoice: !!family.requireLicenseChoice,
      licenseClarificationQuestion: family.licenseClarificationQuestion || '',
      missingInputs,
    } : null,
  };
}

function inferPackTopic(userText, intent) {
  const source = String(userText || '').toLowerCase();
  if (/\bshape?s?\b|\bvirtual machines?\b|\bvm instances?\b|\bcompute\b/.test(source)) return 'vm_shapes';
  if (extractVmShapeMentions(userText).length) return 'vm_shapes';
  if (intent?.serviceFamily) return intent.serviceFamily;
  return 'general_pricing';
}

function buildAssistantContextPack(index, { userText, intent, sessionContext }) {
  const pack = {
    route: intent?.route || '',
    topic: inferPackTopic(userText, intent),
    userQuestion: String(userText || '').trim(),
    quotePlan: intent?.quotePlan || null,
    extractedInputs: intent?.extractedInputs || {},
    session: summarizeSessionContext(sessionContext),
    serviceContext: pickRelevantServices(index, userText, intent),
  };
  if (pack.topic === 'vm_shapes' || pack.serviceContext.family?.domain === 'compute') {
    pack.vmShapes = buildVmShapeContext();
    const mentions = extractVmShapeMentions(userText);
    if (mentions.length >= 2) {
      pack.shapeComparison = mentions.map((shapeName) => {
        const shape = (VM_SHAPES || []).find((item) => String(item.shapeName || '').toUpperCase() === shapeName);
        return shape ? {
          shapeName,
          vendor: shape.vendor || '',
          kind: shape.kind || '',
          family: shape.family || '',
          series: shape.series || '',
          fixedOcpus: Number.isFinite(Number(shape.fixedOcpus)) ? Number(shape.fixedOcpus) : null,
          fixedMemoryGb: Number.isFinite(Number(shape.fixedMemoryGb)) ? Number(shape.fixedMemoryGb) : null,
          ocpuToVcpuRatio: Number.isFinite(Number(shape.ocpuToVcpuRatio)) ? Number(shape.ocpuToVcpuRatio) : null,
        } : { shapeName };
      });
    }
  }
  return pack;
}

function stringifyContextPack(pack) {
  return JSON.stringify(pack, null, 2);
}

function summarizeContextPack(pack) {
  if (!pack || typeof pack !== 'object') return null;
  return {
    topic: pack.topic || '',
    route: pack.route || '',
    quotePlan: pack.quotePlan ? {
      action: pack.quotePlan.action || '',
      targetType: pack.quotePlan.targetType || '',
      domain: pack.quotePlan.domain || '',
      candidateFamilies: Array.isArray(pack.quotePlan.candidateFamilies) ? pack.quotePlan.candidateFamilies.slice(0, 8) : [],
      missingInputs: Array.isArray(pack.quotePlan.missingInputs) ? pack.quotePlan.missingInputs.slice(0, 8) : [],
    } : null,
    family: pack.serviceContext?.family ? {
      id: pack.serviceContext.family.id,
      canonical: pack.serviceContext.family.canonical,
      domain: pack.serviceContext.family.domain,
    } : null,
    registryMatchNames: Array.isArray(pack.serviceContext?.registryMatches)
      ? pack.serviceContext.registryMatches.slice(0, 5).map((item) => item.name)
      : [],
    shapeComparison: Array.isArray(pack.shapeComparison)
      ? pack.shapeComparison.slice(0, 6).map((item) => item.shapeName)
      : [],
  };
}

module.exports = {
  buildAssistantContextPack,
  stringifyContextPack,
  summarizeContextPack,
};
