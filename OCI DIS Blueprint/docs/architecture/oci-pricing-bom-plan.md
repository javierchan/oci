# OCI Pricing and Governed BOM Plan

**Status:** Complete and validated on 2026-07-12
**Milestone:** M27 - Governed OCI Pricing and Bill of Materials
**Reference analyzed:** `OCI_Estimation_Sheet_Customer_WIP.xlsm`

## Objective

Add a governed commercial estimation capability that converts the project's
technical integration demand into an auditable OCI Bill of Materials (BOM).
The result must use current Oracle pricing, preserve the exact price and sizing
inputs used by each estimate, and distinguish public list price from a
customer-specific contracted rate card.

The BOM is an estimate, not an Oracle quote. The existing technical dashboard
remains cost-free by default; commercial information is exposed only through an
explicit project-level BOM module and the corresponding permissions.

## Reference Workbook Findings

The workbook is a VBA-based OCI estimator with these relevant layers:

1. `Settings` stores the pricing, product-preset, and metrics endpoints plus
   language and currency.
2. `OCI Pricing List` materializes a price table keyed by Oracle B Part Number,
   price type, currency, metric, PAYG value, and optional tier range.
3. `OCI Product Presets List` maps Oracle service presets to one or more SKUs.
4. `Master Sheet` builds the service/category hierarchy used by the quotation UI.
5. `Quotation` captures environment, product, metric quantity, instance count,
   monthly hours, and compute modifiers.
6. VBA UDFs such as `CalcRate`, `GetPAYGPriceFromPriceList`,
   `GetPAYGPricePerHour2`, and `GetPAYGPricePerMonth2` resolve modifiers, tiered
   prices, hourly/monthly units, and extended monthly/annual amounts.
7. `Summary` aggregates quotation lines by environment.
8. `BOM` and the dashboard sheets turn those lines into contract-year and
   monthly views.

The workbook refreshes public JSON into Excel and then performs pricing inside
VBA. The App should preserve its useful behavior, but replace mutable worksheet
state with normalized records, immutable snapshots, deterministic calculations,
and auditable review decisions.

The workbook owner has explicitly authorized extracting and copying the formulas,
VBA behavior, pricing tables, presets, and fixtures needed for implementation and
parity validation. The complete workbook should still not be served by the App or
copied into production images. Repository fixtures should remain narrowly scoped
to the behavior under test so CI stays deterministic and maintainable.

## Critical Domain Boundary

The catalog and integration canvas represent **logical integration demand**.
They do not define the physical OCI deployment.

A BOM must not assign one OCI instance or one SKU set to every integration row.
Many integrations share OIC instances, Streaming pools, API Gateways, workspaces,
or observability services. Before pricing, the App needs a project-level
deployment scenario that answers:

- environments: production, QA, development, DR, and others;
- tenancy and region placement;
- shared versus dedicated service instances;
- availability, redundancy, and disaster-recovery policy;
- OIC edition and license model;
- active hours and active months;
- capacity headroom and growth horizon;
- free-tier allocation scope;
- customer-specific commercial rate card, if available.

The governed pipeline is therefore:

```text
Catalog + canvases
        -> technical demand snapshot
        -> approved deployment scenario
        -> service sizing results
        -> approved SKU mapping
        -> immutable price catalog snapshot
        -> deterministic BOM snapshot
        -> review, compare, and export
```

## Fit in the Existing App

### Reuse

- `Service Product Library` remains the canonical identity, capability, limit,
  interoperability, and evidence owner for OCI products.
- `VolumetrySnapshot` remains the immutable source of technical demand.
- Celery runs price synchronization and BOM generation as terminal jobs.
- MinIO / OCI Object Storage stores source payloads and generated exports.
- Existing AuditEvent, evidence verification, exports, and AI Review patterns
  are reused.
- The pure-engine contract remains: services assemble immutable inputs and a
  calculation package performs no database, HTTP, or Celery I/O.

### Add

- A project-level `BOM & Cost` workspace next to Dashboard, Catalog, and Map.
- An Admin Library area for `Pricing Catalog & SKU Mappings`.
- A deployment-scenario editor that bridges technical demand and physical OCI
  resources.
- A separate pure `packages/pricing-engine/` package.
- Price-source adapters for public list pricing and optional contracted rates.

### Keep Separate

- Service limits are not prices.
- Client workload assumptions are not contractual rates.
- Public list price and negotiated net unit price are not interchangeable.
- Technical recalculation does not silently rewrite an approved BOM.
- AI recommendations do not become prices, mappings, or BOM lines without an
  explicit governed approval.

