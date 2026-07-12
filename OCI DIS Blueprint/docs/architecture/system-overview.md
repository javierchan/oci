# System Architecture Overview

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Docker Desktop (macOS)                          │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │  Next.js Web │    │  FastAPI API │    │  Celery      │              │
│  │  :3000       │◄──►│  :8000       │◄──►│  Worker      │              │
│  │  apps/web/   │    │  apps/api/   │    │  async jobs  │              │
│  └──────────────┘    └──────┬───────┘    │  + beat      │              │
│                             │            └──────┬───────┘              │
│                    ┌────────┼────────┐          │                      │
│                    ▼        ▼        ▼          ▼                      │
│              ┌─────────┐ ┌──────┐ ┌─────────────────┐                 │
│              │Postgres │ │Redis │ │  MinIO (dev)    │                 │
│              │:5432    │ │:6379 │ │  OCI OS (prod)  │                 │
│              └─────────┘ └──────┘ └─────────────────┘                 │
│                                                                         │
│  packages/calc-engine/ ──────► called by API service + Celery worker   │
│  agent-worker ─► OCI Responses-first + governed tools + Guardrails     │
│  apps/web/lib/types.ts ──────► typed projections of Pydantic API shape │
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
       ├─► load CatalogIntegrations + client AssumptionSet
       ├─► assemble immutable ServiceRuleBundle from normalized product tables
       ├─► call consolidate_project() [calc-engine/volumetry.py]
       │     ├─ per-row: OIC msgs, DI GB, Functions units, Streaming GB
       │     └─ consolidated: peak packs, total invocations, workspace active
       │
       ├─► persist VolumetrySnapshot (assumption version + service-rule provenance)
       ├─► emit AuditEvent(recalculation)
       └─► trigger DashboardSnapshot generation
```

## Data Flow — Service Product Verification

```
Admin starts verification
       │
       ▼
POST /api/v1/service-products/verification-jobs
       │
       ├─► ServiceVerificationJob created (status=pending)
       └─► Celery: service_verification_worker.execute_service_verification_job_task()
              │
              ├─► fetch allowlisted official evidence sources
              ├─► update evidence freshness and content hashes
              ├─► create reviewable findings for conservative limit/deprecation signals
              ├─► emit AuditEvent for job lifecycle and accepted finding changes
              └─► job status=completed/failed
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Calc engine is pure Python, no I/O | Deterministic and independently testable |
| `SourceIntegrationRow` is immutable | Full source lineage always traceable |
| `VolumetrySnapshot` is immutable | Reproducible dashboard comparisons |
| AuditEvent on every write | PRD-045 — full audit without joins |
| MinIO in dev, OCI Object Storage in prod | S3-compatible — endpoint swap only |
| Celery for long-running jobs | Avoids API timeout on imports, recalculation, AI review, synthetic generation, and service verification |
| Dedicated Docker agent queue | Isolates OCI Function Calling from deterministic background workloads |
| Service Product Library uses canonical `/service-products` APIs | Retires raw service-profile endpoints from the public production contract |
| Normalized service limits are authoritative | Re-seeding never overwrites reviewed limits; Assumptions contain client inputs only |
| One repository-root CI workflow | Prevents drift between non-executed copies and the effective GitHub contract |

## Runtime Rule Ownership

| Data | Authoritative owner | Consumers |
|------|---------------------|-----------|
| Oracle limits | `service_limits` | calc input assembly, canvas, exports |
| Service relationships | `service_interoperability_rules` | canvas and AI Review |
| Evidence freshness | evidence sources + verification jobs/findings | dashboard and AI Review |
| Client workload unknowns | `assumption_sets` | deterministic calc defaults |

The calc engine remains pure: the API service assembles the immutable runtime
object before invoking formulas. Historical snapshots without rule provenance
remain readable and are labeled as not recorded.
