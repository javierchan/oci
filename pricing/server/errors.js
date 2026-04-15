'use strict';

class PricingError extends Error {
  constructor(message, options = {}) {
    super(String(message || 'Internal server error.'));
    this.name = options.name || new.target.name;
    this.code = String(options.code || 'INTERNAL_ERROR');
    this.httpStatus = Number.isInteger(options.httpStatus) ? options.httpStatus : 500;
    this.expose = options.expose !== false;
    this.data = options.data && typeof options.data === 'object' ? { ...options.data } : null;
    this.cause = options.cause;
  }
}

class GenAIError extends PricingError {
  constructor(message = 'OCI GenAI is unavailable.', options = {}) {
    super(message, {
      code: 'GENAI_UNAVAILABLE',
      httpStatus: 503,
      ...options,
    });
  }
}

class CatalogError extends PricingError {
  constructor(message = 'OCI catalog is not ready yet.', options = {}) {
    super(message, {
      code: 'CATALOG_UNAVAILABLE',
      httpStatus: 503,
      ...options,
    });
  }
}

class SessionConflictError extends PricingError {
  constructor(message = 'Session version conflict.', options = {}) {
    super(message, {
      code: 'SESSION_CONFLICT',
      httpStatus: 409,
      ...options,
    });
  }
}

class QuoteResolutionError extends PricingError {
  constructor(message = 'The requested service could not be resolved.', options = {}) {
    super(message, {
      code: 'UNSUPPORTED_SERVICE',
      httpStatus: 422,
      ...options,
    });
  }
}

class ValidationError extends PricingError {
  constructor(message = 'Invalid request.', options = {}) {
    super(message, {
      code: 'VALIDATION_ERROR',
      httpStatus: 400,
      ...options,
    });
  }
}

function normalizeError(error) {
  if (error instanceof PricingError) return error;
  return new PricingError('Internal server error.', {
    code: 'INTERNAL_ERROR',
    httpStatus: 500,
    expose: false,
    cause: error,
  });
}

function buildErrorBody(error) {
  const normalized = normalizeError(error);
  const body = {
    ok: false,
    code: normalized.code,
    message: normalized.expose ? normalized.message : 'Internal server error.',
  };

  if (normalized.data && typeof normalized.data === 'object') {
    Object.assign(body, normalized.data);
  }

  return body;
}

function handleError(res, error) {
  const normalized = normalizeError(error);
  return res.status(normalized.httpStatus).json(buildErrorBody(normalized));
}

module.exports = {
  PricingError,
  GenAIError,
  CatalogError,
  SessionConflictError,
  QuoteResolutionError,
  ValidationError,
  normalizeError,
  buildErrorBody,
  handleError,
};
