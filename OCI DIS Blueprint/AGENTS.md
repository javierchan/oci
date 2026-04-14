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
- [ ] Define all SQLAlchemy models (already scaffolded in `app/models/`)
- [ ] Write Alembic migrations for all tables
- [ ] Seed `PatternDefinition` (17 patterns from workbook `TPL - Patrones`)
- [ ] Seed `DictionaryOption` (frequency, trigger types, tools from `TPL - Diccionario`)
- [ ] Seed `AssumptionSet` v1 (from `TPL - Supuestos`)
- [ ] **Exit criteria**: `docker compose run api alembic upgrade head` succeeds; seed data queryable via API

### M2 — Import Engine
- [ ] Implement `app/services/import_service.py` using `packages/calc-engine/src/engine/importer.py`
- [ ] Wire `POST /api/v1/imports/{project_id}` to Celery worker
- [ ] Persist `ImportBatch`, `SourceIntegrationRow`, and `CatalogIntegration` (from included rows)
- [ ] Apply frequency normalization + audit events per row
- [ ] **Exit criteria**: `test_importer.py` passes; benchmark: 157 TBQ=Y rows → 13 excluded → 144 loaded in order

### M3 — Catalog Grid API
- [ ] Implement `GET /api/v1/catalog/{project_id}` with pagination, filter, search
- [ ] Implement `PATCH /api/v1/catalog/{project_id}/{id}` for architect fields + audit
- [ ] Implement `POST /api/v1/catalog/{project_id}/bulk-patch`
- [ ] Implement `GET /api/v1/catalog/{project_id}/{id}/lineage`
- [ ] Compute QA status using `packages/calc-engine/src/engine/qa.py`
- [ ] **Exit criteria**: API returns 144 rows with correct QA status; lineage traces to source row

### M4 — Calculation Engine
- [ ] Implement Celery recalculation task calling `packages/calc-engine/src/engine/volumetry.py`
- [ ] Persist `VolumetrySnapshot` with row-level and consolidated results
- [ ] Wire `POST /api/v1/recalculate/{project_id}`
- [ ] Compute derived fields `executions_per_day` and `payload_per_hour_kb` on every catalog write
- [ ] **Exit criteria**: `test_volumetry.py` passes; OIC msgs, DI workspace, Functions units match workbook output

### M5 — Dashboard API
- [ ] Implement `GET /api/v1/dashboard/{project_id}/snapshots/{id}`
- [ ] Default mode: technical only — no cost data (PRD-036)
- [ ] KPI strip: OIC msgs/month, peak packs/hr, DI active, DI GB, Functions GB-s
- [ ] Chart data: coverage, completeness, pattern mix, payload distribution, risks
- [ ] **Exit criteria**: Dashboard values match workbook `TPL - Dashboard` for benchmark project

### M6 — Justification Narratives
- [ ] Implement deterministic narrative assembly (no AI in phase 1)
- [ ] Wire approve/override endpoints
- [ ] **Exit criteria**: Methodology blocks render; approve emits AuditEvent

### M7 — Exports
- [ ] XLSX export (catalog + volumetry)
- [ ] JSON snapshot export
- [ ] PDF dashboard export (phase 1 basic)
- [ ] **Exit criteria**: Exported XLSX matches benchmark workbook row count and column structure

### M8 — Admin + Governance
- [ ] Dictionary CRUD (admin role only)
- [ ] Assumption set versioning
- [ ] Prompt versioning (for M6 narrative templates)
- [ ] **Exit criteria**: Admin can update frequency map; recalculation picks up new values

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
