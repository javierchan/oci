# Codex Task Prompt — OCI DIS Blueprint
> Paste the content of the **TASK** section below directly into the Codex prompt field.
> The **SETUP SCRIPT** section goes into the Codex environment setup (pre-task commands).
> Read both sections fully before starting.

---

## HOW TO USE THIS FILE IN CODEX

1. **Connect your repo** — point Codex at the `OCI DIS Blueprint` directory (GitHub repo or local mount).
2. **Paste the setup script** from `codex-setup.sh` into the Codex "Setup commands" / "Environment setup" field.
3. **Paste the TASK below** into the Codex prompt field.
4. **Set the working directory** to the repo root (`OCI DIS Blueprint/`).
5. Fire.

---

---

# TASK

## Context — Read First

You are implementing the **OCI DIS Blueprint** — an API-first web application that replaces an Oracle Integration Cloud design workbook (`Catalogo_Integracion.xlsx`). The full product requirements are already defined in 66 PRD items (PRD-001 through PRD-066) extracted from the workbook's `TLP - PRD` tab.

**Before writing a single line of code, read these files in full:**

1. `AGENTS.md` — your complete implementation contract: stack, repo layout, milestones, coding rules, RBAC, Docker commands, and definition of done.
2. `docs/architecture/system-overview.md` — data flow diagrams and key design decisions.
3. `docs/adr/ADR-001-stack-selection.md` and `ADR-002-calc-engine-isolation.md`
4. `packages/test-fixtures/benchmarks/parity-expectations.json` — benchmark numbers you must reproduce exactly.

The codebase is already scaffolded. Models, routers, and a running calc engine with 26 passing parity tests are in place. **Do not rearchitect. Do not rename. Do not change the folder structure.** Your job is to implement, not redesign.

---

## Your Mission

Implement **Milestones M1 through M4** of the OCI DIS Blueprint in a single continuous build pass. Each milestone has an explicit definition of done. You do not stop until all four milestones pass their tests.

You have unlimited compute. Run tests continuously as you build. Do not ask for confirmation between milestones — just proceed.

---

## Milestone M1 — Schema + Migrations

**Goal:** Every database table exists, is migrated, and is seeded with reference data.

### What to build

**1. Alembic setup**
- Initialize Alembic in `apps/api/` (`alembic init apps/api/migrations` if not already done)
- Configure `alembic.ini` and `migrations/env.py` to use `DATABASE_URL` from `app/core/config.py`
- Import all models from `app/models/` in `env.py` so Alembic detects them
- Generate an initial migration that creates all tables:
  - `projects`, `import_batches`, `source_integration_rows`, `catalog_integrations`
  - `volumetry_snapshots`, `dashboard_snapshots`, `justification_records`, `audit_events`
  - `pattern_definitions`, `dictionary_options`, `assumption_sets`

**2. Seed script — `apps/api/app/migrations/seed.py`**

Run as: `python -m app.migrations.seed`

Seed the following from the workbook data (values below are extracted and ready to use):

**`pattern_definitions` — 17 OCI Integration Patterns (from TPL - Patrones):**

| pattern_id | name | category |
|---|---|---|
| #01 | Request-Reply | SÍNCRONO |
| #02 | Scheduled Batch Transfer | ASÍNCRONO |
| #03 | Event-Driven Push | ASÍNCRONO |
| #04 | Polling Sync | ASÍNCRONO |
| #05 | Data Replication | ASÍNCRONO |
| #06 | Saga / Compensation | SÍNCRONO + ASÍNCRONO |
| #07 | Fanout Broadcast | ASÍNCRONO |
| #08 | Aggregation & Enrichment | SÍNCRONO |
| #09 | File Transfer (FTP/SFTP) | ASÍNCRONO |
| #10 | DB Integration (ORDS/JDBC) | SÍNCRONO |
| #11 | ERP Adapter Integration | ASÍNCRONO |
| #12 | Message Queue Relay | ASÍNCRONO |
| #13 | API-Led Connectivity | SÍNCRONO |
| #14 | Streaming Ingest | ASÍNCRONO |
| #15 | Hybrid Orchestration | SÍNCRONO + ASÍNCRONO |
| #16 | B2B/EDI Gateway | ASÍNCRONO |
| #17 | AI-Augmented Integration | ASÍNCRONO |

