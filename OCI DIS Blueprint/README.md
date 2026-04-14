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
| M9 | Integration Capture Wizard | ⚠ Partial | — |
| M10 | System Dependency Map | ⚠ Partial | — |
| M11 | Navigation + Theme | ✅ Complete | 2026-04-14 |
| M12 | Source Lineage + Template | ✅ Complete | 2026-04-14 |
| M13 | Integration Design Canvas | ✅ Complete | 2026-04-14 |
| M14 | Map Pan + Visual Improvements | ⏳ Pending | — |

## Validation Snapshot

Phase 1 parity has been validated in Docker against the benchmark workbook rules:

- Import parity: `157` TBQ=`Y` rows, `13` excluded `Duplicado 2`, `144` loaded rows in source order
- Reference seed data: `17` patterns, `1` default assumption set, `40` dictionary options
- Calc-engine parity: `26 passed`
- Web and API stack: all six containers running and healthy in Docker Compose

Implementation and benchmark notes for milestones `M1` through `M8` are captured in [`docs/phase1-validation.md`](./docs/phase1-validation.md).

---

## Key References

- OIC Gen3 Service Limits: https://docs.oracle.com/en/cloud/paas/application-integration/oracle-integration-oci/service-limits.html
- OCI Pricing: https://www.oracle.com/cloud/price-list/
- Full PRD: `Catalogo_Integracion.xlsx` → `TLP - PRD`
