# AGENTS.md — OCI DIS Blueprint
> Read this file in full before touching any code.
> This file is the primary contract between the engineering team and OpenAI Codex (or any AI agent working on this repo).

---

## What this product is

**OCI DIS Blueprint** is an API-first web application that replaces the `Catalogo_Integracion.xlsx` workbook.
It enables architects and analysts to import, govern, calculate volumetry, and export OCI integration catalogs aligned with Oracle Integration Cloud (OIC Gen3) patterns.

The workbook is the **source of truth for behavior**. Phase 1 requires exact parity with the workbook — no redesign, no new features — before any productization.

Full requirements are in `TLP - PRD` tab of `Catalogo_Integracion.xlsx` (PRD-001 through PRD-066).

---

## Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Web app | Next.js 14 + TypeScript | `apps/web/` |
| API | FastAPI (Python 3.12) | `apps/api/` |
| Database | PostgreSQL 16 | via Docker |
| Job queue | Celery + Redis | import and recalc jobs |
| Object storage | MinIO (dev) / OCI Object Storage (prod) | files + exports |
| Calc engine | Pure Python (no DB, no HTTP) | `packages/calc-engine/` |
| Shared types | TypeScript (web ↔ API contract) | `packages/shared-schema/` |

**All services run in Docker Desktop on macOS.** No host-level dependencies.
Spin up everything with `docker compose up --build`.

---

## Repo layout

```
apps/
  api/                  FastAPI server
    app/
      main.py           Entry point — router mounting + lifespan
      core/config.py    Settings from env vars
      models/           SQLAlchemy models (project, snapshot, governance)
      routers/          One file per route group (/projects, /imports, /catalog …)
      services/         Business logic (called by routers)
      workers/          Celery tasks (import_worker, recalc_worker)
      migrations/       Alembic migrations
    Dockerfile
    requirements.txt
  web/                  Next.js app
    src/app/            App Router pages (dashboard, catalog, imports …)
    src/components/     Shared UI components
    src/lib/            API client, utils
    Dockerfile
    package.json

packages/
  calc-engine/          Pure Python — deterministic volumetry engine
    src/engine/
      volumetry.py      All OIC/DI/Functions/Streaming calculations
      qa.py             Row-level QA logic
      importer.py       XLSX/CSV parser + inclusion rules
    src/tests/          Pytest parity tests — MUST pass before milestone done
  shared-schema/        TypeScript types shared between web and expected API shape
  ui/                   Reusable React components
  test-fixtures/        Seed data, benchmark files, parity snapshots

infra/
  docker/               Dockerfiles for production
  ci/                   GitHub Actions workflows
  migrations/           SQL init scripts

docs/
  adr/                  Architecture Decision Records
  architecture/         System diagrams and design docs
  api/                  OpenAPI spec (openapi.yaml)

AGENTS.md               ← you are here
README.md               Human-readable setup guide
docker-compose.yml      Local dev stack
.env.example            Template — copy to .env, never commit .env
.gitignore              Excludes *.xlsx, .env, node_modules, __pycache__
```

---

## Milestones (implement in order — PRD-049)

Each milestone ends with **passing tests and a written diff**. Never skip ahead.

### M1 — Schema + Migrations
- [x] Define all SQLAlchemy models (already scaffolded in `app/models/`)
- [x] Write Alembic migrations for all tables
- [x] Seed `PatternDefinition` (17 patterns from workbook `TPL - Patrones`)
- [x] Seed `DictionaryOption` (frequency, trigger types, tools from `TPL - Diccionario`)
- [x] Seed `AssumptionSet` v1 (from `TPL - Supuestos`)
- [x] **Exit criteria**: `docker compose run api alembic upgrade head` succeeds; seed data queryable via API

### M2 — Import Engine
- [x] Implement `app/services/import_service.py` using `packages/calc-engine/src/engine/importer.py`
- [x] Wire `POST /api/v1/imports/{project_id}` to Celery worker
- [x] Persist `ImportBatch`, `SourceIntegrationRow`, and `CatalogIntegration` (from included rows)
- [x] Apply frequency normalization + audit events per row
- [x] **Exit criteria**: `test_importer.py` passes; benchmark: 157 TBQ=Y rows → 13 excluded → 144 loaded in order

### M3 — Catalog Grid API
- [x] Implement `GET /api/v1/catalog/{project_id}` with pagination, filter, search
- [x] Implement `PATCH /api/v1/catalog/{project_id}/{id}` for architect fields + audit
- [x] Implement `POST /api/v1/catalog/{project_id}/bulk-patch`
- [x] Implement `GET /api/v1/catalog/{project_id}/{id}/lineage`
- [x] Compute QA status using `packages/calc-engine/src/engine/qa.py`
- [x] **Exit criteria**: API returns 144 rows with correct QA status; lineage traces to source row

