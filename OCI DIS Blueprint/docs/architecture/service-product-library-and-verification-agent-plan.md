# Service Product Library and Verification Agent Plan

## Objective

Move OCI service-product knowledge out of generic assumptions and into a governed, verifiable product library for data integration architecture. The library should describe each service, its role in integration patterns, interoperability, limits, operational constraints, evidence sources, and verification freshness.

Assumptions should then focus on client/project business variables that affect sizing or architecture decisions when the client has not yet provided enough information.

Integration patterns remain tool-agnostic. A pattern describes an architectural shape; service products describe concrete capabilities, interoperability rules, limits, and evidence for a specific implementation option.

## Product Rationale

The current Library groups patterns, dictionaries, assumptions, and synthetic lab. That is useful for workbook parity, but it mixes three different governance categories:

- Architecture rules: what OCI services can do, how they interoperate, and where hard limits apply.
- Reference metadata: controlled option sets, patterns, tools, service taxonomies, and descriptions.
- Client assumptions: missing client-specific business inputs used to model sizing, risk, and recommendations.

This proposal adds a first-class `Service Products` area to Admin Library and creates a verification agent that checks high-value external sources before the product team treats service metadata as current.

Implementation note, Jun 7 2026: Phase 1 reuses `service_capability_profiles` as the canonical service-product base so existing Canvas and service-profile consumers remain backward-compatible. Normalized child tables now provide versions, limits, evidence, interoperability rules, verification jobs, and verification findings.

## Proposed Library Navigation

Admin Library should expose five main cards:

- `Integration Patterns`
- `Dictionaries`
- `Service Products`
- `Assumptions`
- `Synthetic Lab`

`Service Products` is the canonical place for:

- Oracle Integration 3
- OCI Data Integration
- OCI Data Flow
- OCI Data Catalog
- OCI Streaming
- OCI Functions
- OCI API Gateway
- OCI Events
- OCI Queue
- OCI Object Storage
- OCI Service Connector Hub
- OCI GoldenGate
- OCI GoldenGate Data Transforms
- Oracle Data Integrator
- Oracle Stream Analytics
- Oracle Enterprise Data Quality
- Optional future Oracle entries: Autonomous Database, Oracle Database adapters, Vault, Logging, Monitoring.

Scope decision, Jun 7 2026: non-Oracle products are intentionally out of scope for the current Service Product Library. The verification agent allowlist remains Oracle-controlled sources only.

`Assumptions` becomes the place for global client/project variables such as:

- Business hours and operating calendar.
- Expected growth multipliers.
- Batch windows.
- Peak-hour concentration.
- Retry policy defaults.
- Payload unknown defaults.
- Region and deployment model.
- Client tenancy limit overrides when known.
- Data retention expectations.
- Security classification defaults.
- SLA/RTO/RPO assumptions.

## Domain Model

### New Tables

#### `service_products`

Canonical product/service entry.

Suggested fields:

- `id`
- `service_key`
- `display_name`
- `vendor`
- `category`
- `summary`
- `architecture_role`
- `status`
- `governance_state`
- `last_verified_at`
- `verification_status`
- `verification_score`
- `owner_id`
- `created_at`
- `updated_at`

Example categories:

- `integration_runtime`
- `data_movement`
- `event_streaming`
- `serverless_compute`
- `api_management`
- `storage`
- `observability`
- `security`

#### `service_product_versions`

Versioned metadata snapshots so review decisions are reproducible.

Suggested fields:

- `id`
- `service_product_id`
- `version_label`
- `description`
- `capabilities`
- `use_cases`
- `anti_patterns`
- `regional_availability`
- `commercial_notes`
- `security_notes`
- `deprecation_notes`
- `metadata`
- `effective_from`
- `created_at`
- `created_by`

#### `service_limits`

Hard or soft constraints that can be used by QA, sizing, canvas validation, and AI Review.

Suggested fields:

