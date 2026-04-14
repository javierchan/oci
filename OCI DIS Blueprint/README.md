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

| # | Milestone | Status |
|---|-----------|--------|
| M1 | Schema + Migrations | 🔲 Pending |
| M2 | Import Engine | 🔲 Pending |
| M3 | Catalog Grid API | 🔲 Pending |
| M4 | Calculation Engine | 🔲 Pending |
| M5 | Dashboard API | 🔲 Pending |
| M6 | Justification Narratives | 🔲 Pending |
| M7 | Exports | 🔲 Pending |
| M8 | Admin + Governance | 🔲 Pending |

---

## Key References

- OIC Gen3 Service Limits: https://docs.oracle.com/en/cloud/paas/application-integration/oracle-integration-oci/service-limits.html
- OCI Pricing: https://www.oracle.com/cloud/price-list/
- Full PRD: `Catalogo_Integracion.xlsx` → `TLP - PRD`
