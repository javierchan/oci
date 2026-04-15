# Project Audit Report

**Generated:** 2026-04-14 18:21 CST
**Repository:** https://github.com/javierchan/oci.git
**Branch:** codex/codex-active-work
**Commit:** 6cf2d1c docs: browser QA remediation complete
**Auditor:** Codex (automated)

---

## Executive Summary

The codebase is functionally broad and the local stack is healthy: calc-engine parity tests pass, Ruff is clean, TypeScript is clean, the Docker stack is up, and the live API responds with 46 paths / 64 operations. The repository now contains implementations through M14 plus a documented Browser QA remediation pass. Most milestone work is present in source and reflected in `README.md` and `docs/progress.md`.

The main drift is quality-gate related rather than feature absence. The strict frontend lint gate currently fails under `npx eslint . --ext .ts,.tsx --max-warnings 0`, and backend `mypy` still reports 10 type errors in service code. Those do not prevent the app from running locally, but they do prevent a fully clean “all gates green” release posture. The Browser QA milestone is therefore assessed as `⚠ Partial` even though the UX fixes are present.

Summary:

- Total milestones assessed: 15
- Complete: 14
- Partial: 1
- Not started: 0
- In progress: 0
- Critical blockers: 1

Formal definition-of-done metrics:

- Formal AGENTS milestones with explicit checklist items: M1-M8 only
- Definition-of-done items total: 35
- Items verified: 32
- Items with gaps or unverified drift: 3

---

## Repository Profile

Project shape:

- Backend: FastAPI in `apps/api/`
- Frontend: Next.js 14 / TypeScript in `apps/web/`
- Calc engine: pure Python in `packages/calc-engine/`
- Docker stack: `docker-compose.yml`
- Migrations: `apps/api/migrations/` and `apps/api/alembic.ini`
- Tests: `packages/calc-engine/src/tests`

Repository summary:

```text
git log --format="%ad" --date=short | tail -1
2026-01-07

git log --format="%ad" --date=short | head -1
2026-04-14

git log --oneline | wc -l
     223

git shortlog -sn --no-merges | head -5
[no output]

git status --short
[no output]

git stash list 2>/dev/null | head -5
[no output]

find . -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/.git/*' -not -path '*/dist/*' \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' \) | wc -l
     122

cloc . --exclude-dir=node_modules,.venv,.git,dist,__pycache__ --quiet --sum-one 2>/dev/null | tail -3
[no output]
```

Branch and activity:

```text
git status --short --branch
## codex/codex-active-work...origin/codex/codex-active-work

git branch -vv
* codex/codex-active-work  6cf2d1c [origin/codex/codex-active-work] docs: browser QA remediation complete
  main                     5aa6670 [origin/main] merge: bring safe branch into main
+ vscode/codex-active-work 701778d (/Users/javierchan/Documents/GitHub/oci) [origin/vscode/codex-active-work] chore(oci-dis-blueprint): checkpoint current work

git worktree list
/Users/javierchan/Documents/GitHub/oci       701778d [vscode/codex-active-work]
/Users/javierchan/.codex/worktrees/b3b4/oci  89159b2 (detached HEAD)
/Users/javierchan/.codex/worktrees/b840/oci  6cf2d1c [codex/codex-active-work]

git remote -v
origin  https://github.com/javierchan/oci.git (fetch)
origin  https://github.com/javierchan/oci.git (push)

git log --oneline -5
6cf2d1c docs: browser QA remediation complete
0362e17 fix: browser test findings — dark mode inputs, scroll bug, theme persistence, UX enhancements
6f2655f docs: audit remediation complete — progress log and milestone table updated
edb4de6 docs: mark M8-M10 complete in milestone table
7bc800f chore: add mypy to API requirements
```

Repo-shape note:

- The repo-shape detection commands were run under `bash -lc` because the shell for this worktree is `zsh`, and unmatched globs can fail there.

Progress trend:

```text
git log --oneline --since="14 days ago" --until="7 days ago" | wc -l
       3

git log --oneline --since="7 days ago" | wc -l
      34
```