- `id`
- `service_product_id`
- `limit_key`
- `label`
- `scope`
- `limit_type`
- `value`
- `unit`
- `default_value`
- `can_request_increase`
- `source_url`
- `source_retrieved_at`
- `confidence`
- `notes`

Limit types:

- `hard`
- `soft`
- `quota`
- `performance`
- `payload`
- `retention`
- `regional`
- `operational`

#### `service_interoperability_rules`

Matrix-level rules that explain how products can or should be combined.

Suggested fields:

- `id`
- `source_service_product_id`
- `target_service_product_id`
- `relationship_type`
- `supported`
- `directionality`
- `patterns`
- `required_components`
- `constraints`
- `risk_notes`
- `source_url`
- `confidence`
- `last_verified_at`

Relationship types:

- `adapter`
- `native_action`
- `event_source`
- `event_target`
- `stream_producer`
- `stream_consumer`
- `function_invocation`
- `storage_source`
- `storage_target`
- `private_connectivity`

#### `service_evidence_sources`

Source registry for verification.

Suggested fields:

- `id`
- `service_product_id`
- `source_type`
- `url`
- `title`
- `publisher`
- `trust_tier`
- `retrieval_strategy`
- `expected_update_frequency_days`
- `last_checked_at`
- `last_changed_at`
- `content_hash`
- `status`

Trust tiers:

- `tier_1_official_docs`
- `tier_1_release_notes`
- `tier_1_api_reference`
- `tier_2_official_blog`
- `tier_3_engineering_reference`
- `manual_evidence`

#### `service_verification_jobs`

Job record for the execute agent.

Suggested fields:

- `id`
- `requested_by`
- `scope`
- `status`
- `started_at`
- `completed_at`
- `services_checked`
- `sources_checked`
- `changes_detected`
- `findings`
- `recommendations`
- `error_details`
- `created_at`

#### `service_verification_findings`

Diff and decision queue from verification jobs.

Suggested fields:

- `id`
- `job_id`
- `service_product_id`
- `finding_type`
- `severity`
- `title`
- `summary`
- `old_value`
- `new_value`
- `source_url`
- `evidence_excerpt`
- `recommended_action`
- `review_status`
- `reviewed_by`
- `reviewed_at`

Finding types:

- `new_limit`
- `changed_limit`
- `removed_limit`
- `changed_description`
- `new_interoperability_rule`
- `deprecated_capability`
- `source_unavailable`
- `needs_human_review`

### Refactor Existing Tables

#### `AssumptionSet`

Keep versioned, project-independent defaults, but restrict semantic scope to client/business variables and project modeling defaults.

Examples that should remain assumptions:

- Unknown payload fallback.
- Growth multiplier.
- Peak hour ratio.
- Business calendar.
- Retry default.
- Retention assumption when client did not provide one.
- Client tenancy quota override if unknown.

Examples that should move to Service Products:

- OIC payload limits.
- Streaming partition limits.
- Functions request/response payload maximums.
- Data Integration workspace count limits.
- Adapter-specific constraints.
- Native service interoperability.

## API Plan

Add route group:

```text
/api/v1/service-products
```

Endpoints:

- `GET /api/v1/service-products`
- `GET /api/v1/service-products/{service_key}`
- `GET /api/v1/service-products/{service_key}/limits`
- `GET /api/v1/service-products/{service_key}/interoperability`
- `GET /api/v1/service-products/matrix`
- `GET /api/v1/service-products/verification-alerts`
- `POST /api/v1/service-products/verification-jobs`
- `GET /api/v1/service-products/verification-jobs`
- `GET /api/v1/service-products/verification-jobs/{job_id}`
- `GET /api/v1/service-products/verification-jobs/{job_id}/findings`
- `POST /api/v1/service-products/verification-jobs/{job_id}/findings/{finding_id}/review`

Authorization:

- Viewer: read service library.
- Admin: run verification jobs and record finding review decisions.
- Future productization can split run/review permissions by Analyst and Architect once service-layer RBAC has first-class scoped roles for this module.
- Admin: mutate service products, evidence sources, and limits.

