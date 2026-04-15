# Codex Task — Docker Fix + M1-M4 End-to-End Validation

## Situation

M1-M4 was implemented and smoke-tested locally. The Docker stack is broken:
`docker compose up --build` starts `db` and `redis` successfully but `api`, `web`,
`worker`, and `minio` containers never come up. Port 8000 is unreachable.

## Your Single Mission

**Get all six containers running and prove M1-M4 works end-to-end inside Docker.**

You do not add tests. You do not write docs. You do not refactor. You fix the Docker
build, fix whatever is broken, and run the validation suite. Nothing else.

---

## Step 1 — Diagnose

Run these immediately. Do not skip.

```bash
docker compose build api        2>&1
docker compose build web        2>&1
docker compose build worker     2>&1
docker compose logs             2>&1 | tail -100
```

Read every error line. Find root causes. Fix them.

Common causes to check:
- Dockerfile missing, wrong base image, or referencing files that don't exist
- `requirements.txt` path wrong inside the Docker build context
- `apps/api/app/` has import errors that crash uvicorn on startup
- `alembic.ini` or `env.py` missing DATABASE_URL or wrong path
- `apps/web/` missing `tsconfig.json` or `next.config.js` causing build failure
- Healthcheck failing because the app crashes before the check runs
- Worker Dockerfile missing or referencing wrong module path

---

## Step 2 — Fix Everything

Fix all build and startup errors until:

```bash
docker compose up --build -d
sleep 15
docker compose ps
```

Shows ALL six services with status `Up` or `Up (healthy)`:
- `ocidisblueprint-api-1`
- `ocidisblueprint-web-1`
- `ocidisblueprint-db-1`
- `ocidisblueprint-redis-1`
- `ocidisblueprint-worker-1`
- `ocidisblueprint-minio-1`

If `web` is a full Next.js build and slows things down, fix `api` and `worker` first,
then `web`. Do not leave any container in `Exit` or `Restarting` state.

---

## Step 3 — Run Migrations + Seed Inside Docker

```bash
docker compose exec api alembic upgrade head
docker compose exec api python -m app.migrations.seed
```

Both must exit 0. Then verify:

```bash
docker compose exec api python3 -c "
from sqlalchemy import create_engine, text
import os
engine = create_engine(os.environ['DATABASE_URL'].replace('+asyncpg', ''))
with engine.connect() as c:
    print('patterns:', c.execute(text('SELECT COUNT(*) FROM pattern_definitions')).scalar())
    print('assumptions:', c.execute(text('SELECT COUNT(*) FROM assumption_sets')).scalar())
    print('dict_options:', c.execute(text('SELECT COUNT(*) FROM dictionary_options')).scalar())
"
```

Required output: `patterns: 17`, `assumptions: 1`, `dict_options: 40`

---

## Step 4 — API Health Check

```bash
curl -sf http://localhost:8000/health && echo "✓ API healthy"
curl -sf http://localhost:8000/docs > /dev/null && echo "✓ OpenAPI docs up"
```

Both must pass. If `/health` returns 404, add a health endpoint to `apps/api/app/main.py`:

```python
@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## Step 5 — M1-M4 Live Smoke Against Docker API

Run this single script. It tests M1 through M4 in sequence against the live Docker API.
Do not use a separate DB — use the running Docker stack.

```bash
docker compose exec api python3 -c "
import httpx, sys

API = 'http://localhost:8000/api/v1'
errors = []

# --- M1: Seed data ---
r = httpx.get(f'{API}/patterns')
if r.status_code != 200 or r.json().get('total', len(r.json())) < 17:
    errors.append(f'M1 FAIL: patterns endpoint returned {r.status_code} / {r.text[:200]}')
else:
    print('✓ M1: patterns accessible')

# --- M2: Import via synthetic parity workbook ---
# Create project
r = httpx.post(f'{API}/projects/', json={'name': 'Docker Smoke', 'owner_id': 'codex'})
assert r.status_code in (200, 201), f'Project create failed: {r.status_code} {r.text}'
project_id = r.json()['id']
print(f'✓ M2: project created {project_id}')

# Build minimal parity workbook in memory and upload
import io, openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'Catálogo de Integraciones'
# Rows 1-4: padding
for _ in range(4): ws.append([None])
# Row 5: headers
ws.append(['#','ID de Interfaz','Marca','Proceso de Negocio','Interfaz','Descripción',
           'Tipo','Estado Interfaz','Complejidad','Alcance Inicial','Estado',
           'Estado de Mapeo','Sistema de Origen','Tecnología de Origen','API Reference',
           'Propietario de Origen','Sistema de Destino','Tecnología de Destino',
           'Propietario de Destino','Frecuencia','Tamaño KB','TBQ',
           'Patrones','Incertidumbre','Owner','Identificada en:',
           'Proceso de Negocio DueDiligence','Slide'])
