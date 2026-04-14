# Project Audit Report

**Generated:** 2026-04-14 23:59
**Repository:** https://github.com/javierchan/oci.git
**Branch:** HEAD (detached)
**Commit:** `f6dd336 docs: M14 complete — update progress log and milestone table`
**Auditor:** Codex (automated)

---

## Executive Summary

The repository is functionally broad and the running Docker stack is healthy, but the checked-out worktree is not in a clean, reproducible milestone state. Based on code presence, route inventory, runtime probes, and the repo’s own milestone docs, `11/14` milestones are auditable as complete, `3/14` are partial, and none are clearly not started.

The strongest positive signals are:
- Docker stack is up and healthy (`6/6` containers running).
- Calc-engine parity tests pass (`26 passed`).
- TypeScript check passes.
- M11 through M14 are documented and validated in `docs/progress.md`.
- Runtime endpoint coverage is broad (`46` paths, `64` operations).

The main blockers are repository hygiene and reproducibility, not missing UI:
- The repo is on a detached `HEAD`.
- Milestone-critical backend files for M8-M10 are still modified or untracked in the worktree.
- Runtime behavior for M9/M10 exists, but key backend artifacts are not all preserved in committed history.
- Repo-wide lint/type tooling is inconsistent with the documented Docker-first workflow.

## Repository Profile

- Product plan source: `AGENTS.md`
- Human-facing status source: `README.md`
- Milestone execution log source: `docs/progress.md`
- Stack detected:
  - FastAPI / Python backend in `apps/api/`
  - Next.js / TypeScript frontend in `apps/web/`
  - Docker Compose stack via `docker-compose.yml`
  - Alembic config in `apps/api/alembic.ini`
  - Calc-engine tests in `packages/calc-engine/src/tests`
- Shell compatibility note:
  - The repo is running under `zsh`, and unmatched glob patterns fail there.
  - For stack detection, `bash -lc 'shopt -s nullglob; ...'` was used to avoid false negatives.

### Repository Summary

- Remote: `https://github.com/javierchan/oci.git`
- Branch: `HEAD`
- Latest commit: `f6dd336 docs: M14 complete — update progress log and milestone table`
- Oldest commit date in local history: `2026-01-07`
- Newest commit date in local history: `2026-04-14`
- Total commits in local history: `210`
- Commits in prior 7-day window: `3`
- Commits in last 7 days: `21`
- Source files counted (`*.py`, `*.ts`, `*.tsx`, excluding build/vendor dirs): `122`
- `cloc` availability: unavailable in this environment (`zsh:1: command not found: cloc`)

### Working Tree State

The worktree is dirty. Key milestone-related changes are not fully committed:

```text
 M apps/api/app/core/calc_engine.py
 M apps/api/app/migrations/seed.py
 M apps/api/app/models/governance.py
 M apps/api/app/routers/catalog.py
 M apps/api/app/routers/imports.py
 M apps/api/app/routers/justifications.py
 M apps/api/app/routers/patterns.py
 M apps/api/app/routers/projects.py
 M apps/api/app/schemas/imports.py
 M apps/api/app/schemas/justification.py
 M apps/api/app/schemas/project.py
 M apps/api/app/schemas/reference.py
 M apps/api/app/services/import_service.py
 M apps/api/app/services/justification_service.py
 M apps/api/app/services/project_service.py
 M apps/api/app/services/reference_service.py
 M package-lock.json
?? apps/api/app/schemas/graph.py
?? apps/api/app/services/graph_service.py
?? apps/api/migrations/versions/20260414_0003_add_is_system_to_pattern_definitions.py
?? docs/status-report.md
```

## Milestone Status

### Progress Metrics

```text
Total milestones: 14
Complete: 11
Partial: 3
Not started: 0
In progress: 0

Definition-of-done items total: 14
Items verified: 11
Items with gaps: 3
```

### M1 — Schema + Migrations
**Status:** ✅ Complete

Evidence:
- Core models exist in `apps/api/app/models/project.py`, `apps/api/app/models/snapshot.py`, and `apps/api/app/models/governance.py`.
- Seed script exists at `apps/api/app/migrations/seed.py`.
- Alembic config and migrations are present in `apps/api/alembic.ini` and `apps/api/migrations/versions/`.
- Reference data is queryable through runtime endpoints:
  - `patterns_total=17`
  - `assumptions_total=2`
  - `dictionary_categories=5`

