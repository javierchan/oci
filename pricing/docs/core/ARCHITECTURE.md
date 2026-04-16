# Architecture

## Purpose

`pricing` is a deterministic OCI pricing engine with a natural-language assistant on top.

Document role:

- this file is the source of truth for architectural intent and stable runtime contracts
- sequencing lives in [Execution Plan](/Users/javierchan/Documents/GitHub/oci/pricing/docs/planning/EXECUTION_PLAN.md)
- validated runtime coverage state lives in [Coverage Roadmap](/Users/javierchan/Documents/GitHub/oci/pricing/docs/planning/COVERAGE_ROADMAP.md)
- the full docs map lives in [Docs Guide](/Users/javierchan/Documents/GitHub/oci/pricing/docs/README.md)

The design target is:

1. Understand human input with `GenAI + structured product context`
2. Normalize it into a `quotePlan`
3. Resolve the relevant OCI services and billable SKUs
4. Calculate pricing deterministically from Oracle reference data
5. Return an auditable quote or a safe clarification

The system is intentionally **not** a pure chatbot that invents prices.

## Current Status

This architecture is **implemented and in active hardening**, not a prototype.

### Implemented In Codebase

- OCI live catalog ingestion at startup from four endpoints:
  - `products.json`
  - `metrics.json`
  - `productpresets.json`
  - `products API v1` (`products-apex.json`)
- local filesystem catalog snapshots in `pricing/data/catalog-cache/current/`
- server-authoritative session persistence in `pricing/server/session-store.js`
- backend-owned workbook and RVTools follow-up handling
- `intent -> route -> quotePlan` extraction in `pricing/server/intent-extractor.js` and `pricing/server/normalizer.js`
- `structured product context` generation in `pricing/server/context-packs.js`
- deterministic SKU resolution and pricing in:
  - `pricing/server/dependency-resolver.js`
  - `pricing/server/quotation-engine.js`
  - `pricing/server/consumption-model.js`
- export paths from persisted quotes:
  - `Copy Quote`
  - `Export CSV`
  - `Export XLSX`
- parity and regression coverage across major OCI families
- live assistant resilience and semantic-quality regression tooling in:
  - `pricing/server/scripts/assistant-fuzz.js`
  - `pricing/server/scripts/assistant-quality.js`

### Implemented But Still Being Expanded

- family metadata in `pricing/server/service-families.js`
  - now owns a growing follow-up capability matrix for:
    - license-mode follow-ups
    - composite add/remove/replace behavior for selected families
    - family-owned variant swaps such as `OIC`/`OAC` sibling editions and `Data Safe` / `Log Analytics` variant transitions
  - now also exposes a reusable capability-matrix view from code so tests and future tooling can inspect supported follow-up behavior without re-parsing raw metadata ad hoc
- registry-driven discovery and explanation
- quote follow-ups on active session quotes
- workbook and RVTools migration sizing
- OCI Calculator parity suite

### Still Pending

- broader parity coverage for more OCI Calculator scenarios
- more declarative family metadata to replace remaining manual branches
- deeper quote-followup coverage across all complex families
- more observability and concurrency hardening for production operation

## Design Principles

### Use GenAI For

- intent routing
- understanding vague human questions
- discovery answers
- explanation and summaries
- clarification generation

### Do Not Use GenAI For

- final price calculation
- SKU invention
- tier math
- quantity math
- licensing assumptions that are not backed by metadata or explicit user input

### Core Runtime Contract

- `GenAI` interprets
- `structured product context` constrains the interpretation
- `quotePlan` formalizes the next action
- deterministic engine calculates
- assistant explains without altering totals

## Stable Contracts

These contracts should change rarely and deliberately:

- deterministic pricing remains the source of truth for quote totals and line-item composition
- `GenAI` may interpret, clarify, and explain, but it must not invent arithmetic, SKUs, or unsupported license assumptions
- session state is server-authoritative
- workbook and RVTools follow-ups are resolved from backend-owned context, not from client-only state
- quote export is derived from persisted deterministic quote state

## Evolving Areas

These areas are intentionally still being hardened:

- family metadata depth and capability coverage
- discovery and explanation structure
- active-quote follow-up breadth across more families
- parity breadth for larger mixed OCI bundles
- operational hardening such as observability, startup resilience, and concurrency safeguards

## Sources Of Truth

The repo uses a layered source strategy.

### 1. OCI Live Catalog JSON

Fetched at startup and cached to filesystem:

- `https://www.oracle.com/a/ocom/docs/cloudestimator2/data/products.json`
- `https://www.oracle.com/a/ocom/docs/cloudestimator2/data/metrics.json`
- `https://www.oracle.com/a/ocom/docs/cloudestimator2/data/productpresets.json`
- `https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/`

Purpose:

- active machine-readable pricing
- metrics and units
- additional product metadata

Notes:

- startup uses retries
- catalog snapshots are persisted in `pricing/data/catalog-cache/current/`
- health reporting surfaces catalog load state and retry attempts

### 2. Extracted Price-List Artifacts

These are the durable internal reference artifacts used by the runtime and coverage tooling:

- `pricing/data/xls-extract/`
- `pricing/data/price-list-extract/`
- `pricing/data/rule-registry/`

Purpose:

- workbook service names
- billing notes
- prerequisite rules
- family metadata
- coverage measurement

Important:

- `pricing/data/source-docs/current/` is **not** the normal repo source of truth anymore
- confidential source documents were removed from version control and history
- the repo now depends on extracted artifacts and generated registries instead

### 3. OCI Calculator Artifacts

Used for validation, not as the primary calculator:

- screenshots
- manual golden cases
- parity tests

Purpose:

- validate runtime behavior
- compare line items, quantities, and totals

### 4. Live Assistant Regression Reports

Used for validation of the API-backed assistant layer:

- `pricing/server/scripts/assistant-fuzz.js`
- `pricing/server/scripts/assistant-quality.js`
- [QUALITY_REGRESSION.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/operations/QUALITY_REGRESSION.md)

Purpose:

- verify live API consistency under controlled request pacing
- verify semantic quality of discovery answers across covered OCI services
- catch regressions where the assistant remains available but becomes less accurate or less useful

## Runtime Architecture

### 1. Catalog Bootstrap

Files:

- [index.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/index.js)
- [catalog.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/catalog.js)

Responsibilities:

- retrieve all four remote catalog feeds
- retry failed retrieves up to the configured max attempts
- cache snapshots locally
- merge `products.json` and `products-apex.json` without duplicating equivalent SKUs

### 2. Session Store

Files:

- [session-store.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/session-store.js)

Responsibilities:

- persist sessions server-side
- isolate sessions by `x-client-id`
- persist:
  - messages
  - `sessionContext`
  - `workbookContext`
  - `events`
- support versioned updates for safer concurrent session mutation

This is the current source of truth for chat state. The frontend is no longer intended to be the primary owner of context.

### 3. Intent Extraction

Files:

- [intent-extractor.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/intent-extractor.js)
- `genai` integration module

Responsibilities:

- detect route:
  - `general_answer`
  - `product_discovery`
  - `quote_request`
  - `quote_followup`
  - `workbook_followup`
  - `clarify`
- extract candidate family and inputs
- emit a structured `quotePlan`

### 4. Normalization

Files:

- [normalizer.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/normalizer.js)
- [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js)

Responsibilities:

- normalize aliases and user wording
- infer domain and candidate families
- refine the `quotePlan`
- route discovery questions away from the pricing engine
- rescue deterministic quotes only when inputs are explicit and safe

### 5. Structured Product Context

Files:

- [context-packs.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/context-packs.js)
- [vm-shapes.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/vm-shapes.js)

Responsibilities:

- build constrained context for GenAI
- expose:
  - family metadata
  - pricing dimensions
  - required inputs
  - licensing modes
  - options and variants
  - unsupported-compute guidance
  - active session quote/workbook context summaries

This layer is the main mechanism for reducing manual `if/else` behavior in the assistant.

### 6. Registry Layer

Files:

- [service-registry.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-registry.js)
- [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js)
- [vm_shape_rules.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/vm_shape_rules.json)
- [service_family_rules.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/service_family_rules.json)
- [followup_capability_matrix.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/followup_capability_matrix.json)
- [coverage_matrix.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/coverage_matrix.json)

The new follow-up artifact is the machine-readable summary of supported quote-mutation behavior by family. It is intended for:

- direct inspection during development
- lightweight registry tests
- future tooling or UI surfaces that need to explain what follow-ups are safe for a given family

Responsibilities:

- unify service metadata
- expose coverage status
- drive family-level discovery
- drive VM shape coverage
- support auditability outside the live runtime

### 7. Dependency Resolution

Files:

- [dependency-resolver.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/dependency-resolver.js)

Responsibilities:

- resolve billable parts from normalized requests
- rank candidate SKUs
- enforce prerequisites
- handle licensing-sensitive paths
- keep metric compatibility strict

### 8. Deterministic Pricing

Files:

- [quotation-engine.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/quotation-engine.js)
- [consumption-model.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/consumption-model.js)

Responsibilities:

- compute quantities
- interpret units such as:
  - `OCPU Per Hour`
  - `GPU Per Hour`
  - requests
  - storage capacity
  - performance units
- apply catalog rates and tiers
- generate auditable monthly and annual totals

### 9. Assistant Orchestration

Files:

- [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js)

Responsibilities:

- orchestrate routing
- call GenAI for explanation/discovery
- invoke deterministic engine only when safe
- return clarification or safe unavailability when coverage is incomplete

Important:

- fallback behavior is intentionally conservative
- if the service is not safely quotable, the assistant should say so rather than invent pricing

### 10. Frontend

Files:

- [index.html](/Users/javierchan/Documents/GitHub/oci/pricing/app/index.html)

Responsibilities:

- render server-authoritative sessions
- upload workbooks and images
- render guided clarification flows
- export/copy persisted quotes

Important:

- the frontend should only be a client of persisted backend state
- it should not be treated as the source of truth for conversation context

## API Capabilities

Primary implementation:

- [index.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/index.js)

The backend already exposes a usable application API, not just an internal server for the UI.

### 1. Assistant API

Endpoint:

- `POST /api/assistant`

Capabilities:

- accepts natural-language requests with `text`
- supports multimodal assistant requests with `imageDataUrl`
- consumes persisted session context when `sessionId` is provided
- falls back to inline `conversation` and `sessionContext` when no persisted session is used
- routes requests into:
  - `answer`
  - `quote`
  - `clarification`
- supports:
  - product discovery
  - pricing-dimension explanation
  - deterministic quote generation
  - quote follow-ups on active session quotes
  - workbook follow-ups when a workbook-backed session is active
- returns assistant metadata such as:
  - `intent`
  - `contextPackSummary`
  - `sessionContext`
  - persisted `session` snapshot when applicable

Operational notes:

- `OCI GenAI` must be configured or the endpoint returns a configuration error
- the OCI catalog must be ready before assistant requests are accepted
- session isolation is keyed by `x-client-id`

### 2. Raw GenAI Chat API

Endpoint:

- `POST /api/chat`

Capabilities:

- exposes a lower-level `OCI GenAI` chat bridge
- accepts custom `system` prompt and `messages`
- returns assistant text in a simple chat payload
- useful for prompt testing and controller-level debugging outside the full assistant orchestration

Important:

- this endpoint is not deterministic pricing
- it should not be treated as the source of truth for final quote math

### 3. Deterministic Quote API

Endpoint:

- `POST /api/quote`

Capabilities:

- deterministic quote generation from free text via `text`
- deterministic quote generation from structured pricing lines via `lines`
- returns:
  - quote results
  - line items
  - warnings
  - errors
  - monthly and annual totals

Supported usage patterns:

- direct single-service quote prompts
- structured programmatic quote calls
- regression-safe price validation without involving GenAI explanation

### 4. Workbook Estimation API

Endpoint:

- `POST /api/excel/estimate`

Capabilities:

- processes workbook-backed estimation requests
- persists workbook-driven interaction when `sessionId` is supplied
- supports backend-owned follow-up handling for workbook quote refinements
- returns parsed quote output plus updated session state