# 157 TBQ=Y rows, 13 are Duplicado 2 (excluded), 144 loaded
for i in range(1, 158):
    status = 'Duplicado 2' if i <= 13 else 'En Progreso'
    ws.append([i, f'INT-{i:03d}', 'BrandA', 'Proceso1', f'Interfaz {i}', f'Desc {i}',
               'REST', status, 'Medio', 'Si', status,
               'Pendiente', 'SAP', 'REST', f'/api/v{i}',
               'OwnerA', 'Oracle', 'SOAP', 'OwnerB',
               'Una vez al día', 10.0, 'Y',
               None, None, 'OwnerA', None, None, None])
buf = io.BytesIO()
wb.save(buf)
buf.seek(0)

r = httpx.post(f'{API}/imports/{project_id}',
               files={'file': ('parity.xlsx', buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
               timeout=60)
assert r.status_code in (200, 201, 202), f'Import failed: {r.status_code} {r.text[:400]}'
batch = r.json()
loaded   = batch.get('loaded_count', 0)
excluded = batch.get('excluded_count', 0)
tbq_y    = batch.get('tbq_y_count', 0)
if loaded != 144 or excluded != 13 or tbq_y != 157:
    errors.append(f'M2 PARITY FAIL: loaded={loaded} excluded={excluded} tbq_y={tbq_y} (need 144/13/157)')
else:
    print(f'✓ M2: parity exact — loaded={loaded} excluded={excluded} tbq_y={tbq_y}')

# --- M3: Catalog grid ---
r = httpx.get(f'{API}/catalog/{project_id}?page=1&page_size=10')
assert r.status_code == 200, f'Catalog list failed: {r.status_code}'
data = r.json()
total = data.get('total', 0)
if total != 144:
    errors.append(f'M3 FAIL: catalog total={total} (need 144)')
else:
    print(f'✓ M3: catalog total={total}')

# Patch first row
row_id = data['integrations'][0]['id'] if data.get('integrations') else None
if row_id:
    r = httpx.patch(f'{API}/catalog/{project_id}/{row_id}',
        json={'selected_pattern': '#01', 'pattern_rationale': 'Sync API call'})
    if r.status_code != 200:
        errors.append(f'M3 PATCH FAIL: {r.status_code} {r.text[:200]}')
    else:
        print(f'✓ M3: patch OK status={r.status_code}')

# Audit
r = httpx.get(f'{API}/audit/{project_id}')
audit_total = r.json().get('total', 0) if r.status_code == 200 else 0
if audit_total < 1:
    errors.append(f'M3 AUDIT FAIL: total={audit_total}')
else:
    print(f'✓ M3: audit trail total={audit_total}')

# --- M4: Volumetry recalculation ---
r = httpx.post(f'{API}/recalculate/{project_id}', timeout=60)
assert r.status_code in (200, 201, 202), f'Recalc failed: {r.status_code} {r.text[:400]}'
snap = r.json()
snapshot_id = snap.get('snapshot_id') or snap.get('id')
print(f'✓ M4: snapshot created id={snapshot_id}')

r = httpx.get(f'{API}/volumetry/{project_id}/snapshots/{snapshot_id}/consolidated')
assert r.status_code == 200, f'Consolidated failed: {r.status_code}'
metrics = r.json()
assert 'oic' in metrics, 'Missing oic in consolidated'
assert metrics['oic']['peak_packs_hour'] >= 1, 'peak_packs_hour must be >= 1'
print(f'✓ M4: oic.peak_packs_hour={metrics[\"oic\"][\"peak_packs_hour\"]}')

# --- Final ---
if errors:
    print()
    for e in errors: print(f'FAIL: {e}')
    sys.exit(1)
else:
    print()
    print('✓✓✓ M1-M4 DOCKER VALIDATION PASSED ✓✓✓')
"
```

---

## Step 6 — Parity Tests Still Green

```bash
docker compose exec api python3 -m pytest /app/../../../packages/calc-engine/src/tests/ -v 2>/dev/null \
  || python3 -m pytest packages/calc-engine/src/tests/ -v
```

Must show: **26 passed**

---

## Definition of Done

You are done when ALL of these are true simultaneously:

- [ ] `docker compose ps` shows 6 containers, all `Up` or `Up (healthy)`
- [ ] `curl http://localhost:8000/health` returns `{"status": "ok"}`
- [ ] M1-M4 Docker smoke script exits 0 with `✓✓✓ M1-M4 DOCKER VALIDATION PASSED`
- [ ] 26 parity tests pass
- [ ] `ruff check apps/api/app/` reports 0 errors

Do not stop until all five are green. Do not add scope. Fix, validate, done.