## Price Sources

### Public List Price

Use Oracle's documented product-pricing endpoint as the primary public source:

`https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/`

It supports filtering by `partNumber` and `currencyCode` and returns B Part
Number, display name, metric, service category, PAYG value, and tier ranges.

The legacy web assets embedded in the workbook can be supported only as a
temporary compatibility adapter. They must not be the authoritative production
contract when Oracle documents a supported endpoint.

### Contracted Rate Card

For an authorized customer tenancy, use OCI Subscription Rate Card APIs. These
provide part number, currency, net unit price, discretionary discount, effective
dates, and tiered rates. Credentials must come from workload identity / OCI
configuration and least-privilege policies, never from browser input or committed
environment files.

Also support a governed CSV rate-card upload for cases where direct OCI access is
not permitted. Store the original object, hash, parser version, uploader, and
effective dates.

### Pricing Policy

- Never silently convert currencies.
- Never infer a negotiated discount from list prices.
- Preserve tier semantics (`rangeMin` exclusive, `rangeMax` inclusive).
- Treat free tiers as tenancy-scoped allocation rules, not per-project discounts.
- Keep taxes, support rewards, financing, and contractual commitments excluded
  unless a future explicitly governed module models them.
- Label every result `public_list`, `contract_rate`, or `manual_rate_card`.

## Proposed Data Model

### Pricing Catalog

- `price_sources`: source type, URL/OCI tenancy reference, trust tier, status.
- `price_sync_jobs`: requested scope, currency, state, counts, errors, timestamps.
- `price_catalog_snapshots`: immutable source hash, currency, retrieved/effective
  timestamps, adapter version, approval state.
- `price_items`: part number, description, service category, metric, price type,
  currency, value, tier bounds, unit, effective dates.
- `price_sync_findings`: additions, removals, price changes, unit changes, and
  ambiguous records requiring review.

### Product-to-SKU Resolution

- `service_product_sku_mappings`: Service Product, part number, billing metric,
  edition/license/deployment predicates, formula key, mapping status, evidence,
  confidence, effective dates.
- `service_product_sku_mapping_versions`: immutable approved mapping bundles.

A service can map to multiple SKUs. Examples include Functions execution plus
invocations, Data Integration workspace plus data processed plus operator
execution, and Streaming transfer plus storage.

### Deployment and Commercial Context

- `deployment_scenarios`: project, name, state, region, currency, horizon,
  technical snapshot, growth policy, and approval data.
- `deployment_environments`: environment, active hours/month, active months/year,
  HA/DR role, headroom, shared/dedicated policy.
- `service_deployments`: service product, environment, edition, license model,
  instance/workspace/deployment count, capacity, sizing rationale, override data.
- `commercial_profiles`: price-source preference and rate-card reference. Sensitive
  contract details remain access controlled and separate from AssumptionSet.

### BOM

- `bom_jobs`: job lifecycle and terminal status.
- `bom_snapshots`: immutable references to technical, deployment, mapping, and
  price snapshots plus engine version and totals.
- `bom_line_items`: service, SKU, metric, quantity, unit, unit price, tier,
  monthly/annual amount, environment, formula, inputs, warnings, and provenance.
- `bom_review_findings`: missing metrics, unmapped products, stale prices,
  contradictory options, and manual overrides.

## Deterministic Pricing Engine

Create `packages/pricing-engine/` with typed, pure functions for:

- unit normalization and monthly-hour conversion;
- tier selection and graduated/range pricing;
- hourly, monthly, per-item, and utilized-hour models;
- free-tier allocation across a tenancy-scoped scenario;
- PAYG versus BYOL/edition selection;
- monthly, annual, and contract-horizon extension;
- line, service, environment, and project reconciliation;
- structured `PricingResult` output containing value, currency, formula, inputs,
  selected tier, source item ID, and reason.

No network or database access is allowed in this package. Rounding occurs only at
the output boundary and uses currency precision from the price source.

## Current Project Readiness

The active project currently has 480 integrations and a fresh technical snapshot.
It already provides useful demand for:

- OIC: monthly billing messages, peak hourly messages, and peak packs;
- Data Integration: active workspace indicator and processed GB/month;
- Functions: invocations/month and GB-seconds/month;
- Streaming: transferred GB/month and partition count;
- Queue: usage presence;
- canvas/product footprint: GoldenGate, API Gateway, Events, and Process Automation.

It is not yet sufficient for a complete defensible BOM:

