# Codex Task — Project Status Report

## Mission

Audit the current state of the OCI DIS Blueprint codebase and produce a structured
status report covering every milestone from M1 to M10. Do not implement features.
Do not modify source code. Read, inspect, and report only.

---

## Instructions

Read these files before starting your audit:
1. `AGENTS.md` — milestone definitions and definition of done per milestone
2. `codex-m9-capture.md` — M9 spec and definition of done
3. `codex-m10-graph.md` — M10 spec and definition of done
4. `packages/test-fixtures/benchmarks/parity-expectations.json` — parity benchmark

Then inspect the codebase and run the verification commands below.
Report findings honestly. If something is missing or broken, say so explicitly.

---

## Verification Commands

Run all of these. Capture every output line — include it verbatim in the report.

```bash
# 1. Parity tests
python3 -m pytest packages/calc-engine/src/tests/ -v --tb=short 2>&1

# 2. API lint
cd apps/api && python3 -m ruff check app/ 2>&1; cd ../..

# 3. TypeScript check
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -20; cd ../..

# 4. Docker stack health
docker compose ps 2>&1

# 5. API health
curl -sf http://localhost:8000/health 2>&1

# 6. Endpoint coverage — verify all expected routes exist
curl -sf http://localhost:8000/openapi.json | python3 -c "
import json, sys
spec = json.load(sys.stdin)
paths = sorted(spec.get('paths', {}).keys())
print(f'Total endpoints: {len(paths)}')
for p in paths:
    methods = list(spec[\"paths\"][p].keys())
    print(f'  {\" \".join(m.upper() for m in methods):30s} {p}')
" 2>&1

# 7. File coverage — check key files exist
python3 -c "
import os
checks = [
    # Backend
    ('apps/api/app/main.py',                        'API entry point'),
    ('apps/api/app/core/config.py',                 'Config / settings'),
    ('apps/api/app/core/db.py',                     'DB session'),
    ('apps/api/app/models/project.py',              'Core models'),
    ('apps/api/app/models/snapshot.py',             'Snapshot models'),
    ('apps/api/app/models/governance.py',           'Governance models'),
    ('apps/api/app/services/import_service.py',     'Import service'),
    ('apps/api/app/services/catalog_service.py',    'Catalog service'),
    ('apps/api/app/services/recalc_service.py',     'Recalc service'),
    ('apps/api/app/services/audit_service.py',      'Audit service'),
    ('apps/api/app/services/graph_service.py',      'Graph service (M10)'),
    ('apps/api/app/schemas/catalog.py',             'Catalog schemas'),
    ('apps/api/app/schemas/graph.py',               'Graph schemas (M10)'),
    ('apps/api/app/routers/projects.py',            'Projects router'),
    ('apps/api/app/routers/imports.py',             'Imports router'),
    ('apps/api/app/routers/catalog.py',             'Catalog router'),
    ('apps/api/app/routers/patterns.py',            'Patterns router'),
    ('apps/api/app/routers/dictionaries.py',        'Dictionaries router'),
    ('apps/api/app/routers/recalculate.py',         'Recalculate router'),
    ('apps/api/app/routers/volumetry.py',           'Volumetry router'),
    ('apps/api/app/routers/audit.py',               'Audit router'),
    ('apps/api/app/routers/exports.py',             'Exports router'),
    ('apps/api/app/routers/justifications.py',      'Justifications router'),
    ('apps/api/app/migrations/seed.py',             'Seed script'),
    # Calc engine
    ('packages/calc-engine/src/engine/volumetry.py','Volumetry engine'),
    ('packages/calc-engine/src/engine/qa.py',       'QA engine'),
    ('packages/calc-engine/src/engine/importer.py', 'Importer engine'),
    ('packages/calc-engine/src/tests/test_volumetry.py', 'Volumetry tests'),
    ('packages/calc-engine/src/tests/test_importer.py',  'Importer tests'),
    # Frontend
    ('apps/web/app/layout.tsx',                     'Root layout'),
    ('apps/web/app/projects/page.tsx',              'Projects list page'),
    ('apps/web/app/projects/[projectId]/page.tsx',  'Dashboard page'),
    ('apps/web/app/projects/[projectId]/import/page.tsx',   'Import page'),
    ('apps/web/app/projects/[projectId]/catalog/page.tsx',  'Catalog page'),
    ('apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx', 'Detail page'),
    ('apps/web/app/projects/[projectId]/capture/page.tsx',  'Capture history page (M9)'),
    ('apps/web/app/projects/[projectId]/capture/new/page.tsx', 'Capture wizard (M9)'),
    ('apps/web/app/projects/[projectId]/graph/page.tsx',    'Graph page (M10)'),
    ('apps/web/lib/api.ts',                         'API client'),
    ('apps/web/lib/types.ts',                       'TypeScript types'),
    ('apps/web/components/catalog-table.tsx',       'Catalog table'),
    ('apps/web/components/integration-graph.tsx',   'Graph component (M10)'),
    ('apps/web/components/capture-wizard.tsx',      'Capture wizard component (M9)'),
    ('apps/web/components/oic-estimate-preview.tsx','OIC estimate preview (M9)'),
    ('apps/web/components/qa-preview.tsx',          'QA preview component (M9)'),
    # Infra
    ('docker-compose.yml',                          'Docker Compose stack'),
    ('apps/api/Dockerfile',                         'API Dockerfile'),
    ('apps/web/Dockerfile',                         'Web Dockerfile'),
    ('codex-setup.sh',                              'Codex setup script'),
    ('scripts/seed_qa_project.py',                  'QA seed script'),
]
missing, present = [], []
for path, label in checks:
    if os.path.exists(path):
        size = os.path.getsize(path)
        present.append((path, label, size))
    else:
        missing.append((path, label))

print(f'Present: {len(present)} / {len(checks)}')
print()
for path, label, size in present:
    print(f'  OK   {size:>8} bytes   {label}')
print()
for path, label in missing:
    print(f'  MISS              {label}  ({path})')
" 2>&1

# 8. API endpoint smoke — verify M9 and M10 endpoints specifically
python3 -c "
import httpx, sys
API = 'http://localhost:8000/api/v1'
results = []

def check(label, method, url, **kwargs):
    try:
        r = getattr(httpx, method)(url, timeout=10, **kwargs)
        results.append((label, r.status_code, r.status_code < 500))
    except Exception as e:
        results.append((label, 'ERR', False))

# Core
check('GET /projects',          'get',  f'{API}/projects/')
check('GET /patterns',          'get',  f'{API}/patterns/')
check('GET /dictionaries',      'get',  f'{API}/dictionaries/')
check('GET /assumptions',       'get',  f'{API}/assumptions/')
check('GET /health',            'get',  'http://localhost:8000/health')

# Get first project for scoped tests
try:
    projects = httpx.get(f'{API}/projects/', timeout=10).json()
    pid = projects['projects'][0]['id'] if projects.get('projects') else None
except:
    pid = None

if pid:
    check('GET /catalog/{pid}',         'get', f'{API}/catalog/{pid}')
    check('GET /catalog/{pid}/graph',   'get', f'{API}/catalog/{pid}/graph')
    check('GET /catalog/{pid}/systems', 'get', f'{API}/catalog/{pid}/systems')
    check('GET /catalog/{pid}/duplicates','get', f'{API}/catalog/{pid}/duplicates',
          params={'source_system':'A','destination_system':'B','business_process':'X'})
    check('POST /catalog/{pid}/estimate','post', f'{API}/catalog/{pid}/estimate',
          json={'frequency':'Una vez al día','payload_per_execution_kb':100})
    check('GET /imports/{pid}',         'get', f'{API}/imports/{pid}')
    check('GET /volumetry/{pid}/snapshots','get', f'{API}/volumetry/{pid}/snapshots')
    check('GET /audit/{pid}',           'get', f'{API}/audit/{pid}')
    check('GET /justifications/{pid}',  'get', f'{API}/justifications/{pid}')
    check('GET /dashboard/{pid}/snapshots','get', f'{API}/dashboard/{pid}/snapshots')
else:
    print('  WARN: No project found — scoped endpoint checks skipped')

print(f'Endpoint checks: {sum(1 for _,_,ok in results if ok)}/{len(results)} passed')
for label, status, ok in results:
    mark = 'OK  ' if ok else 'FAIL'
    print(f'  {mark}  {status}   {label}')
" 2>&1
```

