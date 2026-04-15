# Codex Task — M9 + M10: Capture Interface & System Dependency Map

## Situation

Phase 1 (M1-M8) is complete and validated in Docker. All 6 containers are Up.
API is live at http://localhost:8000. Web is live at http://localhost:3000.
Parity: 144 loaded / 13 excluded / 157 TBQ=Y.

You are implementing two new features in a single build pass:
- **M9**: Guided integration capture wizard (form-based catalog entry)
- **M10**: Interactive system dependency map (D3 force graph)

Read the full spec for each before writing any code:
1. `codex-m9-capture.md` — complete M9 specification
2. `codex-m10-graph.md` — complete M10 specification
3. `AGENTS.md` — coding conventions, audit rules, RBAC
4. `apps/api/app/models/project.py` — CatalogIntegration full field list
5. `apps/api/app/routers/catalog.py` — existing endpoints
6. `apps/api/app/schemas/` — existing Pydantic schemas
7. `packages/calc-engine/src/engine/qa.py` — QA rules to mirror in TypeScript
8. `packages/calc-engine/src/engine/volumetry.py` — formulas used by /estimate

Do not start writing code until you have read all 8 files.
Do not rearchitect anything. Do not rename existing files or endpoints.
Do not modify `packages/calc-engine/` unless adding a new pure function with a test.

---

## Execution Order

Complete M9 fully before starting M10. M10 depends on the catalog having data.

---

## M9 — Integration Capture

### Backend (do this first)

**1. Add schema `ManualIntegrationCreate` and `OICEstimateRequest/Response`
to `apps/api/app/schemas/catalog.py`**

```python
class ManualIntegrationCreate(BaseModel):
    # Identity
    interface_id: Optional[str] = None
    brand: str
    business_process: str
    interface_name: str
    description: Optional[str] = None
    # Source
    source_system: str
    source_technology: Optional[str] = None
    source_api_reference: Optional[str] = None
    source_owner: Optional[str] = None
    # Destination
    destination_system: str
    destination_technology: Optional[str] = None
    destination_owner: Optional[str] = None
    # Technical
    type: Optional[str] = None
    frequency: Optional[str] = None
    payload_per_execution_kb: Optional[float] = None
    complexity: Optional[str] = None
    uncertainty: Optional[str] = None
    # Pattern
    selected_pattern: Optional[str] = None
    pattern_rationale: Optional[str] = None
    core_tools: Optional[list[str]] = None
    # Governance
    tbq: str = "Y"
    initial_scope: Optional[str] = None
    owner: Optional[str] = None

class OICEstimateRequest(BaseModel):
    frequency: Optional[str] = None
    payload_per_execution_kb: Optional[float] = None
    response_kb: float = 0.0

class OICEstimateResponse(BaseModel):
    billing_msgs_per_execution: Optional[float] = None
    billing_msgs_per_month: Optional[float] = None
    peak_packs_per_hour: Optional[float] = None
    executions_per_day: Optional[float] = None
    computable: bool   # False if frequency or payload is missing
```

**2. Add service method `manual_create_integration` to
`apps/api/app/services/catalog_service.py`**

Steps inside the method:
1. Query `MAX(source_row_number)` for the project → synthetic_row = max + 1
2. Create `SourceIntegrationRow(included=True, source_row_number=synthetic_row, raw_data=data.model_dump())`
3. Compute `executions_per_day` via `calc_engine.volumetry.executions_per_day()`
4. Compute `payload_per_hour_kb` via `calc_engine.volumetry.payload_per_hour_kb()`
5. Evaluate `qa_status, qa_reasons` via `calc_engine.qa.evaluate_qa()`
6. Create `CatalogIntegration` with all fields from data, computed fields, `tbq="Y"`
7. `await audit_service.emit(event_type="manual_capture", entity_type="catalog_integration", actor_id=actor_id, ...)`
8. Return `CatalogIntegration`

**3. Add four new endpoints to `apps/api/app/routers/catalog.py`**

