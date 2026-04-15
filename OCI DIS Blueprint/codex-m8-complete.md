# Codex Task — M8 Completion: Admin Governance UI + Pattern CRUD

## Situation

Status report identified two structural gaps in M8:
1. `apps/api/app/routers/patterns.py` is read-only — no CREATE, UPDATE, or DELETE
   for PatternDefinition records. Architects cannot add or modify OIC patterns via API.
2. No admin governance UI exists under `apps/web/app/` — dictionary options,
   assumption sets, and patterns have no management surface in the frontend.

Everything else in M8 is complete: DictionaryOption CRUD, AssumptionSet versioning,
and JustificationRecord templates are all implemented and registered.

**Read before writing any code:**
1. `AGENTS.md` — governance rules, RBAC table (Admin role owns pattern mutations)
2. `apps/api/app/models/governance.py` — PatternDefinition, DictionaryOption, AssumptionSet models
3. `apps/api/app/routers/patterns.py` — current read-only state
4. `apps/api/app/routers/dictionaries.py` — reference implementation for governed CRUD
5. `apps/api/app/routers/assumptions.py` — reference for versioned governance
6. `apps/web/app/projects/[projectId]/catalog/page.tsx` — reference page implementation
7. `apps/web/lib/api.ts` — existing API client to extend

Do not rearchitect. Do not rename existing files. Fill the gaps only.

---

## Backend — PatternDefinition CRUD

### Current state of `apps/api/app/routers/patterns.py`
Only `GET /api/v1/patterns/` and `GET /api/v1/patterns/{pattern_id}` exist.

### What to add

**1. Extend `apps/api/app/schemas/reference.py` (or create if missing)**

```python
class PatternDefinitionCreate(BaseModel):
    pattern_id: str              # e.g. "#18" — must be unique, format: #NN
    name: str                    # e.g. "GraphQL Federation"
    category: str                # SÍNCRONO | ASÍNCRONO | SÍNCRONO + ASÍNCRONO
    description: Optional[str] = None
    components: Optional[list[str]] = None    # list of OCI components involved
    flow: Optional[str] = None               # short flow description

class PatternDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    components: Optional[list[str]] = None
    flow: Optional[str] = None

class PatternDefinitionResponse(BaseModel):
    pattern_id: str
    name: str
    category: str
    description: Optional[str]
    components: Optional[list[str]]
    flow: Optional[str]
    is_system: bool              # True for the 17 seeded patterns — cannot be deleted
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

**2. Add `is_system` flag to PatternDefinition model**

In `apps/api/app/models/governance.py`, add:
```python
is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

Generate an Alembic migration for this column:
```bash
cd apps/api
alembic revision --autogenerate -m "add_is_system_to_pattern_definitions"
alembic upgrade head
```

Then update `apps/api/app/migrations/seed.py` to set `is_system=True` on all 17
seeded patterns. Run seed idempotently (upsert, not insert — seed may already have run).

**3. Add service methods — `apps/api/app/services/reference_service.py`**

```python
async def create_pattern(data: PatternDefinitionCreate, db: AsyncSession) -> PatternDefinition:
    """
    Validate pattern_id format (#NN), check uniqueness.
    Create PatternDefinition with is_system=False.
    Emit AuditEvent(event_type='pattern_created').
    """

async def update_pattern(pattern_id: str, data: PatternDefinitionUpdate, db: AsyncSession) -> PatternDefinition:
    """
    Fetch pattern, apply partial update.
    Emit AuditEvent(event_type='pattern_updated', old_value=..., new_value=...).
    """

async def delete_pattern(pattern_id: str, db: AsyncSession) -> None:
    """
    Reject if is_system=True (raise HTTPException 409: 'System patterns cannot be deleted').
    Reject if any CatalogIntegration has selected_pattern == pattern_id
      (raise HTTPException 409: 'Pattern in use by N integrations').
    Delete. Emit AuditEvent(event_type='pattern_deleted').
    """
```

**4. Add endpoints to `apps/api/app/routers/patterns.py`**

```python
POST   /api/v1/patterns/                    # create custom pattern   201
PATCH  /api/v1/patterns/{pattern_id}        # update name/category/desc  200
DELETE /api/v1/patterns/{pattern_id}        # delete if not system + not in use  204
```

**5. Backend verification**