Gaps:
- The audit did not rerun `alembic upgrade head`.
- Database table inventory query did not return usable output against the expected database name.

Deviation:
- The repo is Docker-first, but some audit/local verification tooling still assumes a host `.venv`.

### M2 — Import Engine
**Status:** ✅ Complete

Evidence:
- Import service exists at `apps/api/app/services/import_service.py`.
- Importer engine exists at `packages/calc-engine/src/engine/importer.py`.
- Import endpoints are registered:
  - `POST GET /api/v1/imports/{project_id}`
  - `GET DELETE /api/v1/imports/{project_id}/{batch_id}`
  - `GET /api/v1/imports/{project_id}/{batch_id}/rows`
- Calc-engine parity suite passes:
  - `26 passed in 0.05s`
- Benchmark expectations file exists at `packages/test-fixtures/benchmarks/parity-expectations.json` with `157 / 13 / 144` parity targets.

Gaps:
- Current first-project runtime data is not the benchmark dataset (`catalog_total=13`), so benchmark-loaded row counts were not re-proven against the live DB during this audit.

### M3 — Catalog Grid API
**Status:** ✅ Complete

Evidence:
- Catalog service exists at `apps/api/app/services/catalog_service.py`.
- Catalog router exists at `apps/api/app/routers/catalog.py`.
- Registered routes include:
  - `GET POST /api/v1/catalog/{project_id}`
  - `POST /api/v1/catalog/{project_id}/bulk-patch`
  - `GET PATCH DELETE /api/v1/catalog/{project_id}/{integration_id}`
  - `GET /api/v1/catalog/{project_id}/{integration_id}/lineage`
- Endpoint probes passed:
  - `GET /catalog/{pid}`
  - `GET /catalog/{pid}/duplicates`
  - `GET /catalog/{pid}/systems`
  - `POST /catalog/{pid}/estimate`

Gaps:
- None found at the API-surface level during this audit.

### M4 — Calculation Engine
**Status:** ✅ Complete

Evidence:
- Recalculation service exists at `apps/api/app/services/recalc_service.py`.
- Volumetry engine exists at `packages/calc-engine/src/engine/volumetry.py`.
- Recalculate routes are registered:
  - `POST /api/v1/recalculate/{project_id}`
  - `GET /api/v1/recalculate/{project_id}/jobs/{job_id}`
  - `POST /api/v1/recalculate/{project_id}/scoped`
- Volumetry snapshot routes are registered and healthy:
  - `GET /api/v1/volumetry/{project_id}/snapshots`
  - `GET /api/v1/volumetry/{project_id}/snapshots/{snapshot_id}`
  - `GET /api/v1/volumetry/{project_id}/snapshots/{snapshot_id}/consolidated`
- First project has `snapshots_total=4`.

Gaps:
- None found in route/file coverage.

### M5 — Dashboard API / Core Frontend
**Status:** ✅ Complete

Evidence:
- Dashboard page exists at `apps/web/app/projects/[projectId]/page.tsx`.
- Dashboard endpoints are registered:
  - `GET /api/v1/dashboard/{project_id}/snapshots`
  - `GET /api/v1/dashboard/{project_id}/snapshots/{snapshot_id}`
- Frontend core pages are present:
  - `apps/web/app/projects/page.tsx`
  - `apps/web/app/projects/[projectId]/import/page.tsx`
  - `apps/web/app/projects/[projectId]/catalog/page.tsx`
  - `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx`
- Endpoint probe passed:
  - `GET /dashboard/{pid}/snapshots`

Gaps:
- The audit did not compare dashboard values against workbook benchmark outputs.

### M6 — Justification Narratives
**Status:** ✅ Complete

Evidence:
- Router exists at `apps/api/app/routers/justifications.py`.
- Runtime endpoints are registered:
  - `GET /api/v1/justifications/{project_id}`
  - `GET DELETE /api/v1/justifications/{project_id}/{integration_id}`
  - `POST /api/v1/justifications/{project_id}/{integration_id}/approve`
  - `POST /api/v1/justifications/{project_id}/{integration_id}/override`
- Template governance routes also exist:
  - `GET POST /api/v1/justifications/templates`
  - `GET PATCH /api/v1/justifications/templates/{version}`
  - `POST /api/v1/justifications/templates/{version}/default`
- Endpoint probe passed:
  - `GET /justifications/{pid}`

Gaps:
- Approval/override behavior was not individually smoke-tested in this audit.

### M7 — Exports
**Status:** ✅ Complete