- Queue lacks request-unit calculation.
- Data Integration lacks operator execution hours and explicit workspace hours.
- Streaming needs storage GB-hours distinct from transfer GB.
- GoldenGate lacks OCPU/deployment sizing and BYOL choice.
- API Gateway lacks API call count.
- OIC needs approved edition, BYOL choice, environment count, and shared-instance
  allocation.
- Events and Process Automation need explicit billable/non-billable resolution.
- The catalog has no governed physical environment/deployment topology.

The first generated BOM must show coverage and blockers, not fabricate missing
quantities. A 100% total is allowed only when every used billable product is
mapped and every required metric is present or explicitly approved as an override.

## Smart Assistance

AI adds value around deterministic pricing rather than replacing it:

1. **Deployment Scenario Drafting**: propose shared/dedicated services,
   environments, HA/DR, and headroom from catalog topology and risk profile.
2. **SKU Resolver**: rank candidate SKUs using product, metric, edition, license,
   and source evidence; return confidence and contradictions.
3. **Coverage Agent**: identify missing quantities and ask the smallest set of
   client questions needed to complete the BOM.
4. **Change Explainer**: explain price-sync and BOM deltas by quantity, SKU, tier,
   rate, or deployment change.
5. **Optimization Advisor**: compare approved scenarios (PAYG/BYOL, shared versus
   dedicated, headroom) without silently changing the baseline.
6. **Commercial Review**: detect duplicate charges, free-tier misuse, unit
   mismatches, stale prices, and unsupported manual overrides.

All AI output is advisory, evidence-linked, schema-constrained, and auditable.
Only deterministic services can create final BOM line amounts.

## API Plan

Add route groups:

```text
/api/v1/pricing/sources
/api/v1/pricing/sync-jobs
/api/v1/pricing/catalog-snapshots
/api/v1/pricing/sku-mappings
/api/v1/projects/{project_id}/deployment-scenarios
/api/v1/projects/{project_id}/bom-jobs
/api/v1/projects/{project_id}/bom-snapshots
/api/v1/projects/{project_id}/bom-exports
```

Mutations emit AuditEvent. Admin controls sources, mappings, and contracted rate
cards. Architect owns deployment scenarios. Analyst can generate and compare BOMs.
Viewer receives only explicitly published commercial snapshots.

## UI Plan

### Project `BOM & Cost`

- Readiness header: technical snapshot, price freshness, mapping coverage, and
  unresolved questions.
- Scenario selector: baseline and alternatives without nested-card overload.
- BOM grid: environment, service, SKU, metric, quantity, unit price, monthly and
  annual amounts, source, and confidence.
- Cost breakdown: service, environment, and contract year.
- Findings panel: missing inputs and exact remediation action.
- Compare mode: quantity, rate, tier, and architecture deltas.
- Commands: Generate, Review, Approve, Publish, Export.

### Admin Library

- Price source health and last successful synchronization.
- Snapshot diff and approval queue.
- Service Product to SKU matrix with effective dates and evidence.
- Contract rate-card connection/upload, isolated behind Admin permissions.

The technical Dashboard may show only a compact link/status such as `BOM ready`
or `7 inputs missing`; it does not expose commercial totals by default.

## Implementation Phases

### Phase 0 - Workbook Parity Specification

- Document UDF behavior, price types, tiers, monthly-hour rules, compute modifiers,
  and summary/BOM reconciliation.
- Extract the relevant VBA modules and build focused parity fixtures for OIC,
  Data Integration, Functions, Streaming, Queue, GoldenGate, and API Gateway.
- Record intentional differences from the workbook.

**Exit:** a reviewed pricing behavior specification and deterministic expected
results exist without requiring Excel or VBA at runtime.

### Phase 1 - Pricing Catalog and Sync

- Add migrations, models, source adapters, Celery job, source hashing, diffing,
  approval, audit, and scheduled freshness checks.
- Implement public price sync first; add contracted rate cards behind a disabled
  feature flag until identity and permission policies are validated.

**Exit:** repeatable sync creates immutable snapshots; unchanged sources are
idempotent; changed prices create findings rather than silent updates.

### Phase 2 - SKU Mapping Governance

- Add mapping schema and Admin UI.
- Seed mappings for every billable product used by the active project.
- Reuse Service Product evidence and add price-specific official evidence.

**Exit:** 100% of used products are mapped, explicitly non-billable, or blocked
with a clear reason.

### Phase 3 - Deployment Scenario Model

- Add project scenario, environment, and service deployment APIs/UI.
- Generate a deterministic baseline from the current technical snapshot.
- Add AI drafting only after schema and review behavior are stable.

**Exit:** the architect can approve a physical deployment scenario without
editing integration rows or per-integration canvases.