```bash
docker compose exec api python3 -c "
import httpx, sys
API = 'http://localhost:8000/api/v1'

# Create a custom pattern
r = httpx.post(f'{API}/patterns/', json={
    'pattern_id': '#18',
    'name': 'GraphQL Federation',
    'category': 'SÍNCRONO',
    'description': 'API-led data federation via GraphQL supergraph across microservices',
    'components': ['OCI API Gateway', 'Oracle Functions'],
})
assert r.status_code == 201, f'Create failed: {r.status_code} {r.text}'
print('Created:', r.json()['pattern_id'], r.json()['name'])

# Update it
r = httpx.patch(f'{API}/patterns/%2318', json={'description': 'Updated description'})
assert r.status_code == 200, f'Update failed: {r.status_code} {r.text}'
print('Updated:', r.json()['description'])

# Try deleting a system pattern — must reject
r = httpx.delete(f'{API}/patterns/%2301')
assert r.status_code == 409, f'Should have rejected system pattern delete: {r.status_code}'
print('System delete correctly rejected:', r.status_code)

# Delete the custom pattern
r = httpx.delete(f'{API}/patterns/%2318')
assert r.status_code == 204, f'Delete failed: {r.status_code} {r.text}'
print('Custom pattern deleted: OK')

# Confirm only 17 system patterns remain
r = httpx.get(f'{API}/patterns/')
count = r.json().get('total', len(r.json().get('patterns', [])))
assert count == 17, f'Expected 17 patterns, got {count}'
print(f'Pattern count: {count} — PASSED')
print('M8 BACKEND VERIFIED')
"
```

---

## Frontend — Admin Governance UI

### File structure

```
apps/web/
  app/
    admin/
      page.tsx                        # admin hub — links to each governance section
      patterns/
        page.tsx                      # pattern list + create + edit + delete
      dictionaries/
        page.tsx                      # dictionary options list + create + edit
        [category]/
          page.tsx                    # options for a specific category
      assumptions/
        page.tsx                      # assumption set list + version history
        [version]/
          page.tsx                    # view / edit a specific assumption set
  components/
    admin-pattern-form.tsx            # create/edit form for PatternDefinition
    admin-dictionary-form.tsx         # create/edit form for DictionaryOption
    admin-assumption-form.tsx         # view/edit form for AssumptionSet
    admin-confirm-delete.tsx          # reusable confirm-delete dialog
```

### Add to `apps/web/lib/api.ts`

```typescript
// Pattern admin
createPattern: (body: PatternDefinitionCreate) =>
  apiFetch<PatternDefinition>('/api/v1/patterns/', { method: 'POST', body: JSON.stringify(body) }),
updatePattern: (patternId: string, body: Partial<PatternDefinitionCreate>) =>
  apiFetch<PatternDefinition>(`/api/v1/patterns/${encodeURIComponent(patternId)}`,
    { method: 'PATCH', body: JSON.stringify(body) }),
deletePattern: (patternId: string) =>
  apiFetch<void>(`/api/v1/patterns/${encodeURIComponent(patternId)}`, { method: 'DELETE' }),

// Dictionary admin
createDictOption: (category: string, body: DictOptionCreate) =>
  apiFetch<DictOption>(`/api/v1/dictionaries/${category}`, { method: 'POST', body: JSON.stringify(body) }),
updateDictOption: (category: string, optionId: string, body: Partial<DictOptionCreate>) =>
  apiFetch<DictOption>(`/api/v1/dictionaries/${category}/${optionId}`,
    { method: 'PATCH', body: JSON.stringify(body) }),
deleteDictOption: (category: string, optionId: string) =>
  apiFetch<void>(`/api/v1/dictionaries/${category}/${optionId}`, { method: 'DELETE' }),

// Assumption sets
listAssumptions: () => apiFetch<AssumptionList>('/api/v1/assumptions/'),
getAssumption: (version: string) =>
  apiFetch<AssumptionSet>(`/api/v1/assumptions/${version}`),
createAssumption: (body: AssumptionSetCreate) =>
  apiFetch<AssumptionSet>('/api/v1/assumptions/', { method: 'POST', body: JSON.stringify(body) }),
updateAssumption: (version: string, body: Partial<AssumptionSetCreate>) =>
  apiFetch<AssumptionSet>(`/api/v1/assumptions/${version}`,
    { method: 'PATCH', body: JSON.stringify(body) }),
setDefaultAssumption: (version: string) =>
  apiFetch<AssumptionSet>(`/api/v1/assumptions/${version}/default`, { method: 'POST' }),
```

### Add to `apps/web/lib/types.ts`

