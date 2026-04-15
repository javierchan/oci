'use strict';

const INTENT_VALUES = ['quote', 'discover', 'explain', 'clarify', 'answer'];
const ROUTE_VALUES = ['general_answer', 'product_discovery', 'quote_request', 'quote_followup', 'workbook_followup', 'clarify'];
const QUOTE_PLAN_ACTION_VALUES = ['answer', 'discover', 'quote', 'modify_quote', 'modify_workbook', 'clarify'];
const QUOTE_PLAN_TARGET_TYPE_VALUES = ['general', 'service', 'bundle', 'shape', 'workbook', 'quote'];

const DECLARED_INTENT_FIELDS = [
  'intent',
  'route',
  'shouldQuote',
  'needsClarification',
  'clarificationQuestion',
  'reformulatedRequest',
  'assumptions',
  'serviceFamily',
  'serviceName',
  'extractedInputs',
  'confidence',
  'annualRequested',
  'quotePlan',
];

const DECLARED_QUOTE_PLAN_FIELDS = [
  'action',
  'targetType',
  'domain',
  'candidateFamilies',
  'missingInputs',
  'useDeterministicEngine',
];

const REQUIRED_INTENT_FIELDS = DECLARED_INTENT_FIELDS.filter((field) => field !== 'confidence');

function isPlainObject(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function validateEnum(value, allowedValues, label, errors) {
  if (typeof value !== 'string' || !allowedValues.includes(value)) {
    errors.push(`${label} must be one of: ${allowedValues.join(', ')}`);
  }
}

function validateString(value, label, errors) {
  if (typeof value !== 'string') errors.push(`${label} must be a string`);
}

function validateBoolean(value, label, errors) {
  if (typeof value !== 'boolean') errors.push(`${label} must be a boolean`);
}

function validateStringArray(value, label, errors) {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) {
    errors.push(`${label} must be an array of strings`);
  }
}

function validateIntentPayload(payload) {
  const errors = [];

  if (!isPlainObject(payload)) {
    return {
      ok: false,
      errors: ['intent payload must be a JSON object'],
    };
  }

  for (const field of REQUIRED_INTENT_FIELDS) {
    if (!Object.prototype.hasOwnProperty.call(payload, field)) {
      errors.push(`missing required field: ${field}`);
    }
  }

  if (Object.prototype.hasOwnProperty.call(payload, 'intent')) {
    validateEnum(payload.intent, INTENT_VALUES, 'intent', errors);
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'route')) {
    validateEnum(payload.route, ROUTE_VALUES, 'route', errors);
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'shouldQuote')) {
    validateBoolean(payload.shouldQuote, 'shouldQuote', errors);
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'needsClarification')) {
    validateBoolean(payload.needsClarification, 'needsClarification', errors);
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'clarificationQuestion')) {
    validateString(payload.clarificationQuestion, 'clarificationQuestion', errors);
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'reformulatedRequest')) {
    validateString(payload.reformulatedRequest, 'reformulatedRequest', errors);
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'assumptions')) {
    validateStringArray(payload.assumptions, 'assumptions', errors);
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'serviceFamily')) {
    validateString(payload.serviceFamily, 'serviceFamily', errors);
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'serviceName')) {
    validateString(payload.serviceName, 'serviceName', errors);
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'extractedInputs') && !isPlainObject(payload.extractedInputs)) {
    errors.push('extractedInputs must be an object');
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'confidence') && payload.confidence !== null && typeof payload.confidence !== 'number') {
    errors.push('confidence must be a number or null');
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'annualRequested')) {
    validateBoolean(payload.annualRequested, 'annualRequested', errors);
  }

  if (Object.prototype.hasOwnProperty.call(payload, 'quotePlan')) {
    if (!isPlainObject(payload.quotePlan)) {
      errors.push('quotePlan must be an object');
    } else {
      for (const field of DECLARED_QUOTE_PLAN_FIELDS) {
        if (!Object.prototype.hasOwnProperty.call(payload.quotePlan, field)) {
          errors.push(`missing required field: quotePlan.${field}`);
        }
      }
      if (Object.prototype.hasOwnProperty.call(payload.quotePlan, 'action')) {
        validateEnum(payload.quotePlan.action, QUOTE_PLAN_ACTION_VALUES, 'quotePlan.action', errors);
      }
      if (Object.prototype.hasOwnProperty.call(payload.quotePlan, 'targetType')) {
        validateEnum(payload.quotePlan.targetType, QUOTE_PLAN_TARGET_TYPE_VALUES, 'quotePlan.targetType', errors);
      }
      if (Object.prototype.hasOwnProperty.call(payload.quotePlan, 'domain')) {
        validateString(payload.quotePlan.domain, 'quotePlan.domain', errors);
      }
      if (Object.prototype.hasOwnProperty.call(payload.quotePlan, 'candidateFamilies')) {
        validateStringArray(payload.quotePlan.candidateFamilies, 'quotePlan.candidateFamilies', errors);
      }
      if (Object.prototype.hasOwnProperty.call(payload.quotePlan, 'missingInputs')) {
        validateStringArray(payload.quotePlan.missingInputs, 'quotePlan.missingInputs', errors);
      }
      if (Object.prototype.hasOwnProperty.call(payload.quotePlan, 'useDeterministicEngine')) {
        validateBoolean(payload.quotePlan.useDeterministicEngine, 'quotePlan.useDeterministicEngine', errors);
      }
    }
  }

  return {
    ok: errors.length === 0,
    errors,
  };
}

class InvalidIntentPayloadError extends Error {
  constructor(errors = [], rawModelOutput = '') {
    super(`Invalid intent payload: ${errors.join('; ') || 'unknown schema violation'}`);
    this.name = 'InvalidIntentPayloadError';
    this.code = 'INVALID_INTENT_PAYLOAD';
    this.validationErrors = Array.isArray(errors) ? errors.slice() : [];
    this.rawModelOutput = String(rawModelOutput || '');
  }
}

function validateIntentPayloadOrThrow(payload, rawModelOutput = '') {
  const result = validateIntentPayload(payload);
  if (!result.ok) {
    throw new InvalidIntentPayloadError(result.errors, rawModelOutput);
  }
  return payload;
}

module.exports = {
  INTENT_VALUES,
  ROUTE_VALUES,
  QUOTE_PLAN_ACTION_VALUES,
  QUOTE_PLAN_TARGET_TYPE_VALUES,
  DECLARED_INTENT_FIELDS,
  DECLARED_QUOTE_PLAN_FIELDS,
  InvalidIntentPayloadError,
  validateIntentPayload,
  validateIntentPayloadOrThrow,
};
