# Coverage Roadmap

## Purpose

This document is the operational roadmap for the `pricing` agent.

Use it to answer:

- what is already implemented
- what is covered deterministically today
- what is still pending
- what the next production-grade milestones are

This file is intentionally shorter and more actionable than a running changelog.

## Current Snapshot

Reference artifacts:

- [coverage_matrix.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/coverage_matrix.json)
- [service_family_rules.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/service_family_rules.json)
- [vm_shape_rules.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/vm_shape_rules.json)

Current generated snapshot:

- workbook services: `1004`
- pdf billing rules: `364`
- pdf prerequisite rules: `60`
- VM shapes in registry: `23`
- service families in registry artifact: `9`
- compute residual uncovered count: `0`

Runtime coverage snapshot:

- `L4`: `525`
- `L3`: `31`
- `L2`: `9`
- `L1`: `439`

Interpretation of the current state:

- the most critical `compute residual` block that had been producing misroutes is closed
- the agent is now materially stronger in deterministic quoting than it was at the beginning of this project
- the remaining gaps are mostly:
  - broader parity coverage
  - more declarative metadata
  - more backend follow-up coverage
  - production hardening

## Implemented In Codebase

### Catalog And Source Ingestion

Implemented:

- startup retrieval of all four live OCI catalog feeds
- retry policy for catalog retrieval
- filesystem snapshots in `pricing/data/catalog-cache/current/`
- merged catalog view that includes `products-apex`

Reference:

- [index.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/index.js)
- [catalog.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/catalog.js)

### Sessions And Frontend Persistence

Implemented:

- server-authoritative sessions
- session isolation by `x-client-id`
- persisted:
  - messages
  - session context
  - workbook context
  - event log
- workbook and RVTools follow-ups handled from backend state
- quote export from persisted session quote

Reference:

- [session-store.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/session-store.js)
- [index.html](/Users/javierchan/Documents/GitHub/oci/pricing/app/index.html)
- [index.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/index.js)

### GenAI Routing And Structured Context

Implemented:

- `route + quotePlan` extraction
- structured product context for discovery and explanation
- discovery questions routed away from quote generation
- conceptual prerequisite and quote-composition questions now stay in discovery or answer mode even when the controller over-predicts a quote path
- active-quote conceptual follow-ups now answer without mutating the persisted quote source for covered SKU/component and compute-composition questions
- discovery and explanation prompts with quotable numeric inputs now stay in answer/discovery mode instead of being auto-promoted into deterministic quotes by registry fallback matching
- route normalization now also overrides explicit `quote_request` outputs for clearly explanatory pricing-dimension prompts with measurable inputs
- safer unsupported-service replies when deterministic pricing should not run

Reference:

- [intent-extractor.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/intent-extractor.js)
- [normalizer.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/normalizer.js)
- [context-packs.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/context-packs.js)
- [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js)

### Deterministic Pricing

Implemented:

- deterministic line-item resolution
- metric-aware quantity calculation
- tier-aware pricing
- annual/monthly rollups
- quote export paths

Reference:

- [quotation-engine.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/quotation-engine.js)
- [dependency-resolver.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/dependency-resolver.js)
- [consumption-model.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/consumption-model.js)
- [quote-export.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/quote-export.js)

### VM Shape Coverage

Implemented:

- calculator-aligned VM shape registry
- fixed vs flex handling
- Intel, AMD, and Ampere VM shape coverage
- fixed bare metal legacy coverage in registry
- last major residual compute mismatches closed

Current registry snapshot:

- total shapes: `23`
- flex: `11`
- fixed: `12`

Reference:

- [vm_shape_rules.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/vm_shape_rules.json)
- [vm-shapes.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/vm-shapes.js)

### Workbook And RVTools

Implemented:

- workbook guided quoting
- RVTools detection and VMware-aware sizing
- `vCPU -> OCPU` conversion for VMware x86
- block volume sizing and `VPU` overrides
- persisted workbook follow-ups within a session
- workbook-derived compute requests now also have regression coverage when composed with shared edge and observability services such as load balancer, DNS, FastConnect, monitoring retrieval, and health checks
- workbook-derived requests now also have regression coverage for shared connectivity plus observability combinations, including `FastConnect + Monitoring Retrieval`, across both RVTools single-request paths and guided inventory aggregates
- workbook-origin and RVTools-origin follow-ups now also have regression coverage when shape, VPU, or capacity-reservation changes must preserve shared `FastConnect + Monitoring Retrieval` services in the persisted quote source
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage when shared `FastConnect` or `Monitoring Retrieval` components are explicitly removed from the persisted quote source
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for safe shared-service replacements such as `FastConnect -> DNS`, `Monitoring Retrieval -> Health Checks`, `DNS -> Health Checks`, and `Health Checks -> DNS`
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for parameter-only mutations on persisted shared services, including `FastConnect bandwidth`, `DNS query volume`, and `Health Checks endpoint count`

