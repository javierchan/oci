'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, relativePath), 'utf8'));
}

test('vm shape registry exposes aliases for calculator and shorthand prompts', () => {
  const registry = readJson('data/rule-registry/vm_shape_rules.json');
  const standard3 = registry.shapes.find((shape) => shape.shapeName === 'VM.Standard3.Flex');
  const optimized3 = registry.shapes.find((shape) => shape.shapeName === 'VM.Optimized3.Flex');
  const standard24 = registry.shapes.find((shape) => shape.shapeName === 'VM.Standard2.4');
  const e2Micro = registry.shapes.find((shape) => shape.shapeName === 'VM.Standard.E2.1.Micro');
  const bareMetalX7 = registry.shapes.find((shape) => shape.shapeName === 'BM.Standard2.52');

  assert.ok(standard3);
  assert.ok(optimized3);
  assert.ok(standard24);
  assert.ok(e2Micro);
  assert.ok(bareMetalX7);
  assert.ok(standard3.aliases.includes('Standard3.Flex'));
  assert.ok(optimized3.aliases.includes('Optimized3.Flex'));
  assert.ok(standard24.aliases.includes('Standard2.4'));
  assert.ok(e2Micro.aliases.includes('E2 Micro'));
  assert.ok(bareMetalX7.aliases.includes('Standard2.52'));
});

test('coverage matrix reflects deterministic coverage for formerly residual compute variants', () => {
  const matrix = readJson('data/rule-registry/coverage_matrix.json');
  const audit = matrix.computeVariantAudit;

  assert.ok(audit);
  assert.ok(audit.candidateServiceCount > 0);
  assert.ok(audit.coveredServices.some((item) => item.matchedDeterministicCoverage));
  assert.ok(audit.coveredServices.some((item) => /Compute - GPU/i.test(item.name) && item.coverageMode === 'deterministic_metric'));
  assert.ok(audit.coveredServices.some((item) => /Compute - HPC/i.test(item.name) && item.coverageMode === 'deterministic_metric'));
  assert.ok(audit.coveredServices.some((item) => /E2 Micro - Free/i.test(item.name) && item.coverageMode === 'vm_registry'));
  assert.ok(audit.coveredServices.some((item) => /Windows OS/i.test(item.name) && item.coverageMode === 'deterministic_metric'));
  assert.ok(audit.coveredServices.some((item) => /Microsoft SQL Enterprise/i.test(item.name) && item.coverageMode === 'deterministic_metric'));
  assert.ok(audit.coveredServices.some((item) => /Cloud@Customer/i.test(item.name) && item.coverageMode === 'deterministic_metric'));
  assert.equal(audit.uncoveredServiceCount, 0);
});

test('follow-up capability matrix artifact reflects hardened family metadata', () => {
  const matrix = readJson('data/rule-registry/followup_capability_matrix.json');
  const families = matrix.families || [];

  const oicStandard = families.find((entry) => entry.familyId === 'integration_oic_standard');
  const dataSafe = families.find((entry) => entry.familyId === 'security_data_safe');
  const logAnalytics = families.find((entry) => entry.familyId === 'observability_log_analytics');
  const monitoring = families.find((entry) => entry.familyId === 'observability_monitoring');
  const waf = families.find((entry) => entry.familyId === 'security_waf');

  assert.ok(Array.isArray(families) && families.length > 0);

  assert.ok(oicStandard);
  assert.equal(oicStandard.compositeReplaceSource, true);
  assert.equal(oicStandard.compositeReplaceTarget, true);
  assert.equal(oicStandard.compositeRemove, true);

  assert.ok(dataSafe);
  assert.equal(dataSafe.compositeRemove, true);
  assert.equal(dataSafe.compositeReplaceSource, true);
  assert.equal(dataSafe.compositeReplaceTarget, true);
  assert.equal(dataSafe.activeQuoteRuleCount >= 3, true);

  assert.ok(logAnalytics);
  assert.equal(logAnalytics.compositeRemove, true);
  assert.equal(logAnalytics.compositeReplaceSource, true);
  assert.equal(logAnalytics.compositeReplaceTarget, true);
  assert.equal(logAnalytics.activeQuoteRuleCount, 2);

  assert.ok(monitoring);
  assert.equal(monitoring.compositeRemove, true);
  assert.equal(monitoring.compositeReplaceSource, true);
  assert.equal(monitoring.compositeReplaceTarget, true);
  assert.equal(monitoring.activeQuoteRuleCount, 2);

  assert.ok(waf);
  assert.equal(waf.canonical, 'OCI Web Application Firewall');
  assert.equal(waf.compositeRemove, true);
  assert.equal(waf.compositeReplaceSource, true);
  assert.equal(waf.compositeReplaceTarget, true);
  assert.equal(waf.hasActiveQuoteRules, true);
  assert.equal(waf.activeQuoteRuleCount >= 1, true);
});
