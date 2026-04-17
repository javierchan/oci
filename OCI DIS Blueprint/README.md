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
- **Web:** Next.js 14 (TypeScript) — `apps/web/`
- **Database:** PostgreSQL 16
- **Jobs:** Celery + Redis
- **Storage:** MinIO (dev) / OCI Object Storage (prod)
- **Calc engine:** `packages/calc-engine/` (pure Python, no I/O)

All services run in **Docker Desktop on macOS** — no host dependencies.

---

## Quick Start

```bash
# 1. Clone and enter the project
cd "OCI DIS Blueprint"

# 2. Copy environment template
cp .env.example .env

# 3. Start the full stack
docker compose up --build

# 4. Apply database migrations (first time)
docker compose run --rm api alembic upgrade head

# 5. Seed reference data (patterns, dictionary, assumptions)
docker compose run --rm api python -m app.migrations.seed
```

**Access:**
- Web app: http://localhost:3000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (minio / minio123)

---

## Running Tests

```bash
# Calc engine parity tests (must pass before any milestone is done)
docker compose run --rm api pytest packages/calc-engine/src/tests -v

# API integration tests
docker compose run --rm api pytest app/tests -v

# Web type check
docker compose run --rm web npm run type-check

# Refresh the committed OpenAPI artifact
./.venv/bin/python apps/api/scripts/export_openapi.py

# Verify the committed OpenAPI artifact is in sync
./.venv/bin/python apps/api/scripts/export_openapi.py --check
```

---

## Project Structure

```
apps/api/          FastAPI backend
apps/web/          Next.js frontend
packages/
  calc-engine/     Deterministic volumetry + QA engine
  shared-schema/   TypeScript types
  ui/              React component library
  test-fixtures/   Benchmark data and parity expectations
infra/             Docker, CI, SQL migrations
docs/
  adr/             Architecture Decision Records
  architecture/    System diagrams
  api/             OpenAPI spec
AGENTS.md          Codex implementation guide
docker-compose.yml Local dev stack
.env.example       Environment template
```

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
- Reference seed data: `17` patterns, `1` default assumption set, `55` dictionary options, `11` service capability profiles
- Synthetic enterprise validation: deterministic governed project with `480` catalog rows, `72` distinct systems, full `#01`–`#17` pattern coverage, persisted snapshots, justifications, audit, and XLSX/JSON/PDF exports
- Calc-engine parity: `26 passed`
- Web and API stack: all six containers running and healthy in Docker Compose

Implementation and benchmark notes for milestones `M1` through `M8` are captured in [`docs/phase1-validation.md`](./docs/phase1-validation.md).

---

## Key References

- OIC Gen3 Service Limits: https://docs.oracle.com/en/cloud/paas/application-integration/oracle-integration-oci/service-limits.html
- OCI Pricing: https://www.oracle.com/cloud/price-list/
- Full PRD: `Catalogo_Integracion.xlsx` → `TLP - PRD`
