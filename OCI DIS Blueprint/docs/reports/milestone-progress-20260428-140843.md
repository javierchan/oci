# Milestone Progress Report

**Generated:** 2026-04-28 14:08 CST
**Last Updated:** 2026-04-28 15:03 CST
**Repository:** https://github.com/javierchan/oci.git
**Branch:** codex/codex-active-work
**Execution Wave:** Admin synthetic runtime hardening wave 1
**Source Audit:** `docs/reports/audit-report-20260428-135124.md`

---

## Milestone Status Summary

- `M1` — Schema Readiness Guardrails for Admin Synthetic Routes: `complete`
- `M2` — Runtime Validation Closeout for Schema-Dependent Surfaces: `complete`
- `M3` — Safe Live Smoke Path for Synthetic Job Submission: `complete`
- `M4` — Automated Runtime Smoke Coverage for Admin Synthetic Flows: `partial`

## What Changed In This Wave

- Added schema-readiness translation for the admin synthetic routes in
  `apps/api/app/routers/admin_synthetic.py` so a missing
  `synthetic_generation_jobs` table is surfaced as a structured `503` instead
  of an opaque DB exception path.
- Added the supporting detection helpers in
  `apps/api/app/services/synthetic_service.py`, including the expected
  migration identifier and recovery hint.
- Expanded `apps/api/app/tests/test_admin_synthetic_api.py` with focused
  coverage for both PostgreSQL-style and SQLite-style missing-table failures on
  the list and create routes.
- Added the schema-dependent Admin Synthetic Lab validation contract to
  `docs/architecture/admin-synthetic-lab.md`, including the exact migration,
  API smoke, and browser verification sequence required for closeout.
- Added a top-level operator-facing smoke checklist to `README.md` so local
  runtime validation is discoverable without digging through architecture docs.
- Added a governed `ephemeral-smoke` preset with bounded targets and
  `ephemeral_auto_cleanup` policy so the real admin synthetic job flow can be
  exercised safely in the shared runtime without leaving durable synthetic
  residue behind.
- Updated `apps/api/app/workers/synthetic_worker.py` so completed smoke runs
  automatically clean up their generated project and artifacts, while cleanup
  failures surface as explicit terminal job failures with cleanup-specific
  error details.
- Extended the admin synthetic web UI so the new smoke preset, cleanup policy,
  and cleaned-up job states are rendered clearly on both the list and detail
  pages.
- Added the bounded live smoke script
  `apps/api/scripts/smoke_admin_synthetic_lab.py` so operators can validate the
  real admin synthetic flow through health, presets, create, poll, terminal,
  and recent-jobs checks with one command.
- Added the governed bounded preset `retained-smoke` so explicit cleanup can
  be exercised safely against a small retained project instead of the
  enterprise-scale preset.
- Extracted shared admin synthetic UI-state rules into
  `apps/web/lib/admin-synthetic-ui.ts` and added focused Vitest coverage in
  `apps/web/lib/admin-synthetic-ui.test.ts` so smoke-preset defaults,
  cleanup-policy behavior, job-action visibility, and target-split rules are
  regression-tested.

## What Was Validated

- Reproduced and understood the source-audit defect before implementation:
  - `/admin/synthetic` showed `Failed to fetch`
  - `/api/v1/admin/synthetic/jobs?limit=20` returned `500`
  - API logs showed `relation "synthetic_generation_jobs" does not exist`
- Confirmed the running stack baseline was healthy before and after code work:
  - `docker compose exec -T api alembic upgrade head`
  - `/api/v1/admin/synthetic/presets`: `200`
  - `/api/v1/admin/synthetic/jobs?limit=20`: `200`
- Focused validation for the new guardrail:
  - `cd apps/api && ./.venv/bin/python -m pytest app/tests/test_admin_synthetic_api.py -q`
    -> `6 passed`
  - `cd apps/api && ./.venv/bin/python -m ruff check app/routers/admin_synthetic.py app/services/synthetic_service.py app/tests/test_admin_synthetic_api.py`
    -> `All checks passed!`
- Full quality snapshot after the change:
  - `cd apps/api && ./.venv/bin/python -m pytest --tb=short -q`
    -> `26 passed`
  - `cd apps/api && ./.venv/bin/python -m ruff check .`
    -> `All checks passed!`
  - `cd apps/web && npx tsc --noEmit --skipLibCheck`
    -> exit `0`
  - `cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0`
    -> exit `0`
- Live browser sanity check after the change:
  - `/admin/synthetic` reloads successfully
  - `Failed to fetch` count: `0`
  - `Project Name` field count: `1`
  - `Create Synthetic Job` button count: `1`
  - empty-state jobs text count: `1`
- Focused runtime-safe smoke coverage for the new preset:
  - `cd apps/api && ./.venv/bin/python -m pytest app/tests/test_synthetic_service.py app/tests/test_admin_synthetic_api.py app/tests/test_synthetic_worker.py -q`
    -> `13 passed`
- Full quality snapshot after the smoke-path implementation:
  - `cd apps/api && ./.venv/bin/python -m pytest --tb=short -q`
    -> `31 passed`
  - `cd apps/api && ./.venv/bin/python -m ruff check .`
    -> `All checks passed!`
  - `cd apps/web && npx tsc --noEmit --skipLibCheck`
    -> exit `0`
  - `cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0`
    -> exit `0`
