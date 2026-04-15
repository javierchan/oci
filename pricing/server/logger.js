'use strict';

const crypto = require('crypto');
const pino = require('pino');

const LOG_LEVEL = String(
  process.env.LOG_LEVEL || (process.env.NODE_ENV === 'test' ? 'silent' : (process.env.NODE_ENV === 'production' ? 'info' : 'debug')),
).trim().toLowerCase() || 'info';
const LOG_FORMAT = String(process.env.LOG_FORMAT || '').trim().toLowerCase();
const LOG_JSON = LOG_FORMAT === 'json' || process.env.NODE_ENV === 'production';

function redactClientId(clientId) {
  const source = String(clientId || '').trim();
  if (!source) return 'anonymous';
  const digest = crypto.createHash('sha256').update(source).digest('hex').slice(0, 12);
  return `cid_${digest}`;
}

function truncateSessionId(sessionId) {
  const source = String(sessionId || '').trim();
  if (!source) return '';
  return source.length <= 18 ? source : `${source.slice(0, 8)}...${source.slice(-6)}`;
}

function createDevStream(target = process.stdout) {
  return {
    write(chunk) {
      const line = String(chunk || '').trim();
      if (!line) return;
      try {
        const payload = JSON.parse(line);
        target.write(`${formatDevLine(payload)}\n`);
      } catch {
        target.write(`${line}\n`);
      }
    },
  };
}

function formatDevLine(payload) {
  const time = payload.time || payload.timestamp || new Date().toISOString();
  const level = String(payload.level || 'info').toUpperCase();
  const msg = String(payload.msg || '');
  const meta = { ...payload };
  delete meta.level;
  delete meta.time;
  delete meta.timestamp;
  delete meta.msg;
  delete meta.pid;
  delete meta.hostname;

  const fields = Object.entries(meta)
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${key}=${formatValue(value)}`);

  return [`[${time}]`, level, msg].concat(fields).filter(Boolean).join(' ');
}

function formatValue(value) {
  if (value instanceof Error) return JSON.stringify({ message: value.message, stack: value.stack });
  if (typeof value === 'string') return JSON.stringify(value);
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

const destination = LOG_JSON ? process.stdout : createDevStream(process.stdout);

const logger = pino({
  level: LOG_LEVEL,
  base: LOG_JSON ? undefined : null,
  timestamp: pino.stdTimeFunctions.isoTime,
  formatters: {
    level(label) {
      return { level: label };
    },
  },
  serializers: {
    err(error) {
      if (!error) return error;
      return {
        type: error.name,
        message: error.message,
        stack: error.stack,
      };
    },
  },
}, destination);

function buildRequestLogger(fields = {}) {
  const childFields = {
    routeName: fields.routeName || '',
    requestId: fields.requestId || '',
    clientId: redactClientId(fields.clientId),
    sessionId: truncateSessionId(fields.sessionId),
  };
  if (fields.profile) childFields.profile = fields.profile;
  return logger.child(childFields);
}

function createTrace() {
  return {
    genaiCalls: [],
  };
}

function recordGenAICall(trace, call) {
  if (!trace || !Array.isArray(trace.genaiCalls)) return;
  trace.genaiCalls.push({
    kind: call.kind || 'chat',
    profile: call.profile || '',
    modelId: call.modelId || '',
    latencyMs: Number(call.latencyMs || 0),
    ok: Boolean(call.ok),
    fallbackUsed: call.fallbackUsed || '',
    errorMessage: call.errorMessage || '',
  });
}

function summarizeTrace(trace) {
  const calls = Array.isArray(trace?.genaiCalls) ? trace.genaiCalls : [];
  return {
    genaiCallCount: calls.length,
    genaiLatencyMs: calls.reduce((sum, item) => sum + Number(item.latencyMs || 0), 0),
    genaiCalls: calls,
  };
}

module.exports = {
  LOG_JSON,
  buildRequestLogger,
  createTrace,
  logger,
  recordGenAICall,
  redactClientId,
  summarizeTrace,
  truncateSessionId,
};