---

## Milestone Status

### M1 — Schema + Migrations
**Status:** ✅ Complete

Evidence:

- Core models exist in `apps/api/app/models/project.py`, `apps/api/app/models/snapshot.py`, and `apps/api/app/models/governance.py`.
- Alembic migration files exist in `apps/api/migrations/versions/20260413_0001_initial_schema.py`, `apps/api/migrations/versions/20260414_0002_prompt_template_versions.py`, and `apps/api/migrations/versions/20260414_0003_add_is_system_to_pattern_definitions.py`.
- Seed logic exists in `apps/api/app/migrations/seed.py` and references `PatternDefinition`, `DictionaryOption`, `AssumptionSet`, `AuditEvent`, and `PromptTemplateVersion`.

Gaps:

- None found in source.

Deviation:

- None.

### M2 — Import Engine
**Status:** ✅ Complete

Evidence:

- Import router endpoints are present in `apps/api/app/routers/imports.py`, including `POST /api/v1/imports/{project_id}`, batch list/detail, rows, and delete routes.
- Import persistence models exist in `apps/api/app/models/project.py` for `ImportBatch`, `SourceIntegrationRow`, and `CatalogIntegration`.
- Business logic is implemented in `apps/api/app/services/import_service.py`.
- Calc-engine parity remains green: `26 passed in 0.06s`, including importer tests.

Gaps:

- None found in source.

Deviation:

- Live DB benchmark parity was not re-proven during this audit; current confidence comes from source, prior project docs, and passing calc-engine parity tests.

### M3 — Catalog Grid API
**Status:** ✅ Complete

Evidence:

- `apps/api/app/routers/catalog.py` exposes list, manual create, duplicate check, systems autocomplete, estimate, detail, patch, bulk-patch, lineage, graph, and delete routes.
- `apps/api/app/services/catalog_service.py` contains lineage and column-name mapping logic (`get_lineage`, `_build_column_names`).
- Frontend catalog surfaces exist in `apps/web/app/projects/[projectId]/catalog/page.tsx` and `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx`.
- `apps/web/components/catalog-table.tsx` provides search, filter, pagination, view/edit actions, and the new clear-filters control.

Gaps:

- None found in source.

Deviation:

- None.

### M4 — Calculation Engine
**Status:** ✅ Complete

Evidence:

- Recalculation routes exist in `apps/api/app/routers/recalculate.py`.
- Volumetry snapshot routes exist in `apps/api/app/routers/volumetry.py`.
- Snapshot model exists at `apps/api/app/models/snapshot.py:10`.
- Calc-engine parity remains green: `26 passed in 0.06s`.

Gaps:

- None found in source.

Deviation:

- Backend type-check cleanliness has drifted; `mypy` still reports service-level issues in recalculation-related code.

### M5 — Dashboard API
**Status:** ✅ Complete

Evidence:

- Dashboard routes exist in `apps/api/app/routers/dashboard.py` for snapshot list and detail.
- `apps/api/app/services/dashboard_service.py` builds `kpi_strip`, `coverage`, `completeness`, `pattern_mix`, `payload_distribution`, `risks`, and `maturity`.
- Dashboard schemas exist in `apps/api/app/schemas/dashboard.py`.
- A project dashboard page exists in `apps/web/app/projects/[projectId]/page.tsx`.

Gaps:

- No source-level gaps in the API.

Deviation:

- The current web dashboard page is a thinner KPI/QA summary view and does not render the full snapshot charts/risks payload produced by `dashboard_service.py`, so the frontend is lighter than the AGENTS milestone description even though the API layer is present.

### M6 — Justification Narratives
**Status:** ✅ Complete

Evidence:

- Narrative and approval routes are present in `apps/api/app/routers/justifications.py`.
- Deterministic narrative and prompt-template services exist in `apps/api/app/services/justification_service.py`.
- `JustificationRecord` exists in `apps/api/app/models/snapshot.py:35`.
- Prompt versioning support exists in `apps/api/app/models/governance.py:66` and related schema/router/service files.

