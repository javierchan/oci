## M11 — Navigation + Color System + Light/Dark Theme

**Completed:** 2026-04-14
**Status:** ✅ Complete

### What was implemented

- `apps/web/components/breadcrumb.tsx` — reusable breadcrumb navigation for project and admin pages
- `apps/web/lib/use-theme.ts` and `apps/web/components/theme-toggle.tsx` — persistent light, dark, and system theme switching
- `apps/web/app/layout.tsx` and `apps/web/app/globals.css` — no-flash theme initialization and semantic color tokens for shared surfaces, badges, and tables
- `apps/web/components/qa-badge.tsx`, `apps/web/components/pattern-badge.tsx`, and `apps/web/components/complexity-badge.tsx` — semantic badge styling driven by the color token system
- Breadcrumbs added across projects, dashboard, import, catalog, detail, capture, graph, and admin routes
- Contextual actions added on the integration detail page and catalog row actions updated to support direct view and edit navigation
- Admin governance pages, forms, and integration detail lineage cards updated to use theme-aware surfaces and contrast-safe table styling

### Verification results

```text
TypeScript: 0 errors
ruff: All checks passed!
pytest: 26 passed, 2 warnings
docker compose ps: 6/6 containers Up
Page reachability:
200 /projects
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d/import
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d/catalog
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d/catalog/48728494-d042-4124-a272-eb9bc47b2dce
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d/capture
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d/capture/new
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d/graph
200 /admin
200 /admin/patterns
200 /admin/dictionaries
200 /admin/assumptions
```

### Gaps / known limitations

None

---

## M15 — UX Overhaul P0: Core Workflow Fixes (2026-04-15)

**Status:** ✅ Complete

- Canvas rebuilt as an SVG flow diagram with draggable tool nodes, connectable directed edges, pan, zoom, edge labels, and keyboard delete support
- Catalog paginated at 20 rows per page with Prev and Next controls plus a rows-per-page selector
- Invalid project IDs now render a graceful project not-found page instead of the Next.js error overlay

## M16 — UX Overhaul P1: Data Accuracy + Surface Completeness (2026-04-15)

**Status:** ✅ Complete

- Interface Name now resolves from the correct workbook header match instead of falling through to the Interface ID column
- QA Reasons now render as human-readable guidance cards with a title and actionable hint
- Dashboard now renders pattern mix, payload distribution, risks, and maturity from the full backend payload
- Graph auto-fits on load and renders directed arrowheads for flow direction
- "View in Catalog" from the graph node panel now pre-filters by system

## M17 — UX Overhaul P2: Layout + Polish (2026-04-15)

**Status:** ✅ Complete

- Architect Patch is sticky and keeps Save and Remove actions visible at the top of the panel
- Audit Trail now shows field names instead of raw numeric array indexes for source-row changes
- Capture wizard step pills are numbered and render progress/completed states
- Import page now shows the full required-columns list without truncation
- Projects list now supports text filtering and an archived-projects toggle
- Graph now supports filtering by system to highlight a node and its neighbors
- Admin hub now shows a last-modified date for each governance category

---

## Audit Follow-up — Recalculation Endpoint Cleanup

**Completed:** 2026-04-15
**Status:** ✅ Complete

### What was implemented

- Verified the 2026-04-15 audit report against the current `codex/codex-active-work` branch and confirmed that the catalog, import, governance, dashboard, justification, export, and audit routers were already restored in this worktree
- `apps/api/app/routers/recalculate.py` — replaced the remaining placeholder scoped/job endpoints with real snapshot-backed responses
- `apps/api/app/services/recalc_service.py` — added scoped recalculation validation plus persisted job-status serialization sourced from `VolumetrySnapshot`
- `apps/api/app/schemas/volumetry.py` — added explicit request/response schemas for scoped recalculation and job polling

### Verification results

```text
ruff: All checks passed!
mypy: 0 errors
TypeScript: 0 errors
ESLint: 0 warnings / 0 errors
pytest: 26 passed
docker compose ps: 6/6 containers Up
API health: {"status":"ok","version":"1.0.0"}
Scoped recalculation smoke:
- POST /api/v1/recalculate/{project_id}/scoped -> completed
- GET /api/v1/recalculate/{project_id}/jobs/{job_id} -> completed
- snapshot_id returned from both endpoints and matched the persisted job ID
```

### Gaps / known limitations

- The 2026-04-15 audit report was generated from `main` and is stale relative to this branch; remaining follow-up should use a fresh audit run before planning larger remediation work

---

## Quality Gates — ESLint + mypy Clean (2026-04-14)

**Status:** ✅ Complete

- Fixed `react/no-unescaped-entities` in `system-autocomplete.tsx`
- Prefixed unused callback params with `_` across `graph-controls.tsx`,
  `integration-graph.tsx`, `use-theme.ts`, `system-autocomplete.tsx`
- Fixed 10 mypy errors in `recalc_service.py`, `import_service.py`,
  `export_service.py` using `cast(dict[str, Any], ...)` at ORM return sites
- All five quality gates now green: pytest, ruff, mypy, tsc, eslint

