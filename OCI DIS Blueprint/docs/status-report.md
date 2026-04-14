# OCI DIS Blueprint — Status Report
Generated: 2026-04-14
Codebase: 9282b8d Document completed Phase 1 validation

---

## Executive Summary

| Area | Status | Coverage |
|------|--------|----------|
| Backend API | ⚠ Partial | 45/45 endpoints registered in OpenAPI |
| Calc Engine | ⚠ Partial | 0/26 via requested host command; supplemental `.venv` run = 26/26 |
| Frontend | ⚠ Partial | 8/8 milestone pages found |
| Docker Stack | ✅ Complete | 6/6 containers Up |
| M9 Capture | ⚠ Partial | 4/4 backend routes, 6/6 frontend files present |
| M10 Graph | ⚠ Partial | 1/1 backend route, 5/5 frontend files present |

---

## Milestone Coverage

### M1 — Schema + Migrations
**Status:** ✅ Complete

Evidence:
- [x] Alembic migration file exists at `apps/api/migrations/versions/`
- [x] `seed.py` exists and live data shows 17 patterns and 40 dictionary options; default `1.0.0` assumption set is present
- [x] All 11 tables are present in `apps/api/migrations/versions/20260413_0001_initial_schema.py`

Gaps: Live database currently contains 2 assumption sets (`1.0.0` and `1.0.1`), so it no longer matches the original seed-only expectation of exactly 1 assumption set.

---

### M2 — Import Engine
**Status:** ⚠ Partial

Evidence:
- [x] `apps/api/app/services/import_service.py` exists
- [x] `POST /api/v1/imports/{project_id}` endpoint is registered
- [ ] Parity `loaded=144`, `excluded=13`, `tbq_y=157` was verified by the requested host command set

Gaps: `apps/api/app/routers/imports.py` calls `process_import()` directly instead of dispatching a worker; the requested host pytest command failed because `python3` does not have `pytest`; exact API-side parity import (`144/13/157`) was not revalidated during this audit.

---

### M3 — Catalog Grid API
**Status:** ✅ Complete

Evidence:
- [x] `apps/api/app/services/catalog_service.py` exists
- [x] `GET /catalog/{pid}` with filters is registered
- [x] `PATCH /catalog/{pid}/{id}` with audit is registered
- [x] `GET /catalog/{pid}/{id}/lineage` is registered

Gaps: None

---

### M4 — Calculation Engine Integration
**Status:** ⚠ Partial

Evidence:
- [x] `apps/api/app/services/recalc_service.py` exists
- [x] `POST /recalculate/{pid}` endpoint is registered
- [x] `VolumetrySnapshot` is persisted by recalculation flow
- [x] Consolidated metrics endpoint is registered and live

Gaps: `apps/api/app/routers/recalculate.py` still recalculates synchronously; `POST /api/v1/recalculate/{project_id}/scoped` and `GET /api/v1/recalculate/{project_id}/jobs/{job_id}` are placeholders rather than real job handling.

---

### M5 — Next.js Frontend (Core Pages)
**Status:** ✅ Complete

Evidence:
- [x] Projects list page
- [x] Project dashboard page with OIC metrics
- [x] Import upload page
- [x] Catalog grid with filters
- [x] Integration detail + patch form

Gaps: No browser/E2E verification was executed in this audit; status is based on file coverage, type-checking, and route wiring.

---

### M6 — Justification Narratives
**Status:** ✅ Complete

Evidence:
- [x] `justifications.py` router exists
- [x] `GET /justifications/{pid}/{integration_id}` is registered
- [x] `POST /justifications/{pid}/{integration_id}/approve` is registered
- [x] `JustificationRecord` model is present

Gaps: None

---

### M7 — Exports
**Status:** ⚠ Partial

Evidence:
- [x] `exports.py` router exists
- [x] `POST /exports/{pid}/xlsx` is registered
- [x] `POST /exports/{pid}/pdf` is registered
- [x] `POST /exports/{pid}/json` is registered

Gaps: Export output parity against the benchmark workbook/PDF/JSON was not revalidated during this audit.

---

