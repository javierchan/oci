# OCI DIS Blueprint

**API-first web application for OCI integration design assessment.**

Replaces `Catalogo_Integracion.xlsx` with a governed platform enabling architects and analysts to:
- Import integration inventories (XLSX/CSV)
- Govern catalog metadata with full audit trail
- Calculate volumetry (OIC, Data Integration, Functions, Streaming)
- Generate deterministic technical dashboards and justification narratives
- Export results for delivery teams and clients

**Source of truth for behavior:** `Catalogo_Integracion.xlsx` → tab `TLP - PRD`
**Agent instructions (Codex):** [`AGENTS.md`](./AGENTS.md)

---

## Stack

- **API:** FastAPI (Python 3.12) — `apps/api/`
- **Web:** Next.js 15 (TypeScript, Node.js 26.0.0) — `apps/web/`
- **Database:** PostgreSQL 16
- **Jobs:** Celery + Redis
- **Storage:** MinIO (local runtime) / OCI Object Storage (deployed runtime)
- **Calc engine:** `packages/calc-engine/` (pure Python, no I/O)
- **Service rules:** normalized Service Product tables; Assumptions contain client workload inputs only

All services run in **production mode** on Docker Desktop — no host Python or
Node.js dependencies and no source-code bind mounts.

---

## Quick Start

```bash
# 1. Clone and enter the project
cd "OCI DIS Blueprint"

# 2. Copy environment template
cp .env.example .env

# 3. Build and start the production stack
docker compose up -d --build --wait

# 4. Apply database migrations (first time)
docker compose exec -T api alembic upgrade head

# 5. Seed reference data (patterns, dictionary, assumptions)
docker compose exec -T api python -m app.migrations.seed
```

**Access:**
- Web app: http://localhost:3000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (minio / minio123)

## Codex Backend for AI Review

AI Review uses the Codex backend configuration mounted into the API and worker
containers. LLM credentials must not be provided through `.env`; the deprecated
`OCA_API_KEY` path is ignored by the application.

```bash
CODEX_HOME="$HOME/.codex" \
  docker compose -f docker-compose.yml -f docker-compose.codex.yml \
  up -d --build --wait
```

The override mounts `${CODEX_HOME}/config.toml` and `${CODEX_HOME}/auth.json`
read-only under `/codex-host`. The production entrypoint copies them to a private
runtime directory and immediately drops API and worker execution to `app:10001`.

---

## Running Tests

```bash
# API integration tests with ephemeral export storage
docker run --rm \
  --tmpfs /app/uploads:rw,uid=10001,gid=10001,mode=0770 \
  ocidisblueprint-api:latest \
  python -m pytest -p no:cacheprovider app/tests -q

# Pure calc-engine parity tests
docker run --rm -w /calc-engine ocidisblueprint-api:latest \
  python -m pytest -p no:cacheprovider src/tests -q

# Web tests and static checks, using non-runtime Docker build targets
docker build --target test --output type=cacheonly -f apps/web/Dockerfile .
docker build --target lint --output type=cacheonly -f apps/web/Dockerfile .

# Verify the OpenAPI artifact packaged in the production image
docker run --rm ocidisblueprint-api:latest \
  python scripts/export_openapi.py --check

# Production build and dependency audit
docker build --target production -t ocidisblueprint-web:latest \
  -f apps/web/Dockerfile .
docker run --rm -v "$PWD":/workspace -w /workspace node:26.0.0-alpine \
  npm audit --audit-level=high
```

## Schema-Dependent Admin Smoke Check

When the Admin Synthetic Lab schema, router, worker, or UI changes, run this
against the live production-mode stack before calling the feature validated:

```bash
# Ensure the running API container has the latest DB schema.
docker compose exec -T api alembic upgrade head

# Confirm API health.
curl -sf http://localhost:8000/health

# Confirm the synthetic admin endpoints are readable with admin headers.
curl -sf \
  -H 'X-Actor-Id: web-admin' \
  -H 'X-Actor-Role: Admin' \
  http://localhost:8000/api/v1/admin/synthetic/presets

curl -sf \
  -H 'X-Actor-Id: web-admin' \
  -H 'X-Actor-Role: Admin' \
  'http://localhost:8000/api/v1/admin/synthetic/jobs?limit=20'
```

Then reload `http://localhost:3000/admin/synthetic` and confirm the page shows
the preset form or empty-state jobs table, not `Failed to fetch`.

If the synthetic worker flow or cleanup policy changed, prefer the automated
bounded smoke script:

```bash
./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_lab.py
```

This validates health, preset discovery, job creation, polling, recent-job
visibility, and the `cleaned_up` terminal contract for the
`ephemeral-smoke` preset.

To validate explicit cleanup on a retained small project instead of the
ephemeral auto-clean path:

```bash
./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_lab.py --preset-code retained-smoke
```

That retained run must reach `completed`, invoke the cleanup route, and finish
as `cleaned_up` in the same script execution.

Manual fallback:

```bash
curl -sf \
  -X POST \
  -H 'X-Actor-Id: web-admin' \
  -H 'X-Actor-Role: Admin' \
  -H 'Content-Type: application/json' \
  http://localhost:8000/api/v1/admin/synthetic/jobs \
  -d '{"preset_code":"ephemeral-smoke"}'
```

The created job should terminate as `cleaned_up` with
`cleanup_policy = ephemeral_auto_cleanup`, `project_id = null`, and populated
`cleanup_removed_paths`.

To validate retry end to end on a controlled failed job without inventing a
new product preset:

```bash
./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_retry.py
```