**`assumption_sets` — version 1.0.0 (from TPL - Supuestos):**
```json
{
  "oic_rest_max_payload_kb": 50000,
  "oic_ftp_max_payload_kb": 50000,
  "oic_kafka_max_payload_kb": 10000,
  "oic_timeout_s": 300,
  "oic_billing_threshold_kb": 50,
  "oic_pack_size_msgs_per_hour": 5000,
  "month_days": 30,
  "streaming_partition_throughput_mb_s": 1.0,
  "functions_default_duration_ms": 200,
  "functions_default_memory_mb": 256,
  "functions_default_concurrency": 1
}
```

**`dictionary_options` — Frequency category (from TPL - Diccionario):**

| code | value | executions_per_day |
|---|---|---|
| FREQ-01 | Una vez al día | 1.0 |
| FREQ-02 | 2 veces al día | 2.0 |
| FREQ-03 | 4 veces al día | 4.0 |
| FREQ-04 | Cada hora | 24.0 |
| FREQ-05 | Cada 30 minutos | 48.0 |
| FREQ-06 | Cada 15 minutos | 96.0 |
| FREQ-07 | Cada 5 minutos | 288.0 |
| FREQ-08 | Cada minuto | 1440.0 |
| FREQ-09 | Tiempo real | 1440.0 |
| FREQ-10 | Semanal | 0.142857 |
| FREQ-11 | Mensual | 0.033333 |
| FREQ-12 | Bajo demanda | 1.0 |
| FREQ-13 | TBD | null |

**`dictionary_options` — Trigger type category:**
`Scheduled`, `REST`, `Event`, `FTP/SFTP`, `DB Polling`, `JMS`, `Kafka`, `Webhook`, `SOAP`

**`dictionary_options` — Complexity category:**
`Bajo`, `Medio`, `Alto`

**`dictionary_options` — QA Status:**
`OK`, `REVISAR`, `PENDING`

**`dictionary_options` — Tools (core tools governed list):**
`OIC Gen3`, `OCI API Gateway`, `OCI Streaming`, `OCI Queue`, `Oracle Functions`, `OCI Data Integration`, `Oracle ORDS`, `ATP`, `Oracle DB`, `SFTP`, `OCI Object Storage`, `OCI APM`

### M1 Definition of Done
```bash
python3 -m pytest packages/calc-engine/src/tests/ -v          # 26 passed
python -m app.migrations.seed                                  # exits 0, no errors
# Query via Python:
python3 -c "
from sqlalchemy import create_engine, text
engine = create_engine('postgresql://dis:dis@localhost:5432/oci_dis')
with engine.connect() as c:
    print('patterns:', c.execute(text('SELECT COUNT(*) FROM pattern_definitions')).scalar())
    print('assumptions:', c.execute(text('SELECT COUNT(*) FROM assumption_sets')).scalar())
    print('dict_options:', c.execute(text('SELECT COUNT(*) FROM dictionary_options')).scalar())
"
# Expected: patterns=17, assumptions=1, dict_options>=30
```

---

## Milestone M2 — Import Engine

**Goal:** Upload an XLSX file, parse it with workbook-parity rules, persist all rows, and produce the correct counts.

### What to build

**1. `apps/api/app/services/import_service.py`**

```python
async def process_import(batch_id: str, file_path: str, db: AsyncSession) -> ImportBatch:
    """
    1. Read XLSX using openpyxl (data_only=True)
    2. Get all rows from the sheet as a list of lists
    3. Call packages/calc-engine/src/engine/importer.parse_rows()
    4. Persist SourceIntegrationRow for every source row (immutable)
    5. For included rows: create CatalogIntegration
       - Compute executions_per_day via calc_engine.volumetry.executions_per_day()
       - Compute payload_per_hour_kb via calc_engine.volumetry.payload_per_hour_kb()
       - Compute QA status via calc_engine.qa.evaluate_qa()
    6. Emit AuditEvent for every normalization_event on every row
    7. Update ImportBatch: status=completed, counts, header_map
    8. Return updated ImportBatch
    """
```

Rules (from PRD-017, PRD-018, confirmed in parity-expectations.json):
- Source tab: `Catálogo de Integraciones` (not `TPL - Catálogo`)
- Headers at row 5 (index 4), data starts at row 6 (index 5)
- Keep rows where TBQ = Y (case-insensitive)
- Exclude rows where Estado = `Duplicado 2` (exact string)
- Include `Duplicado 1` — do not exclude it
- Preserve source order — no sorting or grouping
- `excluded_count` counts only TBQ=Y rows excluded (i.e. Duplicado 2 only)

**2. `apps/api/app/workers/import_worker.py`**

Celery task that calls `import_service.process_import()`. Handles exceptions, updates `ImportBatch.status=failed` on error with `error_details`.