This is the API surface used for:

- Excel upload estimation
- workbook selection follow-ups
- RVTools and migration-style sizing flows already persisted in session state

### 5. Catalog And Registry APIs

Endpoints:

- `GET /api/catalog/search`
- `GET /api/catalog/:file`
- `POST /api/catalog/reload`
- `GET /api/coverage`

Capabilities:

- full-text search across:
  - normalized products
  - presets
  - service registry entries
- direct inspection of loaded raw catalog files:
  - `products.json`
  - `metrics.json`
  - `productpresets.json`
  - `products-apex.json`
- runtime catalog reload without restarting the application
- registry and coverage inspection for auditable service support status

This API group is useful for:

- debugging SKU resolution
- validating catalog ingestion
- inspecting runtime coverage and registry quality
- building internal tooling around supported OCI services

### 6. Session APIs

Endpoints:

- `GET /api/sessions`
- `POST /api/sessions`
- `GET /api/sessions/:id`
- `POST /api/sessions/:id/messages`
- `POST /api/sessions/:id/state`
- `GET /api/sessions/:id/quote-export`
- `DELETE /api/sessions/:id`
- `DELETE /api/sessions`

Capabilities:

- create and list persisted conversations
- retrieve full server-authoritative session state
- append messages server-side
- update:
  - `sessionContext`
  - `workbookContext`
  - `title`
- export the last persisted quote in HTTP form
- delete one session or clear all sessions for a client

Concurrency notes:

- session writes support `expectedVersion`
- conflicting updates return `409`
- the backend, not the browser, is the authority for session mutation

### 7. Health And Configuration APIs

Endpoints:

- `GET /api/health`
- `GET /api/providers`

Capabilities:

- report OCI catalog readiness and per-file load state
- expose retry attempts and last catalog errors
- report whether `OCI GenAI` is configured
- surface active model/provider metadata such as:
  - region
  - endpoint
  - compartment
  - modelId
  - profile

These endpoints are the current operational entry point for:

- smoke tests
- local environment validation
- readiness checks before assistant or quote traffic

### API Design Characteristics

The current API design already has several strong properties:

- deterministic pricing is separated from LLM interpretation
- assistant traffic is stateful when desired, but can still run statelessly
- session state is backend-owned and exportable
- catalog and coverage inspection are first-class runtime capabilities
- workbook flows and chat flows converge in a single persisted session model
- the same backend can serve:
  - frontend UI
  - manual API testing
  - regression tooling
  - future automation clients

## Coverage Model

Coverage levels:

- `L0`: not usable
- `L1`: searchable only
- `L2`: deterministically quotable
- `L3`: quotable + explainable
- `L4`: quotable + explainable + prerequisites/licensing modeled

Current machine-readable source:

- [coverage_matrix.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/coverage_matrix.json)

Current snapshot at time of this doc update:

- workbook services: `1004`
- VM shapes in registry: `23`
- compute residual uncovered count: `0`
- runtime coverage:
  - `L4`: `525`
  - `L3`: `31`
  - `L2`: `9`
  - `L1`: `439`

These values should be refreshed from the generated artifact, not edited manually when coverage changes.

## Current Strengths

- server-authoritative chat/session model
- deterministic pricing on major OCI families
- workbook and RVTools sizing with persisted artifact context
- explicit VM shape coverage with calculator-aligned registries
- growing OCI Calculator parity suite
- safer handling of unsupported residual compute

## Current Pending Work

- widen parity coverage across more OCI Calculator scenarios
- keep moving manual logic out of `assistant.js` and into registries/context packs
- continue formalizing `quotePlan` as the contract between interpretation and pricing
- broaden quote-followup coverage for more families and modifiers
- improve observability and production telemetry

## Development Rule

When adding support for a new OCI family, prefer this order:

1. update family metadata or registries
2. update context packs
3. update normalization and `quotePlan` shaping
4. update deterministic resolver/pricing only if required
5. add parity/regression tests
6. only then add narrow assistant-specific logic if there is still a real gap

If a fix only helps one prompt and does not improve metadata, routing, or deterministic behavior, it is probably the wrong abstraction.