```typescript
export interface PatternDefinitionCreate {
  pattern_id: string
  name: string
  category: 'SÍNCRONO' | 'ASÍNCRONO' | 'SÍNCRONO + ASÍNCRONO'
  description?: string
  components?: string[]
  flow?: string
}

export interface DictOptionCreate {
  code: string
  value: string
  description?: string
  executions_per_day?: number | null
}

export interface DictOption {
  id: string
  category: string
  code: string
  value: string
  description?: string
  executions_per_day?: number | null
}

export interface AssumptionSetCreate {
  version: string
  oic_billing_threshold_kb: number
  oic_pack_size_msgs_per_hour: number
  month_days: number
  oic_rest_max_payload_kb: number
  oic_ftp_max_payload_kb: number
  oic_kafka_max_payload_kb: number
  oic_timeout_s: number
  streaming_partition_throughput_mb_s: number
  functions_default_duration_ms: number
  functions_default_memory_mb: number
  functions_default_concurrency: number
}

export interface AssumptionSet extends AssumptionSetCreate {
  id: string
  is_default: boolean
  created_at: string
}

export interface AssumptionList { assumption_sets: AssumptionSet[]; total: number }
```

### Admin Hub — `apps/web/app/admin/page.tsx`

Server Component. Three navigation cards:

```
┌───────────────────────────────────────────────────────┐
│  Admin Governance                                      │
│  Manage reference data used across all projects        │
├─────────────────┬─────────────────┬───────────────────┤
│  OIC Patterns   │  Dictionaries   │  Assumptions      │
│  17 patterns    │  5 categories   │  1 active version │
│  Manage →       │  Manage →       │  Manage →         │
└─────────────────┴─────────────────┴───────────────────┘
```

Each card shows count (fetched server-side) and links to its section.
Display a warning banner: "Changes here affect all projects. System patterns
(seeded) cannot be deleted."

### Patterns Page — `apps/web/app/admin/patterns/page.tsx`

Client Component.

Table columns: Pattern ID | Name | Category | Components | System | Actions

- **System patterns** (is_system=true): show lock icon 🔒, no Delete button
- **Custom patterns**: show Edit (pencil) + Delete (trash) buttons
- **"New Pattern" button** → opens inline form or slide-over panel

`<AdminPatternForm />` fields:
- Pattern ID: text input, placeholder "#18", validates format `#\d+`
- Name: text input (required)
- Category: select — SÍNCRONO / ASÍNCRONO / SÍNCRONO + ASÍNCRONO
- Description: textarea
- OCI Components: multi-select checkboxes (list from TOOLS dictionary)
- Flow description: textarea

On save: `api.createPattern()` or `api.updatePattern()`. On success: refresh table.

Delete button → opens `<AdminConfirmDelete />` dialog:
> "Delete pattern #18 — GraphQL Federation? This cannot be undone."
> Confirm / Cancel

If API returns 409 (in use): show error message with count:
> "Cannot delete: 3 integrations are using this pattern. Reassign them first."

### Dictionaries Page — `apps/web/app/admin/dictionaries/page.tsx`

Server Component. Shows all 5 categories as expandable sections:
FREQUENCY | TRIGGER_TYPE | COMPLEXITY | QA_STATUS | TOOLS

Each section shows option count and a "Manage" link to `/admin/dictionaries/{category}`.

### Dictionary Category Page — `apps/web/app/admin/dictionaries/[category]/page.tsx`

Client Component.

Table: Code | Value | Description | Executions/Day | Actions (Edit / Delete)

- "New Option" button → inline form
- Edit → opens form pre-filled with current values
- Delete → confirm dialog, calls `api.deleteDictOption()`

`<AdminDictionaryForm />` fields:
- Code: text input (e.g. FREQ-14)
- Value: text input (e.g. "Cada 2 horas")
- Description: text input (optional)
- Executions per day: number input (optional — only relevant for FREQUENCY category)

### Assumptions Page — `apps/web/app/admin/assumptions/page.tsx`

Client Component.

Table: Version | Created | Is Default | Actions

- "New Version" button → opens `<AdminAssumptionForm />` pre-filled with current default values (clone-and-edit pattern)
- "Set as Default" button → calls `api.setDefaultAssumption(version)`
- Active default row highlighted with green badge

`<AdminAssumptionForm />` fields — grouped in two sections:

**OIC Parameters:**
- Billing threshold (KB): number input (default 50)
- Pack size (msgs/hour): number input (default 5000)
- REST max payload (KB): number input
- FTP max payload (KB): number input
- Kafka max payload (KB): number input
- Timeout (seconds): number input
- Month days: number input (default 30)

**OCI Services Parameters:**
- Streaming partition throughput (MB/s): number input
- Functions default duration (ms): number input
- Functions default memory (MB): number input
- Functions default concurrency: number input

