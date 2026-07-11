# OCI DIS Blueprint Status Report

**Validated:** 2026-07-10
**Branch:** `main`
**Base commit:** `7b663ce08f755a08b654d6d4f655981f99bc726d`
**Detailed remediation:** `milestone-progress-20260710-140234.md`

## Current Status

| Area | Status | Evidence |
|---|---|---|
| Backend API and calc engine | complete | 114 tests passed, including all 42 calc-engine tests |
| Frontend | complete | TypeScript, ESLint, 19 tests, and production build passed |
| Browser workflows | complete | 3 Playwright E2E tests passed |
| Dependency security | complete | npm audit 0; Trivy 0 HIGH/CRITICAL for API and web images |
| Database | complete | Alembic at `20260710_0015`; seed idempotent |
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

## Production Runtime

- Compose builds API, worker, beat, and web exclusively from production targets.
- API code, calc engine, and OpenAPI artifacts are packaged into immutable
  images; runtime source-code bind mounts and hot reload are not present.
- API, worker, and beat share one non-root API image. The optional Codex override
  preserves read-only `0600` credentials through a root-only bootstrap that
  immediately drops API and worker execution to `app:10001`.
- API and worker share only the persistent `uploads_data` volume required for
  imports and exports; source code never enters that writable volume.

## Production Dependency Cleanup

- Python dependencies are separated into production runtime and non-deployable
  quality sets. The CI aggregate installs both, while the production image
  installs only `requirements-runtime.txt`.
- The API production image excludes pytest, mypy, Ruff, aiosqlite, API tests,
  calc-engine tests, generated reports, and dependency manifests. It retains an
  empty writable `generated-reports` runtime directory required by Synthetic Lab.
- The API image now reports approximately 867 MB local virtual size, down from
  approximately 1.11 GB before cleanup. The web image remains approximately
  302 MB local virtual size and contains only the standalone Next.js runtime.
- Celery startup broker retry behavior is explicit and regression-tested for
  forward compatibility with Celery 6.
- Removed the unused `@testing-library/react` dependency and moved D3 type
  declarations to frontend development dependencies. `npm audit` remains at zero.
- Removed approximately 1.15 GB of ignored host artifacts, including `.venv`,
  `node_modules`, `.next`, caches, temporary uploads, and test outputs. Versioned
  audit evidence was preserved. Temporary quality and Playwright images were
  deleted after validation; no dangling OCI DIS Blueprint images remain.

## Terminal Job Evidence

- Playwright creates one ephemeral job and asserts final `cleaned_up` state.
- Playwright creates one retained job, asserts `completed`, validates critical
  project surfaces, then cleans it and asserts final `cleaned_up` state.
- PostgreSQL had 0 jobs in `pending` or `running` after the suite.
- Historical `failed` jobs are terminal records retained for audit, not stuck work.

## Runtime Recalculation

- The only active project (`OCI DIS Blueprint Demo Enterprise 2026`) was
  recalculated after the rule-source migration and evidence refresh.
- Recalculation job `1ffe6943-9769-4906-a775-cb201a12a7ae` completed and created
  volumetry snapshot `93aa4451-55c1-477f-9539-8955441067be` plus dashboard
  snapshot `6b1bc014-5fb0-4ec8-8922-e8e61b6380e2`.
- The current snapshot records `service-rules-f349865c8d38e84f` from
  `normalized_service_products`, with `freshness_status=current`, zero stale
  evidence, and zero open findings; historical snapshots remain immutable.

## Service Product Verification

- Governed verification jobs `b27ca6b8-7ec9-40aa-bc70-eacc8f1f7110` and
  `866a1239-29b0-423d-a615-a25cb614b69f` refreshed all 62 previously stale
  evidence records against official Oracle sources.
- One retired OIC documentation URL returned HTTP 404. Alembic revision
  `20260710_0015` replaces it with the canonical
  `message-pack-usage-synchronous-requests.html` source for existing databases,
  and the reference seed now uses the same URL.
- Follow-up verification job `b101426f-e8ee-41bb-9581-839a0ad0bc9b` received
  HTTP 200 and found no content or governed-limit changes. The historical 404
  finding is reviewed with an audit note; no limit update was accepted.
- Final state: 81 of 81 evidence sources verified, zero stale or due sources,
  zero open findings, zero verification alerts, and zero active jobs.
- Browser validation confirmed the Library counters and Verification Agent state
  with no console warnings or errors.

## Residual Risk

- No current evidence-freshness risk is open. Scheduled governed verification
  remains required as each source reaches its configured review interval.
- Dated reports and files under `docs/prompts/` are historical evidence and are
  explicitly non-normative; this report and the repository contracts above are current.