**3. Wire `POST /api/v1/imports/{project_id}`** in `apps/api/app/routers/imports.py`
- Accept `UploadFile`
- Save file to `uploads/` directory (local dev — skip MinIO for now)
- Create `ImportBatch` record (status=pending)
- Call `import_service.process_import()` directly (sync for M2, async worker in M3+)
- Return `ImportBatch` as response

**4. Wire `GET /api/v1/imports/{project_id}`** — list batches
**5. Wire `GET /api/v1/imports/{project_id}/{batch_id}`** — batch status + counts
**6. Wire `GET /api/v1/imports/{project_id}/{batch_id}/rows`** — paginated source rows with inclusion/exclusion reasons

### M2 Definition of Done
```bash
# Run parity tests — must still be 26 passed
python3 -m pytest packages/calc-engine/src/tests/ -v

# API smoke test — start the API first: uvicorn app.main:app --reload
# Then:
python3 -c "
import httpx, json

# Create a project first
r = httpx.post('http://localhost:8000/api/v1/projects/', json={'name': 'Parity Test', 'owner_id': 'test-user'})
project_id = r.json()['id']
print('Project:', project_id)

# Upload the workbook
with open('Catalogo_Integracion.xlsx', 'rb') as f:
    r = httpx.post(f'http://localhost:8000/api/v1/imports/{project_id}',
                   files={'file': ('Catalogo_Integracion.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})

batch = r.json()
print('Batch status:', batch['status'])
print('Loaded count:', batch['loaded_count'])     # must be 144
print('Excluded count:', batch['excluded_count'])  # must be 13
print('TBQ Y count:', batch['tbq_y_count'])        # must be 157
assert batch['loaded_count'] == 144, f'Parity FAILED: expected 144, got {batch[\"loaded_count\"]}'
assert batch['excluded_count'] == 13
assert batch['tbq_y_count'] == 157
print('✓ M2 PARITY PASSED')
"
```

---

## Milestone M3 — Catalog Grid API

**Goal:** The catalog is fully queryable, filterable, and editable via API. QA status is computed per row.

### What to build

**1. `apps/api/app/services/catalog_service.py`**

```python
async def list_integrations(project_id, page, page_size, filters, db) -> Page[CatalogIntegration]
async def get_integration(project_id, integration_id, db) -> CatalogIntegrationDetail  # includes lineage
async def update_integration(project_id, integration_id, patch, actor_id, db) -> CatalogIntegration
async def bulk_patch(project_id, integration_ids, patch, actor_id, db) -> BulkPatchResult
async def get_lineage(project_id, integration_id, db) -> LineageDetail
```

**Allowed fields for PATCH** (architect-owned — PRD-022):
`selected_pattern`, `pattern_rationale`, `comments`, `retry_policy`, `core_tools`, `additional_tools_overlays`

Every PATCH must:
1. Validate `selected_pattern` against `pattern_definitions` table
2. Validate `core_tools` values against `dictionary_options` where category=`TOOLS`
3. Recompute `qa_status` and `qa_reasons` using `calc_engine.qa.evaluate_qa()`
4. Emit `AuditEvent` with `old_value` and `new_value`
5. If `core_tools`, `payload_per_execution_kb`, or `frequency` changed: recompute `executions_per_day` and `payload_per_hour_kb`

**2. Pydantic schemas** — `apps/api/app/schemas/catalog.py`:
```python
class CatalogIntegrationResponse(BaseModel)  # full row with QA
class CatalogIntegrationPatch(BaseModel)      # architect fields only
class CatalogIntegrationDetail(BaseModel)     # + source lineage + normalization events
class BulkPatchRequest(BaseModel)
class BulkPatchResult(BaseModel)
class LineageDetail(BaseModel)
```

**3. Wire all endpoints in `apps/api/app/routers/catalog.py`**:
- `GET  /api/v1/catalog/{project_id}` — paginated, filterable by `pattern`, `brand`, `qa_status`, free-text `search`
- `GET  /api/v1/catalog/{project_id}/{integration_id}` — full detail + lineage
- `PATCH /api/v1/catalog/{project_id}/{integration_id}` — architect fields + audit
- `POST  /api/v1/catalog/{project_id}/bulk-patch`
- `GET  /api/v1/catalog/{project_id}/{integration_id}/lineage`

**4. `apps/api/app/services/audit_service.py`**
```python
async def emit(event_type, entity_type, entity_id, actor_id, old_value, new_value, project_id, db, correlation_id=None)
```