- Live admin synthetic smoke submission with the governed auto-cleanup preset:
  - orphaned pre-restart job `12e211c7-e08f-453a-9a82-0630ef0e59ce`
    recovered to `failed` with a worker-reload recovery hint
  - worker logs confirmed the registered task list includes
    `app.workers.synthetic_worker.execute_synthetic_generation_job_task`
  - submitted `POST /api/v1/admin/synthetic/jobs` with
    `{"preset_code":"ephemeral-smoke"}`
  - live job `6642bc7a-ea48-4eca-97a7-b95ee0c7bf77` reached terminal status
    `cleaned_up`
  - terminal payload confirmed:
    - `normalized_payload.cleanup_policy = "ephemeral_auto_cleanup"`
    - `project_id = null`
    - `result_summary.cleanup_removed_paths` populated
    - validation targets met:
      `catalog_count = 18`, `distinct_systems = 32`,
      `import_included_count = 12`, `manual_count = 6`,
      `excluded_import_count = 2`,
      full pattern coverage `#01` through `#17`
- Live in-app browser verification after the successful smoke run:
  - `/admin/synthetic` renders the `Ephemeral Smoke Validation` preset in the
    governed preset selector
  - selecting the smoke preset renders the auto-cleanup guidance copy and
    summary values:
    `18` catalog target, `12 / 6` import-manual split, `2` excluded rows,
    `Ephemeral auto-cleanup`
  - recent runs table shows job
    `6642bc7a-ea48-4eca-97a7-b95ee0c7bf77` with status `CLEANED_UP`
  - `/admin/synthetic/6642bc7a-ea48-4eca-97a7-b95ee0c7bf77` renders the
    cleaned-up job detail state, including normalized inputs, validation
    results, preserved artifact paths, and cleanup metadata
  - browser console inspection on the verified admin synthetic surfaces showed
    only development informational logs and no runtime `error` entries
- Automated runtime smoke validation for the bounded path:
  - `./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_lab.py`
    -> `ok = true`
    -> live job `5c6aac25-f30f-4c31-a339-6c0712d3d6ab` reached `cleaned_up`
    -> preset count `3`
    -> validated `catalog_count = 18`, `distinct_systems = 32`,
       `import_included_count = 12`, `manual_count = 6`,
       `excluded_import_count = 2`, populated `cleanup_removed_paths`
- Automated explicit cleanup coverage for the bounded retained path:
  - `./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_lab.py --preset-code retained-smoke`
    -> `ok = true`
    -> live job `42e4485a-964c-459b-890e-60f6130ec5d1` reached `completed`
       before cleanup and `cleaned_up` after cleanup
    -> `cleanup_mode = explicit`
    -> validated `catalog_count = 18`, `distinct_systems = 32`,
       `import_included_count = 12`, `manual_count = 6`,
       `excluded_import_count = 2`, populated `cleanup_removed_paths`
- Updated focused/full backend coverage after the retained-smoke addition:
  - `cd apps/api && ./.venv/bin/python -m pytest app/tests/test_admin_synthetic_api.py app/tests/test_synthetic_service.py app/tests/test_synthetic_worker.py --tb=short -q`
    -> `14 passed`
  - `cd apps/api && ./.venv/bin/python -m pytest --tb=short -q`
    -> `32 passed`
- Automated UI-state coverage for the admin synthetic surfaces:
  - `cd apps/web && npm test`
    -> `9 passed`
  - new admin synthetic helper coverage validates:
    smoke preset defaults, selected-preset fallback, target mismatch guidance,
    cleaned-up job cleanup policy, and retry/cleanup action visibility
- Post-refactor in-app browser verification:
  - `/admin/synthetic` preset selector now includes `Retained Smoke Validation`
  - `/admin/synthetic` renders recent job
    `42e4485a-964c-459b-890e-60f6130ec5d1` with status `CLEANED_UP`
  - `/admin/synthetic` renders recent job
    `5c6aac25-f30f-4c31-a339-6c0712d3d6ab` with status `CLEANED_UP`
  - `/admin/synthetic/42e4485a-964c-459b-890e-60f6130ec5d1` renders the
    cleaned-up retained-smoke detail state correctly
  - `/admin/synthetic/5c6aac25-f30f-4c31-a339-6c0712d3d6ab` renders the
    cleaned-up detail state correctly
  - browser console inspection again showed `0` runtime `error` entries on the
    touched admin synthetic routes
- Verified the new `M2` documentation commands exactly as written:
  - `docker compose exec -T api alembic upgrade head`
  - `curl -sf http://localhost:8000/health`
  - `curl -sf -H 'X-Actor-Id: web-admin' -H 'X-Actor-Role: Admin' http://localhost:8000/api/v1/admin/synthetic/presets`
  - `curl -sf -H 'X-Actor-Id: web-admin' -H 'X-Actor-Role: Admin' 'http://localhost:8000/api/v1/admin/synthetic/jobs?limit=20'`
  - live browser reload of `/admin/synthetic` with all expected healthy signals present

## Residual Risk

- The bounded happy path and explicit cleanup path are now automated, but retry
  still relies on targeted tests plus manual/live validation rather than the
  smoke script itself.
- The repo now has deterministic UI-state coverage, but it still does not have
  a repo-runner browser E2E suite for the admin synthetic pages.

## Next Milestone Recommendation

Complete `M4` with the remaining coverage gaps:

1. Extend the smoke automation to cover retry semantics on a controlled failed
   job path.
2. Decide whether the remaining browser validation should stay as live operator
   smoke or graduate into a lightweight repo-runner E2E check.