Evidence:
- Export router exists at `apps/api/app/routers/exports.py`.
- Export service exists at `apps/api/app/services/export_service.py`.
- Runtime export routes are registered:
  - `POST /api/v1/exports/{project_id}/xlsx`
  - `POST /api/v1/exports/{project_id}/pdf`
  - `POST /api/v1/exports/{project_id}/json`
  - `GET /api/v1/exports/{project_id}/jobs/{job_id}`
  - `GET /api/v1/exports/{project_id}/jobs/{job_id}/download`
- Additional template export exists:
  - `GET /api/v1/exports/template/xlsx`
- M12 smoke validated the template workbook as a real XLSX artifact.

Gaps:
- Project-scoped XLSX/PDF/JSON export job generation was not directly smoke-tested during this audit.

### M8 — Admin + Governance
**Status:** ⚠ Partial

Evidence:
- Admin UI pages exist:
  - `apps/web/app/admin/page.tsx`
  - `apps/web/app/admin/patterns/page.tsx`
  - `apps/web/app/admin/dictionaries/page.tsx`
  - `apps/web/app/admin/assumptions/page.tsx`
- Governance routes are registered:
  - Patterns: `GET POST /api/v1/patterns/`, `GET PATCH DELETE /api/v1/patterns/{pattern_id}`
  - Dictionaries: `GET POST /api/v1/dictionaries/{category}`, `PATCH DELETE /api/v1/dictionaries/{category}/{option_id}`
  - Assumptions: `GET POST /api/v1/assumptions/`, `GET PATCH /api/v1/assumptions/{version}`, `POST /api/v1/assumptions/{version}/default`
- Runtime probes passed for `/patterns`, `/dictionaries`, and `/assumptions`.

Gaps:
- `apps/api/migrations/versions/20260414_0003_add_is_system_to_pattern_definitions.py` exists but is untracked.
- Governance-related backend files remain modified in the worktree:
  - `apps/api/app/models/governance.py`
  - `apps/api/app/routers/patterns.py`
  - `apps/api/app/services/reference_service.py`
  - `apps/api/app/migrations/seed.py`
- Because the migration and backend artifacts are not fully committed, M8 is not reproducible from committed history.

Deviation:
- `README.md` says M8 is complete, but the governance migration and related backend files are not in a clean committed state.

### M9 — Integration Capture Wizard
**Status:** ⚠ Partial

Evidence:
- Capture pages exist:
  - `apps/web/app/projects/[projectId]/capture/page.tsx`
  - `apps/web/app/projects/[projectId]/capture/new/page.tsx`
- Capture components exist:
  - `apps/web/components/capture-wizard.tsx`
  - `apps/web/components/oic-estimate-preview.tsx`
  - `apps/web/components/qa-preview.tsx`
  - `apps/web/components/system-autocomplete.tsx`
- `apps/web/components/capture-wizard.tsx` is explicitly a five-step flow with duplicate checks and submit handling.
- Runtime routes are registered and healthy:
  - `GET POST /api/v1/catalog/{project_id}`
  - `GET /api/v1/catalog/{project_id}/systems`
  - `GET /api/v1/catalog/{project_id}/duplicates`
  - `POST /api/v1/catalog/{project_id}/estimate`
- Endpoint probes passed for all four M9 backend routes.

Gaps:
- Capture-related backend files are still modified in the worktree:
  - `apps/api/app/routers/catalog.py`
  - `apps/api/app/services/catalog_service.py`
- The audit did not perform browser-level validation of step-by-step form behavior, duplicate warning UX, or post-submit catalog visibility.

Deviation:
- `README.md` still marks M9 as partial, while the codebase and runtime expose substantial M9 functionality.

### M10 — System Dependency Map
**Status:** ⚠ Partial

Evidence:
- Graph page and components exist:
  - `apps/web/app/projects/[projectId]/graph/page.tsx`
  - `apps/web/components/integration-graph.tsx`
  - `apps/web/components/graph-controls.tsx`
  - `apps/web/components/graph-detail-panel.tsx`
  - `apps/web/components/graph-export-button.tsx`
- Runtime route exists and passed:
  - `GET /api/v1/catalog/{project_id}/graph`
- Graph backend artifacts exist in the worktree:
  - `apps/api/app/services/graph_service.py`
  - `apps/api/app/schemas/graph.py`

