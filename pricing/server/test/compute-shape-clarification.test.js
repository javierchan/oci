'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const { detectGenericComputeShapeClarification } = require(path.join(ROOT, 'compute-shape-clarification.js'));

test('compute shape clarification detects generic intel VM sizing without an explicit shape', () => {
  const result = detectGenericComputeShapeClarification(
    'Dame el quote para una virtual machine con procesador intel, 4 OCPUs, 16 GB RAM, 200 GB Block Storage',
  );

  assert.ok(result);
  assert.equal(result.serviceFamily, 'compute_vm_generic');
  assert.deepEqual(result.extractedInputs, {
    ocpus: 4,
    memoryGb: 16,
    capacityGb: 200,
    processorVendor: 'intel',
  });
  assert.match(result.question, /which oci vm shape/i);
});

test('compute shape clarification detects amd prompts and recommends amd shapes', () => {
  const result = detectGenericComputeShapeClarification(
    'Dame el quote de una VM AMD con 8 OCPUs, 32 GB RAM y 1 TB de block storage',
  );

  assert.ok(result);
  assert.equal(result.extractedInputs.processorVendor, 'amd');
  assert.match(result.question, /amd vm shape/i);
  assert.match(result.question, /VM\.Standard\.E4\.Flex/);
});

test('compute shape clarification ignores prompts that already include a concrete shape', () => {
  const result = detectGenericComputeShapeClarification(
    'Quote VM.Standard.E5.Flex 4 OCPUs 16 GB RAM 200 GB Block Storage',
  );

  assert.equal(result, null);
});

test('compute shape clarification ignores non-vm prompts even if they contain storage values', () => {
  const result = detectGenericComputeShapeClarification(
    'Quote OCI Block Volume 200 GB with 20 VPUs',
  );

  assert.equal(result, null);
});
