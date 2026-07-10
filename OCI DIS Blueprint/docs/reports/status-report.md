# OCI DIS Blueprint Status Report

**Validated:** 2026-07-10
**Branch:** `main`
**Base commit:** `38cfb30426a59bc3392f2ebe1ebde00b6175d688`
**Detailed remediation:** `milestone-progress-20260710-140234.md`

## Current Status

| Area | Status | Evidence |
|---|---|---|
| Backend API and calc engine | complete | 113 tests passed, including all 42 calc-engine tests |
| Frontend | complete | TypeScript, ESLint, 19 tests, and production build passed |
| Browser workflows | complete | 3 Playwright E2E tests passed |
| Dependency security | complete | npm audit 0; Trivy 0 HIGH/CRITICAL for API and web images |
| Database | complete | Alembic at `20260710_0014`; seed idempotent |
| Runtime | complete | 7 Compose services running; no recent error signatures |
| Effective CI | complete | one root workflow covers code, browser, build, and image gates |

## Governed Rule Ownership

- Service Product Library normalized tables are the operational source for
  service profiles, interoperability, evidence, findings, and 131 active limits.
- Assumption sets contain client/business workload inputs only. Versions
  `1.0.0` and `1.0.1` contain no migrated OIC or Queue service-limit keys.
- Calc-engine static defaults remain deterministic fallbacks for pure isolated
  execution; API recalculation overlays the versioned normalized rule bundle.
- New dashboard, export, and AI-review evidence carries the effective rule
  bundle version and freshness metadata.

## Terminal Job Evidence

- Playwright creates one ephemeral job and asserts final `cleaned_up` state.
- Playwright creates one retained job, asserts `completed`, validates critical
  project surfaces, then cleans it and asserts final `cleaned_up` state.
- PostgreSQL had 0 jobs in `pending` or `running` after the suite.
- Historical `failed` jobs are terminal records retained for audit, not stuck work.

## Runtime Recalculation

- The only active project (`OCI DIS Blueprint Demo Enterprise 2026`) was
  recalculated after the rule-source migration.
- Recalculation job `464301ef-f977-42bf-b8c8-dc51d572038c` completed and created
  volumetry snapshot `25bd21d6-9f91-496f-87b0-9ca32c846097` plus dashboard
  snapshot `af7179bb-f80d-445e-ad6c-7850c9115c15`.
- The current snapshot records `service-rules-f349865c8d38e84f` from
  `normalized_service_products`; historical snapshots remain immutable.

## Residual Risk

- Current rule provenance is present, but the verification bundle reports 62
  stale evidence records. There are no open findings; refreshing those records
  requires an explicit governed Verification Agent run with Internet access.
- Dated reports and files under `docs/prompts/` are historical evidence and are
  explicitly non-normative; this report and the repository contracts above are current.
