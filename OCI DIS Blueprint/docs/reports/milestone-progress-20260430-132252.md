# Milestone Execution Progress

**Generated:** 2026-04-30 13:22 America/Mexico_City
**Source Audit:** `docs/reports/audit-report-20260430-125817.md`
**Branch:** `codex/codex-active-work`
**Execution Location:** `/Users/javierchan/.codex/worktrees/b840/oci/OCI DIS Blueprint`

## Execution Wave

Work will follow the audit milestone order:

1. M1 - Commit And Release Catalog Graph Recovery
2. M2 - Restore Service-Backed Snapshot And Governance Routers
3. M3 - Repair Recalculation Input Contract
4. M4 - Regenerate And Gate API Contract
5. M5 - Close Backend Typing And CI Hygiene
6. M6 - Schedule Dependency Maintenance Wave

## Status Summary

| Milestone | Status | Notes |
|---|---|---|
| M1 | partial | Local implementation validated. Release/commit criterion remains pending because commit/push is not authorized in this execution wave. |
| M2 | complete | Stub routers restored to service-backed behavior and live probes return persisted data. |
| M3 | complete | Recalculation input contract now matches calc-engine `IntegrationInput`. |
| M4 | complete | OpenAPI artifact regenerated and `--check` passes. |
| M5 | complete | Backend typing passes, local hygiene cleaned, and root CI workflow added for quality gates. |
| M6 | deferred | Dependency wave remains deferred until runtime blockers and gates are clean. |

## Current Checkpoint

### What changed

- Created this progress report before implementation work, as required by the audit hand-off workflow.

### What was validated

- `git status --short` confirmed the starting state:

```text
 M apps/api/app/routers/catalog.py
 M apps/web/app/projects/[projectId]/graph/page.tsx
?? docs/reports/audit-report-20260430-125817.md
```

### Residual Risk

- M1 cannot be fully closed against its original "committed/released" wording without explicit git commit/push authorization.
- The execution will still validate and stabilize the code changes locally before proceeding to functional remediation.

### Next Milestone Recommendation

- Start M2 router restoration. M1 has no remaining implementation gap, but it still has release hygiene pending explicit git authorization.

## M1 Checkpoint - Catalog Graph Recovery

### What changed

- No new source changes were made in M1 during this execution wave.
- The existing recovery diff was reviewed and remains scoped to:
  - `apps/api/app/routers/catalog.py`
  - `apps/web/app/projects/[projectId]/graph/page.tsx`

### What was validated

- Catalog API probe returned `total=480` and 1 row for `page_size=1`.
- Graph API probe returned `72` nodes and `338` edges.
- `cd apps/api && ./.venv/bin/python -m ruff check app/routers/catalog.py` passed.
- `cd apps/api && ./.venv/bin/python -m pytest app/tests/test_catalog_api.py app/tests/test_reference_api.py -q` passed with `9 passed`.
- `cd apps/web && npx eslint 'app/projects/[projectId]/graph/page.tsx' --max-warnings 0` passed.
- `cd apps/web && npx tsc --noEmit --skipLibCheck` passed.
- Playwright opened the Graph page, captured a DOM snapshot with `Nodes=72`, `Edges=338`, `Integrations=480`, and saved a screenshot to `output/playwright/graph-m1-validation.png`.
- Browser console contained only the React DevTools informational message.

### Residual Risk

- M1 cannot be marked fully complete because the original exit criteria require source changes to be committed/released, and no git commit/push was requested for this execution.

### Next Milestone Recommendation

- Proceed to M2 because the implementation side of M1 is validated and the remaining M1 gap is release hygiene rather than runtime behavior.

## M2 Checkpoint - Service-Backed Routers

### What changed

- Replaced hardcoded empty payloads in:
  - `apps/api/app/routers/audit.py`
  - `apps/api/app/routers/dashboard.py`
  - `apps/api/app/routers/assumptions.py`
  - `apps/api/app/routers/volumetry.py`
- Added `VolumetrySnapshotRowResultsResponse` to `apps/api/app/schemas/volumetry.py`.
- Added `recalc_service.list_snapshot_rows(...)` to keep the row-level volumetry router thin.

