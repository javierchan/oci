# Milestone Progress Report

**Execution Wave:** Audit follow-up remediation
**Codebase:** `/Users/javierchan/.codex/worktrees/b840/oci/OCI DIS Blueprint`
**Branch:** `codex/codex-active-work`
**Started:** 2026-04-15 13:39 CST

---

## Milestone Status Summary

- `M1 — Align Import Dispatch Contract`: complete
- `M2 — Route Imports Through Celery Worker Lifecycle`: complete
- `M3 — Validate Async Import Observability`: complete
- `M4 — Align Recalculation Dispatch Contract`: complete
- `M5 — Route Recalculation Through Celery Worker Lifecycle`: complete
- `M6 — Validate Async Recalculation Job Flow`: complete
- `M7 — Checkpoint The Audited Branch State`: open
- `M8 — Rerun Release Audit On Clean HEAD`: open

---

## Current Milestone

### M1 — Align Import Dispatch Contract

**Status:** complete

### Scope Confirmation

- The import UI already supports the batch lifecycle `pending | processing | completed | failed`.
- The current gap is not a missing UI contract; it is the mismatch between the route semantics (`202 Accepted`) and the synchronous in-request import execution.
- The worktree was not clean when execution started:
  - `apps/api/app/routers/recalculate.py`
  - `apps/api/app/schemas/volumetry.py`
  - `apps/api/app/services/recalc_service.py`
  - `docs/progress.md`
  - `docs/reports/` (new audit artifacts)

### Working Assumption

M1 should preserve the existing frontend response shape and batch lifecycle while making the import route contract internally consistent and ready for worker dispatch in M2.

### What Changed In The Current Milestone

- `apps/api/app/routers/imports.py` now returns a real queued `ImportBatchResponse` and dispatches the import workload to the Celery task instead of executing workbook parsing in the request cycle.
- `apps/web/components/import-upload.tsx` now reflects queued background processing in its copy, CTA label, and batch-status panel instead of implying immediate completion.
- `apps/api/app/workers/celery_app.py` now imports the worker modules explicitly so the Celery app registers both import and recalculation tasks when the module is loaded.

### What Was Validated

- `apps/web/components/import-upload.tsx` already handled the batch lifecycle states without needing a contract-breaking frontend rewrite.
- `apps/web/lib/types.ts` already modeled the correct import batch status values.
- `POST /api/v1/imports/{project_id}` now returns `initial_status=pending` immediately for a real XLSX upload, proving the route no longer parses the workbook in the request cycle.
- `docker compose exec -T worker python -c ...` now reports:
  - `import_task_registered=True`
  - `recalc_task_registered=True`

### Residual Risk

- The branch still contains pre-existing local modifications outside the import flow, so milestone execution must stay narrow and avoid cross-contaminating unrelated work.

### Next Milestone Recommendation

- Move to `M4` and apply the same queued-contract pattern to recalculation, now that the worker reliably registers both import and recalculation tasks.

---

## Milestone Checkpoint

### M2 — Route Imports Through Celery Worker Lifecycle

**Status:** complete

### What Changed

- Restarted the `worker` container after the Celery task-registration fix so the live worker process loaded:
  - `app.workers.import_worker.process_import_task`
  - `app.workers.recalc_worker.recalculate_project_task`
- Verified in-container registration with:
  - `import_task_registered=True`
  - `recalc_task_registered=True`

### Validation

- Re-ran the queued import smoke test after restart.
- Observed:
  - `initial_status=pending`
  - `poll_1 status=completed loaded=1 excluded=0 tbq=1`
  - `rows_total=1 page_rows=1`

### Outcome

The import route is now executing through the worker lifecycle instead of the API request cycle.

---

## Milestone Checkpoint

### M3 — Validate Async Import Observability

**Status:** complete

### What Was Validated

- The queued import path can be observed from submission to completion using the existing batch detail endpoint.
- Import row materialization remains inspectable immediately after completion.
- The import UI contract did not require a breaking type change; it now communicates background processing accurately.