### M3 Definition of Done
```bash
python3 -c "
import httpx

API = 'http://localhost:8000/api/v1'
# (reuse project_id and batch_id from M2 smoke test)

# List catalog
r = httpx.get(f'{API}/catalog/{project_id}?page=1&page_size=50')
data = r.json()
assert data['total'] == 144, f'Expected 144 rows, got {data[\"total\"]}'

# Filter by QA status
r = httpx.get(f'{API}/catalog/{project_id}?qa_status=REVISAR')
assert r.json()['total'] == 144  # all should be REVISAR initially (no formal IDs)

# Patch a row
row_id = data['integrations'][0]['id']
r = httpx.patch(f'{API}/catalog/{project_id}/{row_id}',
    json={'selected_pattern': '#01', 'pattern_rationale': 'Request-Reply for synchronous API call'})
assert r.status_code == 200

# Verify lineage
r = httpx.get(f'{API}/catalog/{project_id}/{row_id}/lineage')
lineage = r.json()
assert 'source_row_number' in lineage
assert 'raw_data' in lineage

# Verify audit event was emitted
r = httpx.get(f'{API}/audit/{project_id}?entity_type=catalog_integration&entity_id={row_id}')
assert r.json()['total'] >= 1

print('✓ M3 PASSED')
"
```

---

## Milestone M4 — Calculation Engine Integration

**Goal:** Full-project volumetry recalculation runs, produces an immutable `VolumetrySnapshot`, and the consolidated numbers are accessible via API.

### What to build

**1. `apps/api/app/services/recalc_service.py`**

```python
async def recalculate_project(project_id: str, actor_id: str, db: AsyncSession) -> VolumetrySnapshot:
    """
    1. Load all CatalogIntegration rows for the project
    2. Load the default AssumptionSet (is_default=True)
    3. Build list[IntegrationInput] from the catalog rows
    4. Call packages/calc-engine/src/engine/volumetry.consolidate_project()
    5. For each row: also compute individual metrics (oic_msgs_month, payload_per_hour, etc.)
    6. Persist VolumetrySnapshot:
       - row_results: {integration_id: {oic_msgs_month, payload_per_hour_kb, executions_per_day, ...}}
       - consolidated: {oic: {...}, data_integration: {...}, functions: {...}, streaming: {...}}
    7. Emit AuditEvent(event_type='recalculation', entity_type='project')
    8. Return VolumetrySnapshot
    """
```

**2. Wire endpoints in `apps/api/app/routers/recalculate.py`**:
- `POST /api/v1/recalculate/{project_id}` — trigger and wait (sync for M4, async worker in M5+)
- `GET  /api/v1/volumetry/{project_id}/snapshots` — list snapshots
- `GET  /api/v1/volumetry/{project_id}/snapshots/{snapshot_id}` — full snapshot
- `GET  /api/v1/volumetry/{project_id}/snapshots/{snapshot_id}/consolidated` — totals only

**3. Pydantic schemas** — `apps/api/app/schemas/volumetry.py`:
```python
class VolumetrySnapshotResponse(BaseModel)
class ConsolidatedMetrics(BaseModel)
class OICMetrics(BaseModel)
class DIMetrics(BaseModel)
class FunctionsMetrics(BaseModel)
class StreamingMetrics(BaseModel)
```

**OIC Metrics must include** (from PRD-030, PRD-031):
- `total_billing_msgs_month: float`
- `peak_billing_msgs_hour: float`
- `peak_packs_hour: float` (rounded up to 5K packs)
- `row_count: int`

**4. Recalculation trigger** — patch endpoints in catalog_service must call `recalc_service.recalculate_project()` after any change to `core_tools`, `payload_per_execution_kb`, or `selected_pattern`.

### M4 Definition of Done
```bash
python3 -c "
import httpx

API = 'http://localhost:8000/api/v1'

# Trigger recalculation
r = httpx.post(f'{API}/recalculate/{project_id}')
snapshot_id = r.json()['snapshot_id']
assert snapshot_id is not None

# Get consolidated metrics
r = httpx.get(f'{API}/volumetry/{project_id}/snapshots/{snapshot_id}/consolidated')
metrics = r.json()
print('OIC msgs/month:', metrics['oic']['total_billing_msgs_month'])
print('Peak packs/hour:', metrics['oic']['peak_packs_hour'])
print('DI workspace active:', metrics['data_integration']['workspace_active'])
print('Functions invocations:', metrics['functions']['total_invocations_month'])

# Validate structure
assert 'oic' in metrics
assert 'data_integration' in metrics
assert 'functions' in metrics
assert metrics['oic']['peak_packs_hour'] >= 1

# Verify snapshot is immutable (same ID, same values on second call)
r2 = httpx.post(f'{API}/recalculate/{project_id}')
snapshot_id_2 = r2.json()['snapshot_id']
assert snapshot_id_2 != snapshot_id  # new snapshot, old one unchanged

print('✓ M4 PASSED')
"

# Run all parity tests — must still be 26 passed
python3 -m pytest packages/calc-engine/src/tests/ -v
```