### M4 — Calculation Engine
- [x] Implement Celery recalculation task calling `packages/calc-engine/src/engine/volumetry.py`
- [x] Persist `VolumetrySnapshot` with row-level and consolidated results
- [x] Wire `POST /api/v1/recalculate/{project_id}`
- [x] Compute derived fields `executions_per_day` and `payload_per_hour_kb` on every catalog write
- [x] **Exit criteria**: `test_volumetry.py` passes; OIC msgs, DI workspace, Functions units match workbook output

### M5 — Dashboard API
- [x] Implement `GET /api/v1/dashboard/{project_id}/snapshots/{id}`
- [x] Default mode: technical only — no cost data (PRD-036)
- [x] KPI strip: OIC msgs/month, peak packs/hr, DI active, DI GB, Functions GB-s
- [x] Chart data: coverage, completeness, pattern mix, payload distribution, risks
- [x] **Exit criteria**: Dashboard values match workbook `TPL - Dashboard` for benchmark project

### M6 — Justification Narratives
- [x] Implement deterministic narrative assembly (no AI in phase 1)
- [x] Wire approve/override endpoints
- [x] **Exit criteria**: Methodology blocks render; approve emits AuditEvent

### M7 — Exports
- [x] XLSX export (catalog + volumetry)
- [x] JSON snapshot export
- [x] PDF dashboard export (phase 1 basic)
- [x] **Exit criteria**: Exported XLSX matches benchmark workbook row count and column structure

### M8 — Admin + Governance
- [x] Dictionary CRUD (admin role only)
- [x] Assumption set versioning
- [x] Prompt versioning (for M6 narrative templates)
- [x] **Exit criteria**: Admin can update frequency map; recalculation picks up new values

### M9 — Integration Capture Wizard
- [x] Add the guided five-step capture flow for manual catalog entry
- [x] Validate required source, destination, and technical fields before submit
- [x] Support duplicate checks, review, and submission into the governed catalog flow
- [x] **Exit criteria**: architects can create a new integration through the wizard without bypassing catalog governance

### M10 — System Dependency Map
- [x] Add the project graph view for source-to-destination system topology
- [x] Render node and edge metadata from the catalog graph payload
- [x] Support detail drill-through from graph selections into catalog context
- [x] **Exit criteria**: the dependency map loads project topology correctly and supports investigation workflows

### M11 — Navigation + Theme
- [x] Add persistent navigation context with reusable breadcrumbs across project and admin surfaces
- [x] Implement light, dark, and system themes with no-flash initialization and durable storage
- [x] Apply semantic theme tokens to shared UI surfaces, badges, and tables
- [x] **Exit criteria**: theme selection persists across navigation and shared surfaces stay readable in both modes

### M12 — Source Lineage + Template
- [x] Expose human-readable source-lineage labels and import batch context on integration detail pages
- [x] Add the downloadable workbook template for offline capture with governed headers and validations
- [x] Improve import UX so users can retrieve the template directly from the import workflow
- [x] **Exit criteria**: integration detail shows readable lineage and import users can download the governed template

### M13 — Integration Design Canvas
- [x] Add the interactive integration design surface for source, tools, and destination flow modeling
- [x] Surface tool selection and route context directly in the integration-detail workflow
- [x] Show immediate technical context such as payload and OIC estimate hints without waiting for a full save cycle
- [x] **Exit criteria**: architects can design and review the intended integration route from the detail page

### M14 — Map Pan + Visual Improvements
- [x] Improve graph navigation with pan, zoom, and keyboard shortcuts
- [x] Add richer graph labeling, hover states, legend context, and visual emphasis for analysis
- [x] Preserve reachability and usability of the graph route under the improved interaction model
- [x] **Exit criteria**: the map is navigable and visually readable for real project analysis

### M15 — UX Overhaul P0: Core Workflow Fixes
- [x] Integration Design Canvas rebuilt as SVG flow diagram with draggable nodes,
      connectable edges (with arrowheads), pan, and zoom
- [x] Multiple instances of same tool type allowed (instance-based node model)
- [x] Catalog table paginated at 20 rows/page with Prev/Next and rows-per-page selector
- [x] Invalid project ID renders graceful not-found page (no Next.js dev error overlay)
- [x] **Exit criteria**: Canvas renders a working flow; catalog paginates; 404 shows
      a user-friendly message; all 5 quality gates green