### Verification Evidence

- `POST /api/v1/imports/{project_id}` returned `pending` immediately for a real `.xlsx` upload.
- Polling `GET /api/v1/imports/{project_id}/{batch_id}` transitioned to `completed` with populated counts.
- `GET /api/v1/imports/{project_id}/{batch_id}/rows?page=1&page_size=5` returned persisted source rows.
- Quality gates stayed green for this slice:
  - `ruff` on updated Python files: pass
  - `mypy apps/api/app`: pass
  - `tsc --noEmit --skipLibCheck`: pass
  - `eslint components/import-upload.tsx --max-warnings 0`: pass
  - `pytest packages/calc-engine/src/tests/ -q`: `26 passed`

### Next Milestone Recommendation

- Start `M4 — Align Recalculation Dispatch Contract` using the same queue-first response pattern proven in the import flow.

---

## Milestone Checkpoint

### M4 — Align Recalculation Dispatch Contract

**Status:** complete

### What Changed

- `apps/api/app/routers/recalculate.py` now returns queued `RecalculationJobStatusResponse` payloads for both full-project and scoped recalculation requests.
- `apps/web/lib/api.ts` and `apps/web/lib/types.ts` now model recalculation jobs explicitly instead of treating `POST /recalculate/{project_id}` as an immediate snapshot response.
- `apps/web/components/recalculate-button.tsx` now handles queued recalculation feedback and short-interval job polling before refreshing the dashboard.

### Validation

- Full recalculation now returns `pending` immediately with a job ID instead of an inline snapshot payload.
- Scoped recalculation also returns `pending` immediately with scope and integration IDs preserved.

### Outcome

The recalculation API and frontend now agree on a queued job contract.

---

## Milestone Checkpoint

### M5 — Route Recalculation Through Celery Worker Lifecycle

**Status:** complete

### What Changed

- `apps/api/app/workers/recalc_worker.py` now executes both full and scoped recalculation through Celery tasks.
- `apps/api/app/services/recalc_service.py` now resolves queued job status from Celery `AsyncResult` and maps successful jobs back to persisted snapshots.
- `apps/api/app/workers/async_runner.py` was added so Celery worker processes reuse a persistent event loop instead of creating a new loop per task with `asyncio.run()`.

### Validation

- Worker task registration:
  - `full_task_registered=True`
  - `scoped_task_registered=True`
- Worker execution log:
  - `Task app.workers.recalc_worker.recalculate_project_task[...] succeeded`
  - `Task app.workers.recalc_worker.recalculate_scoped_task[...] succeeded`

### Outcome

Both recalculation paths now execute in the worker process instead of the API request cycle.

---

## Milestone Checkpoint

### M6 — Validate Async Recalculation Job Flow

**Status:** complete

### What Was Validated

- Full-project recalculation:
  - `full_initial status=pending`
  - `full_poll_1 status=completed snapshot_id=a779078e-ac0d-4d21-996e-26ae9b0fe676`
- Scoped recalculation:
  - `scoped_initial status=pending`
  - `scoped_poll_1 status=completed snapshot_id=77470b85-7d52-4420-90ca-0a505eddb1db scope=scoped ids=['2f3b0968-74e6-4198-8c47-321643888736']`
- Quality gates stayed green for this slice:
  - `ruff` on updated backend files: pass
  - `mypy apps/api/app`: pass
  - `tsc --noEmit --skipLibCheck`: pass
  - `eslint components/recalculate-button.tsx lib/api.ts lib/types.ts --max-warnings 0`: pass
  - `pytest packages/calc-engine/src/tests/ -q`: `26 passed`

### Residual Risk

- The branch still contains accumulated validated changes that are not yet checkpointed into committed history.

### Next Milestone Recommendation

- Move to `M7 — Checkpoint The Audited Branch State` so the validated import and recalculation waves become reproducible from git history before running another release audit.