---

## Cross-Cutting Rules (Apply to All Milestones)

### Never break parity tests
Run `python3 -m pytest packages/calc-engine/src/tests/ -v` after every change to `packages/calc-engine/`. If any test fails, fix it before proceeding.

### Type everything
- All Python functions: explicit type hints on parameters and return types
- All Pydantic models: no `Any`, no bare `dict`
- Strict Pydantic v2 (`model_config = ConfigDict(strict=True)` where appropriate)

### Audit everything
Every mutating operation on `CatalogIntegration`, `PatternDefinition`, `DictionaryOption`, `AssumptionSet` must call `audit_service.emit()`. This is non-negotiable.

### Calc engine stays pure
If you need a new calculation, add it to `packages/calc-engine/src/engine/volumetry.py` or `qa.py`. Never put formula logic in routers or services. Always write a test for new formulas.

### Database sessions
Use `AsyncSession` with `async with session.begin()` for all writes. Never commit inside a service function — let the router/context manager handle it.

### Error handling
Use FastAPI's `HTTPException` with explicit status codes. Return structured error responses `{"detail": "...", "error_code": "..."}`. Never let a 500 surface to the client without a log entry.

### Pydantic schemas
Create dedicated request/response schemas in `apps/api/app/schemas/`. Never return SQLAlchemy model objects directly from endpoints.

---

## Coding Conventions Quick Reference

```python
# Router (thin) — only HTTP concern + schema validation
@router.post("/{project_id}", response_model=ImportBatchResponse, status_code=202)
async def upload_and_import(project_id: str, file: UploadFile, db: AsyncSession = Depends(get_db)):
    return await import_service.process_import(project_id, file, db)

# Service (business logic)
async def process_import(project_id: str, file: UploadFile, db: AsyncSession) -> ImportBatch:
    result = calc_engine_importer.parse_rows(rows)  # call engine, never embed logic here
    await audit_service.emit(...)
    return batch

# Calc engine (pure)
def oic_billing_messages_per_execution(payload_kb: float, response_kb: float, assumptions: Assumptions) -> CalcResult:
    value = math.ceil(payload_kb / assumptions.oic_billing_threshold_kb) + math.ceil(response_kb / assumptions.oic_billing_threshold_kb)
    return CalcResult(value=float(value), unit="billing messages/execution", formula="...", inputs={...})
```

---

## Environment Commands

```bash
# Start API (from apps/api/)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Apply migrations
alembic upgrade head

# Seed reference data
python -m app.migrations.seed

# Run all tests
python3 -m pytest packages/calc-engine/src/tests/ -v

# Lint
ruff check apps/api/app/

# TypeScript check
cd apps/web && npx tsc --noEmit
```

---

## What Success Looks Like

When all four milestones are done:
1. `python3 -m pytest packages/calc-engine/src/tests/ -v` → **26 passed**
2. Upload `Catalogo_Integracion.xlsx` → API returns `loaded_count=144`, `excluded_count=13`, `tbq_y_count=157`
3. `GET /api/v1/catalog/{project_id}?page_size=200` → **144 rows**, all with `qa_status=REVISAR`, all in source order
4. `POST /api/v1/recalculate/{project_id}` → returns a `VolumetrySnapshot` with valid OIC, DI, Functions, Streaming metrics
5. Every write has a corresponding `AuditEvent`
6. `ruff check apps/api/app/` → **0 errors**
7. `tsc --noEmit` → **0 errors**

This is the parity milestone. Phase 1 is the foundation. Do not add features, do not redesign. Implement exactly what the PRD specifies, make the tests pass, make the numbers match.

---

## Out of Scope for This Task

- Authentication / JWT (RBAC scaffold is in models, skip enforcement for now)
- Celery async workers (call services directly — async worker wiring is M5+)
- MinIO / object storage integration (save files to local `uploads/` dir for now)
- Next.js frontend (UI work is M5+)
- Justification narratives (M6)
- Exports (M7)
- Admin governance UI (M8)

---

*Built from: `Catalogo_Integracion.xlsx` → `TLP - PRD` (PRD-001 through PRD-050)*
*Stack: FastAPI + PostgreSQL + Python 3.12 + Next.js 14 + Docker Desktop (macOS)*
*Parity benchmark: 144 loaded / 13 excluded / 157 TBQ=Y*