Gaps:

- None found in source.

Deviation:

- None.

### M7 — Exports
**Status:** ✅ Complete

Evidence:

- Export routes for XLSX, PDF, JSON, template download, job status, and artifact download exist in `apps/api/app/routers/exports.py`.
- Export generation logic exists in `apps/api/app/services/export_service.py`, including `generate_capture_template`.
- Export response schema exists in `apps/api/app/schemas/export.py`.

Gaps:

- None found in source.

Deviation:

- Benchmark-structure validation for exported artifacts was not re-run in this audit pass.

### M8 — Admin + Governance
**Status:** ✅ Complete

Evidence:

- Pattern CRUD routes exist in `apps/api/app/routers/patterns.py` (`GET`, `POST`, `PATCH`, `DELETE`).
- Dictionary CRUD exists in `apps/api/app/routers/dictionaries.py`.
- Assumption versioning and defaulting exists in `apps/api/app/routers/assumptions.py` and `apps/api/app/services/reference_service.py`.
- Prompt template versioning exists in `apps/api/app/routers/justifications.py` and `apps/api/app/models/governance.py`.
- Admin pages exist in `apps/web/app/admin/page.tsx`, `apps/web/app/admin/patterns/page.tsx`, `apps/web/app/admin/dictionaries/page.tsx`, and `apps/web/app/admin/assumptions/page.tsx`.

Gaps:

- None found in source.

Deviation:

- Recalculation-after-governance-change behavior was not re-executed in this audit; current assessment relies on source coverage plus prior progress documentation.

### M9 — Integration Capture Wizard
**Status:** ✅ Complete

Evidence:

- Manual create, systems autocomplete, duplicate check, and live estimate routes exist in `apps/api/app/routers/catalog.py`.
- Capture wizard page exists in `apps/web/app/projects/[projectId]/capture/new/page.tsx`.
- Wizard and step components exist in `apps/web/components/capture-wizard.tsx`, `capture-step-identity.tsx`, `capture-step-source.tsx`, `capture-step-destination.tsx`, and `capture-step-technical.tsx`.
- Supporting UX exists in `apps/web/components/oic-estimate-preview.tsx` and `apps/web/components/system-autocomplete.tsx`.

Gaps:

- None found in source.

Deviation:

- None.

### M10 — System Dependency Map
**Status:** ✅ Complete

Evidence:

- Graph route exists at `GET /api/v1/catalog/{project_id}/graph` in `apps/api/app/routers/catalog.py`.
- Graph service exists in `apps/api/app/services/graph_service.py`.
- Graph schema exists in `apps/api/app/schemas/graph.py`.
- Frontend surfaces exist in `apps/web/app/projects/[projectId]/graph/page.tsx`, `apps/web/components/graph-controls.tsx`, `apps/web/components/integration-graph.tsx`, and `apps/web/components/graph-detail-panel.tsx`.

Gaps:

- None found in source.

Deviation:

- None.

### M11 — Navigation + Theme
**Status:** ✅ Complete

Evidence:

- Breadcrumb component exists in `apps/web/components/breadcrumb.tsx` and is imported across project/admin pages.
- Theme persistence logic exists in `apps/web/lib/use-theme.ts` with the `oci-dis-theme` storage key.
- No-flash theme initialization exists in `apps/web/app/layout.tsx`.
- Shared theme tokens and dark-mode variables exist in `apps/web/app/globals.css`.

Gaps:

- None found in source.

Deviation:

- The repo-level strict ESLint gate still reports a `no-unused-vars` warning in `apps/web/lib/use-theme.ts`, but the theme feature itself is implemented.

### M12 — Source Lineage + Template
**Status:** ✅ Complete

Evidence:

- `column_names` is present in `apps/web/lib/types.ts` and `apps/api/app/schemas/catalog.py`.
- Lineage column-name generation exists in `apps/api/app/services/catalog_service.py`.
- Template download route exists in `apps/api/app/routers/exports.py`.
- Template generation exists in `apps/api/app/services/export_service.py`.
- Import-page download action exists in `apps/web/components/import-upload.tsx`.