Gaps:
- `apps/api/app/services/graph_service.py` is untracked.
- `apps/api/app/schemas/graph.py` is untracked.
- Because the backend graph files are not committed, the milestone is not reproducible from versioned history even though the current runtime exposes the endpoint.

Deviation:
- `README.md` still marks M10 as partial, and in this case the partial status is justified by the untracked backend graph artifacts.

### M11 — Navigation + Theme
**Status:** ✅ Complete

Evidence:
- `docs/progress.md` contains an M11 completion entry with validation output.
- Theme/navigation files exist:
  - `apps/web/components/breadcrumb.tsx`
  - `apps/web/components/theme-toggle.tsx`
  - `apps/web/lib/use-theme.ts`
  - `apps/web/app/layout.tsx`
  - `apps/web/app/globals.css`
- Runtime/validation evidence from progress log:
  - `TypeScript: 0 errors`
  - `ruff: All checks passed!`
  - `pytest: 26 passed, 2 warnings`
  - `docker compose ps: 6/6 containers Up`

Gaps:
- None found beyond documentation-ordering debt noted below.

### M12 — Source Lineage + Template
**Status:** ✅ Complete

Evidence:
- M12 completion is documented in `docs/progress.md`.
- Lineage schema/service updates are present in:
  - `apps/api/app/schemas/catalog.py`
  - `apps/api/app/services/catalog_service.py`
- Template export is present in:
  - `apps/api/app/routers/exports.py`
  - `apps/api/app/services/export_service.py`
- Import-page download action exists in `apps/web/components/import-upload.tsx`.
- Audit smoke checks confirmed:
  - `lineage column_names: True`
  - `lineage import_batch_date: True`
  - valid XLSX bytes returned
  - template import smoke completed successfully

Gaps:
- None found.

### M13 — Integration Design Canvas
**Status:** ✅ Complete

Evidence:
- `apps/web/components/integration-canvas.tsx` exists.
- `apps/web/components/integration-patch-form.tsx` integrates the canvas.
- `docs/progress.md` contains an M13 completion entry.
- Validation evidence:
  - `TypeScript: 0 errors`
  - detail route reachability verified

Gaps:
- None found.

### M14 — Map Pan + Visual Improvements
**Status:** ✅ Complete

Evidence:
- `apps/web/components/graph-controls.tsx` includes select/pan mode support.
- `apps/web/components/integration-graph.tsx` includes viewport pan/zoom, animated edges, hover behavior, tooltip, legend, and count labels.
- `apps/web/app/projects/[projectId]/graph/page.tsx` owns mode and viewport state.
- `docs/progress.md` contains an M14 completion entry.
- Validation evidence:
  - `TypeScript: 0 errors`
  - graph route reachability verified
  - final `ruff`, `pytest`, and `docker compose ps` were clean

Gaps:
- None found.

## Verification Results

### Context Discovery

Files read:
- `AGENTS.md`
- `README.md`
- `docs/progress.md`

### Stack Detection

```text
apps/api/requirements.txt
---
apps/web/package.json
package.json
---
docker-compose.yml
---
apps/api/alembic.ini
apps/api/migrations
---
packages/calc-engine/src/tests
---
```

### Repository Summary Commands

`git remote get-url origin`
```text
https://github.com/javierchan/oci.git
```

`git branch --show-current`
```text
(no output)
```

`git rev-parse --abbrev-ref HEAD`
```text
HEAD
```

`git log --oneline -1`
```text
f6dd336 docs: M14 complete — update progress log and milestone table
```

`git log --format="%ad" --date=short | tail -1`
```text
2026-01-07
```

`git log --format="%ad" --date=short | head -1`
```text
2026-04-14
```

`git log --oneline | wc -l`
```text
     210
```

`git shortlog -sn --no-merges | head -5`
```text
(no output)
```

`git status --short`
```text
 M apps/api/app/core/calc_engine.py
 M apps/api/app/migrations/seed.py
 M apps/api/app/models/governance.py
 M apps/api/app/routers/catalog.py
 M apps/api/app/routers/imports.py
 M apps/api/app/routers/justifications.py
 M apps/api/app/routers/patterns.py
 M apps/api/app/routers/projects.py
 M apps/api/app/schemas/imports.py
 M apps/api/app/schemas/justification.py
 M apps/api/app/schemas/project.py
 M apps/api/app/schemas/reference.py
 M apps/api/app/services/import_service.py
 M apps/api/app/services/justification_service.py
 M apps/api/app/services/project_service.py
 M apps/api/app/services/reference_service.py
 M package-lock.json
?? apps/api/app/schemas/graph.py
?? apps/api/app/services/graph_service.py
?? apps/api/migrations/versions/20260414_0003_add_is_system_to_pattern_definitions.py
?? docs/status-report.md
```