```python
# Create individual integration (manual capture)
POST   /{project_id}                  → manual_create_integration()  201
# Autocomplete: unique systems already in catalog
GET    /{project_id}/systems          → list unique source+destination system names
# Duplicate detection before submit
GET    /{project_id}/duplicates       → query params: source_system, destination_system, business_process
# Live OIC cost estimate (no DB write)
POST   /{project_id}/estimate         → compute OIC metrics from frequency+payload, return immediately
```

For `/estimate`: load the default `AssumptionSet` from DB, call calc engine functions,
return `OICEstimateResponse`. If frequency or payload is null, return `computable=False`
with all metric fields as null.

For `/systems`: `SELECT DISTINCT source_system ... UNION SELECT DISTINCT destination_system ...`
WHERE project_id = X AND value IS NOT NULL. Return sorted list of strings.

For `/duplicates`: return list of `CatalogIntegrationResponse` where
source_system + destination_system + business_process all match. Empty list = no duplicates.

**4. Verify backend before touching frontend**

```bash
docker compose exec api python3 -c "
import httpx, json
API = 'http://localhost:8000/api/v1'

# Get existing project
projects = httpx.get(f'{API}/projects/').json()
pid = projects['projects'][0]['id']

# Test /systems
r = httpx.get(f'{API}/catalog/{pid}/systems')
assert r.status_code == 200
print('systems:', r.json())

# Test /estimate
r = httpx.post(f'{API}/catalog/{pid}/estimate',
    json={'frequency': 'Una vez al día', 'payload_per_execution_kb': 100})
assert r.status_code == 200
assert r.json()['computable'] == True
print('estimate:', r.json())

# Test /duplicates
r = httpx.get(f'{API}/catalog/{pid}/duplicates',
    params={'source_system': 'SAP', 'destination_system': 'Oracle', 'business_process': 'Finance'})
assert r.status_code == 200
print('duplicates:', len(r.json()), 'found')

# Test POST (create)
r = httpx.post(f'{API}/catalog/{pid}', json={
    'brand': 'TestBrand',
    'business_process': 'TestBP',
    'interface_name': 'Test Integration',
    'source_system': 'SystemA',
    'destination_system': 'SystemB',
})
assert r.status_code == 201, r.text
new_id = r.json()['id']
print('created:', new_id)

# Verify it appears in catalog list
r = httpx.get(f'{API}/catalog/{pid}?search=TestBrand')
assert r.json()['total'] >= 1
print('visible in catalog: OK')
print('M9 BACKEND VERIFIED')
"
```

Only proceed to frontend after this script exits cleanly.

### Frontend (M9)

**File structure to create:**
```
apps/web/
  app/projects/[projectId]/capture/
    page.tsx                     # capture history + "New Integration" CTA
    new/
      page.tsx                   # 5-step wizard shell
  components/
    capture-wizard.tsx           # wizard state machine + step renderer
    capture-step-identity.tsx    # Step 1
    capture-step-source.tsx      # Step 2
    capture-step-destination.tsx # Step 3
    capture-step-technical.tsx   # Step 4 — includes OIC estimate + QA preview
    capture-step-review.tsx      # Step 5
    oic-estimate-preview.tsx     # live OIC cost card (debounced fetch)
    qa-preview.tsx               # client-side QA rule checklist
    system-autocomplete.tsx      # text input with dropdown from /systems
```

**Add to `apps/web/lib/api.ts`:**
```typescript
createIntegration: (projectId: string, body: ManualIntegrationCreate) =>
  apiFetch<Integration>(`/api/v1/catalog/${projectId}`, { method: 'POST', body: JSON.stringify(body) }),
getSystems: (projectId: string) =>
  apiFetch<string[]>(`/api/v1/catalog/${projectId}/systems`),
checkDuplicates: (projectId: string, params: DuplicateCheckParams) => {
  const q = new URLSearchParams(params as Record<string, string>).toString()
  return apiFetch<Integration[]>(`/api/v1/catalog/${projectId}/duplicates?${q}`)
},
estimateOIC: (projectId: string, body: OICEstimateRequest) =>
  apiFetch<OICEstimateResponse>(`/api/v1/catalog/${projectId}/estimate`,
    { method: 'POST', body: JSON.stringify(body) }),
```

