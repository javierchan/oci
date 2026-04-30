# Milestone Progress Report

**Execution Wave:** Post-audit remediation
**Codebase:** `/Users/javierchan/.codex/worktrees/b840/oci/OCI DIS Blueprint`
**Branch:** `codex/codex-active-work`
**Started:** 2026-04-15 14:19 CST

---

## Milestone Status Summary

- `M1 — Replace The Stubbed Project Patch Route`: complete
- `M2 — Validate Project Patch Audit And API Contract`: complete
- `M3 — Introduce API Integration Test Harness`: complete
- `M4 — Cover Core API Flows In CI`: complete
- `M5 — Restore Source-Controlled OpenAPI Artifact`: complete
- `M6 — Validate Spec Sync And Release Traceability`: complete

---

## Current Milestone

### M1 — Replace The Stubbed Project Patch Route

**Status:** complete

### Scope Confirmation

- `apps/api/app/routers/projects.py` still contains a stubbed `PATCH /projects/{project_id}` route that accepts a raw `dict` and does not delegate to the service layer.
- `apps/api/app/services/project_service.py` already centralizes project CRUD and archive/delete audit behavior, so the patch remediation should extend that pattern instead of introducing a parallel update path.
- `apps/api/app/schemas/project.py` currently lacks a dedicated partial-update request model.

### Working Assumption

The project patch route should support typed updates for user-visible project metadata (`name`, `owner_id`, `description`) while keeping archive state changes on the dedicated archive endpoint.

### What Changed In The Current Milestone

- `apps/api/app/schemas/project.py` now defines `ProjectPatchRequest` so project metadata updates are typed and restricted to `name`, `owner_id`, and `description`.
- `apps/api/app/services/project_service.py` now exposes `update_project(...)`, applies partial updates through the service layer, and emits `project_updated` audit events when values actually change.
- `apps/api/app/routers/projects.py` now uses the typed request model, depends on `AsyncSession`, and returns a real `ProjectResponse` instead of placeholder dict expansion.

### What Was Validated

- `ruff` on the changed backend files: pass
- `mypy apps/api/app --ignore-missing-imports --no-error-summary`: pass
- `pytest packages/calc-engine/src/tests/ -q`: `26 passed`
- `cd apps/web && npx tsc --noEmit --skipLibCheck`: pass
- Live smoke validation:
  - created temporary project successfully
  - patched `name` and `description` through `PATCH /api/v1/projects/{project_id}`
  - fetched updated project successfully
  - observed `project_updated` in `/api/v1/audit/{project_id}`
  - archived and deleted the temporary project successfully

### Residual Risk

- The worktree still contains untracked audit/progress artifacts from this remediation wave, so source commits should keep report files separate from code changes if checkpointing is requested.

### Next Milestone Recommendation

- Start `M3 — Introduce API Integration Test Harness` with a minimal backend fixture layout and one representative route-level test so the repo begins closing the largest remaining quality gap.

---

## Milestone Checkpoint

### M3 — Introduce API Integration Test Harness

**Status:** complete

### What Changed

- Added `apps/api/app/tests/` as the committed backend integration test package.
- Added `apps/api/app/tests/conftest.py` with an isolated async SQLite harness, FastAPI dependency override, and `httpx.AsyncClient` fixture.
- Added `apps/api/app/tests/test_projects_api.py` to validate project patch plus audit-event emission end to end.

### Validation

- `./.venv/bin/python -m pytest apps/api/app/tests -q` -> `1 passed`
- `./.venv/bin/python -m ruff check apps/api/app/tests ...` -> pass
- `./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary` -> pass

### Outcome

The repository now contains a runnable backend API integration test harness instead of relying exclusively on manual smoke probes.

---

## Milestone Checkpoint

### M4 — Cover Core API Flows In CI

**Status:** complete

### What Changed

- Added `apps/api/app/tests/test_catalog_api.py` to validate manual capture, catalog listing, and lineage retrieval.
- Added `apps/api/app/tests/test_exports_api.py` to validate the capture-template export endpoint returns a readable workbook.
- Added a legacy backend validation workflow at the time of this checkpoint to run backend lint, mypy, the API integration suite, calc-engine parity tests, and the OpenAPI sync check. This workflow was retired on 2026-04-30 when the repository moved to Docker-first local validation with no active GitHub Actions workflows.

### Validation

- `./.venv/bin/python -m pytest apps/api/app/tests -q` -> `3 passed`
- `./.venv/bin/python -m pytest packages/calc-engine/src/tests -q` -> `26 passed`
- `./.venv/bin/python -m ruff check apps/api/app apps/api/app/tests apps/api/scripts` -> pass
- Workflow sanity:
  - Legacy backend validation workflow existed at checkpoint time
  - Retired on 2026-04-30; no active GitHub Actions workflow files remain

### Outcome

Representative backend route coverage now exists in a committed suite and is wired into a reproducible CI gate.

---

## Milestone Checkpoint

### M5 — Restore Source-Controlled OpenAPI Artifact

**Status:** complete

### What Changed

- Added `apps/api/scripts/export_openapi.py` to export the runtime OpenAPI document to the documented repository path.
- Generated `docs/api/openapi.yaml` from the current app contract.

### Validation

- `./.venv/bin/python apps/api/scripts/export_openapi.py` -> wrote `docs/api/openapi.yaml`
- `head -5 docs/api/openapi.yaml` -> file present and populated

### Outcome

The repository now contains the source-controlled OpenAPI artifact that earlier audits flagged as missing.

---

## Milestone Checkpoint

### M6 — Validate Spec Sync And Release Traceability

**Status:** complete

### What Changed

- Added `./.venv/bin/python apps/api/scripts/export_openapi.py --check` as the contract-sync verification path.
- Updated `README.md` with refresh and check commands for the OpenAPI artifact.
- Documented the OpenAPI sync check for the legacy backend validation workflow. That workflow was retired on 2026-04-30; OpenAPI sync remains available through the local validation command.

### Validation

- `./.venv/bin/python apps/api/scripts/export_openapi.py --check` -> OpenAPI artifact is up to date
- `cd apps/web && npx tsc --noEmit --skipLibCheck` -> pass
- `./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary` -> pass

### Residual Risk

- The export-template integration test emits upstream `openpyxl` deprecation warnings, but the endpoint behavior remains correct and the warnings are from library internals rather than repository code.

### Next Milestone Recommendation

- Checkpoint the validated source changes and the supporting report artifacts in separate commits if you want this remediation wave preserved cleanly in git history.
