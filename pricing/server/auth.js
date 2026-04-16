'use strict';

// M9 keeps the internal/development trust model intentionally small: callers supply
// x-client-id and a shared x-api-key protects sensitive operations from trivial abuse.
// Production deployments should insert JWT/OAuth2 principal validation ahead of that
// client-id lookup instead of trusting request-provided identity directly.

function parsePositiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ''), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function loadAuthSettings(env = process.env) {
  return {
    sharedApiKey: String(env.PRICING_SHARED_API_KEY || '').trim(),
    rateLimitRpm: parsePositiveInteger(env.PRICING_RATE_LIMIT_RPM, 20),
    rateLimitWindowMs: 60 * 1000,
  };
}

function isSharedApiKeyAuthorized(providedKey, settings = loadAuthSettings()) {
  if (!settings.sharedApiKey) return false;
  return String(providedKey || '').trim() === settings.sharedApiKey;
}

function createRateLimiter(settings = loadAuthSettings()) {
  const buckets = new Map();
  const windowMs = settings.rateLimitWindowMs;
  const limit = settings.rateLimitRpm;

  function check(clientId, now = Date.now()) {
    const key = String(clientId || 'anonymous').trim() || 'anonymous';
    const entry = buckets.get(key);

    if (!entry || now >= entry.resetAt) {
      const resetAt = now + windowMs;
      buckets.set(key, { count: 1, resetAt });
      return {
        allowed: true,
        limit,
        remaining: Math.max(limit - 1, 0),
        resetAt,
        retryAfterSeconds: 0,
      };
    }

    if (entry.count >= limit) {
      return {
        allowed: false,
        limit,
        remaining: 0,
        resetAt: entry.resetAt,
        retryAfterSeconds: Math.max(1, Math.ceil((entry.resetAt - now) / 1000)),
      };
    }

    entry.count += 1;
    return {
      allowed: true,
      limit,
      remaining: Math.max(limit - entry.count, 0),
      resetAt: entry.resetAt,
      retryAfterSeconds: 0,
    };
  }

  function reset() {
    buckets.clear();
  }

  return {
    check,
    reset,
    getSettings() {
      return {
        rateLimitRpm: limit,
        rateLimitWindowMs: windowMs,
      };
    },
  };
}

module.exports = {
  createRateLimiter,
  isSharedApiKeyAuthorized,
  loadAuthSettings,
  parsePositiveInteger,
};