### M8 — Admin + Governance
**Status:** ⚠ Partial

Evidence:
- [ ] PatternDefinition CRUD endpoints
- [x] DictionaryOption management
- [x] AssumptionSet versioning
- [ ] Admin UI page (if applicable)

Gaps: `apps/api/app/routers/patterns.py` is read-only (`GET` only); no dedicated admin UI page was found under `apps/web/app/`; governance exists for dictionaries, assumptions, and prompt templates, but not full pattern CRUD.

---

### M9 — Integration Capture Interface
**Status:** ⚠ Partial

Backend:
- [x] `POST /catalog/{pid}` — manual create
- [x] `GET /catalog/{pid}/systems` — autocomplete
- [x] `GET /catalog/{pid}/duplicates` — duplicate check
- [x] `POST /catalog/{pid}/estimate` — OIC preview

Frontend:
- [x] Capture history page
- [x] 5-step wizard (`capture/new/page.tsx`)
- [x] `capture-wizard.tsx` component
- [x] `oic-estimate-preview.tsx` component
- [x] `qa-preview.tsx` component
- [x] `system-autocomplete.tsx` component

Gaps: `codex-m9-capture.md` was not present at the repo root, so exact spec traceability could not be audited; browser-level validation of step progression, submit confirmation, and catalog visibility was not executed in this pass.

---

### M10 — System Dependency Map
**Status:** ⚠ Partial

Backend:
- [x] `GET /catalog/{pid}/graph` endpoint
- [x] `graph_service.py`
- [x] `GraphResponse` schema (`graph.py`)

Frontend:
- [x] Graph page (`/projects/{pid}/graph`)
- [x] `integration-graph.tsx` (D3 force + React SVG)
- [x] `graph-detail-panel.tsx`
- [x] `graph-controls.tsx`
- [x] `graph-export-button.tsx`
- [x] D3 installed in `package.json`

Gaps: `codex-m10-graph.md` was not present at the repo root, so exact spec traceability could not be audited; graph rendering, zoom, color mode, and PNG export were not browser-verified in this audit.

---

## Test Coverage

### Calc Engine Parity Tests
```text
/opt/homebrew/opt/python@3.14/bin/python3.14: No module named pytest
```
Result: 0/26 passed

Supplemental observation: `./.venv/bin/python -m pytest packages/calc-engine/src/tests/ -v --tb=short` passed 26/26 tests during this audit.

### API Lint (ruff)
```text
/opt/homebrew/opt/python@3.14/bin/python3.14: No module named ruff
```
Result: ❌ Verification command failed because host `python3` does not have `ruff`

Supplemental observation: `./.venv/bin/python -m ruff check apps/api/app/` returned `All checks passed!`.

### TypeScript
```text
```
Result: ✅ Clean

---

## Endpoint Inventory