### M16 — UX Overhaul P1: Data Accuracy + Surface Completeness
- [x] Interface Name shows descriptive name from source workbook (not Interface ID)
- [x] QA Reasons rendered as human-readable cards with title + actionable hint
- [x] Dashboard renders pattern mix, payload distribution, risks, and maturity
      from the full backend payload (not just KPI strip)
- [x] Graph auto-fits all nodes on load with no nodes cut off below viewport
- [x] Graph edges have directional arrowheads (source → destination)
- [x] "View in Catalog" from graph node panel pre-filters catalog by system name
- [x] **Exit criteria**: No integration detail shows ID as name; dashboard uses
      full backend payload; graph fits viewport; all quality gates green

### M17 — UX Overhaul P2: Layout + Polish
- [x] Architect Patch Save button visible without scrolling (sticky panel or top placement)
- [x] Audit Trail entries show field names instead of array index notation
- [x] Capture wizard step pills numbered (1–5) with progress line and completed state
- [x] Import page required columns list shows all columns without truncation
- [x] Projects list has text filter and archived-projects toggle
- [x] Graph has "filter by system" dropdown to highlight a system and its neighbors
- [x] Admin hub shows "Last modified" date per governance category
- [x] **Exit criteria**: All checklist items visually confirmed; no regressions;
      all quality gates green

### M18 — Workbook Import Fidelity: Header Semantics + Source Traceability
- [x] Resolve source columns by workbook header name first, not fallback position,
      for both `Catálogo de Integraciones` and `TPL - Catálogo`
- [x] Map workbook headers such as `Interfaz` → `interface_name` and
      `Alcance Inicial` → `initial_scope` even when the source header row starts
      at row 5 with leading blank columns
- [x] Preserve real workbook header labels in lineage and raw-column rendering so
      named fields do not degrade into `Column N` unless the workbook header is blank
- [x] Align import normalization with the workbook operating rules documented in
      `TPL - Prompts`: preserve source order, include `Duplicado 1`, exclude only
      `Duplicado 2`, and retain `TBD`, uncertainty, and payload `0`
- [x] Normalize split destination technologies and trigger capture semantics
      conservatively from workbook evidence without inventing missing values
- [x] **Exit criteria**: ADN workbook imports with descriptive Interface Name and
      Initial Scope, raw column tables show workbook headers, and importer tests
      cover workbook alias/header policy cases

### M19 — Governed Reference Data 2.0: Patterns, Frequencies, and Tool Taxonomy
- [x] Seed all 17 patterns with full workbook metadata: description/tagline,
      OCI components, when-to-use, anti-pattern, technical flow, and business value
- [x] Expand the frequency dictionary to workbook codes `FQ01`–`FQ16` with exact
      executions/day semantics and alias normalization
- [x] Correct `Tiempo Real` semantics to the workbook proxy (`24` exec/day) where
      the workbook explicitly models it as batch-equivalent rather than per-minute
- [x] Expand the tool dictionary with tool IDs, direct/proxy volumetric flags,
      descriptions, and the allowed Architectural Overlay (`AO`) catalog
- [x] Expose enriched pattern, frequency, and tool metadata through API and admin
      surfaces without breaking existing governance CRUD
- [x] **Exit criteria**: reference endpoints return workbook-grade metadata, admin
      can review/edit it, and calc + UI helpers consume the same governed frequency rules

### M20 — Canvas Intelligence: Standard Combinations + Overlay Governance
- [x] Seed workbook combinations `G01`–`G18` with supported flow, compatible
      patterns, activated metrics, recommended overlays, and usage guidance
- [x] Separate volumetric core tools (`AN`) from architectural overlays (`AO`) in
      the saved canvas semantics and patch payloads
- [x] Teach the canvas to suggest compatible combinations and pattern candidates
      based on the tools actually placed in the flow
- [x] Validate that the designed pipeline connects source to destination while
      preventing unsupported shortcut edges from acting as the effective design
- [x] Reflect real pipeline composition in the processing summary and future
      volumetry hints instead of implying fixed OIC-only processing
- [x] **Exit criteria**: the canvas can explain supported tool stacks, recommend
      matching patterns/groups, and persist core tools vs overlays distinctly

### M21 — Volumetry Assumption Parity: Service Limits + Unit Governance
- [x] Compare `AssumptionSet v1.0.0` against `TPL - Supuestos` and add the missing
      technical service constraints for OIC, Streaming, Queue, Functions,
      Data Integration, and Data Integrator proxy usage
- [x] Align OIC billing rules with workbook guidance for inbound triggers,
      scheduling, thresholding, and BYOL vs non-BYOL pack sizes