**Add to `apps/web/lib/types.ts`:**
```typescript
export interface ManualIntegrationCreate {
  interface_id?: string; brand: string; business_process: string
  interface_name: string; description?: string
  source_system: string; source_technology?: string
  source_api_reference?: string; source_owner?: string
  destination_system: string; destination_technology?: string
  destination_owner?: string; type?: string; frequency?: string
  payload_per_execution_kb?: number; complexity?: string
  uncertainty?: string; selected_pattern?: string
  pattern_rationale?: string; core_tools?: string[]
  tbq?: string; owner?: string
}
export interface OICEstimateRequest {
  frequency?: string; payload_per_execution_kb?: number; response_kb?: number
}
export interface OICEstimateResponse {
  billing_msgs_per_execution: number | null
  billing_msgs_per_month: number | null
  peak_packs_per_hour: number | null
  executions_per_day: number | null
  computable: boolean
}
export interface DuplicateCheckParams {
  source_system: string; destination_system: string; business_process: string
}
```

**Wizard behavior:**

Step progression: Identity → Source → Destination → Technical → Review

Each step validates with Zod before allowing Next. Required fields per step:
- Step 1: brand, business_process, interface_name
- Step 2: source_system
- Step 3: destination_system
- Step 4: no required fields (all optional)
- Step 5: review only, no new inputs

Duplicate check: fire `api.checkDuplicates()` after Step 3 when both
`source_system` and `destination_system` are set. Show warning card if results > 0,
but allow the user to continue.

OIC estimate (`oic-estimate-preview.tsx`): debounce 400ms, fires on any change to
`frequency` or `payload_per_execution_kb` in Step 4. Show skeleton while loading.
Show `computable=false` message when fields are empty.

QA preview (`qa-preview.tsx`): pure client-side, no API call. Mirror these rules
from `calc_engine/qa.py` in TypeScript:
```typescript
const rules = [
  { code: 'MISSING_ID_FORMAL',   label: 'Interface ID assigned',      pass: !!f.interface_id },
  { code: 'INVALID_TRIGGER_TYPE',label: 'Trigger type set',           pass: !!f.type },
  { code: 'INVALID_PATTERN',     label: 'OIC Pattern assigned',       pass: !!f.selected_pattern },
  { code: 'MISSING_RATIONALE',   label: 'Pattern rationale provided', pass: !f.selected_pattern || !!f.pattern_rationale },
  { code: 'MISSING_CORE_TOOLS',  label: 'Core tools selected',        pass: !!f.core_tools?.length },
  { code: 'MISSING_PAYLOAD',     label: 'Payload KB specified',        pass: f.payload_per_execution_kb != null },
  { code: 'TBD_UNCERTAINTY',     label: 'Uncertainty resolved',        pass: f.uncertainty !== 'TBD' },
]
```
Show green checkmark for pass, red X for fail. Derive `qa_status`: all pass → OK, else REVISAR.

On submit (Step 5): call `api.createIntegration()`. On 201 success, show:
```
✓ Integration captured — {interface_name}
[View in Catalog]   [Capture Another]
```
"Capture Another" resets wizard state to Step 1 with empty form.

Add "Capture" to sidebar nav under current project, between Import and Catalog.

---

## M10 — System Dependency Map

### Backend

**1. Create `apps/api/app/schemas/graph.py`**

```python
from pydantic import BaseModel
from typing import Optional

class GraphNode(BaseModel):
    id: str
    label: str
    integration_count: int
    as_source_count: int
    as_destination_count: int
    brands: list[str]
    business_processes: list[str]

class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    integration_count: int
    integration_ids: list[str]
    integration_names: list[str]
    business_processes: list[str]
    patterns: list[str]
    qa_statuses: dict[str, int]
    dominant_qa_status: str

class GraphMeta(BaseModel):
    node_count: int
    edge_count: int
    integration_count: int
    business_processes: list[str]
    brands: list[str]

class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    meta: GraphMeta
```

**2. Create `apps/api/app/services/graph_service.py`**