Every accepted change must emit `AuditEvent`.

## Verification Agent Plan

### Execution Model

Use a Celery job for normal execution. A bounded `sync` execution mode exists only for smoke tests and controlled local validation.

Flow:

1. Admin or Analyst clicks `Verify with Agent`.
2. API creates `service_verification_jobs` with status `pending`.
3. Celery worker fetches trusted sources.
4. Agent extracts structured claims:
   - limits
   - capabilities
   - interoperability
   - deprecations
   - changed dates
5. Agent compares extracted claims against current `service_products`, `service_limits`, and `service_interoperability_rules`.
6. Job writes findings, but does not auto-change governed rules.
7. Architect/Admin reviews and accepts findings.
8. Accepted findings update governed tables and emit audit events.
9. Impact analysis flags affected patterns, canvas combinations, QA checks, and assumptions.

### Source Policy

Default source priority:

1. Oracle official docs.
2. Oracle release notes / What's New.
3. Oracle API references.
4. Oracle official blog or architecture center.
5. Manual evidence uploaded by Admin.

Non-goals:

- Do not scrape random blogs as authoritative rules.
- Do not auto-apply changes from the internet.
- Do not treat LLM summaries as source of truth.

### Evidence Record

Each extracted claim should store:

- source URL
- retrieved timestamp
- source title
- content hash
- exact section label when available
- extracted value
- confidence
- parser/agent version

### Network and Security

The agent needs outbound internet access, but it should be isolated:

- Allowlist domains, initially `docs.oracle.com` and official Oracle documentation surfaces.
- No customer data is sent to external sources.
- Source fetches are read-only.
- Store raw snapshots only if licensing permits; otherwise store content hash, structured claim, URL, and short evidence excerpt.
- Add per-job timeout and source count limits.
- Add audit events for job creation and accepted updates.

## UI Plan

### Admin Library

Add `Service Products` card:

- count of governed services
- last verification date
- stale source count
- open findings count
- `Manage` action

### Service Products List

Columns:

- Service
- Category
- Architecture role
- Last verified
- Verification status
- Open findings
- Linked patterns
- Linked tools

Filters:

- Category
- Verification status
- Stale only
- Has findings
- Used by current workbook patterns

### Service Detail

Tabs:

- `Overview`
- `Capabilities`
- `Limits`
- `Interoperability`
- `Patterns`
- `Evidence`
- `Verification Jobs`

### Interoperability Matrix

Grid:

- rows: source services
- columns: target services
- cell state:
  - supported
  - supported with constraints
  - not recommended
  - unknown
  - deprecated

Cell detail:

- relationship type
- required components
- supported patterns
- constraints
- evidence source
- last verified

### Verification UX

Controls:

- `Verify all`
- `Verify selected service`
- `Verify stale sources`
- `Review findings`

Finding drawer:

- old value
- new value
- source link
- confidence
- impact analysis
- accept / dismiss

## Impact on Existing Product Logic

### Canvas

Canvas validation should read:

- `service_interoperability_rules`
- `service_limits`
- governed combinations
- pattern support matrix

This lets the canvas explain why a service route is supported, constrained, or risky while keeping integration patterns tool-agnostic.

### AI Review

AI Review should cite:

- service product version
- specific limits
- source verification freshness
- stale/changed evidence warnings

### Volumetry

Calc-engine should continue to receive a pure assumptions/rules object, but the API service should assemble it from:

- client assumptions
- service product limits
- pattern rules
- project overrides

Calc-engine remains pure and unaware of SQL/API.

### Exports

XLSX/JSON/PDF/brief exports should include:

- service product version used
- verification date
- stale evidence warnings
- accepted override notes

### Dashboard

Add confidence indicators:

- `service rules current`
- `stale product metadata`
- `tenancy quota unknown`
- `client assumptions unresolved`

## Migration Strategy

### Phase 1 — Read Model and Seed

- Add new tables.
- Seed initial service products from current dictionaries/assumptions/tool taxonomy.
- Copy service limits out of `AssumptionSet` into `service_limits`.
- Keep assumptions backward-compatible during transition.
- Add read-only UI pages.