```text
Total endpoints: 45
  GET POST                       /api/v1/assumptions/
  GET                            /api/v1/assumptions/default
  GET PATCH                      /api/v1/assumptions/{version}
  POST                           /api/v1/assumptions/{version}/default
  GET                            /api/v1/audit/{project_id}
  GET POST                       /api/v1/catalog/{project_id}
  POST                           /api/v1/catalog/{project_id}/bulk-patch
  GET                            /api/v1/catalog/{project_id}/duplicates
  POST                           /api/v1/catalog/{project_id}/estimate
  GET                            /api/v1/catalog/{project_id}/graph
  GET                            /api/v1/catalog/{project_id}/systems
  GET PATCH DELETE               /api/v1/catalog/{project_id}/{integration_id}
  GET                            /api/v1/catalog/{project_id}/{integration_id}/lineage
  GET                            /api/v1/dashboard/{project_id}/snapshots
  GET                            /api/v1/dashboard/{project_id}/snapshots/{snapshot_id}
  GET                            /api/v1/dictionaries/
  GET POST                       /api/v1/dictionaries/{category}
  PATCH DELETE                   /api/v1/dictionaries/{category}/{option_id}
  GET                            /api/v1/exports/{project_id}/jobs/{job_id}
  GET                            /api/v1/exports/{project_id}/jobs/{job_id}/download
  POST                           /api/v1/exports/{project_id}/json
  POST                           /api/v1/exports/{project_id}/pdf
  POST                           /api/v1/exports/{project_id}/xlsx
  POST GET                       /api/v1/imports/{project_id}
  GET DELETE                     /api/v1/imports/{project_id}/{batch_id}
  GET                            /api/v1/imports/{project_id}/{batch_id}/rows
  GET POST                       /api/v1/justifications/templates
  GET PATCH                      /api/v1/justifications/templates/{version}
  POST                           /api/v1/justifications/templates/{version}/default
  GET                            /api/v1/justifications/{project_id}
  GET DELETE                     /api/v1/justifications/{project_id}/{integration_id}
  POST                           /api/v1/justifications/{project_id}/{integration_id}/approve
  POST                           /api/v1/justifications/{project_id}/{integration_id}/override
  GET                            /api/v1/patterns/
  GET                            /api/v1/patterns/{pattern_id}
  GET POST                       /api/v1/projects/
  GET DELETE PATCH               /api/v1/projects/{project_id}
  POST                           /api/v1/projects/{project_id}/archive
  POST                           /api/v1/recalculate/{project_id}
  GET                            /api/v1/recalculate/{project_id}/jobs/{job_id}
  POST                           /api/v1/recalculate/{project_id}/scoped
  GET                            /api/v1/volumetry/{project_id}/snapshots
  GET                            /api/v1/volumetry/{project_id}/snapshots/{snapshot_id}
  GET                            /api/v1/volumetry/{project_id}/snapshots/{snapshot_id}/consolidated
  GET                            /health
```
Total: 45 endpoints registered

Requested endpoint smoke command output:
```text
Traceback (most recent call last):
  File "<string>", line 2, in <module>
    import httpx, sys
ModuleNotFoundError: No module named 'httpx'
```

Supplemental scoped endpoint probe:
- `GET /api/v1/catalog/{pid}/systems` → 200
- `GET /api/v1/catalog/{pid}/duplicates` → 200
- `POST /api/v1/catalog/{pid}/estimate` → 200
- `GET /api/v1/catalog/{pid}/graph` → 200

---

## File Inventory

```text
Present: 49 / 50

  OK       2484 bytes   API entry point
  OK       1546 bytes   Config / settings
  OK       1433 bytes   DB session
  OK       7522 bytes   Core models
  OK       3361 bytes   Snapshot models
  OK       3554 bytes   Governance models
  OK      19000 bytes   Import service
  OK      24683 bytes   Catalog service
  OK      11925 bytes   Recalc service
  OK       2930 bytes   Audit service
  OK       6549 bytes   Graph service (M10)
  OK       5689 bytes   Catalog schemas
  OK       1356 bytes   Graph schemas (M10)
  OK       2284 bytes   Projects router
  OK       3421 bytes   Imports router
  OK       5956 bytes   Catalog router
  OK        957 bytes   Patterns router
  OK       2873 bytes   Dictionaries router
  OK       1374 bytes   Recalculate router
  OK       1412 bytes   Volumetry router
  OK       1069 bytes   Audit router
  OK       2171 bytes   Exports router
  OK       5745 bytes   Justifications router
  OK      11981 bytes   Seed script
  OK      13685 bytes   Volumetry engine
  OK       2385 bytes   QA engine
  OK       8004 bytes   Importer engine
  OK       4501 bytes   Volumetry tests
  OK       5342 bytes   Importer tests
  OK       1526 bytes   Root layout
  OK        740 bytes   Projects list page
  OK       6325 bytes   Dashboard page
  OK        490 bytes   Import page
  OK       2557 bytes   Catalog page
  OK       9671 bytes   Detail page
  OK       2955 bytes   Capture history page (M9)
  OK       1598 bytes   Capture wizard (M9)
  OK       5771 bytes   Graph page (M10)
  OK       6645 bytes   API client
  OK       8969 bytes   TypeScript types
  OK      11613 bytes   Catalog table
  OK       6327 bytes   Graph component (M10)
  OK      12820 bytes   Capture wizard component (M9)
  OK       3862 bytes   OIC estimate preview (M9)
  OK       2811 bytes   QA preview component (M9)
  OK       5389 bytes   Docker Compose stack
  OK        908 bytes   API Dockerfile
  OK        872 bytes   Web Dockerfile
  OK       4648 bytes   Codex setup script

  MISS              QA seed script  (scripts/seed_qa_project.py)
```
Present: 49 / 50 expected files