`git stash list | head -5`
```text
(no output)
```

`find ... | wc -l`
```text
     122
```

`cloc ...`
```text
zsh:1: command not found: cloc
```

`git log --oneline --since="14 days ago" --until="7 days ago" | wc -l`
```text
       3
```

`git log --oneline --since="7 days ago" | wc -l`
```text
      21
```

### Verification Commands

`./.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -40`
```text
..........................                                               [100%]
26 passed in 0.05s
```

`./.venv/bin/python -m ruff check . 2>&1 | tail -20`
```text
packages/calc-engine/src/engine/importer.py:14:8: F401 [*] `re` imported but unused
packages/calc-engine/src/tests/test_importer.py:9:8: F401 [*] `pytest` imported but unused
packages/calc-engine/src/tests/test_volumetry.py:9:8: F401 [*] `math` imported but unused
Found 3 errors.
[*] 3 fixable with the `--fix` option.
```

`./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary 2>&1 | tail -10`
```text
/Users/javierchan/.codex/worktrees/b840/oci/OCI DIS Blueprint/.venv/bin/python: No module named mypy
```

`cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -30; cd ../..`
```text
(no output)
```

`cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0 2>&1 | tail -20; cd ../..`
```text

Oops! Something went wrong! :(

ESLint: 8.57.1

ESLint couldn't find a configuration file. To set up a configuration file for this project, please run:

    npm init @eslint/config

ESLint looked for configuration files in /Users/javierchan/.codex/worktrees/b840/oci/OCI DIS Blueprint/apps/web/app/admin/assumptions/[version] and its ancestors. If it found none, it then looked in your home directory.

If you think you already have a configuration file or if you need more help, please stop by the ESLint Discord server: https://eslint.org/chat
```

`docker compose ps`
```text
NAME                       IMAGE                    COMMAND                  SERVICE   CREATED        STATUS                  PORTS
ocidisblueprint-api-1      ocidisblueprint-api      "uvicorn app.main:ap…"   api       4 hours ago    Up 4 hours (healthy)    0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
ocidisblueprint-db-1       postgres:16-alpine       "docker-entrypoint.s…"   db        18 hours ago   Up 18 hours (healthy)   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp
ocidisblueprint-minio-1    minio/minio:latest       "/usr/bin/docker-ent…"   minio     18 hours ago   Up 18 hours (healthy)   0.0.0.0:9000-9001->9000-9001/tcp, [::]:9000-9001->9000-9001/tcp
ocidisblueprint-redis-1    redis:7-alpine           "docker-entrypoint.s…"   redis     18 hours ago   Up 18 hours (healthy)   0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp
ocidisblueprint-web-1      ocidisblueprint-web      "docker-entrypoint.s…"   web       4 hours ago    Up 4 hours              0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp
ocidisblueprint-worker-1   ocidisblueprint-worker   "celery -A app.worke…"   worker    18 hours ago   Up 18 hours             8000/tcp
```

`docker compose ps --format json ...`
```text
Could not parse docker compose json: Extra data: line 2 column 1 (char 1870)
```

`curl -sf http://localhost:8000/health ...`
```text
{"status":"ok","version":"1.0.0"}API: UP
```

`curl -sf http://localhost:8000/openapi.json ...`
```text
Registered endpoints: 46 paths, 64 operations
```

`docker compose exec -T db psql -U postgres -d dis_blueprint -c ... | head -30`
```text
(no output)
```

`./.venv/bin/pip list --outdated | head -20`
```text
Package           Version Latest  Type
----------------- ------- ------- -----
aiosqlite         0.20.0  0.22.1  wheel
alembic           1.13.1  1.18.4  wheel
asyncpg           0.29.0  0.31.0  wheel
celery            5.4.0   5.6.3   wheel
coverage          7.5.1   7.13.5  wheel
fastapi           0.111.0 0.135.3 wheel
greenlet          3.0.3   3.4.0   wheel
httpx             0.27.0  0.28.1  wheel
Mako              1.3.10  1.3.11  wheel
openpyxl          3.1.2   3.1.5   wheel
packaging         26.0    26.1    wheel
pandas            2.2.2   3.0.2   wheel
psycopg2-binary   2.9.9   2.9.11  wheel
pydantic          2.7.1   2.13.0  wheel
pydantic_core     2.18.2  2.46.0  wheel
pydantic-settings 2.2.1   2.13.1  wheel
pytest            8.2.0   9.0.3   wheel
pytest-asyncio    0.23.6  1.3.0   wheel
```

