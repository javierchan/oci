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