Gaps:

- None found in source.

Deviation:

- None.

### M13 — Integration Design Canvas
**Status:** ✅ Complete

Evidence:

- `apps/web/components/integration-canvas.tsx` exists and is wired into `apps/web/components/integration-patch-form.tsx`.
- The canvas is rendered from the integration detail page path `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx`.

Gaps:

- None found in source.

Deviation:

- None.

### M14 — Map Pan + Visual Improvements
**Status:** ✅ Complete

Evidence:

- Graph mode controls exist in `apps/web/components/graph-controls.tsx`.
- Interactive pan/zoom rendering exists in `apps/web/components/integration-graph.tsx`.
- Graph page state wiring exists in `apps/web/app/projects/[projectId]/graph/page.tsx`.
- `apps/web/app/globals.css` includes animated edge styling via `@keyframes flow` and `.graph-edge-animated`.

Gaps:

- None found in source.

Deviation:

- The strict ESLint gate reports warnings in `apps/web/components/graph-controls.tsx` and `apps/web/components/integration-graph.tsx`, but the feature implementation is present.

### Browser QA — Bug Fixes + UX Enhancements
**Status:** ⚠ Partial

Evidence:

- Browser remediation changes are documented in `docs/progress.md:44`.
- Recent implementation commit exists: `0362e17 fix: browser test findings — dark mode inputs, scroll bug, theme persistence, UX enhancements`.
- Relevant source updates are present in `apps/web/app/globals.css`, `apps/web/lib/use-theme.ts`, `apps/web/components/system-autocomplete.tsx`, `apps/web/components/catalog-table.tsx`, `apps/web/components/import-upload.tsx`, `apps/web/components/projects-page-client.tsx`, and `apps/web/components/capture-wizard.tsx`.

Gaps:

- The strict frontend lint gate fails: `apps/web/components/system-autocomplete.tsx` now triggers `react/no-unescaped-entities`, and the repo still has 17 warnings under `--max-warnings 0`.

Deviation:

- Functionally, the UX fixes are present; operationally, the milestone is not fully clean under the stricter audit lint gate.

---

## Verification Results

### Stack / Shape Detection

```text
bash -lc 'shopt -s nullglob; ls pyproject.toml setup.py requirements*.txt apps/api/requirements*.txt 2>/dev/null; echo "---"; ls package.json apps/web/package.json tsconfig.json 2>/dev/null; echo "---"; ls docker-compose.yml docker-compose.yaml Dockerfile 2>/dev/null; echo "---"; ls -d apps/api/migrations apps/api/alembic.ini alembic.ini 2>/dev/null; echo "---"; ls -d packages/*/src/tests tests __tests__ cypress playwright 2>/dev/null; echo "---"; ls .github/workflows/*.yml .gitlab-ci.yml Jenkinsfile 2>/dev/null'
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

### Backend Verification

```text
./.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -40
..........................                                               [100%]
26 passed in 0.06s

./.venv/bin/python -m ruff check . 2>&1 | tail -20
All checks passed!

./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary 2>&1 | tail -10
apps/api/app/services/recalc_service.py:126: error: Argument after ** must be a mapping, not "object"  [arg-type]
apps/api/app/services/recalc_service.py:127: error: Argument after ** must be a mapping, not "object"  [arg-type]
apps/api/app/services/recalc_service.py:128: error: Argument after ** must be a mapping, not "object"  [arg-type]
apps/api/app/services/recalc_service.py:129: error: Argument after ** must be a mapping, not "object"  [arg-type]
apps/api/app/services/import_service.py:268: error: Value of type "object" is not indexable  [index]
apps/api/app/services/import_service.py:269: error: Value of type "object" is not indexable  [index]
apps/api/app/services/import_service.py:281: error: Argument "normalization_events" to "_build_catalog_integration" has incompatible type "list[object]"; expected "list[dict[str, object]]"  [arg-type]
apps/api/app/services/import_service.py:305: error: Incompatible types in assignment (expression has type "object", variable has type "SQLCoreOperations[dict[Any, Any] | None] | dict[Any, Any] | None")  [assignment]
apps/api/app/services/export_service.py:185: error: Argument 1 to "ExportJobResponse" has incompatible type "**dict[str, object]"; expected "str"  [arg-type]
apps/api/app/services/export_service.py:185: error: Argument 1 to "ExportJobResponse" has incompatible type "**dict[str, object]"; expected "datetime"  [arg-type]
```

### Frontend Verification

```text
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -30; cd ../..
[no output]

cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0 2>&1 | tail -20; cd ../..
  16:46  warning  'value' is defined but never used. Allowed unused args must match /^_/u  no-unused-vars
  18:23  warning  'mode' is defined but never used. Allowed unused args must match /^_/u   no-unused-vars
  20:18  warning  'mode' is defined but never used. Allowed unused args must match /^_/u   no-unused-vars

/Users/javierchan/.codex/worktrees/b840/oci/OCI DIS Blueprint/apps/web/components/integration-graph.tsx
  17:17  warning  'node' is defined but never used. Allowed unused args must match /^_/u     no-unused-vars
  18:17  warning  'edge' is defined but never used. Allowed unused args must match /^_/u     no-unused-vars
  24:5   warning  'updater' is defined but never used. Allowed unused args must match /^_/u  no-unused-vars
  26:11  warning  'current' is defined but never used. Allowed unused args must match /^_/u  no-unused-vars

/Users/javierchan/.codex/worktrees/b840/oci/OCI DIS Blueprint/apps/web/components/system-autocomplete.tsx
  13:14  warning  'value' is defined but never used. Allowed unused args must match /^_/u  no-unused-vars
  98:37  error    `"` can be escaped with `&quot;`, `&ldquo;`, `&#34;`, `&rdquo;`          react/no-unescaped-entities
  98:45  error    `"` can be escaped with `&quot;`, `&ldquo;`, `&#34;`, `&rdquo;`          react/no-unescaped-entities

/Users/javierchan/.codex/worktrees/b840/oci/OCI DIS Blueprint/apps/web/lib/use-theme.ts
  11:14  warning  'theme' is defined but never used. Allowed unused args must match /^_/u  no-unused-vars

✖ 20 problems (3 errors, 17 warnings)
```

### Docker / Live Environment

```text
docker compose ps 2>&1
NAME                       IMAGE                    COMMAND                  SERVICE   CREATED        STATUS                  PORTS
ocidisblueprint-api-1      ocidisblueprint-api      "uvicorn app.main:ap…"   api       5 hours ago    Up 5 hours (healthy)    0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
ocidisblueprint-db-1       postgres:16-alpine       "docker-entrypoint.s…"   db        19 hours ago   Up 19 hours (healthy)   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp
ocidisblueprint-minio-1    minio/minio:latest       "/usr/bin/docker-ent…"   minio     19 hours ago   Up 19 hours (healthy)   0.0.0.0:9000-9001->9000-9001/tcp, [::]:9000-9001->9000-9001/tcp
ocidisblueprint-redis-1    redis:7-alpine           "docker-entrypoint.s…"   redis     19 hours ago   Up 19 hours (healthy)   0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp
ocidisblueprint-web-1      ocidisblueprint-web      "docker-entrypoint.s…"   web       5 hours ago    Up 5 hours              0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp
ocidisblueprint-worker-1   ocidisblueprint-worker   "celery -A app.worke…"   worker    19 hours ago   Up 19 hours             8000/tcp

docker compose ps --format json 2>/dev/null | python3 -c ...
zsh rerun note: initial inline Python parse failed under zsh quoting.
bash rerun result: docker compose ps --format json produced no output

curl -sf http://localhost:8000/health 2>/dev/null && echo "API: UP" || echo "API: DOWN"
{"status":"ok","version":"1.0.0"}API: UP