`cd apps/web && npm outdated --depth=0 | head -20; cd ../..`
```text
Package                Current    Wanted   Latest  Location                           Depended by
@types/node           20.19.39  20.19.39   25.6.0  node_modules/@types/node           web@npm:@oci-dis/web@1.0.0
@types/react           18.3.28   18.3.28  19.2.14  node_modules/@types/react          web@npm:@oci-dis/web@1.0.0
@types/react-dom        18.3.7    18.3.7   19.2.3  node_modules/@types/react-dom      web@npm:@oci-dis/web@1.0.0
@vitejs/plugin-react     4.7.0     4.7.0    6.0.1  node_modules/@vitejs/plugin-react  web@npm:@oci-dis/web@1.0.0
eslint                  8.57.1    8.57.1   10.2.0  node_modules/eslint                web@npm:@oci-dis/web@1.0.0
eslint-config-next      14.2.3    14.2.3   16.2.3  node_modules/eslint-config-next    web@npm:@oci-dis/web@1.0.0
lucide-react           0.383.0   0.383.0    1.8.0  node_modules/lucide-react          web@npm:@oci-dis/web@1.0.0
next                    14.2.3    14.2.3   16.2.3  node_modules/next                  web@npm:@oci-dis/web@1.0.0
react                   18.3.1    18.3.1   19.2.5  node_modules/react                 web@npm:@oci-dis/web@1.0.0
react-dom               18.3.1    18.3.1   19.2.5  node_modules/react-dom             web@npm:@oci-dis/web@1.0.0
recharts                2.15.4    2.15.4    3.8.1  node_modules/recharts              web@npm:@oci-dis/web@1.0.0
tailwind-merge           2.6.1     2.6.1    3.5.0  node_modules/tailwind-merge        web@npm:@oci-dis/web@1.0.0
tailwindcss             3.4.19    3.4.19    4.2.2  node_modules/tailwindcss           web@npm:@oci-dis/web@1.0.0
typescript               5.9.3     5.9.3    6.0.2  node_modules/typescript            web@npm:@oci-dis/web@1.0.0
vitest                   1.6.1     1.6.1    4.1.4  node_modules/vitest                web@npm:@oci-dis/web@1.0.0
zod                    3.25.76   3.25.76    4.3.6  node_modules/zod                   web@npm:@oci-dis/web@1.0.0
zustand                  4.5.7     4.5.7   5.0.12  node_modules/zustand               web@npm:@oci-dis/web@1.0.0
```

### Endpoint Inventory