```python
async def compute_graph(
    project_id: str,
    business_process: Optional[str],
    brand: Optional[str],
    qa_status: Optional[str],
    db: AsyncSession,
) -> GraphResponse:
    # Load filtered catalog rows
    # Build nodes: union of all non-null source_system + destination_system values
    # Build edges: group by (source_system, destination_system) pairs
    # For each edge: collect integration_ids, names, BPs, patterns, qa_status counts
    # dominant_qa_status = max by count
    # Exclude rows where source_system or destination_system is None
    # Return GraphResponse
```

**3. Add endpoint to `apps/api/app/routers/catalog.py`**

```python
@router.get("/{project_id}/graph", response_model=GraphResponse)
async def get_graph(
    project_id: str,
    business_process: Optional[str] = None,
    brand: Optional[str] = None,
    qa_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await graph_service.compute_graph(project_id, business_process, brand, qa_status, db)
```

**4. Verify backend before touching frontend**

```bash
docker compose exec api python3 -c "
import httpx
API = 'http://localhost:8000/api/v1'
pid = httpx.get(f'{API}/projects/').json()['projects'][0]['id']
r = httpx.get(f'{API}/catalog/{pid}/graph')
assert r.status_code == 200, r.text
g = r.json()
assert g['meta']['node_count'] >= 2, f'Need at least 2 nodes, got {g[\"meta\"][\"node_count\"]}'
assert g['meta']['edge_count'] >= 1, f'Need at least 1 edge, got {g[\"meta\"][\"edge_count\"]}'
print(f'nodes={g[\"meta\"][\"node_count\"]} edges={g[\"meta\"][\"edge_count\"]} integrations={g[\"meta\"][\"integration_count\"]}')
print('M10 BACKEND VERIFIED')
"
```

### Frontend (M10)

**Install D3:**
```bash
cd apps/web && npm install d3 @types/d3
```

**File structure:**
```
apps/web/
  app/projects/[projectId]/graph/
    page.tsx                     # graph page shell + controls
  components/
    integration-graph.tsx        # SVG graph renderer (D3 force + React SVG)
    graph-detail-panel.tsx       # node/edge click detail panel
    graph-controls.tsx           # filter bar + zoom buttons + export
    graph-export-button.tsx      # PNG export via canvas
```

**Add to `apps/web/lib/api.ts`:**
```typescript
getGraph: (projectId: string, params?: GraphParams) => {
  const q = new URLSearchParams(params as Record<string, string> ?? {}).toString()
  return apiFetch<GraphResponse>(`/api/v1/catalog/${projectId}/graph?${q}`)
},
```

**Add to `apps/web/lib/types.ts`:**
```typescript
export interface GraphNode {
  id: string; label: string; integration_count: number
  as_source_count: number; as_destination_count: number
  brands: string[]; business_processes: string[]
}
export interface GraphEdge {
  id: string; source: string; target: string
  integration_count: number; integration_ids: string[]
  integration_names: string[]; business_processes: string[]
  patterns: string[]; qa_statuses: Record<string, number>
  dominant_qa_status: string
}
export interface GraphMeta {
  node_count: number; edge_count: number; integration_count: number
  business_processes: string[]; brands: string[]
}
export interface GraphResponse { nodes: GraphNode[]; edges: GraphEdge[]; meta: GraphMeta }
export interface GraphParams { business_process?: string; brand?: string; qa_status?: string }
```

**`integration-graph.tsx` — implementation rules:**

D3 force simulation is used only for computing (x, y) positions.
React + SVG handles all rendering. Never call `d3.select()` on the DOM.

```typescript
// Force simulation setup (run once per data change):
const sim = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(edges).id((d) => d.id).distance(120))
  .force('charge', d3.forceManyBody().strength(-400))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collision', d3.forceCollide().radius((d) => nodeRadius(d) + 20))

// Run 300 ticks synchronously (no animation)
sim.tick(300)
sim.stop()

// Extract final positions into React state
setPositions(nodes.map(n => ({ id: n.id, x: n.x, y: n.y })))
```

