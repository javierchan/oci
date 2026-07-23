# Pricing Governance Workspace

## Purpose

Admin Pricing turns official Oracle commercial evidence into explainable,
certified inputs for customer BOMs. The workspace keeps source acquisition,
product identity, reviewer decisions, immutable releases, and deterministic
calculation separate because each stage has a different authority and failure
mode.

The overview is the entry point. It reports current readiness, identifies the
next governed action, explains the certification path, and clarifies why SKUs
follow different pricing paths. It does not calculate or approve commercial
data by itself.

## Workspace Views

| View | User question | Responsibility |
| --- | --- | --- |
| Overview | What is ready, and what must happen next? | Readiness signals, next action, certification rationale |
| Official Sources | What evidence do we currently trust? | Public Oracle price sync, private Price List + Supplement workbook capture, customer rate cards, verification artifacts, normalized price items |
| Products & SKUs | What does Oracle sell, and can the App quote it? | Product catalog identity and BOM capability review |
| Review & Certification | What still requires explicit disposition? | Candidate review, exceptions, field authority, approval rationale |
| Releases & BOM | Which approved inputs can calculation consume? | Immutable catalog snapshots, service-to-SKU mappings, recent sync jobs |

The selected top-level view is persisted in the `view` query parameter so the
workspace survives reloads and can be linked directly.

The three source lanes remain intentionally distinct:

- the public pricing API governs current public rates and typed price tiers;
- the private Oracle workbook governs commercial hierarchy, SKU descriptions
  and placement, licensing and commitment terms, minimums, and supporting
  guidance;
- an authorized customer rate card governs customer-specific contract rates.

Private workbooks are uploaded only through **Official Sources**, stored as
immutable objects in MinIO or OCI Object Storage, and represented by a hashed
database snapshot. The workbook is evidence, not an automatic approval:
reviewer disposition, rule fixtures, release publication, and BOM calculation
remain separate governed stages. Private workbook contents are never committed
to this repository.

## Certification Path

1. **Capture** Oracle documents, APIs, and authorized customer rate cards.
2. **Identify** the product, SKU, metric, edition, and licensing identity.
3. **Classify** the commercial path supported by the evidence.
4. **Validate** deterministic commercial rules and quotation fixtures.
5. **Approve** the reviewer disposition and rationale explicitly.
6. **Release** an immutable approved catalog scope.
7. **Calculate** quantities, tiers, terms, monthly periods, and totals in the BOM engine.

A SKU is never quote-ready merely because it exists in an Oracle source. The
App requires identity, pricing behavior, evidence quality, validation, approval,
and release scope to remain independently traceable.

## SKU Pricing Paths

| Path | Why it is separate | BOM behavior |
| --- | --- | --- |
| Directly metered | Public Oracle unit price and deterministic usage rule exist | Price measured demand with governed tiers and units |
| Contract rate | SKU is valid but its rate is customer-specific | Require an authorized rate card; do not substitute public price silently |
| Input required | A real billed unit cannot be inferred safely | Require an architect-provided quantity or deployment decision |
| Dependent entitlement | Included, prerequisite-driven, or priced through another component | Keep evidence and dependency, but do not add an independent charge |

These paths describe commercial semantics, not quality grades. Deterministic
services calculate quantities, increments, minimums, tiers, periods, rates, and
totals. Human reviewers decide whether evidence is authoritative, an exception
is acceptable, a product is BOM-ready, and a release may be published.

## Validation Contract

- Pure navigation and next-action behavior is covered by frontend unit tests.
- The production Next.js build must pass with all five views.
- The Pricing/BOM browser E2E must synchronize a public source, approve the
  resulting snapshot, locate it in Releases & BOM, and complete a governed BOM
  workflow.
- Desktop, mobile, light, and dark visual checks must show no horizontal page
  overflow and must preserve readable progressive disclosure.