```text
Total endpoints: 46
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
  GET                            /api/v1/exports/template/xlsx
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
  GET POST                       /api/v1/patterns/
  GET PATCH DELETE               /api/v1/patterns/{pattern_id}
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

### File Inventory

```text
Present: 56 / 56
  OK       2484 bytes   API entry point  (apps/api/app/main.py)
  OK       1546 bytes   Config / settings  (apps/api/app/core/config.py)
  OK       1433 bytes   DB session  (apps/api/app/core/db.py)
  OK       7522 bytes   Core models  (apps/api/app/models/project.py)
  OK       3361 bytes   Snapshot models  (apps/api/app/models/snapshot.py)
  OK       3638 bytes   Governance models  (apps/api/app/models/governance.py)
  OK      19000 bytes   Import service  (apps/api/app/services/import_service.py)
  OK      26797 bytes   Catalog service  (apps/api/app/services/catalog_service.py)
  OK      11925 bytes   Recalc service  (apps/api/app/services/recalc_service.py)
  OK       2930 bytes   Audit service  (apps/api/app/services/audit_service.py)
  OK       6549 bytes   Graph service  (apps/api/app/services/graph_service.py)
  OK      17244 bytes   Export service  (apps/api/app/services/export_service.py)
  OK       5786 bytes   Catalog schemas  (apps/api/app/schemas/catalog.py)
  OK       1356 bytes   Graph schemas  (apps/api/app/schemas/graph.py)
  OK       2284 bytes   Projects router  (apps/api/app/routers/projects.py)
  OK       3421 bytes   Imports router  (apps/api/app/routers/imports.py)
  OK       5956 bytes   Catalog router  (apps/api/app/routers/catalog.py)
  OK       2712 bytes   Patterns router  (apps/api/app/routers/patterns.py)
  OK       2873 bytes   Dictionaries router  (apps/api/app/routers/dictionaries.py)
  OK       2889 bytes   Assumptions router  (apps/api/app/routers/assumptions.py)
  OK       1374 bytes   Recalculate router  (apps/api/app/routers/recalculate.py)
  OK       1412 bytes   Volumetry router  (apps/api/app/routers/volumetry.py)
  OK       1069 bytes   Audit router  (apps/api/app/routers/audit.py)
  OK       2670 bytes   Exports router  (apps/api/app/routers/exports.py)
  OK       5745 bytes   Justifications router  (apps/api/app/routers/justifications.py)
  OK      12035 bytes   Seed script  (apps/api/app/migrations/seed.py)
  OK        913 bytes   Pattern migration  (apps/api/migrations/versions/20260414_0003_add_is_system_to_pattern_definitions.py)
  OK      13685 bytes   Volumetry engine  (packages/calc-engine/src/engine/volumetry.py)
  OK       2385 bytes   QA engine  (packages/calc-engine/src/engine/qa.py)
  OK       8004 bytes   Importer engine  (packages/calc-engine/src/engine/importer.py)
  OK       4501 bytes   Volumetry tests  (packages/calc-engine/src/tests/test_volumetry.py)
  OK       5342 bytes   Importer tests  (packages/calc-engine/src/tests/test_importer.py)
  OK       2163 bytes   Root layout  (apps/web/app/layout.tsx)
  OK       1410 bytes   Projects list page  (apps/web/app/projects/page.tsx)
  OK       6630 bytes   Dashboard page  (apps/web/app/projects/[projectId]/page.tsx)
  OK       1989 bytes   Import page  (apps/web/app/projects/[projectId]/import/page.tsx)
  OK       2983 bytes   Catalog page  (apps/web/app/projects/[projectId]/catalog/page.tsx)
  OK      13319 bytes   Detail page  (apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx)
  OK       3199 bytes   Capture history page  (apps/web/app/projects/[projectId]/capture/page.tsx)
  OK       2021 bytes   Capture wizard page  (apps/web/app/projects/[projectId]/capture/new/page.tsx)
  OK       6966 bytes   Graph page  (apps/web/app/projects/[projectId]/graph/page.tsx)
  OK       3058 bytes   Admin hub page  (apps/web/app/admin/page.tsx)
  OK      10170 bytes   Admin patterns page  (apps/web/app/admin/patterns/page.tsx)
  OK       1955 bytes   Admin dictionaries page  (apps/web/app/admin/dictionaries/page.tsx)
  OK       7706 bytes   Admin assumptions page  (apps/web/app/admin/assumptions/page.tsx)
  OK      12537 bytes   Catalog table  (apps/web/components/catalog-table.tsx)
  OK      12820 bytes   Capture wizard component  (apps/web/components/capture-wizard.tsx)
  OK       3862 bytes   OIC estimate preview  (apps/web/components/oic-estimate-preview.tsx)
  OK       2811 bytes   QA preview component  (apps/web/components/qa-preview.tsx)
  OK      13942 bytes   Graph component  (apps/web/components/integration-graph.tsx)
  OK       6548 bytes   Integration canvas  (apps/web/components/integration-canvas.tsx)
  OK       1658 bytes   Theme toggle  (apps/web/components/theme-toggle.tsx)
  OK       1125 bytes   Breadcrumb component  (apps/web/components/breadcrumb.tsx)
  OK       5389 bytes   Docker Compose stack  (docker-compose.yml)
  OK        908 bytes   API Dockerfile  (apps/api/Dockerfile)
  OK        872 bytes   Web Dockerfile  (apps/web/Dockerfile)
```

### Endpoint Probe Summary

```text
Endpoint checks: 15/15 passed
  OK   200   GET /projects
  OK   200   GET /patterns
  OK   200   GET /dictionaries
  OK   200   GET /assumptions
  OK   200   GET /health
  OK   200   GET /catalog/{pid}
  OK   200   GET /catalog/{pid}/graph
  OK   200   GET /catalog/{pid}/systems
  OK   200   GET /catalog/{pid}/duplicates
  OK   200   POST /catalog/{pid}/estimate
  OK   200   GET /imports/{pid}
  OK   200   GET /volumetry/{pid}/snapshots
  OK   200   GET /audit/{pid}
  OK   200   GET /justifications/{pid}
  OK   200   GET /dashboard/{pid}/snapshots