**SVG structure:**
```tsx
<svg width={width} height={height} style={{ transform: `scale(${zoom})` }}>
  <defs>
    <marker id="arrow" ...> {/* arrowhead */} </marker>
  </defs>
  {/* Edges first (rendered under nodes) */}
  {edges.map(edge => (
    <g key={edge.id} onClick={() => onEdgeClick(edge)} style={{ cursor: 'pointer' }}>
      <line
        x1={pos[edge.source].x} y1={pos[edge.source].y}
        x2={pos[edge.target].x} y2={pos[edge.target].y}
        strokeWidth={edgeWidth(edge.integration_count)}
        stroke={edgeColor(edge.dominant_qa_status)}
        markerEnd="url(#arrow)"
      />
    </g>
  ))}
  {/* Nodes */}
  {nodes.map(node => (
    <g key={node.id}
       transform={`translate(${pos[node.id].x}, ${pos[node.id].y})`}
       onClick={() => onNodeClick(node)}
       style={{ cursor: 'pointer' }}>
      <circle r={nodeRadius(node.integration_count)} fill={nodeColor(node, colorMode)} />
      <text textAnchor="middle" dy={nodeRadius(node.integration_count) + 14} fontSize={11}>
        {node.label}
      </text>
      <text textAnchor="middle" dy={4} fontSize={10} fill="white" fontWeight="bold">
        {node.integration_count}
      </text>
    </g>
  ))}
</svg>
```

**Visual encoding:**

Node radius: `20 + (integration_count / maxCount) * 30` (min 20px, max 50px)

Node color (qa mode):
```typescript
function nodeColor(node: GraphNode, mode: 'qa' | 'bp'): string {
  if (mode === 'bp') return BP_COLORS[bpIndex % 8]
  // Derive from edges involving this node
  if (allOK)    return '#22c55e'   // green
  if (allREV)   return '#f97316'   // orange
  if (hasPEND)  return '#6b7280'   // gray
  return '#eab308'                  // yellow (mixed)
}
```

Edge color:
```typescript
const EDGE_COLORS = { OK: '#86efac', REVISAR: '#fde047', PENDING: '#d1d5db' }
```

Edge width: `1.5 + (integration_count / maxEdgeCount) * 4.5` (min 1.5px, max 6px)

**Zoom:** maintain a `zoom` state (default 1.0). + button: zoom * 1.2, - button: zoom / 1.2,
Reset: zoom = 1.0. Apply as CSS `transform: scale(zoom)` on the SVG wrapper div.

**Warning for large graphs:**
```tsx
{nodes.length > 50 && (
  <div className="bg-yellow-900 text-yellow-200 p-3 rounded mb-4 text-sm">
    ⚠ {nodes.length} systems detected. Apply a filter to improve readability.
  </div>
)}
```

**`graph-detail-panel.tsx`:**

Node selected:
- System name as heading
- "As source: N" / "As destination: N"
- Business processes list
- Connected systems list: each with → or ← arrow and integration count
- "View in Catalog →" → `/projects/{pid}/catalog?source_system={node.id}`

Edge selected:
- "{source} → {target}" as heading
- Integration count badge
- QA breakdown: N OK / N REVISAR / N PENDING
- Patterns list
- Business processes list
- Integration list: name + qa_status badge for each
- "View all in Catalog →" → `/projects/{pid}/catalog?source_system={edge.source}&destination_system={edge.target}`

**`graph-export-button.tsx`:**
```typescript
function exportPNG(svgRef: RefObject<SVGSVGElement>, projectId: string) {
  const svg = svgRef.current
  const serializer = new XMLSerializer()
  const svgStr = serializer.serializeToString(svg)
  const img = new Image()
  img.onload = () => {
    const canvas = document.createElement('canvas')
    canvas.width = svg.clientWidth * 2   // 2x for retina
    canvas.height = svg.clientHeight * 2
    const ctx = canvas.getContext('2d')!
    ctx.scale(2, 2)
    ctx.drawImage(img, 0, 0)
    const a = document.createElement('a')
    a.download = `integration-map-${projectId}-${new Date().toISOString().slice(0,10)}.png`
    a.href = canvas.toDataURL('image/png')
    a.click()
  }
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgStr)
}
```

