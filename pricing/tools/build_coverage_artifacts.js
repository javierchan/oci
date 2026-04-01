'use strict';

const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const { loadWorkbookRules } = require(path.join(root, 'server', 'workbook-rules.js'));
const { buildServiceRegistry } = require(path.join(root, 'server', 'service-registry.js'));
const { SERVICE_FAMILIES } = require(path.join(root, 'server', 'service-families.js'));

const vmShapeRules = require(path.join(root, 'data', 'rule-registry', 'vm_shape_rules.json'));
const ruleRegistry = require(path.join(root, 'data', 'rule-registry', 'rules.json'));

function writeJson(targetPath, payload) {
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  fs.writeFileSync(targetPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function unique(items) {
  return Array.from(new Set((items || []).filter(Boolean)));
}

function countBy(items, selector) {
  return items.reduce((acc, item) => {
    const key = selector(item);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function familyFromServiceName(name) {
  const text = String(name || '').toLowerCase();
  if (/\bcompute|virtual machine|bare metal|ocpu|ecpu|gpu|dense i\/o|standard2|standard3|optimized3|e\d|a\d\b/.test(text)) return 'compute';
  if (/\bdatabase|autonomous|exadata|mysql|postgres|postgresql|data safe|heatwave\b/.test(text)) return 'database';
  if (/\bfastconnect|load balancer|health checks|dns|network|gateway|waf|firewall\b/.test(text)) return 'network_security';
  if (/\bobject storage|block volume|file storage|lustre|storage\b/.test(text)) return 'storage';
  if (/\bfunctions|serverless|api gateway|events|streaming\b/.test(text)) return 'serverless';
  if (/\banalytics|integration|oic|oac|data integration|goldengate\b/.test(text)) return 'analytics_integration';
  if (/\blog analytics|monitoring|notifications|operations insights|observability|fleet|batch\b/.test(text)) return 'operations_observability';
  if (/\bai|vision|speech|media|vector|search|threat intelligence|agents\b/.test(text)) return 'ai_media';
  return 'other';
}

function buildServiceFamilyRules() {
  const workbookRules = loadWorkbookRules();
  const registry = buildServiceRegistry({ products: [], workbookRules }).services;
  const grouped = new Map();

  for (const service of registry) {
    const family = familyFromServiceName(service.name);
    if (!grouped.has(family)) {
      grouped.set(family, {
        id: family,
        serviceCount: 0,
        partNumbers: new Set(),
        patterns: new Set(),
        coverageLevels: {},
        exampleServices: [],
        unresolvedPrerequisiteServices: 0,
      });
    }
    const entry = grouped.get(family);
    entry.serviceCount += 1;
    for (const part of service.partNumbers || []) entry.partNumbers.add(part);
    for (const pattern of service.patterns || []) entry.patterns.add(pattern);
    entry.coverageLevels[service.coverageLevel] = (entry.coverageLevels[service.coverageLevel] || 0) + 1;
    if (entry.exampleServices.length < 10) entry.exampleServices.push(service.name);
    if (!service.prerequisitesResolved && (service.prerequisites || []).length) entry.unresolvedPrerequisiteServices += 1;
  }

  return Array.from(grouped.values())
    .map((entry) => ({
      id: entry.id,
      serviceCount: entry.serviceCount,
      partNumberCount: entry.partNumbers.size,
      patterns: Array.from(entry.patterns).sort(),
      coverageLevels: entry.coverageLevels,
      unresolvedPrerequisiteServices: entry.unresolvedPrerequisiteServices,
      exampleServices: entry.exampleServices,
    }))
    .sort((a, b) => b.serviceCount - a.serviceCount || a.id.localeCompare(b.id));
}

function buildComputeVariantAudit() {
  const workbookRules = loadWorkbookRules();
  const coveredVmParts = new Set(
    (vmShapeRules.shapes || []).flatMap((shape) => Array.isArray(shape.partNumbers) ? shape.partNumbers : [])
  );
  const candidateServices = (workbookRules.services || []).filter((service) => {
    const name = String(service.name || '');
    return (
      /^Oracle Cloud Infrastructure - Compute - /i.test(name) ||
      /Compute - Virtual Machine/i.test(name) ||
      /Compute - Bare Metal/i.test(name) ||
      /Compute - GPU/i.test(name) ||
      /Compute - HPC/i.test(name)
    );
  });

  const covered = [];
  const uncovered = [];

  for (const service of candidateServices) {
    const parts = Array.isArray(service.partNumbers) ? service.partNumbers : [];
    const metrics = Array.isArray(service.metrics) ? service.metrics : [];
    const record = {
      name: service.name,
      partNumbers: parts,
      metrics,
      matchedVmRegistry: parts.some((partNumber) => coveredVmParts.has(partNumber)),
    };
    if (record.matchedVmRegistry) covered.push(record);
    else uncovered.push(record);
  }

  return {
    candidateServiceCount: candidateServices.length,
    coveredServiceCount: covered.length,
    uncoveredServiceCount: uncovered.length,
    coveredServices: covered,
    uncoveredServices: uncovered,
  };
}

function buildCoverageMatrix(serviceFamilies) {
  const workbookRules = loadWorkbookRules();
  const registry = buildServiceRegistry({ products: [], workbookRules });
  const services = registry.services;
  const l0l1Gaps = services
    .filter((item) => ['L0', 'L1'].includes(item.coverageLevel))
    .slice(0, 120)
    .map((item) => ({
      name: item.name,
      domain: item.domain,
      coverageLevel: item.coverageLevel,
      requiredInputs: item.requiredInputs,
      partNumbers: item.partNumbers.slice(0, 6),
    }));

  return {
    metadata: {
      generatedAt: new Date().toISOString(),
      generatedBy: 'pricing/tools/build_coverage_artifacts.js',
    },
    sourceStats: {
      workbookServices: workbookRules.services.length,
      ruleRegistryServices: (ruleRegistry.services || []).length,
      ruleRegistryParts: (ruleRegistry.parts || []).length,
      pdfBillingRules: (ruleRegistry.rules?.billing || []).length,
      pdfPrerequisiteRules: (ruleRegistry.rules?.prerequisites || []).length,
      vmShapes: (vmShapeRules.shapes || []).length,
      serviceFamilies: serviceFamilies.length,
    },
    runtimeCoverage: {
      serviceRegistrySummary: registry.summary,
      byCoverageLevel: countBy(services, (item) => item.coverageLevel),
      byDomain: countBy(services, (item) => item.domain),
    },
    vmShapeCoverage: {
      totalShapes: (vmShapeRules.shapes || []).length,
      byKind: countBy(vmShapeRules.shapes || [], (item) => item.kind),
      byVendor: countBy(vmShapeRules.shapes || [], (item) => item.vendor),
      shapes: vmShapeRules.shapes || [],
    },
    computeVariantAudit: buildComputeVariantAudit(),
    resolverCoverage: SERVICE_FAMILIES.map((item) => ({
      id: item.id,
      canonical: item.canonical,
      domain: item.domain,
      resolver: item.resolver,
    })),
    lowestCoverageServices: l0l1Gaps,
  };
}

function main() {
  const serviceFamilies = buildServiceFamilyRules();
  const coverageMatrix = buildCoverageMatrix(serviceFamilies);

  writeJson(path.join(root, 'data', 'rule-registry', 'service_family_rules.json'), {
    metadata: {
      generatedBy: 'pricing/tools/build_coverage_artifacts.js',
      description: 'Grouped service-family rules derived from workbook and PDF extracts.',
    },
    families: serviceFamilies,
  });

  writeJson(path.join(root, 'data', 'rule-registry', 'coverage_matrix.json'), coverageMatrix);
}

main();
