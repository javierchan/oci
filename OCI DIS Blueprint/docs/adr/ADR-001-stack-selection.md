# ADR-001: Technology Stack Selection

**Status:** Accepted
**Date:** 2026-04-13
**Deciders:** Architecture team
**PRD Reference:** PRD-047, PRD-048

---

## Context

The `Catalogo_Integracion.xlsx` workbook manages OCI integration design for enterprise clients.
It must be replaced by a governed web application with API parity. The stack must support:
deterministic calculations, full audit trail, RBAC, file import/export, async jobs, and
Docker Desktop deployment on macOS (no host dependencies).

## Decision

Adopt the following monorepo stack:

| Component | Decision | Rationale |
|-----------|----------|-----------|
| API | FastAPI (Python 3.12) | Native async, OpenAPI 3.1 auto-generation, strong typing via Pydantic, Python aligns with calc engine |
| Web | Next.js 14 (TypeScript) | App Router for clean server/client separation, strong ecosystem, type-safe API client generation |
| Database | PostgreSQL 16 | ACID guarantees for audit trail, JSONB for raw payloads and snapshots, mature async driver (asyncpg) |
| Job queue | Celery + Redis | Battle-tested for import and recalculation jobs; Redis doubles as result backend |
| Object storage | MinIO (dev) / OCI Object Storage (prod) | S3-compatible API — swap endpoint, same code |
| Calc engine | Pure Python package | Isolation from I/O; enables independent testing; callable from both API and CLI |
| Containerization | Docker Compose | Full stack runs in Docker Desktop on macOS; zero host-level dependencies |

## Options Considered

### Option A: Next.js + FastAPI + PostgreSQL (Selected)
**Pros:** Strong typing end-to-end; Python calc engine reuse; async everywhere; excellent OpenAPI tooling
**Cons:** Two runtimes (Node + Python); slightly more complex Docker setup

### Option B: Next.js + Node.js API (TypeScript monolith)
**Pros:** Single language; simpler CI
**Cons:** Python calc engine would require rewrite or subprocess bridge; weaker ecosystem for scientific calculations

### Option C: Django REST Framework
**Pros:** Batteries-included, ORM, admin panel
**Cons:** Synchronous by default (requires ASGI workaround); slower OpenAPI ergonomics; heavier for API-first approach

## Consequences

- Calculation logic in `packages/calc-engine/` can be tested independently of the API
- TypeScript types in `packages/shared-schema/` must be kept in sync with Pydantic schemas — enforce via CI
- Alembic manages all schema migrations — no ad-hoc SQL allowed
- MinIO → OCI Object Storage swap is configuration-only (S3 endpoint + credentials)
- Team needs Python and TypeScript proficiency; document patterns clearly in AGENTS.md

## Action Items

- [x] Scaffold monorepo structure
- [x] Create Dockerfiles for API and Web
- [x] Create docker-compose.yml with all services
- [ ] Generate OpenAPI spec and TypeScript client from it
- [ ] Set up Alembic migration baseline
