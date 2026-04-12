'use strict';

const { parsePromptRequest } = require('./quotation-engine');
const { getClarificationMessage } = require('./service-families');

function detectGenericComputeShapeClarification(text) {
  const source = String(text || '');
  const parsed = parsePromptRequest(source);
  const hasVmSignal = /\bvirtual machine\b|\bcompute instance\b|\bvm\b/i.test(source) || !!parsed.processorVendor;
  const hasSizing = Number(parsed.ocpus || 0) > 0 && Number(parsed.memoryQuantity || 0) > 0;
  const missingShape = !parsed.shapeSeries && !parsed.shape;
  if (!hasVmSignal || !hasSizing || !missingShape) return null;
  return {
    serviceFamily: 'compute_vm_generic',
    extractedInputs: {
      ocpus: parsed.ocpus,
      memoryGb: parsed.memoryQuantity,
      capacityGb: parsed.capacityGb,
      processorVendor: parsed.processorVendor,
    },
    question: getClarificationMessage({
      serviceFamily: 'compute_vm_generic',
      extractedInputs: { processorVendor: parsed.processorVendor },
    }),
  };
}

module.exports = {
  detectGenericComputeShapeClarification,
};