### What was validated

- `cd apps/api && ./.venv/bin/python -m ruff check app/routers/audit.py app/routers/dashboard.py app/routers/assumptions.py app/routers/volumetry.py app/services/recalc_service.py app/schemas/volumetry.py` passed.
- `cd apps/api && ./.venv/bin/python -m pytest app/tests/test_projects_api.py app/tests/test_dashboard_service.py app/tests/test_reference_api.py app/tests/test_catalog_api.py -q` passed with `12 passed`.
- Live API probes returned:
  - audit `total=625`
  - dashboard `total=3`
  - volumetry snapshots `3`
  - volumetry rows `total=480`
  - assumptions `2`
  - default assumption `version=1.0.0`

### Residual Risk

- None for M2 behavior after the full backend suite passed in M3.

### Next Milestone Recommendation

- Continue to M3 to repair the recalculation contract regression discovered by full backend tests.

## M3 Checkpoint - Recalculation Input Contract

### What changed

- Removed unsupported `selected_pattern` keyword arguments from `IntegrationInput` construction in `apps/api/app/services/recalc_service.py`.

### What was validated

- `cd apps/api && ./.venv/bin/python -m pytest app/tests/test_recalc_design_warnings.py app/tests/test_projects_api.py -q` passed with `2 passed`.
- `cd apps/api && ./.venv/bin/python -m pytest --tb=short -q` passed with `38 passed`.
- `cd apps/api && ./.venv/bin/python -m ruff check app/services/recalc_service.py app/routers/audit.py app/routers/dashboard.py app/routers/assumptions.py app/routers/volumetry.py app/schemas/volumetry.py` passed.

### Residual Risk

- None identified for the tested recalculation contract.

### Next Milestone Recommendation

- Continue to M4 and refresh the API contract artifact after route changes.

## M4 Checkpoint - OpenAPI Contract

### What changed

- Regenerated `docs/api/openapi.yaml` using `apps/api/scripts/export_openapi.py`.

### What was validated

- `cd apps/api && ./.venv/bin/python scripts/export_openapi.py --check` reported the OpenAPI artifact is up to date.

### Residual Risk

- None identified locally. Contract drift should now be caught by the new CI workflow added in M5.

### Next Milestone Recommendation

- Continue to M5 to close typing and continuous gate enforcement.

## M5 Checkpoint - Typing, CI, And Hygiene

### What changed

- Added typed payload narrowing helper `_payload_int(...)` in `apps/api/app/services/synthetic_service.py`.
- Annotated synthetic audit `old_value` payloads as `dict[str, object]`.
- Passed sorted sequences to `normalize_canvas_design(...)` from `apps/api/app/services/catalog_service.py`.
- Removed local ignored artifact `docs/.DS_Store`.
- Added root workflow `.github/workflows/oci-dis-blueprint-quality.yml` with backend pytest, ruff, mypy, OpenAPI check, frontend tsc, and frontend eslint gates.

### What was validated

- `cd apps/api && ./.venv/bin/python -m mypy app --ignore-missing-imports --no-error-summary` passed.
- `cd apps/api && ./.venv/bin/python -m ruff check .` passed.
- `cd apps/api && ./.venv/bin/python -m pytest --tb=short -q` passed with `38 passed`.
- `cd apps/api && ./.venv/bin/python scripts/export_openapi.py --check` passed.
- `cd apps/web && npx tsc --noEmit --skipLibCheck` passed.
- `cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0` passed.
- Live endpoint probes passed for catalog, graph, audit, dashboard, volumetry, row-level volumetry, consolidated volumetry, assumptions, and default assumptions.
- `docker compose ps` shows all six services running, with API and DB healthy.
- `docs/.DS_Store` is absent.

### Residual Risk

- The GitHub Actions workflow was not executed on GitHub in this local session. Its commands are the same local gates that passed.
- M1 still has release hygiene pending because no commit/push was requested.

### Next Milestone Recommendation

- Keep M6 deferred until after these changes are committed and reviewed. Then run dependency maintenance as a separate controlled wave.