---

## Browser Test Remediation — Bug Fixes + UX Enhancements

**Completed:** 2026-04-14
**Status:** ✅ Complete

### What was fixed

**Bugs:**
- BUG-01: Dark mode form inputs — added CSS baseline for input/select/textarea in `globals.css`
- BUG-02: Dashboard QA cards dark mode — replaced hardcoded colors with CSS variable tokens
- BUG-03: Phantom scroll on detail page — fixed two-column layout with `items-start`
- BUG-04: Theme not persisted across navigation — fixed `useTheme` hook initialization and storage key consistency
- BUG-05: Autocomplete silent empty state — added a “will be created as new” hint and loading indicator

**Enhancements:**
- ENH-01: Projects list duplicate names — added `#id` suffixes for duplicate project names
- ENH-02: Graph trivial topology — added an info banner when nodes are below meaningful map size
- ENH-03: OIC Estimate activation hint — replaced “—” guidance with a clearer prompt when frequency or payload are missing
- ENH-04: Admin hub global scope warning — added an amber warning banner for global governance impact
- ENH-05: Import history filename — now shows uploaded workbook filenames with the batch UUID on hover
- ENH-06: Catalog clear filters button — added a one-click reset action when any filter is active
- ENH-07: Capture wizard sessionStorage — persists form state and restores the current step, with an unload warning guard

### Verification results

```text
TypeScript: 0 errors
ruff: All checks passed!
pytest: 26 passed
docker compose: 6/6 containers Up
```

### Gaps / known limitations

None

---

## Remediation — Audit Cleanup

**Completed:** 2026-04-14
**Status:** ✅ Complete

### What was fixed

- Committed 17 modified and 4 untracked milestone files for M8, M9, and M10 into reproducible git history
- Moved the worktree off detached HEAD onto the `main` branch
- Removed 3 unused imports in `packages/calc-engine/` to clear Ruff `F401` findings
- Added `apps/web/.eslintrc.json` so the ESLint quality gate runs successfully
- Installed `mypy` in `.venv` and added it to `apps/api/requirements.txt`
- Updated `README.md` so M8, M9, and M10 are marked `✅ Complete`

### Verification results

```text
pytest:  26 passed
ruff:    All checks passed!
tsc:     0 errors
ESLint:  running (17 warnings, <=50 limit)
Docker:  6/6 containers Up
git:     working tree clean
```

### Gaps / known limitations

- ESLint warnings still remain and should be triaged before tightening `--max-warnings` to `0`
- Benchmark DB parity (144 rows) is not yet demonstrated in the live database; the current first project still reports 13 catalog rows
- mypy errors are not yet triaged; this remediation only confirms that the tool is installed and runnable

---

## M14 — Map Pan + Visual Improvements

**Completed:** 2026-04-14
**Status:** ✅ Complete

### What was implemented

- `apps/web/components/graph-controls.tsx` — added select/pan mode toggle with `V` and `H` shortcut support, alongside the existing filter, color, zoom, and export controls
- `apps/web/components/integration-graph.tsx` — added viewport-based pan and cursor-centered zoom, animated flow edges, hover dim/highlight behavior, node tooltip, edge hover label, legend, and richer node labeling with integration and brand counts
- `apps/web/app/projects/[projectId]/graph/page.tsx` — introduced shared viewport/mode state, keyboard shortcuts, theme-aware KPI cards, and graph reset wiring

### Verification results

```text
TypeScript: 0 errors
ruff: All checks passed!
pytest: 26 passed, 2 warnings
docker compose ps: 6/6 containers Up
Graph route reachability: OK
```

### Gaps / known limitations

None

---

## M13 — Integration Design Canvas

**Completed:** 2026-04-14
**Status:** ✅ Complete

### What was implemented

- `apps/web/components/integration-canvas.tsx` — reactive architecture-flow canvas that renders source, selected OCI tool nodes, and destination in canonical left-to-right order
- `apps/web/components/integration-patch-form.tsx` — canvas integration directly below the core-tools selector so unsaved pattern and tool changes update the design preview immediately
- Client-side execution and billing estimates added to the canvas annotation strip to show payload, OIC billing messages, and destination context without requiring a save round-trip

### Verification results

```text
TypeScript: 0 errors
Detail route reachability: OK
docker compose ps: 6/6 containers Up
```

### Gaps / known limitations

None

---

## M12 — Source Lineage + Template

**Completed:** 2026-04-14
**Status:** ✅ Complete

### What was implemented

- `apps/api/app/schemas/catalog.py` and `apps/api/app/services/catalog_service.py` — lineage responses now include `column_names` and `import_batch_date`, with canonical field labels derived from the stored import header map
- `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx` — source lineage now renders human-readable field names, hides empty columns by default, and exposes a `Show all columns` toggle
- `apps/api/app/routers/exports.py` and `apps/api/app/services/export_service.py` — added `GET /api/v1/exports/template/xlsx` to generate the offline capture workbook with instructions, styled headers, example row, validations, and frozen panes
- `apps/web/components/import-upload.tsx` — added the download action for the capture template directly on the import screen
- `apps/web/lib/types.ts` — updated frontend lineage contracts for the new API shape