curl -sf http://localhost:8000/openapi.json 2>/dev/null | python3 -c ...
Registered endpoints: 46 paths, 64 operations

docker compose exec -T db psql -U postgres -d dis_blueprint -c "SELECT schemaname, tablename, n_live_tup AS rows FROM pg_stat_user_tables ORDER BY tablename;" 2>&1 | head -30
psql: error: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed: FATAL:  role "postgres" does not exist
```

### Dependency Drift

```text
./.venv/bin/pip list --outdated 2>/dev/null | head -20
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

cd apps/web && npm outdated --depth=0 2>/dev/null | head -20; cd ../..
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

---

## Pending Tasks

### CRITICAL

- `apps/web/components/system-autocomplete.tsx`, `apps/web/components/graph-controls.tsx`, `apps/web/components/integration-graph.tsx`, `apps/web/lib/use-theme.ts` — Browser QA / M11 / M14: the strict frontend lint gate fails with `3 errors` and `17 warnings`, blocking a zero-warning release-quality audit.

### INCOMPLETE

- `apps/api/app/services/recalc_service.py`, `apps/api/app/services/import_service.py`, `apps/api/app/services/export_service.py` — M2 / M4 / M7: backend `mypy` still reports 10 type errors, so the type-check gate is not clean.
- `apps/web/app/projects/[projectId]/page.tsx` — M5: the current dashboard UI does not expose the full chart/risk snapshot payload that the backend dashboard service already produces.
- `docker compose exec -T db psql -U postgres -d dis_blueprint ...` — environment verification: the documented audit DB probe is not reproducible in the running local stack because the `postgres` role is unavailable.

### DEFERRED

- `.venv` Python dependencies and `apps/web/package.json` dependencies — dependency maintenance: numerous packages are outdated, but upgrades were not part of this audit and should be handled in a planned dependency-refresh pass.

---

## Debt Markers

```text
grep -r "TODO\|FIXME\|HACK\|PLACEHOLDER\|XXX\|NOCOMMIT" --include="*.py" --include="*.ts" --include="*.tsx" --exclude-dir=node_modules --exclude-dir=.venv -n . 2>/dev/null | grep -v "test_\|spec\." | head -30
./apps/api/app/routers/projects.py:62:    # TODO: partial update + audit
```

Observations:

- The explicit debt signal is small, but the stricter lint/type gates reveal quality debt beyond inline TODO markers.
- `docs/progress.md` currently contains milestone entries for M11, M12, M13, M14, Browser QA, and audit remediation; earlier milestones are tracked more heavily via `README.md` and git history than via progress-log continuity.

---

## Recommended Next Actions

1. Fix the frontend lint regressions in `apps/web/components/system-autocomplete.tsx` and the unused-parameter warnings in graph/theme components, then rerun `npx eslint . --ext .ts,.tsx --max-warnings 0`.
2. Triage and resolve the 10 backend `mypy` errors in `apps/api/app/services/recalc_service.py`, `apps/api/app/services/import_service.py`, and `apps/api/app/services/export_service.py`.
3. Decide whether M5 should stay “API-complete / UI-light” or whether `apps/web/app/projects/[projectId]/page.tsx` should render the full dashboard snapshot charts and risk data already generated by `dashboard_service.py`.
4. Document or fix the database credentials expected by the audit SQL probe so table-level verification can be reproduced from the checked-out repo without guesswork.
5. Plan a dependency-refresh pass once the branch is otherwise stable, prioritizing FastAPI, Pydantic, Next.js, TypeScript, and ESLint ecosystem packages.

---

## Dependency Drift

Python drift is significant across the backend toolchain (`fastapi`, `pydantic`, `alembic`, `pytest`, `celery`, `asyncpg`). Frontend drift is also broad, with the largest potential migration surfaces around `next`, `react`, `eslint`, `typescript`, `tailwindcss`, and `zod`. None of these should be upgraded as part of a milestone audit, but they should be scheduled and scoped because future lint/build/tooling friction is likely to increase if they continue to lag.

