# Improvement Milestones

## Purpose

This document captures the full set of architectural improvements identified through a deep design review of the `pricing` codebase.

Document role:

- this file is the source of truth for architectural remediation milestones, their rationale, and their exit criteria
- sequencing and active tactical work live in [Execution Plan](EXECUTION_PLAN.md)
- system-level design intent lives in [Architecture](ARCHITECTURE.md)
- the full docs map lives in [Docs Guide](README.md)

Each milestone is self-contained: it names the problem, the root cause, the target state, the files most likely to change, and what done looks like. Milestones are grouped by risk tier (highest impact / highest risk first).

---

## Milestone Index

| ID | Title | Tier | Status |
|----|-------|------|--------|
| [M1](#m1--service-detection-metadata-migration) | Service Detection Metadata Migration | Critical | complete |
| [M2](#m2--genai-intent-output-validation) | GenAI Intent Output Validation | Critical | complete |
| [M3](#m3--session-store-async-and-hardening) | Session Store Async and Hardening | Critical | complete |
| [M4](#m4--genai-configuration-externalization) | GenAI Configuration Externalization | High | complete |
| [M5](#m5--structured-logging) | Structured Logging | High | complete |
| [M6](#m6--prompt-caching-and-token-optimization) | Prompt Caching and Token Optimization | High | complete |
| [M7](#m7--semantic-error-handling-and-error-codes) | Semantic Error Handling and Error Codes | High | open |
| [M8](#m8--api-versioning-and-contract-hardening) | API Versioning and Contract Hardening | Medium | open |
| [M9](#m9--authentication-and-rate-limiting) | Authentication and Rate Limiting | Medium | open |
| [M10](#m10--observability-and-cost-metrics) | Observability and Cost Metrics | Medium | open |

---

## M1 — Service Detection Metadata Migration

**Tier:** Critical

### Problem

Service detection heuristics are implemented as scattered string-matching functions in `dependency-resolver.js`:

```javascript
if (isFastConnectRequest(request.source)) { ... }
if (isBlockVolumeRequest(request.source)) { ... }
```

These functions match against `request.source`, which is free-text user input that has already been interpreted by GenAI. This creates a double-classification problem: GenAI classifies intent, then code re-classifies from the raw text, producing ordering-dependent and fragile routing behavior. The fallback chain in `resolveRequestDependencies()` is implicit — it is not declared anywhere, only inferred by reading the execution order of twelve `if` blocks.

Additionally, shape resolution is triggered both as a top-level `if` block and via `FAMILY_RESOLVERS['compute_flex']`, meaning the same request can enter two resolution paths depending on which condition matches first.

### Root Cause

Service detection logic was added incrementally to `dependency-resolver.js` instead of being declared in `service-families.js`, which already exists as the canonical metadata store for service routing behavior.

### Target State

- every service detection signal (`isFastConnectRequest`, `isBlockVolumeRequest`, etc.) is replaced by a metadata key in `service-families.js`
- `resolveRequestDependencies()` dispatches by reading `FAMILY_RESOLVERS[intent.serviceFamily]` from the incoming intent — no text re-parsing in the resolver
- the fallback chain is declared as an explicit ordered list in metadata, not as implicit `if` ordering in code
- `compute_flex` and `compute_fixed` shapes are handled exclusively through `FAMILY_RESOLVERS` — the duplicate top-level shape check is removed
- the set of supported service families and their resolution entry points can be read from `service-families.js` without inspecting `dependency-resolver.js`

### Files Most Likely To Change

- `pricing/server/dependency-resolver.js` — remove heuristic functions, collapse to metadata-driven dispatch
- `pricing/server/service-families.js` — add detection metadata keys for each family
- `pricing/server/intent-extractor.js` — verify `serviceFamily` key is always present in intent output

### Exit Criteria

- `isFastConnectRequest`, `isBlockVolumeRequest`, and any equivalent `is*Request` functions are deleted from `dependency-resolver.js`
- `resolveRequestDependencies()` contains no string matching against `request.source`
- the duplicate shape-dispatch block is removed and all shape resolution flows through `FAMILY_RESOLVERS`
- all existing parity and regression tests continue to pass without modification

---

## M2 — GenAI Intent Output Validation

**Tier:** Critical

### Problem

`analyzeIntent()` in `intent-extractor.js` sends a prompt that instructs the model to return a JSON object. The JSON is consumed downstream in `assistant.js` and `dependency-resolver.js` without validation against any schema. If the model hallucinates an unexpected field, omits a required field, or returns a malformed structure, the pipeline processes corrupted state silently.

Examples of silent failure today:
- a missing `serviceFamily` key causes `FAMILY_RESOLVERS[undefined]` to return `undefined`, which falls through to generic matching
- an unexpected `route` value causes the wrong pipeline branch to execute with no warning
- `shouldQuote: "yes"` (string) instead of `shouldQuote: true` (boolean) causes truthy evaluation inconsistencies

### Root Cause

The system trusts GenAI output as correct-by-construction. There is no validation boundary between the GenAI call and the orchestration pipeline.

### Target State

- a JSON schema is declared for the intent object (in `intent-extractor.js` or a companion `intent-schema.js`)
- every `analyzeIntent()` call validates the parsed JSON against this schema before returning
- if validation fails, the system falls back to `fallbackIntentOnAnalysisFailure()` — the same path already used for GenAI network errors
- the schema is the single source of truth for what fields the pipeline is allowed to read from an intent object
- schema violations are logged with the raw model output for debugging

### Files Most Likely To Change

- `pricing/server/intent-extractor.js` — add validation step after JSON parse
- new file: `pricing/server/intent-schema.js` — declare and export the intent schema
- `pricing/server/assistant.js` — remove any field access that the schema does not declare

### Exit Criteria

- every field read from an intent object in `assistant.js` and `dependency-resolver.js` corresponds to a declared field in `intent-schema.js`
- injecting a malformed intent JSON (missing required fields, wrong types) causes fallback behavior — not a runtime exception
- a unit test covers at least five malformed intent shapes and asserts fallback is invoked

---

## M3 — Session Store Async and Hardening

**Tier:** Critical

### Problem

`session-store.js` uses `fs.writeFileSync()` on every session mutation — appending a message, updating state, or appending an event all trigger a full synchronous re-serialization of the entire session store to disk. Because Node.js is single-threaded, this blocks the event loop for every concurrent request during the write. The block duration scales linearly with the total size of `pricing/data/session-store.json`, which grows unboundedly because there is no TTL, GC, or size limit on stored sessions.

Secondary problems in the same module:

- client IDs are accepted from the request body and header with no verification — any client can read or write any other client's sessions by spoofing `x-client-id`
- `sessionContext` passed in the request body is merged into server state if the session lookup fails (index.js line ~616), allowing a client to inject state into the server
- the session store contains unencrypted quote context, workbook metadata, and conversation history

### Root Cause

The session store was designed for single-user development and was never hardened for concurrent or production use.

### Target State

- `fs.writeFileSync` is replaced by an async write queue: a single writer flushes pending state changes to disk non-blockingly, coalescing multiple rapid mutations into a single write
- sessions that have not been updated in more than N days (configurable, default 30) are pruned on startup and on a periodic interval
- the maximum number of sessions per client is capped (configurable, default 50, with LRU eviction of the oldest)
- `sessionContext` is never read from the request body — it is always loaded from server-side storage and the request body value is ignored
- client-ID validation documents its trust model explicitly in code comments: the current header-based model is acceptable for internal/development use but the code notes where an auth token check would be inserted for production deployment

### Files Most Likely To Change

- `pricing/server/session-store.js` — async write queue, TTL pruning, LRU cap
- `pricing/server/index.js` — remove `req.body.sessionContext` merge path (~line 616)

### Exit Criteria

- `fs.writeFileSync` is not called anywhere in `session-store.js`
- a concurrent-write test appends N messages simultaneously and verifies the session store ends in a consistent state (no torn writes)
- sessions older than the configured TTL are not present after startup or after a prune cycle
- a test verifies that `sessionContext` passed in a request body is ignored when a valid server-side session exists

---

## M4 — GenAI Configuration Externalization

**Tier:** High

### Problem

GenAI runtime parameters are hardcoded at multiple points across the codebase:

- model OCID is hardcoded as a fallback string in `index.js` (lines 44–45)
- token budgets are hardcoded as inline literals: `500` in `analyzeIntent()`, `700` in `analyzeImageIntent()`, `450` in workbook enrichment
- sampling parameters `temperature=0.7`, `topP=0.75`, `topK=-1` are hardcoded in `genai.js` and are the same for all request types
- the same model is used for intent classification (a precision task that benefits from low temperature and a small model) and discovery narrative generation (a fluency task that benefits from a larger model and moderate temperature)

Using identical sampling parameters for structurally different tasks degrades output quality: classification prompts that return JSON should use near-zero temperature for determinism, while narrative prompts can use moderate temperature for fluency.

### Root Cause

Parameters were chosen once during initial development and never externalized as the system grew to include distinct request types with different quality requirements.

### Target State

- a `genai-profiles.js` module (or equivalent section in `genai.js`) declares named request profiles:
  - `intent` — low temperature (≤0.1), strict token budget, small model if available
  - `narrative` — moderate temperature (0.5–0.7), generous token budget, largest available model
  - `discovery` — moderate temperature, generous token budget, largest available model
  - `image` — moderate temperature, generous token budget, multimodal model
- each caller passes a profile name; `genai.js` resolves sampling parameters from the profile
- model OCID, endpoint, and default profile values are read from `genai.yaml` or environment variables — no fallback OCID is hardcoded in application source
- token budgets are declared per profile in one place, not scattered across callers

### Files Most Likely To Change

- `pricing/server/genai.js` — add profile resolution, remove hardcoded defaults
- new file: `pricing/server/genai-profiles.js` — declare named profiles
- `pricing/server/intent-extractor.js` — pass `intent` profile instead of raw token count
- `pricing/server/discovery-routing.js` — pass `discovery` profile
- `pricing/server/index.js` — pass `narrative` profile for workbook enrichment, remove hardcoded model OCID

### Exit Criteria

- no hardcoded model OCID appears in any `.js` file
- no inline token integer (`500`, `700`, `450`) appears in any caller of `runChat()` or `runMultimodalChat()`
- changing `temperature` for intent classification requires editing only `genai-profiles.js`
- a unit test verifies each named profile resolves to expected parameters without calling the OCI API

---

## M5 — Structured Logging

**Tier:** High

### Problem

The codebase emits only `console.warn()` for error conditions and has no logging at `debug`, `info`, or `error` levels. There is no way to trace a request through the pipeline, identify which routing branch was taken, see what intent was classified, or understand why a quote failed — without attaching a debugger or adding temporary console statements.

Without structured logging, the only observable state of the system in production is the HTTP response. All intermediate decisions — routing branches, intent extraction, quote resolution steps, GenAI calls — are invisible.

### Root Cause

No logging infrastructure was established early in the project. `console.warn` was used as a stopgap and was never replaced.

### Target State

- a logger module (`pricing/server/logger.js`) wraps a logging library (pino is recommended for Node.js: low overhead, JSON output, child loggers)
- log levels: `debug` for step-by-step pipeline tracing, `info` for request lifecycle events, `warn` for recoverable anomalies, `error` for failures
- every request to `/api/assistant` and `/api/chat` logs at `info`:
  - client ID (hashed or truncated)
  - session ID
  - resolved intent (route, serviceFamily, shouldQuote)
  - routing path taken (early exit / fast path / full pipeline)
  - GenAI calls made and their latency
  - quote produced or clarification triggered
- GenAI call failures log at `warn` with the error message and which fallback was used
- all `console.warn` calls are replaced by `logger.warn`
- in development mode, log output is human-readable; in production, JSON

### Files Most Likely To Change

- new file: `pricing/server/logger.js`
- `pricing/server/assistant.js` — add pipeline tracing at each stage
- `pricing/server/genai.js` — add call/response logging with latency
- `pricing/server/intent-extractor.js` — log classified intent
- `pricing/server/index.js` — replace `console.warn`, add request lifecycle events

### Exit Criteria

- `console.warn` is not called anywhere in `pricing/server/`
- a single assistant request produces a parseable log trace showing: intent, route taken, GenAI call count, and whether a quote or clarification was returned
- running the server in development produces human-readable log output; `LOG_FORMAT=json` produces newline-delimited JSON

---

## M6 — Prompt Caching and Token Optimization

**Tier:** High

### Problem

Every call to `analyzeIntent()` sends the full conversation history to the OCI GenAI endpoint. The system prompt and product context injected into intent extraction calls are static or near-static for a given catalog version — they are ideal candidates for prompt caching. Re-sending them on every request is both wasteful (cost) and slower (latency) than caching would allow.

Secondary problem: conversation history sent to GenAI is never truncated. Long sessions send unbounded context to the model, increasing token cost and latency with no quality benefit once the relevant turns are more than a few messages ago.

### Root Cause

The GenAI integration was built without cost or latency optimization. Prompt caching was not implemented because it requires explicit SDK configuration that was never added.

### Target State

- the system prompt and static product context passed to `analyzeIntent()` are marked as cacheable using the OCI GenAI SDK cache control mechanism (if supported by the deployed model)
- if the OCI GenAI SDK does not expose prompt caching, conversation history is truncated to the last N turns before sending (configurable, default 6 turns)
- a `tokenBudget` guard in `genai.js` warns when the estimated input token count exceeds a configured threshold
- token counts (input, output) from every GenAI response are logged at `debug` level (available after M5 is complete)

### Files Most Likely To Change

- `pricing/server/genai.js` — add cache control headers or history truncation
- `pricing/server/intent-extractor.js` — truncate conversation before passing to GenAI

### Exit Criteria

- conversation history passed to `analyzeIntent()` is at most N turns (default 6) regardless of session length
- a test with a 20-turn conversation verifies that only the last 6 turns are sent to GenAI
- if prompt caching is supported by the OCI SDK, at least the system prompt is marked cacheable and a comment in code explains the cache key strategy

---

## M7 — Semantic Error Handling and Error Codes

**Tier:** High

### Problem

All runtime errors in the assistant pipeline are caught by a single `try/catch` at the HTTP layer and returned as HTTP 502 with `{ ok: false, error: error.message }`. This gives the client no ability to distinguish between:

- a GenAI API failure (retriable, possibly transient)
- a catalog parse error (not retriable, requires catalog reload)
- a quote resolution failure for an unsupported service (expected, needs clarification)
- a programming error (bug, should be surfaced differently)
- a session conflict (optimistic lock violation, client must resubmit)

Inconsistent error shapes across endpoints compound the problem:
- some endpoints return `{ ok: false, error: '...' }` with HTTP 400
- some return the same shape with HTTP 502
- the `/api/chat` endpoint returns `{ type: 'error', error: { type, message, code } }` (different schema)

### Root Cause

Error handling was added endpoint-by-endpoint with no shared error taxonomy. A shared error type hierarchy was never established.

### Target State

- an error taxonomy is declared in `pricing/server/errors.js`:
  - `PricingError` base class with `code` (machine-readable string) and `httpStatus`
  - subclasses: `GenAIError`, `CatalogError`, `SessionConflictError`, `QuoteResolutionError`, `ValidationError`
- every HTTP endpoint uses a shared `handleError(res, error)` helper that maps `PricingError` subtypes to the correct HTTP status and returns `{ ok: false, code, message }`
- error responses always include a `code` field (e.g., `GENAI_UNAVAILABLE`, `CATALOG_STALE`, `SESSION_CONFLICT`, `UNSUPPORTED_SERVICE`)
- the `/api/chat` endpoint error shape is unified with the `/api/assistant` error shape
- internal errors (programming bugs) return HTTP 500 with `code: INTERNAL_ERROR` and do not leak stack traces to the client

### Files Most Likely To Change

- new file: `pricing/server/errors.js`
- `pricing/server/index.js` — replace per-endpoint try/catch with shared handler
- `pricing/server/genai.js` — throw `GenAIError` instead of raw errors
- `pricing/server/catalog.js` — throw `CatalogError`

### Exit Criteria

- every HTTP endpoint calls `handleError()` rather than inline `res.status(N).json({...})`
- a test verifies that a simulated GenAI failure returns HTTP 503 with `code: GENAI_UNAVAILABLE`
- a test verifies that a session conflict returns HTTP 409 with `code: SESSION_CONFLICT`
- no endpoint returns a response body that includes a Node.js stack trace

---

## M8 — API Versioning and Contract Hardening

**Tier:** Medium

### Problem

All routes are unversioned (`/api/assistant`, `/api/chat`, etc.). Any breaking change to the request or response schema requires coordinating the frontend and backend simultaneously with no transition window. There is no machine-readable API contract, so regressions in response shape are caught only at runtime or in manual testing.

Secondary problems:
- `POST /api/assistant` handles new sessions, existing sessions, text input, image input, workbook follow-ups, and general conversation — all in one endpoint with conditional logic scattered across 100 lines of `index.js`
- `sessionContext` in the request body can override server state in some code paths (addressed in M3, but the API contract should also forbid it explicitly)

### Root Cause

The API grew organically alongside the assistant without a versioning strategy or a contract definition.

### Target State

- all routes are prefixed with `/api/v1/`
- old routes (`/api/assistant`, etc.) are kept as aliases during a transition window, then removed
- an OpenAPI 3.1 spec file (`pricing/docs/openapi.yaml`) documents all `/api/v1/` endpoints with request schemas, response schemas, and error codes
- `POST /api/v1/assistant` request schema explicitly marks `sessionContext` as ignored (or removes it from the schema entirely)
- the OpenAPI spec is the source of truth for what fields are valid in each endpoint — no undocumented fields are processed by the server

### Files Most Likely To Change

- `pricing/server/index.js` — add `/api/v1/` route prefix, keep aliases
- new file: `pricing/docs/openapi.yaml`

### Exit Criteria

- all new client code uses `/api/v1/` routes
- `pricing/docs/openapi.yaml` validates against the OpenAPI 3.1 schema (use `openapi-schema-validator` or equivalent)
- a CI check verifies the spec file is present and valid on every merge
- the old unversioned routes return HTTP 301 redirects to their `/api/v1/` equivalents (or HTTP 410 after the transition window)

---

## M9 — Authentication and Rate Limiting

**Tier:** Medium

### Problem

The system identifies users by `x-client-id`, which is accepted from the request header or request body with no verification. Any caller can claim any client ID and read or write that client's sessions. There is no mechanism to prevent a single client from flooding the assistant endpoint, triggering unbounded GenAI calls and exhausting the OCI GenAI quota.

The catalog reload endpoint (`POST /api/catalog/reload`) and provider config endpoint (`GET /api/providers`) are fully unauthenticated.

### Root Cause

The system was built for internal or single-tenant use where trust-based identification was sufficient. It was never hardened for multi-tenant or internet-exposed deployment.

### Target State

- the authentication model is explicitly declared in `pricing/server/auth.js`:
  - for internal/development deployment: header-based client ID with a shared secret (`x-api-key`) to prevent trivial abuse
  - for production deployment: the code documents the injection point for a JWT or OAuth2 middleware without requiring it to be implemented now
- `POST /api/catalog/reload` requires the shared secret (`x-api-key`)
- `GET /api/providers` does not leak OCI config values (tenancy, fingerprint, region) — it returns only connectivity status (`ok: true/false`)
- per-client rate limiting is applied to `/api/v1/assistant` and `/api/v1/chat`:
  - configurable requests-per-minute limit (default: 20 rpm per client ID)
  - HTTP 429 with `Retry-After` header on limit exceeded
  - rate limit state is in-memory (no external Redis required for single-instance deployment)

### Files Most Likely To Change

- new file: `pricing/server/auth.js`
- `pricing/server/index.js` — add rate limiting middleware, protect sensitive endpoints, sanitize `/api/providers` response

### Exit Criteria

- `POST /api/catalog/reload` returns HTTP 401 if `x-api-key` is absent or incorrect
- `GET /api/providers` does not include `tenancy`, `fingerprint`, `privateKeyPem`, or `user` fields in its response
- a test verifies HTTP 429 is returned after the configured RPM limit is exceeded
- rate limit configuration is read from environment variables, not hardcoded

---

## M10 — Observability and Cost Metrics

**Tier:** Medium

### Problem

There is no visibility into the operational behavior of the system:

- GenAI token usage and cost are completely invisible — there is no way to know which requests are expensive or whether the system is within OCI GenAI quota
- quote pipeline metrics (how often deterministic quotes are produced vs. discovery answers vs. clarifications) are not tracked
- GenAI call latency is not measured, so slow model responses are indistinguishable from network errors
- session lifecycle events (created, completed, abandoned) are not emitted in a form that can be analyzed

Without this visibility, it is impossible to optimize for cost, detect degradation, or understand user behavior.

### Root Cause

Observability was deferred in favor of functional coverage. No instrumentation hooks were established early in the project.

### Target State

- a metrics module (`pricing/server/metrics.js`) maintains in-process counters and histograms:
  - `genai_calls_total` — counter, labeled by call type (`intent`, `narrative`, `discovery`, `image`)
  - `genai_tokens_input_total` — counter, labeled by call type
  - `genai_tokens_output_total` — counter, labeled by call type
  - `genai_latency_ms` — histogram, labeled by call type
  - `assistant_requests_total` — counter, labeled by outcome (`quote`, `clarification`, `discovery`, `error`)
  - `quote_resolution_path` — counter, labeled by path (`fast_path`, `intent_pipeline`, `early_exit`)
- metrics are exposed at `GET /api/metrics` in Prometheus text format
- the metrics endpoint does not require authentication (standard Prometheus scrape convention) but is configurable to require the shared secret from M9
- after M5 is complete, structured log events include `genai_tokens_in`, `genai_tokens_out`, and `latency_ms` on every GenAI call

### Files Most Likely To Change

- new file: `pricing/server/metrics.js`
- `pricing/server/genai.js` — record token counts and latency from SDK response
- `pricing/server/assistant.js` — record routing path and outcome
- `pricing/server/index.js` — expose `/api/metrics` route

### Exit Criteria

- `GET /api/metrics` returns valid Prometheus text format
- making one assistant request increments `assistant_requests_total` by 1
- making one GenAI call increments `genai_calls_total` and `genai_tokens_input_total`
- a test verifies the metrics endpoint returns HTTP 200 and contains the expected counter names
- token counts are read from the OCI GenAI SDK response object, not estimated — if the SDK does not expose them, the metric is recorded as `0` and a `TODO` comment documents what SDK field to read when it becomes available

---

## Execution Sequence

The milestones are independent enough to be worked in parallel across two lanes, but M5 (logging) unlocks M10 (metrics) and M3 (session store) should precede M9 (auth) since session hardening reduces the blast radius of the trust-based client ID.

Recommended sequencing:

```
Wave 1 (highest impact, low coupling):
  M1 — Service Detection Metadata Migration
  M2 — GenAI Intent Output Validation
  M3 — Session Store Async and Hardening

Wave 2 (quality and cost, depends on Wave 1 stability):
  M4 — GenAI Configuration Externalization
  M5 — Structured Logging
  M7 — Semantic Error Handling and Error Codes

Wave 3 (operational hardening, depends on Wave 2):
  M6 — Prompt Caching and Token Optimization  (depends on M5 for token logging)
  M8 — API Versioning and Contract Hardening
  M9 — Authentication and Rate Limiting       (depends on M3)
  M10 — Observability and Cost Metrics        (depends on M5)
```

Each milestone's exit criteria must be satisfied before it is marked complete. A milestone is not complete if tests pass but the problem statement still applies in a different code path.
