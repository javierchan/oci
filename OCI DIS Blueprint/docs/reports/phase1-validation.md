# Phase 1 Validation

This note captures the validated implementation state for milestones `M1` through `M8`.

## Milestone Summary

### M1 — Schema + Migrations

- Alembic is configured in `apps/api/` and the initial schema migration is applied.
- Seed data is available for patterns, dictionary options, assumptions, and prompt templates.
- Validation:
  - `patterns = 17`
  - `assumptions = 1`
  - `dictionary_options = 40`

### M2 — Import Engine

- XLSX imports persist immutable source rows and governed catalog rows.
- Workbook parity rules are enforced:
  - source tab `Catálogo de Integraciones`
  - headers at row `5`
  - data starts at row `6`
  - keep only `TBQ = Y`
  - exclude `Estado = Duplicado 2`
  - preserve source order
- Benchmark result:
  - `157` TBQ source rows
  - `13` excluded rows
  - `144` loaded rows

### M3 — Catalog Grid API

- Catalog listing, filters, detail, lineage, row patching, and bulk patch are implemented.
- QA is recomputed on mutation and catalog writes emit audit events.
- Benchmark result:
  - `144` catalog rows returned in source order
  - initial QA state `REVISAR` across the benchmark import

### M4 — Calculation Engine Integration

- Full-project recalculation persists immutable `VolumetrySnapshot` records.
- Consolidated OIC, Data Integration, Functions, Queue, and Streaming metrics are exposed by API.
- Recalculation emits project audit events and creates row-level volumetry results.

### M5 — Dashboard API

- Technical dashboard snapshots are generated from volumetry snapshots.
- Dashboard list/detail endpoints are live.
- Missing dashboard snapshots are backfilled for older volumetry snapshots.

### M6 — Justification Narratives

- Deterministic justification narratives are assembled from catalog and lineage data.
- Approval and override flows persist `JustificationRecord` rows and emit audit events.
- Prompt template versions are governed and the default template drives live narrative assembly.

### M7 — Exports

- Synchronous exports are available for:
  - XLSX
  - JSON snapshot bundle
  - basic PDF dashboard export
- Export jobs are retrievable and artifacts are downloadable through the API.
- Benchmark result:
  - exported XLSX includes `144` catalog rows and `144` volumetry rows

### M8 — Admin + Governance

- Admin-only mutation endpoints are available for dictionary options and assumption sets.
- Prompt template version governance is available under `/api/v1/justifications/templates`.
- Recalculation now reads governed `FREQUENCY` options at runtime.
- Validation result:
  - changing `Una vez al día` from `1.0` to `2.0` caused recalculated `executions_per_day` to update from `1.0` to `2.0`

## Validation Commands

The following checks were used repeatedly during milestone completion:

```bash
docker compose exec api python3 -m ruff check /app/app/
docker compose exec api python3 -m pytest /calc-engine/src/tests/ -v
docker compose exec web npx tsc --noEmit
docker compose exec api alembic upgrade head
docker compose exec api python -m app.migrations.seed
```

## Current Benchmark Snapshot

- Docker stack: `api`, `web`, `db`, `redis`, `worker`, and `minio` are running
- Calc engine parity: `26 passed`
- Import parity: `144 loaded / 13 excluded / 157 TBQ=Y`
- Dashboard benchmark basis:
  - `total_integrations = 144`
  - `with_formal_id = 11`
  - `without_formal_id = 133`
  - `qa_ok = 0`
  - `qa_revisar = 144`
  - `pattern_assigned = 144`
  - `payload_informed = 142`

## Residual Notes

- The current worktree is on a detached `HEAD`.
- Dev runtime artifacts under `apps/api/uploads/` are intentionally gitignored and may be cleaned separately when desired.