Add "Map" to sidebar nav under Catalog.
Icon: `<Network />` from lucide-react.

---

## Final Verification

Run after both M9 and M10 are complete:

```bash
# 1. Parity tests unchanged
docker compose exec api python3 -m pytest packages/calc-engine/src/tests/ -v
# Expected: 26 passed

# 2. API lint
docker compose exec api python3 -m ruff check /app/app/
# Expected: 0 errors

# 3. TypeScript
docker compose exec web npx tsc --noEmit --skipLibCheck
# Expected: 0 errors

# 4. M9 backend smoke
docker compose exec api python3 -c "
import httpx
API = 'http://localhost:8000/api/v1'
pid = httpx.get(f'{API}/projects/').json()['projects'][0]['id']

r = httpx.get(f'{API}/catalog/{pid}/systems')
assert r.status_code == 200

r = httpx.post(f'{API}/catalog/{pid}/estimate',
    json={'frequency': 'Una vez al día', 'payload_per_execution_kb': 500})
assert r.json()['computable'] == True
assert r.json()['billing_msgs_per_month'] > 0

r = httpx.post(f'{API}/catalog/{pid}', json={
    'brand': 'VerifyBrand', 'business_process': 'VerifyBP',
    'interface_name': 'Verify M9', 'source_system': 'SysA', 'destination_system': 'SysB'
})
assert r.status_code == 201
print('M9 backend: PASSED')
"

# 5. M10 backend smoke
docker compose exec api python3 -c "
import httpx
API = 'http://localhost:8000/api/v1'
pid = httpx.get(f'{API}/projects/').json()['projects'][0]['id']
r = httpx.get(f'{API}/catalog/{pid}/graph')
assert r.status_code == 200
g = r.json()
assert g['meta']['node_count'] >= 2
assert g['meta']['edge_count'] >= 1
print(f'M10 backend: PASSED — {g[\"meta\"][\"node_count\"]} nodes, {g[\"meta\"][\"edge_count\"]} edges')
"

# 6. UI reachability
curl -sf http://localhost:3000/projects > /dev/null && echo 'Web: UP'
curl -sf http://localhost:8000/health && echo 'API: UP'
```

---

## Definition of Done

M9:
- [ ] POST /api/v1/catalog/{projectId} creates integration + source row + audit event
- [ ] GET /api/v1/catalog/{projectId}/systems returns system list
- [ ] GET /api/v1/catalog/{projectId}/duplicates returns matching integrations
- [ ] POST /api/v1/catalog/{projectId}/estimate returns OIC preview, computable=true when fields set
- [ ] 5-step wizard renders and validates per step
- [ ] System autocomplete works in Steps 2 and 3
- [ ] Duplicate warning fires when source+destination+BP matches existing
- [ ] Live OIC estimate updates in Step 4 (debounced)
- [ ] QA rule checklist updates in real time in Step 4
- [ ] Submit creates integration, confirmation screen shows, "Capture Another" resets form
- [ ] Manually captured integration visible in Catalog grid

M10:
- [ ] GET /api/v1/catalog/{projectId}/graph returns nodes + edges + meta
- [ ] Filters (business_process, brand, qa_status) narrow graph correctly
- [ ] Graph renders in browser at /projects/{projectId}/graph
- [ ] Nodes sized by integration_count, colored by dominant QA status
- [ ] Edges show direction (arrowhead) and width scaled by integration_count
- [ ] Click node → detail panel shows system stats + connected systems
- [ ] Click edge → detail panel shows integration list with QA badges
- [ ] "View in Catalog" from detail panel navigates with filters pre-applied
- [ ] Color mode toggle (QA / Business Process) works
- [ ] Zoom +/- /reset works
- [ ] Export PNG downloads graph as file
- [ ] Warning shown when node_count > 50

Both:
- [ ] 26 parity tests pass
- [ ] 0 TypeScript errors
- [ ] 0 ruff errors
- [ ] All 6 Docker containers remain Up after build
