# Architecture

## Purpose

`pricing` is a deterministic OCI pricing engine with a natural-language assistant on top.

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

### Implemented But Still Being Expanded

- family metadata in `pricing/server/service-families.js`
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
- [coverage_matrix.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/coverage_matrix.json)

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