- [x] Enforce explicit KB/MB normalization so workbook values captured in MB cannot
      silently distort KB-based formulas or previews
- [x] Centralize remaining hardcoded technical limits across calc, dashboard,
      export, and preview paths behind versioned assumptions
- [x] Preserve pricing and service references as governed assumption metadata
      without forcing the default dashboard into commercial mode
- [x] **Exit criteria**: assumptions are workbook-complete, technical previews use
      shared governed limits, and unit handling is explicit and test-covered

### M22 — QA Coverage + Confidence Signals
- [x] Decouple QA activation from formal ID presence so every active source row is
      evaluated even when the formal integration ID is blank
- [x] Align trigger vocabulary and QA checks with workbook capture semantics such
      as `Scheduled`, `REST Trigger`, `SOAP Trigger`, and `Event Trigger`
- [x] Add completeness indicators for payload, pattern, ID, trigger, and fan-out
      coverage so QA and dashboard surfaces communicate confidence, not just status
- [x] Add low-confidence forecast messaging when billing is extrapolated from sparse
      payload coverage or other weak source inputs
- [x] Preserve workbook uncertainty instead of overwriting it merely to turn QA green
- [x] **Exit criteria**: QA no longer hides active rows behind missing formal IDs,
      and forecast surfaces clearly communicate uncertainty when coverage is weak

### M23 — Pattern Coverage 03–17: End-to-End Operationalization
- [x] Decide and document whether patterns `#03`–`#17` are fully supported in phase
      parity or explicitly out of scope beyond reference-library status
- [x] For every supported pattern, implement sizing inputs, QA hints, narrative
      branches, dashboard grouping, and export behavior
- [x] Ensure unsupported patterns are clearly marked in UI/admin instead of acting
      like generic placeholders with misleading confidence
- [x] Use workbook anti-pattern guidance to improve QA hints and pattern selection support
- [x] **Exit criteria**: supported patterns have end-to-end app behavior, and any
      unsupported patterns are explicitly documented and surfaced as such

### M24 — Admin Synthetic Lab: Governed Test Project Generation
- [x] Add a reusable synthetic-generation service layer in `apps/api/app/services/`
      that can build deterministic enterprise-scale datasets without placing any
      orchestration logic inside `packages/calc-engine/`
- [x] Create an executable script at
      `apps/api/scripts/seed_synthetic_enterprise_project.py` that uses the real
      project/import/catalog/recalc/dashboard/justification/export flows to seed
      one governed synthetic project from the current codebase state
- [x] Generate a large, realistic synthetic enterprise project with governed
      metadata and validation targets:
      approximately 72 distinct systems, at least 480 catalog integrations,
      a mixed import/manual capture profile, excluded import rows for traceability,
      full use of patterns, core tools, overlays, canvas state, architect
      rationale, retries, comments, justifications, snapshots, audit, and exports
- [x] Ensure imported synthetic rows traverse the real workbook parser path:
      create a workbook with supported headers, persist `ImportBatch` and
      `SourceIntegrationRow`, preserve inclusion/exclusion evidence, and only then
      materialize `CatalogIntegration`
- [x] Ensure manual synthetic rows traverse the governed capture path:
      use the manual catalog service, preserve lineage, and then apply follow-up
      architect patches only through supported service-layer mutations
- [x] Validate synthetic scale and truthfulness deterministically:
      `catalog_count >= 480`, `distinct_systems >= 70`, and all 17 pattern IDs
      covered in the final governed catalog
- [x] Persist and validate downstream artifacts from supported product routes:
      at least one volumetry snapshot, at least one dashboard snapshot,
      persisted justifications, and generated XLSX/JSON/PDF exports
- [x] Write machine-readable and human-readable run reports under
      `apps/api/generated-reports/` summarizing the created project, counts,
      pattern/tool coverage, snapshot IDs, export artifacts, and smoke-test URLs
- [x] Document the productization path for the future Admin Synthetic Lab without
      implementing the full admin module yet. The design doc must cover:
      reusable service extraction, persisted `SyntheticGenerationJob`, Alembic
      migration expectations, admin-only router, service-layer authorization,
      Celery execution, governed presets and inputs, synthetic project metadata,
      UI placement under `apps/web/app/admin/`, API/type updates, labeling,
      validation rules, testing strategy, and operational runbooks
- [x] Preserve the current architecture contract:
      thin routers, service-owned business logic, async DB access in the API,
      calc-engine purity, auditable writes, and conservative no-reset data handling