Additional audit note: `codex-m9-capture.md` and `codex-m10-graph.md` were not present at the repo root, even though they were referenced as required audit inputs.

---

## Docker Stack

```text
NAME                       IMAGE                    COMMAND                  SERVICE   CREATED        STATUS                  PORTS
ocidisblueprint-api-1      ocidisblueprint-api      "uvicorn app.main:ap…"   api       14 hours ago   Up 14 hours (healthy)   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
ocidisblueprint-db-1       postgres:16-alpine       "docker-entrypoint.s…"   db        14 hours ago   Up 14 hours (healthy)   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp
ocidisblueprint-minio-1    minio/minio:latest       "/usr/bin/docker-ent…"   minio     14 hours ago   Up 14 hours (healthy)   0.0.0.0:9000-9001->9000-9001/tcp, [::]:9000-9001->9000-9001/tcp
ocidisblueprint-redis-1    redis:7-alpine           "docker-entrypoint.s…"   redis     14 hours ago   Up 14 hours (healthy)   0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp
ocidisblueprint-web-1      ocidisblueprint-web      "docker-entrypoint.s…"   web       3 hours ago    Up 3 hours              0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp
ocidisblueprint-worker-1   ocidisblueprint-worker   "celery -A app.worke…"   worker    14 hours ago   Up 14 hours             8000/tcp
```

API health command output:
```text
{"status":"ok","version":"1.0.0"}
```

---

## Pending Tasks

### Critical (blocks QA or demo)
- Host verification environment is incomplete: the requested commands fail because host `python3` cannot import `pytest`, `ruff`, or `httpx`.
- `codex-m9-capture.md` is missing from the repo root.
- `codex-m10-graph.md` is missing from the repo root.
- `scripts/seed_qa_project.py` is missing.

### Incomplete (partial implementation)
- `apps/api/app/routers/imports.py` still processes imports synchronously instead of dispatching a worker-backed job path.
- `apps/api/app/routers/recalculate.py` exposes placeholder endpoints at `/api/v1/recalculate/{project_id}/scoped` and `/api/v1/recalculate/{project_id}/jobs/{job_id}`.
- `apps/api/app/routers/patterns.py` does not provide PatternDefinition admin CRUD; it is read-only.
- No admin governance UI page was found under `apps/web/app/` for pattern/dictionary/assumption management.
- Export parity against the benchmark workbook/PDF output has not been revalidated in this audit.

### Optional / Future
- Add browser/E2E coverage for `apps/web/app/projects/[projectId]/capture/new/page.tsx` and `apps/web/app/projects/[projectId]/graph/page.tsx`.
- Decide whether the extra live assumption set `1.0.1` should remain for governance demos or whether demo environments should reset to the seed-only baseline.
- Review dependency drift in `apps/web/package.json` (`axios`, `@tanstack/react-query`) since the implemented API layer uses `fetch`.

---

## Recommended Next Actions

1. Fix the local verification toolchain so the exact host audit commands succeed without falling back to `.venv` (`pytest`, `ruff`, `httpx` under `python3`).
2. Restore the missing audit/support files: `codex-m9-capture.md`, `codex-m10-graph.md`, and `scripts/seed_qa_project.py`.
3. Complete M8 governance by adding PatternDefinition admin mutations in `apps/api/app/routers/patterns.py` and a corresponding admin UI surface under `apps/web/app/`.
4. Replace the synchronous/placeholder import and recalculation job flows in `apps/api/app/routers/imports.py` and `apps/api/app/routers/recalculate.py` with real worker-backed behavior, or remove the placeholder job endpoints until they are implemented.
5. Re-run benchmark-level validation for exports and browser-level validation for the M9 capture wizard and M10 dependency graph.