### Phase 4 - Pricing Engine and BOM Jobs

- Implement the pure engine and parity tests.
- Add BOM generation job, coverage validation, immutable snapshots, and audit.
- Block publication when required quantities, mappings, or current prices are
  missing.

**Exit:** the active project produces a reconciled BOM whose every line traces to
technical demand, deployment choice, SKU mapping, and exact price record.

### Phase 5 - UI, Comparison, and Exports

- Build the project BOM workspace and Admin pricing screens.
- Add XLSX, JSON, and PDF exports with formula/provenance columns.
- Add baseline comparison and price/quantity/architecture delta explanations.

**Exit:** browser workflows generate, review, approve, compare, publish, and
export a terminal BOM job with no console, accessibility, or visual defects.

### Phase 6 - Contract Pricing and Smart Assistance

- Add OCI Subscription Rate Card adapter and governed CSV upload.
- Add scenario drafting, SKU suggestions, question minimization, and change
  explanation through OCI Generative AI using redacted governed evidence.
- Add quotas, redaction, data retention, and role checks.

**Exit:** list-price and contract-price BOMs are visibly distinct, reproducible,
and protected by negative authorization tests.

## Validation Strategy

- Pure unit and property tests for every price type and tier boundary.
- Workbook-parity tests against sanitized expected values.
- Adapter contract tests with recorded official response fixtures; no live network
  dependency in unit tests.
- Integration tests for idempotent sync, source changes, stale data, approval,
  audit, and BOM reconciliation.
- RBAC tests for public and contracted pricing.
- Playwright tests that poll price-sync and BOM jobs to terminal states and clean
  fixtures.
- Visual validation in light/dark and desktop/mobile modes.
- Export round-trip checks and formula/error scans.
- CI dependency audit and production image scanning remain blocking.

## Acceptance Criteria for the First Customer BOM

1. Uses an approved current technical snapshot.
2. Uses an approved deployment scenario with explicit environments and HA/DR.
3. Resolves every billable product to approved SKU mappings.
4. Uses one immutable price catalog snapshot with currency and effective time.
5. Reconciles line totals to service, environment, monthly, annual, and contract
   totals with zero unexplained difference.
6. Shows list versus contracted pricing provenance without mixing them.
7. Shows 100% pricing coverage or blocks publication with exact missing inputs.
8. Exports an auditable BOM and never labels the result an official quote.
9. Passes backend, engine, frontend, E2E, migration, audit, and image quality gates.

## Validation Evidence

- PostgreSQL migrations `20260712_0019` and `20260712_0020` applied successfully,
  seeded one official public source plus 17 governed SKU mapping decisions, and
  persist price/money boundaries with exact `NUMERIC` precision.
- Live Oracle public synchronization reached `completed` with 712 normalized USD
  price items and an immutable approved snapshot.
- The active 480-integration project produced a published 13-line BOM covering
  all 9 detected products with 100% coverage and no blocked lines.
- Backend, calc-engine, and pricing-engine: 146 tests passed; Ruff and mypy clean.
- Frontend: 37 tests passed; strict TypeScript, ESLint, and Next.js production
  build clean.
- Playwright E2E reached terminal price-sync and BOM job states and validated the
  Admin Pricing and project BOM workspaces.
- Browser inspection passed in light/dark, desktop/mobile, with zero console
  warnings or errors; XLSX, JSON, and PDF downloads were validated.
- `npm audit` found 0 vulnerabilities. Trivy found 0 HIGH/CRITICAL findings in
  both production images. The generated OpenAPI artifact matches the API image.

## Implemented Decisions

- Public list prices refresh online from Oracle's documented product endpoint;
  authorized contractual prices enter through an Admin-only governed CSV import.
- Currency and contract horizon are explicit scenario inputs. Currency conversion
  is intentionally unsupported.
- Environments, demand allocation, active hours, HA multiplier, OIC edition, BYOL,
  Streaming retention, Data Integration execution, and GoldenGate capacity are
  explicit scenario inputs that require approval before a BOM job can run.
- Commercial source and mapping administration is Admin-only. Architect can
  approve scenarios and BOMs; Analyst can draft and run; Viewer is read-only.
- OCI Generative AI receives redacted governed evidence for optional scenario
  explanation. It never receives rate-card files and cannot create quantities,
  prices, mappings, approvals, or line totals.
- Direct OCI Subscription Rate Card credentials are intentionally not stored in
  this release. The authorized CSV adapter is the production contract-rate path
  until workload identity and tenancy policies are supplied and validated.