- [x] **Exit criteria**: the repo contains the documented `M24` plan, the
      synthetic generation service and script run successfully against the real
      stack, one final synthetic project is queryable through the supported API/UI
      routes, generated reports exist on disk, focused backend validation and
      smoke tests pass, and all required quality gates are green

---

## Coding rules

### General
- **TypeScript strict mode** everywhere in `apps/web/` and `packages/shared-schema/`
- **Python type hints** on every function signature in `apps/api/` and `packages/calc-engine/`
- No `any` in TypeScript. No untyped function args in Python.
- Every new file must have a module docstring explaining its purpose.

### FastAPI conventions
- Routers in `app/routers/` — one file per route group, thin (delegate to `app/services/`)
- Services in `app/services/` — all business logic, DB access, worker dispatch
- Models in `app/models/` — SQLAlchemy only, no Pydantic here
- Schemas in `app/schemas/` — Pydantic request/response DTOs, never raw dicts in endpoints
- Every mutating endpoint emits an `AuditEvent` via `app/services/audit_service.py`
- Never put calculation logic in routers or services — call `packages/calc-engine/`

### Calc engine rules (critical)
- `packages/calc-engine/` is **pure Python** — no SQLAlchemy, no HTTP, no Celery imports
- Every public function returns a `CalcResult` (value, unit, formula, inputs, reason)
- No global mutable state — pass `Assumptions` explicitly
- Round only at output boundary, never mid-calculation
- Every new formula needs a test in `src/tests/`

### Database
- All migrations via Alembic — no manual schema changes
- Use `async` SQLAlchemy sessions everywhere in the API
- Never expose raw SQL in routers — use service + repository pattern
- `SourceIntegrationRow.raw_data` is immutable after insert — never UPDATE it

### Audit trail
- Every write (insert, update, delete) on `CatalogIntegration`, `JustificationRecord`,
  `AssumptionSet`, `DictionaryOption`, `PatternDefinition` must emit an `AuditEvent`
- `AuditEvent` must include: actor_id, event_type, entity_type, entity_id, old_value, new_value
- Use correlation IDs for multi-step operations (import batch, recalculation job)

### Testing
- API tests: `pytest` with `httpx.AsyncClient` against a test DB (separate from dev DB)
- Calc engine tests: `pytest` — pure, no DB, no HTTP
- Parity tests must reproduce workbook benchmark numbers exactly
- Never mark a test as `xfail` to make a milestone pass — fix the code

---

## Environment and Docker

All commands run inside Docker containers — no local Python or Node required on macOS host.

```bash
# First time setup
cp .env.example .env
docker compose up --build

# Run API tests
docker compose run --rm api pytest packages/calc-engine/src/tests -v

# Apply migrations
docker compose run --rm api alembic upgrade head

# Seed reference data
docker compose run --rm api python -m app.migrations.seed

# Open API docs
open http://localhost:8000/docs

# Open web app
open http://localhost:3000

# MinIO console (object storage)
open http://localhost:9001  # user: minio / pass: minio123
```

---

## API contract

OpenAPI 3.1 spec lives at `docs/api/openapi.yaml` and is served at `http://localhost:8000/openapi.json`.

Route groups (PRD-043):
```
/api/v1/projects
/api/v1/imports
/api/v1/catalog
/api/v1/patterns
/api/v1/dictionaries
/api/v1/assumptions
/api/v1/recalculate
/api/v1/volumetry
/api/v1/dashboard
/api/v1/justifications
/api/v1/audit
/api/v1/exports
```

---

## Definition of done (PRD-050)

A milestone is **not done** until:
1. All parity tests pass (`pytest -v`)
2. API smoke tests pass (key endpoints return correct shape)
3. No TypeScript errors (`tsc --noEmit`)
4. No linting errors (`ruff check app/`)
5. A written summary of changes (diff) is produced
6. Benchmark comparison to workbook outputs is documented

---

## RBAC roles (PRD-005 to PRD-008)

| Role | Permissions |
|------|------------|
| Admin | Full access: dictionaries, assumptions, prompts, audit, exports |
| Architect | Edit: pattern, rationale, comments, retry, core tools, overlays, overlays; approve justifications |
| Analyst | Import, bulk edit, filter, compare, resolve mapping issues |
| Viewer | Read-only: dashboard, exports |

Enforce at the service layer using project-scoped authorization. Never trust role claims from the request body.

---

## What is out of scope for Phase 1 (PRD-055)

- Contract quote generation
- Live source-system connectors
- AI-generated narratives (optional layer — must not replace deterministic text)
- Commercial pricing dashboard (cost data stays isolated)
- Portfolio analytics