That helper seeds a bounded failed source job through the service layer, calls
the real retry API, waits for the retried job to finish, and then cleans up the
seeded failed source job.

To validate the admin synthetic pages through a repo-owned browser E2E path:

```bash
cd apps/web
npm run test:e2e:install
npm run test:e2e
```

The Playwright suite covers the Synthetic Lab landing page, terminal cleanup
for `ephemeral-smoke`, terminal completion plus explicit cleanup for
`retained-smoke`, and dashboard, catalog preview tabs, integration canvas,
topology, Service Products, and Assumptions.

---

## Project Structure

```
apps/api/          FastAPI backend
apps/web/          Next.js frontend
packages/
  calc-engine/     Deterministic volumetry + QA engine
  test-fixtures/   Benchmark data and parity expectations
infra/             SQL/bootstrap infrastructure
docs/
  adr/             Architecture Decision Records
  architecture/    System diagrams
  api/             OpenAPI spec
  reports/         Current status plus dated audit evidence
  prompts/         Historical execution prompts; not active contracts
AGENTS.md          Codex implementation guide
docker-compose.yml Local dev stack
.env.example       Environment template
```

The only effective CI definition is the repository-root workflow at
`.github/workflows/oci-dis-blueprint-quality.yml`. It runs API and calc tests,
Ruff, mypy, migrations, OpenAPI drift, frontend types/lint/tests/build, npm
audit, browser E2E, and production image scans.

---

## Milestones

See [`AGENTS.md`](./AGENTS.md#milestones-implement-in-order--prd-049) for the full ordered build plan.

| Milestone | Description | Status | Completed |
|-----------|-------------|--------|-----------|
| M1 | Schema + Migrations | ✅ Complete | 2026-04-13 |
| M2 | Import Engine | ✅ Complete | 2026-04-13 |
| M3 | Catalog Grid API | ✅ Complete | 2026-04-13 |
| M4 | Calculation Engine | ✅ Complete | 2026-04-13 |
| M5 | Dashboard API | ✅ Complete | 2026-04-13 |
| M6 | Justification Narratives | ✅ Complete | 2026-04-13 |
| M7 | Exports | ✅ Complete | 2026-04-13 |
| M8 | Admin + Governance | ✅ Complete | 2026-04-14 |
| M9 | Integration Capture Wizard | ✅ Complete | 2026-04-14 |
| M10 | System Dependency Map | ✅ Complete | 2026-04-14 |
| M11 | Navigation + Theme | ✅ Complete | 2026-04-14 |
| M12 | Source Lineage + Template | ✅ Complete | 2026-04-14 |
| M13 | Integration Design Canvas | ✅ Complete | 2026-04-14 |
| M14 | Map Pan + Visual Improvements | ✅ Complete | 2026-04-14 |
| M15 | UX Overhaul P0 — Canvas + Pagination + Error Handling | ✅ Complete | 2026-04-15 |
| M16 | UX Overhaul P1 — Data Accuracy + Surface Completeness | ✅ Complete | 2026-04-15 |
| M17 | UX Overhaul P2 — Layout + Polish | ✅ Complete | 2026-04-15 |
| M18 | Workbook Import Fidelity — Header Semantics + Source Traceability | ✅ Complete | 2026-04-15 |
| M19 | Governed Reference Data 2.0 — Patterns + Frequencies + Tool Taxonomy | ✅ Complete | 2026-04-15 |
| M20 | Canvas Intelligence — Standard Combinations + Overlay Governance | ✅ Complete | 2026-04-15 |
| M21 | Volumetry Assumption Parity — Service Limits + Unit Governance | ✅ Complete | 2026-04-15 |
| M22 | QA Coverage + Confidence Signals | ✅ Complete | 2026-04-16 |
| M23 | Pattern Coverage 03–17 — End-to-End Operationalization | ✅ Complete | 2026-04-16 |
| M24 | Admin Synthetic Lab — Governed Test Project Generation | ✅ Complete | 2026-04-16 |
| Browser QA | Bug fixes + UX enhancements from live browser test | ✅ Complete | 2026-04-14 |

## Validation Snapshot

Phase 1 parity has been validated in Docker against the benchmark workbook rules:

- Import parity: `157` TBQ=`Y` rows, `13` excluded `Duplicado 2`, `144` loaded rows in source order
- Reference seed data: `17` patterns, client-only assumption sets, governed dictionaries, and `18` normalized service products
- Synthetic enterprise validation: deterministic governed project with `480` catalog rows, `72` distinct systems, full `#01`–`#17` pattern coverage, persisted snapshots, justifications, audit, and XLSX/JSON/PDF exports
- Backend + calc-engine: `113 passed` (`42` calc-engine tests)
- Frontend: `19 passed`, strict TypeScript, ESLint, and production build green
- Browser E2E: `3 passed`, including terminal job state and cleanup validation
- Dependency audit: `0` vulnerabilities
- Web and API stack: all seven services running and healthy in Docker Compose

The current validated state is recorded in
[`docs/reports/status-report.md`](./docs/reports/status-report.md). Historical
implementation prompts and dated reports are retained only as traceability
evidence; `AGENTS.md`, `README.md`, the root workflow, and current architecture
documents define the active operational contract.

---

## Key References

- OIC Gen3 Service Limits: https://docs.oracle.com/en/cloud/paas/application-integration/oracle-integration-oci/service-limits.html
- OCI Pricing: https://www.oracle.com/cloud/price-list/
- Full PRD: `Catalogo_Integracion.xlsx` → `TLP - PRD`