On save: `api.createAssumption()`. Version string auto-incremented suggestion shown
as placeholder (e.g. "1.0.2" if current default is "1.0.1").

### Assumption Detail — `apps/web/app/admin/assumptions/[version]/page.tsx`

Server Component. Full read-only view of all assumption values for a specific version.
Shows which projects used this version for their last recalculation (if available).
"Set as Default" button (client component). "Clone as New Version" link → `/admin/assumptions/new?clone={version}`.

### Navigation update

Add "Admin" link to the main sidebar (global — not project-scoped).
Icon: `<Settings />` from lucide-react.
Position: below all project links, above Settings.
Only show when no project is selected or always visible at bottom of nav.

### Reusable component — `apps/web/components/admin-confirm-delete.tsx`

```typescript
// Props: title, description, onConfirm, onCancel, isLoading
// Renders a modal dialog with:
//   - Warning icon
//   - title as heading
//   - description as body
//   - "Delete" (red) and "Cancel" (gray) buttons
//   - isLoading → shows spinner on Delete button, disables both buttons
// Use Radix UI Dialog (@radix-ui/react-dialog — already installed)
```

---

## Definition of Done

Backend:
- [ ] `POST /api/v1/patterns/` creates a custom PatternDefinition, returns 201
- [ ] `PATCH /api/v1/patterns/{pattern_id}` updates name/category/description, returns 200
- [ ] `DELETE /api/v1/patterns/{pattern_id}` deletes non-system patterns, returns 204
- [ ] DELETE returns 409 when `is_system=True`
- [ ] DELETE returns 409 when pattern is in use by any CatalogIntegration
- [ ] Alembic migration adds `is_system` column
- [ ] Seed script marks all 17 original patterns with `is_system=True`
- [ ] AuditEvent emitted on create, update, delete

Frontend:
- [ ] `/admin` hub page loads with 3 section cards showing counts
- [ ] `/admin/patterns` lists all patterns with lock icon on system patterns
- [ ] "New Pattern" form creates a custom pattern visible in the table
- [ ] Edit updates pattern name/category/description in place
- [ ] Delete with confirm dialog removes custom pattern
- [ ] Delete attempt on system pattern shows 409 error message
- [ ] `/admin/dictionaries` lists 5 categories with option counts
- [ ] `/admin/dictionaries/{category}` allows create/edit/delete of options
- [ ] `/admin/assumptions` lists all assumption set versions
- [ ] "New Version" clones current default and allows editing all fields
- [ ] "Set as Default" marks a version active with green badge
- [ ] Admin link visible in sidebar navigation

Both:
- [ ] 26 parity tests still pass
- [ ] 0 TypeScript errors
- [ ] 0 ruff errors
- [ ] 6/6 Docker containers remain Up

---

## Final Verification

```bash
# Parity tests
docker compose exec api python3 -m pytest \
  /app/../../../packages/calc-engine/src/tests/ -v --tb=short

# Lint
docker compose exec api python3 -m ruff check /app/app/

# TypeScript
docker compose exec web npx tsc --noEmit --skipLibCheck

# Pattern CRUD smoke
docker compose exec api python3 -c "
import httpx
API = 'http://localhost:8000/api/v1'

r = httpx.post(f'{API}/patterns/', json={
    'pattern_id': '#99',
    'name': 'Smoke Test Pattern',
    'category': 'SÍNCRONO',
})
assert r.status_code == 201
pid = r.json()['pattern_id']

r = httpx.patch(f'{API}/patterns/{pid.replace(\"#\", \"%23\")}',
    json={'description': 'Updated'})
assert r.status_code == 200

r = httpx.delete(f'{API}/patterns/%2301')
assert r.status_code == 409, 'System pattern delete must be rejected'

r = httpx.delete(f'{API}/patterns/{pid.replace(\"#\", \"%23\")}')
assert r.status_code == 204

r = httpx.get(f'{API}/patterns/')
total = r.json().get('total', len(r.json().get('patterns', [])))
assert total == 17, f'Expected 17 after cleanup, got {total}'
print('M8 Pattern CRUD: PASSED')
"

# Admin pages reachable
curl -sf http://localhost:3000/admin > /dev/null && echo 'Admin hub: OK'
curl -sf http://localhost:3000/admin/patterns > /dev/null && echo 'Admin patterns: OK'
curl -sf http://localhost:3000/admin/dictionaries > /dev/null && echo 'Admin dicts: OK'
curl -sf http://localhost:3000/admin/assumptions > /dev/null && echo 'Admin assumptions: OK'
```