---

## Report Format

Write the report to `docs/status-report.md` using exactly this structure:

```markdown
# OCI DIS Blueprint — Status Report
Generated: {date}
Codebase: {git log --oneline -1}

---

## Executive Summary

| Area | Status | Coverage |
|------|--------|----------|
| Backend API | ✅ Complete / ⚠ Partial / ❌ Missing | X/Y endpoints |
| Calc Engine | ✅ / ⚠ / ❌ | X/26 tests |
| Frontend | ✅ / ⚠ / ❌ | X/Y pages |
| Docker Stack | ✅ / ⚠ / ❌ | X/6 containers Up |
| M9 Capture | ✅ / ⚠ / ❌ | |
| M10 Graph | ✅ / ⚠ / ❌ | |

---

## Milestone Coverage

### M1 — Schema + Migrations
**Status:** ✅ Complete / ⚠ Partial / ❌ Not Started

Evidence:
- [ ] Alembic migration file exists at apps/api/migrations/versions/
- [ ] seed.py exists and seeds 17 patterns, 1 assumption set, 40 dict options
- [ ] All 11 tables present in migration

Gaps: {list any missing items or "None"}

---

### M2 — Import Engine
**Status:** ✅ / ⚠ / ❌

Evidence:
- [ ] import_service.py exists
- [ ] POST /api/v1/imports/{project_id} endpoint registered
- [ ] Parity: loaded=144, excluded=13, tbq_y=157 verified

Gaps: {list any gaps}

---

### M3 — Catalog Grid API
**Status:** ✅ / ⚠ / ❌

Evidence:
- [ ] catalog_service.py exists
- [ ] GET /catalog/{pid} with filters
- [ ] PATCH /catalog/{pid}/{id} with audit
- [ ] GET /catalog/{pid}/{id}/lineage

Gaps:

---

### M4 — Calculation Engine Integration
**Status:** ✅ / ⚠ / ❌

Evidence:
- [ ] recalc_service.py exists
- [ ] POST /recalculate/{pid} endpoint
- [ ] VolumetrySnapshot created on recalculation
- [ ] Consolidated metrics accessible

Gaps:

---

### M5 — Next.js Frontend (Core Pages)
**Status:** ✅ / ⚠ / ❌

Evidence:
- [ ] Projects list page
- [ ] Project dashboard page with OIC metrics
- [ ] Import upload page
- [ ] Catalog grid with filters
- [ ] Integration detail + patch form

Gaps:

---

### M6 — Justification Narratives
**Status:** ✅ / ⚠ / ❌

Evidence:
- [ ] justifications.py router exists
- [ ] GET /justifications/{pid}/{integration_id}
- [ ] POST /justifications/{pid}/{integration_id}/approve
- [ ] JustificationRecord model present

Gaps:

---

### M7 — Exports
**Status:** ✅ / ⚠ / ❌

Evidence:
- [ ] exports.py router exists
- [ ] POST /exports/{pid}/xlsx
- [ ] POST /exports/{pid}/pdf
- [ ] POST /exports/{pid}/json

Gaps:

---

### M8 — Admin + Governance
**Status:** ✅ / ⚠ / ❌

Evidence:
- [ ] PatternDefinition CRUD endpoints
- [ ] DictionaryOption management
- [ ] AssumptionSet versioning
- [ ] Admin UI page (if applicable)

Gaps:

---

### M9 — Integration Capture Interface
**Status:** ✅ / ⚠ / ❌

Backend:
- [ ] POST /catalog/{pid} — manual create
- [ ] GET /catalog/{pid}/systems — autocomplete
- [ ] GET /catalog/{pid}/duplicates — duplicate check
- [ ] POST /catalog/{pid}/estimate — OIC preview

Frontend:
- [ ] Capture history page
- [ ] 5-step wizard (capture/new/page.tsx)
- [ ] capture-wizard.tsx component
- [ ] oic-estimate-preview.tsx component
- [ ] qa-preview.tsx component
- [ ] system-autocomplete.tsx component

Gaps:

---

### M10 — System Dependency Map
**Status:** ✅ / ⚠ / ❌

Backend:
- [ ] GET /catalog/{pid}/graph endpoint
- [ ] graph_service.py
- [ ] GraphResponse schema (graph.py)

Frontend:
- [ ] Graph page (/projects/{pid}/graph)
- [ ] integration-graph.tsx (D3 force + React SVG)
- [ ] graph-detail-panel.tsx
- [ ] graph-controls.tsx
- [ ] graph-export-button.tsx
- [ ] D3 installed in package.json

Gaps:

---

## Test Coverage

### Calc Engine Parity Tests
{paste full pytest output}
Result: X/26 passed

### API Lint (ruff)
{paste ruff output}
Result: ✅ Clean / ❌ X errors

### TypeScript
{paste tsc output}
Result: ✅ Clean / ❌ X errors

---

## Endpoint Inventory

{paste full endpoint list from openapi.json check}
Total: X endpoints registered

---

## File Inventory

{paste full file check output}
Present: X / Y expected files

---

## Docker Stack

{paste docker compose ps output}

---

## Pending Tasks

### Critical (blocks QA or demo)
{list anything that is missing and prevents the app from working end-to-end}

### Incomplete (partial implementation)
{list anything that exists but is not fully functional}

### Optional / Future
{list anything deferred by design — not a gap, just not yet scheduled}

---

## Recommended Next Actions

{ordered list of the 3-5 highest-priority items to complete before the next demo}
```

---

## Definition of Done

- [ ] `docs/status-report.md` exists and is committed
- [ ] All verification commands were run and their output is included verbatim
- [ ] Every milestone M1-M10 has a status (✅ / ⚠ / ❌) with evidence
- [ ] Pending tasks section lists specific file paths or endpoint names — no vague statements
- [ ] Recommended next actions are ordered by priority
