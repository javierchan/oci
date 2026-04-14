# System Architecture Overview

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Docker Desktop (macOS)                          │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │  Next.js Web │    │  FastAPI API │    │  Celery      │              │
│  │  :3000       │◄──►│  :8000       │◄──►│  Worker      │              │
│  │  apps/web/   │    │  apps/api/   │    │  (import +   │              │
│  └──────────────┘    └──────┬───────┘    │  recalc)     │              │
│                             │            └──────┬───────┘              │
│                    ┌────────┼────────┐          │                      │
│                    ▼        ▼        ▼          ▼                      │
│              ┌─────────┐ ┌──────┐ ┌─────────────────┐                 │
│              │Postgres │ │Redis │ │  MinIO (dev)    │                 │
│              │:5432    │ │:6379 │ │  OCI OS (prod)  │                 │
│              └─────────┘ └──────┘ └─────────────────┘                 │
│                                                                         │
│  packages/calc-engine/ ──────► called by API service + Celery worker   │
│  packages/shared-schema/ ────► TypeScript types shared web ↔ API shape │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow — Import

```
User uploads XLSX
       │
       ▼
POST /api/v1/imports/{project_id}
       │  (file → MinIO object storage)
       ▼
ImportBatch created (status=pending)
       │
       ▼
Celery: import_worker.process_import()
       │
       ├─► parse_rows() [calc-engine/importer.py]
       │     ├─ detect headers (row 5)
       │     ├─ apply TBQ=Y / exclude Duplicado 2 (PRD-017)
       │     ├─ normalize frequency, status (PRD-019)
       │     └─ emit NormalizationEvents per row
       │
       ├─► persist SourceIntegrationRow (immutable)
       ├─► persist CatalogIntegration (governed working copy)
       ├─► compute derived fields (executions_per_day, payload_per_hour_kb)
       ├─► compute QA status per row [calc-engine/qa.py]
       ├─► emit AuditEvent per normalization event
       └─► ImportBatch status=completed, loaded_count=144
```

## Data Flow — Recalculation

```
Trigger: pattern change, payload edit, assumption update
       │
       ▼
POST /api/v1/recalculate/{project_id}
       │
       ▼
Celery: recalc_worker.recalculate_project()
       │
       ├─► load CatalogIntegrations + current AssumptionSet
       ├─► call consolidate_project() [calc-engine/volumetry.py]
       │     ├─ per-row: OIC msgs, DI GB, Functions units, Streaming GB
       │     └─ consolidated: peak packs, total invocations, workspace active
       │
       ├─► persist VolumetrySnapshot (immutable, with assumption_set_version)
       ├─► emit AuditEvent(recalculation)
       └─► trigger DashboardSnapshot generation
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Calc engine is pure Python, no I/O | Deterministic and independently testable |
| `SourceIntegrationRow` is immutable | Full source lineage always traceable |
| `VolumetrySnapshot` is immutable | Reproducible dashboard comparisons |
| AuditEvent on every write | PRD-045 — full audit without joins |
| MinIO in dev, OCI Object Storage in prod | S3-compatible — endpoint swap only |
| Celery for import + recalc | Avoids API timeout on large files; async job polling |

## Service Limits (from workbook TPL - Supuestos)

| Service | Limit | Applied in |
|---------|-------|-----------|
| OIC Gen3 REST payload | 50 MB max | importer validation |
| OIC Gen3 FTP payload | 50 MB max | importer validation |
| OIC Kafka payload | 10 MB max | importer validation |
| OIC timeout | 300s | pattern recommendation logic |
| OIC billing threshold | 50 KB/message | volumetry.py |
| OIC pack size | 5,000 msgs/hour | volumetry.py |
