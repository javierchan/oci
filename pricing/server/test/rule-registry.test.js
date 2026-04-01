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

  assert.ok(standard3);
  assert.ok(optimized3);
  assert.ok(standard24);
  assert.ok(standard3.aliases.includes('Standard3.Flex'));
  assert.ok(optimized3.aliases.includes('Optimized3.Flex'));
  assert.ok(standard24.aliases.includes('Standard2.4'));
});

test('coverage matrix exposes residual compute variants not yet mapped in the VM shape registry', () => {
  const matrix = readJson('data/rule-registry/coverage_matrix.json');
  const audit = matrix.computeVariantAudit;

  assert.ok(audit);
  assert.ok(audit.candidateServiceCount > 0);
  assert.ok(audit.uncoveredServiceCount > 0);
  assert.ok(audit.uncoveredServices.some((item) => /Compute - GPU/i.test(item.name)));
  assert.ok(audit.uncoveredServices.some((item) => /Compute - HPC/i.test(item.name)));
});
