# Ideal Enterprise Reference Project

## Purpose

The ideal enterprise reference project is a retained fictional dataset for
testing whether the App, governed data, pricing, specialized agents, embeddings,
and contextual assistant operate together. It is not a customer deliverable or
an Oracle quotation.

The builder uses only supported HTTP APIs. It does not write to PostgreSQL,
Object Storage, Celery state, or ORM models directly. The resulting project
therefore exercises the same import, manual capture, recalculation, scenario,
BOM, publication, and agent boundaries used by the product.

## Reproducible Builder

Run the builder against a healthy production Compose stack:

```bash
docker compose exec -T api \
  python scripts/create_ideal_demo_project.py
```

The default fictional identity is:

- Customer: `Aurora Retail Nexus, S.A.P.I. de C.V. (Fictitious)`
- Project: `DEMO - Aurora Retail Integration Blueprint 2027-2029`
- Seed: `20260725`

The command is resumable after an interrupted synthetic generation:

```bash
docker compose exec -T api \
  python scripts/create_ideal_demo_project.py --job-id <synthetic-job-id>
```

An existing project can be revalidated without generating another project:

```bash
docker compose exec -T api \
  python scripts/create_ideal_demo_project.py \
  --project-id <project-id> \
  --skip-agents
```

The process fails immediately if any required invariant is not satisfied and
prints one machine-readable summary only after successful completion.

## Governed Invariants

The project contains exactly 350 catalog integrations: 300 traverse the real
workbook import path and 50 traverse governed manual capture. Twelve excluded
source rows remain available as immutable import evidence. At least 72 distinct
systems provide a realistic topology.

Generated patterns `#15` and `#16` are family-level designs without a complete
billable product path in the current commercial contract. The builder converts
them through the catalog API to certified, commercially resolvable designs:

- `#15` becomes `#06` with OIC Gen3 and OCI API Gateway.
- `#16` becomes `#13` with OIC Gen3, OCI API Gateway, OCI IAM and Security
  Services, and OCI Observability.

This preserves governed intent while preventing an ideal demo from claiming
commercial readiness for unresolved family labels. Every row is also supplied
with explicit criticality, latency, classification, retention, retry, and
idempotency evidence. The builder requires the final QA distribution to be
exactly `{"OK": 350}`.

## Commercial Coverage

A single scenario cannot contain mutually exclusive OIC licensing and edition
predicates. Complete verified-SKU coverage therefore uses four approved
36-month scenarios:

- License Included, Standard
- License Included, Enterprise
- BYOL, Standard
- BYOL, Enterprise

Each scenario has DEV, QA, and PRD environments. DEV activates in month 1, QA in
month 7, and PRD in month 13. Every applicable product grows linearly from a
governed low quantity to a higher quantity in its native commercial unit. The
builder verifies all 36 periods, the six-month activation offsets, non-zero
activation, and monotonically non-decreasing portfolio totals.

The coverage claim is intentionally precise:

- All approved **billable** SKU mappings with part numbers must appear across the
  published BOM suite.
- Every BOM must have 100% coverage before publication.
- Approved **non-billable** mappings are counted and reported, but they are not
  mislabeled as verified billable SKUs.

## Agent and Assistant Validation

The terminal builder run executes Architecture Review and BOM Scenario agents
with governed project evidence. The retained reference project is also the
target for the App Assistant evaluation matrix:

- catalog QA and integration counts;
- import and source-lineage evidence;
- ordered business-process evidence;
- published BOM coverage and commercial totals.

Completed assistant answers must use provider-space embeddings, remain grounded
at the correct evidence grain, and report `fallback_used = false`. Configured
embedding, OCI synthesis, Guardrails, or grounding failures remain visible
terminal failures.

## Validated Local Instance

The 2026-07-25 validation retained project
`6635ea67-c05d-44d3-aacf-19c5dd5d2bee` with:

- `350/350` integrations at `QA = OK`;
- 300 imported and 50 manually captured integrations;
- 12 excluded source rows and 72 systems;
- four approved scenarios and four published BOMs at 100% coverage;
- all 31 approved billable mappings and 31 distinct part numbers covered;
- three approved non-billable mappings explicitly excluded from the billable
  coverage claim;
- completed Architecture Review and BOM Scenario agents;
- `4/4` contextual assistant cases completed with provider embeddings and no
  fallback;
- no browser console warnings or errors on Dashboard, Catalog, Map, and BOM.

Because this identifier belongs to local retained data, a different environment
will produce a different project identifier while preserving the same invariants.