### Verification results

```text
TypeScript: 0 errors
ruff: All checks passed!
pytest: 26 passed, 2 warnings
docker compose ps: 6/6 containers Up
Lineage smoke:
- column_names present: True
- import_batch_date present: True
Template smoke:
- bytes returned: 6314
- header row starts with: ['#', 'ID de Interfaz', 'Marca', 'Proceso de Negocio', 'Interfaz']
- example row TBQ: Y
- freeze panes: A6
Template import smoke:
- import status: completed
- loaded count: 1
- excluded count: 0
```

### Gaps / known limitations

None

---

## Post-Audit Remediation — Project Patch, API Tests, and OpenAPI Traceability

**Completed:** 2026-04-15
**Status:** ✅ Complete

### What was implemented

- `apps/api/app/schemas/project.py`, `apps/api/app/services/project_service.py`, and `apps/api/app/routers/projects.py` — replaced the stubbed project patch route with a typed, service-backed implementation that emits `project_updated` audit events
- `apps/api/app/tests/` — added the backend API integration test harness with isolated async SQLite fixtures and route-level coverage for project patch/audit, manual catalog capture/lineage, and the capture-template export endpoint
- `.github/workflows/api-validation.yml` — added a reproducible backend validation gate that runs Ruff, mypy, the API integration suite, calc-engine parity tests, and the OpenAPI sync check
- `apps/api/scripts/export_openapi.py` and `docs/api/openapi.yaml` — restored the source-controlled OpenAPI artifact and added a `--check` mode for drift detection
- `README.md` — documented the refresh and verification commands for the committed OpenAPI artifact

### Verification results

```text
ruff: All checks passed!
mypy: 0 errors
API integration tests: 3 passed
calc-engine parity: 26 passed
TypeScript: 0 errors
OpenAPI sync: up to date
Workflow sanity:
- name: API Validation
- job: backend-quality
```

### Gaps / known limitations

- The export-template API test triggers `openpyxl` deprecation warnings from library internals, but endpoint behavior remains correct.

---

## Deferred Follow-up — Export Warning Cleanup + Live Benchmark Dashboard

**Completed:** 2026-04-15
**Status:** ✅ Complete

### What was implemented

- `apps/api/app/tests/test_exports_api.py` — added targeted `pytest` warning filters for the known upstream `openpyxl` `datetime.utcnow()` deprecation warnings emitted during XLSX export generation
- Revalidated the export-template integration test so the backend API test suite runs cleanly without library-internal warning noise
- Refreshed the live benchmark project `Parity Test` (`a51bb83a-110b-4226-94f0-d2f590e3cd1d`) through `POST /api/v1/recalculate/{project_id}`
- Confirmed the recalculation created a new volumetry snapshot and a new technical dashboard snapshot, so future audits can use a live benchmark project with dashboard evidence instead of relying only on contract checks

### Verification results

```text
pytest apps/api/app/tests/test_exports_api.py -q -W default: 1 passed, 0 warnings
pytest apps/api/app/tests -q -W default: 3 passed
pytest packages/calc-engine/src/tests -q: 26 passed
ruff: All checks passed!
mypy: 0 errors
TypeScript: 0 errors
docker compose ps: 6/6 containers Up
API health: {"status":"ok","version":"1.0.0"}
Parity Test benchmark refresh:
- before_dashboard_total=8
- recalculation job completed
- volumetry_snapshot_id=28f46381-ccb7-4aef-a598-47ea4c7c21f1
- after_dashboard_total=9
- latest_dashboard_snapshot_id=47373044-a3e1-43e5-9d0d-b3a0ac6560d1
- dashboard_mode=technical
- kpi_oic_msgs_month=12960.0
```

### Gaps / known limitations

None

---

## Canvas, Graph, Theme, Column & Template UX Fix (2026-04-15)

**Status:** ✅ Complete

- ISSUE 1: Raw column values now show actual Excel header text; cells are inline-editable via PATCH with optimistic update and toast confirmation.
- ISSUE 2: Integration Design Canvas allows multiple instances of the same tool type (instance-based model); node labels are editable; edges support fan-out (1:N); edge labels and node payload notes added.
- ISSUE 3: Graph arrowhead markers resized to `markerWidth`/`markerHeight=6`; edge stroke-width baseline reduced; canvas pan/zoom interaction unblocked by fixing `pointer-events` on overlay elements.
- ISSUE 4: Theme active state driven exclusively by `theme` (user choice), not `resolvedTheme`; sidebar context label sources page name from route segment, never falls back to UUID.
- ISSUE 5: Import page now has a two-step layout with a prominent template download section; template includes sample row, Reference sheet, frozen headers, and column order aligned with importer.

### Verification results

```text
pytest: 29 passed
ruff: All checks passed!
mypy: 0 errors
TypeScript: 0 errors
ESLint: 0 warnings / 0 errors
docker compose ps: 6/6 containers Up
API health: {"status":"ok","version":"1.0.0"}
```

### Gaps / known limitations

None

---