Reference:

- [excel.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/excel.js)
- [index.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/index.js)

### OCI Calculator Parity

Implemented:

- parity suite exists and is actively used
- parity coverage includes major families already exercised in runtime:
  - compute
  - block volume
  - load balancer
  - WAF
  - fastconnect
  - DNS
  - API Gateway
  - Email Delivery
  - File/Object Storage
  - OIC
  - OAC
  - Base Database Service
  - Database Cloud Service
  - Data Safe
  - Network Firewall
- several observability/platform services
- parity already includes mixed database, integration, storage, and edge bundles instead of only isolated family cases
- parity now also exercises larger enterprise bundles that mix analytics/integration with file storage and Exadata platform lines
- parity now also covers enterprise database and Exadata bundles that mix observability and security primitives such as monitoring, health checks, firewall, and log analytics
- parity now also covers Base Database, Database Cloud Service, and Exadata Cloud@Customer combinations that mix Data Safe, monitoring, health checks, notifications, and log analytics in the same deterministic request
- parity now also covers Autonomous AI Lakehouse and Autonomous AI Transaction Processing bundles that mix Data Integration, firewall, load balancer, DNS, monitoring, notifications, and health checks

Reference:

- [calculator-parity.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/calculator-parity.test.js)

### Current Test Baseline

Current test baseline:

- assistant follow-up regression suite: `242 pass / 0 fail`
- workbook-focused suite: `27 pass / 0 fail`
- parity suite: `136 pass / 0 fail`
- quote export endpoint suite: `3 pass / 0 fail`
- full server suite in sandbox: `483 pass / 0 fail`

This is the operational baseline at the time of this documentation update.

## What Is Explicitly Closed

These blocks should now be treated as closed unless a regression reopens them:

### 1. Server-Authoritative Session Model

Closed:

- frontend is no longer the source of truth for active session state
- workbook follow-up detection is backend-owned
- session events and contexts are persisted server-side

### 2. Critical VM Shape Misclassification

Closed:

- `VM.Standard3.Flex` and related VM-family gaps that were causing severe misroutes
- `computeVariantAudit.uncoveredServiceCount = 0`

### 3. Copy/Export Based On Persisted Quotes

Closed at baseline level:

- `Copy Quote`
- `Export CSV`
- `Export XLSX`

These now operate from persisted quote state rather than depending purely on transient DOM state.

### 4. Safe Failure Policy

Closed at baseline level:

- unsupported pricing scenarios should return safe guidance or clarification
- the agent should not invent deterministic quotes for unsupported families

## What Is Still Pending

### 1. Broader OCI Calculator Parity

Pending:

- more multi-service golden cases
- more database combinations
- more analytics/integration combinations
- more workbook/RVTools parity cases
- more mixed networking/security architectures

Why this matters:

- parity is the strongest evidence that the deterministic engine is production-safe

### 2. More Declarative Family Coverage

Pending:

- move more behavior from `assistant.js` into:
  - `service-families`
  - `context-packs`
  - generated registries
- continue moving non-follow-up family policy out of `assistant.js`
- extend the declarative capability matrix beyond the currently hardened active-quote replacement categories

Why this matters:

- lowers long-term maintenance cost
- reduces one-off prompt handling

### 3. Stronger Quote Follow-Ups Across More Families

Pending:

- more complete backend quote-followup support for:
  - licensing changes
  - component add/remove
  - currency/modifier updates
  - conceptual active-quote questions that should answer instead of mutate
  - family-specific modifications outside the currently hardened set

### 4. Observability And Production Telemetry

Pending:

- better per-turn structured logs for:
  - route
  - quotePlan
  - context pack summary
  - quote source
  - warnings
- stronger startup and health diagnostics

### 5. Concurrency And Multiuser Hardening

Pending:

- more explicit tests for concurrent session mutation
- more verification of session isolation at scale
- more browser rehydration and race-condition tests

## Not In Scope For “Done”

These are intentionally not required for considering the current roadmap materially successful:

- quoting every OCI service in existence
- removing GenAI entirely from the system
- perfect zero-maintenance parity for all future Oracle catalog changes

The target is a production-grade pricing agent for the practical OCI quoting perimeter, not infinite scope.

## Next Recommended Work Order

### Priority 1

- widen OCI Calculator parity with more family-level and bundled scenarios

### Priority 2

- keep moving family and discovery logic out of `assistant.js` into registries and context packs

### Priority 3

- expand backend quote-followup handling across more complex families

### Priority 4

- strengthen observability, startup checks, and multiuser concurrency coverage

## Update Rule For This Document

When this roadmap is updated:

1. refresh values from generated artifacts instead of editing counts by memory
2. move work from `Pending` to `Implemented` only after code + tests are green
3. treat one-off fixes as incomplete unless they improve metadata, parity, or deterministic runtime behavior

This file should remain a reference document, not a historical dump of every incremental change.