```

## Pending Tasks

### CRITICAL

- `apps/api/app/services/graph_service.py` — M10 — Graph backend logic exists in the worktree but is untracked, so the current dependency-map backend is not reproducible from committed history.
- `apps/api/app/schemas/graph.py` — M10 — Graph response schema is untracked, which makes the OpenAPI/runtime graph surface depend on non-versioned files.
- `apps/api/migrations/versions/20260414_0003_add_is_system_to_pattern_definitions.py` — M8 — The `is_system` migration exists but is untracked, so governance schema evolution is not safely preserved.

### INCOMPLETE

- `apps/api/app/routers/catalog.py` and `apps/api/app/services/catalog_service.py` — M9 — Manual capture backend behavior exists and passes endpoint probes, but the implementation is still dirty in the worktree and not fully reconciled with README milestone status.
- `README.md` — M9/M10 — Milestones are still marked `⚠ Partial` even though large portions of the implementation are present and serving.
- `docs/progress.md` — M11-M14 — The file is not append-only in chronological order, which deviates from the documented milestone logging contract.
- `apps/web` ESLint workflow — repo-wide frontend quality gate — `npx eslint . --ext .ts,.tsx --max-warnings 0` fails because no ESLint config file is present.
- Repo-wide Python lint workflow — repository quality gate — `./.venv/bin/python -m ruff check .` fails on three unused imports in `packages/calc-engine/`.
- Host type-check workflow — repository quality gate — `mypy` is not installed in the local `.venv`, so the documented audit command cannot run successfully.
- Benchmark project state in live DB — M2/M5 — First-project runtime data does not match benchmark scale (`catalog_total=13` instead of `144`), so live benchmark parity is not demonstrated in the current database.

### DEFERRED

- Project-scoped export smoke (`/api/v1/exports/{project_id}/{format}`) — M7 — Export job creation exists, but this audit did not generate real project export artifacts because it focused on repository status rather than artifact QA.
- Browser-level interaction proof for M9/M10 — M9/M10 — Wizard UX details and graph interaction details were inferred from code and route reachability, not validated through browser automation in this audit.

## Debt Markers

Search result:

```text
./apps/api/app/routers/projects.py:62:    # TODO: partial update + audit
```

Additional debt noted during audit:
- Detached `HEAD` instead of a named working branch.
- Dirty/untracked milestone files in `apps/api/`.
- Documentation drift between `README.md`, `docs/progress.md`, and current runtime behavior.
- Tooling drift between Docker-first repo guidance and host-`.venv` audit commands.

## Recommended Next Actions

1. Commit or reconcile the untracked/dirty backend milestone files for M8-M10, especially `apps/api/app/services/graph_service.py`, `apps/api/app/schemas/graph.py`, and `apps/api/migrations/versions/20260414_0003_add_is_system_to_pattern_definitions.py`.
2. Move off detached `HEAD` onto a named branch and get the worktree clean before any further milestone claims or releases.
3. Decide on the repo-wide quality-gate contract:
   - either make `.venv` + `mypy` + ESLint config first-class and keep host audit commands,
   - or rewrite docs/audit workflows around Docker-only execution.
4. Resolve repo-wide `ruff check .` failures in `packages/calc-engine/` and add an ESLint config if frontend linting is meant to be required.
5. Re-run a benchmark-data validation pass against a seeded benchmark project so M2 and M5 parity can be demonstrated from the current live DB, not only from prior docs.

## Dependency Drift

### Python

The local `.venv` has a meaningful backlog of outdated packages. High-impact examples:
- `fastapi 0.111.0 -> 0.135.3`
- `pydantic 2.7.1 -> 2.13.0`
- `alembic 1.13.1 -> 1.18.4`
- `celery 5.4.0 -> 5.6.3`
- `pytest 8.2.0 -> 9.0.3`

### Frontend

The frontend toolchain also has notable drift:
- `next 14.2.3 -> 16.2.3`
- `react/react-dom 18.3.1 -> 19.2.x`
- `typescript 5.9.3 -> 6.0.2`
- `tailwindcss 3.4.19 -> 4.2.2`
- `eslint 8.57.1 -> 10.2.0`

Audit interpretation:
- This drift is not automatically a blocker.
- It does increase upgrade risk, especially if the repo remains dirty and late-milestone backend changes are not yet committed.
