# Remediation Milestone Progress

**Started:** 2026-07-10 14:02 CST
**Branch:** `main`
**Base commit:** `38cfb30426a59bc3392f2ebe1ebde00b6175d688`
**Source audit:** `docs/reports/audit-report-20260710-130519.md`

## Execution Wave

1. Dependency security and effective CI completeness.
2. Service Product rule-source consolidation.
3. Browser, visual, and terminal-job regression coverage.
4. Legacy contract and documentation cleanup.
5. Full code, runtime, and browser validation.

## Milestone Status

| Workstream | Status |
|---|---|
| npm vulnerability remediation | complete |
| effective CI completeness | complete |
| Service Product rule consolidation | complete |
| Playwright expansion | complete |
| legacy contract cleanup | complete |
| full validation and closeout | complete |

## Current Checkpoint

### What Changed

- Resolved the npm dependency graph to zero reported vulnerabilities.
- Consolidated all effective gates in the repository-root GitHub workflow.
- Added normalized Service Product runtime assembly and provenance.
- Migrated service-owned keys out of Assumptions and restricted the admin UI to client inputs.
- Expanded Playwright to terminal jobs and critical project/admin surfaces.
- Removed two non-effective CI copies and nonexistent npm workspaces.
- Rebuilt the API production image from repository root with calc-engine included and a non-root runtime.
- Upgraded the vulnerable FastAPI dependency family and hardened the web runtime by removing unused npm tooling.
- Reconciled root quality scripts and marked historical prompts/reports as non-normative evidence.

### What Was Validated

- `npm audit`: 0 vulnerabilities.
- Backend + calc engine: 111 tests passed, including all 42 calc-engine tests.
- Ruff and mypy passed.
- Frontend: 19 tests, TypeScript, ESLint, and Next.js production build passed.
- Alembic migrated PostgreSQL to `20260710_0014`; seed remained idempotent.
- Seven Docker Compose services are up and healthy.
- Playwright: 3 E2E tests passed with terminal job and cleanup assertions.
- In-app browser review confirmed Assumptions and Service Product Library layout and content.
- Trivy: API and web production images have 0 HIGH/CRITICAL findings.
- PostgreSQL: 131 active normalized service limits, no service-owned keys in Assumptions, and 0 active synthetic jobs.
- Runtime logs: no error, exception, traceback, critical, or failed entries after E2E.
- The only active project was recalculated successfully; its current volumetry
  and dashboard snapshots reference `service-rules-f349865c8d38e84f`.

### Residual Risk

- The current rule bundle has 62 stale evidence records and no open findings;
  an Internet-enabled governed Verification Agent run is required to refresh them.
- Dated reports and execution prompts retain historical values by design; they are explicitly non-normative.

### Next Milestone Recommendation

Publish the validated diff through the normal review and Git workflow.