Exit criteria:

- Service Products visible in Library.
- Current app behavior unchanged.
- Existing tests pass.

### Phase 2 — Verification Agent

- [x] Add evidence source registry.
- [x] Add verification job tables.
- [x] Add bounded execution with source allowlist, HTTP fetch, content hashes, source status updates, and auditable jobs.
- [x] Implement structured findings for source changes, unavailable sources, and non-allowlisted sources.
- [x] Add manual finding review flow.
- [x] Move long-running verification to Celery for scheduled and large-scope runs.
- [x] Add source-claim extraction so findings can propose specific limit diffs.
- [x] Add governed acceptance so approved limit findings update `service_limits` with audit events.
- [x] Add verification alert queue for stale sources and open findings.

Exit criteria:

- Agent can verify one service from official docs.
- Findings are auditable.
- No automatic rule mutation.
- Default API execution returns a pending job and dispatches Celery; accepted findings mutate governed tables only after human approval.

### Phase 3 — Rule Consumption

- Update canvas validation to read service interoperability.
- Update AI Review evidence bundle to include service product metadata and verification freshness.
- Update export brief and dashboard confidence signals.
- Update calc-engine input assembly while preserving calc-engine purity.

Exit criteria:

- Canvas and AI Review explain service constraints from governed products.
- Volumetry output remains deterministic.
- Regression tests cover service limit ingestion.

### Phase 4 — Assumption Split

- Refactor Assumptions UI into business/client assumptions only.
- Add migration report showing moved keys.
- Add compatibility shim for older snapshots.
- Update documentation and export labels.

Exit criteria:

- Assumptions no longer own hard service rules.
- Historical snapshots remain reproducible.

### Phase 5 — Productization Hardening

- Add role and approval policies.
- Add domain allowlist configuration.
- Add source refresh schedule.
- Add stale metadata alerts.
- Add CI contract checks for seeded service metadata.
- Add admin runbook.

Exit criteria:

- Production-ready source verification workflow.
- Evidence freshness visible in UI.
- No unaudited internet-derived rule changes.

## Testing Plan

Backend:

- Migration tests for service tables.
- Seed tests for core OCI services.
- API contract tests for list/detail/matrix.
- Verification worker tests with mocked official docs snapshots.
- Accept/dismiss audit tests.
- Regression tests for AI Review evidence bundles.
- Regression tests for canvas validation.

Frontend:

- Library card render.
- Service list filters.
- Service detail tabs.
- Interoperability matrix.
- Verification job lifecycle.
- Findings drawer accept/dismiss.
- Dark/light visual checks.

End-to-end:

- Seed service products.
- Run verification job against mocked source.
- Accept changed limit.
- Confirm canvas and AI Review cite updated value.
- Confirm export includes service metadata version.

## Acceptance Criteria

- Service Products is visible from Admin Library.
- Service limits and interoperability are governed separately from client assumptions.
- Verification jobs can check official sources and produce findings.
- No external finding mutates rules without Architect/Admin approval.
- Accepted findings are audited.
- Canvas, AI Review, dashboard, and exports can cite the service product version used.
- Historical snapshots remain reproducible.

## Initial Source Registry Candidates

- Oracle Integration 3 documentation and adapters/connectivity.
- Oracle Integration 3 service limits.
- OCI Limits by Service.
- OCI Data Integration documentation.
- OCI Streaming limits.
- OCI Functions limits and payload limits.

## Open Decisions

- Whether to store source snapshots or only structured claims plus hashes.
- Whether verification schedule should be enabled in production by default or kept opt-in via `SERVICE_VERIFICATION_SCHEDULE_ENABLED`.
- Whether tenant-specific OCI quota overrides should live in project settings or assumption sets.
- Whether to include non-Oracle products is deferred; current scope is Oracle-only.
- Whether the verification agent should use browser-based extraction, HTTP-only fetch, or curated adapters per source.
