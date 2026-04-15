# Codex Task — M10: System Dependency Map

## Context

The catalog has 144 integrations connecting multiple enterprise systems across
business processes. Right now the only way to see relationships is a flat table.
There is no visual representation of which systems talk to each other, how many
integrations exist between them, or how business processes flow across system
boundaries.

This milestone adds an interactive graph that renders the full integration topology:
systems as nodes, integrations as edges, business processes as overlaid groupings.
It serves two purposes:
1. **Discovery validation** — during client workshops, show the map in real time so
   stakeholders can confirm or challenge the integration topology being captured
2. **Architecture communication** — export the map as a snapshot for stakeholders
   who do not use the app directly

**Read before touching any code:**
1. `AGENTS.md` — conventions, no backend changes without explicit spec
2. `apps/api/app/models/project.py` — CatalogIntegration fields: source_system,
   destination_system, business_process, selected_pattern, qa_status, complexity
3. `apps/api/app/routers/catalog.py` — existing endpoints
4. `apps/web/package.json` — current dependencies

---

## Backend Changes Required

### New endpoint — `apps/api/app/routers/catalog.py`

```python
@router.get("/{project_id}/graph")
async def get_integration_graph(
    project_id: str,
    business_process: Optional[str] = None,   # filter to one BP
    brand: Optional[str] = None,
    qa_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> GraphResponse:
    """
    Computes the system dependency graph from the current catalog state.
    Returns nodes (systems) + edges (integrations) in a format ready for rendering.
    No pagination — returns the full graph, always computed fresh.
    """
```

### New schema — `apps/api/app/schemas/graph.py`

```python
from pydantic import BaseModel
from typing import Optional

class GraphNode(BaseModel):
    id: str                          # system name (unique)
    label: str                       # display label
    integration_count: int           # total integrations involving this node
    as_source_count: int             # integrations where this is source
    as_destination_count: int        # integrations where this is destination
    brands: list[str]                # unique brands using this system
    business_processes: list[str]    # unique BPs flowing through this system

class GraphEdge(BaseModel):
    id: str                          # f"{source_id}→{target_id}"
    source: str                      # source system node id
    target: str                      # destination system node id
    integration_count: int           # number of integrations on this edge
    integration_ids: list[str]       # catalog integration UUIDs
    integration_names: list[str]     # interface_name values for tooltip
    business_processes: list[str]    # unique BPs on this edge
    patterns: list[str]              # unique patterns assigned on this edge
    qa_statuses: dict[str, int]      # {"OK": 2, "REVISAR": 5, "PENDING": 0}
    dominant_qa_status: str          # status with highest count

class GraphMeta(BaseModel):
    node_count: int
    edge_count: int
    integration_count: int           # total integrations included in this graph
    business_processes: list[str]    # all unique BPs in the result
    brands: list[str]                # all unique brands

class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    meta: GraphMeta
```

### Service implementation — `apps/api/app/services/graph_service.py`

```python
async def compute_graph(
    project_id: str,
    filters: GraphFilters,
    db: AsyncSession,
) -> GraphResponse:
    """
    1. Load all CatalogIntegration rows for the project (apply filters)
    2. Extract unique systems: union of all source_system + destination_system values
    3. Build GraphNode for each system with aggregated counts
    4. Build GraphEdge for each unique (source_system, destination_system) pair
       - Multiple integrations on the same pair collapse into one edge
       - edge.integration_count = number of integrations on that pair
       - edge.dominant_qa_status = most frequent qa_status on the edge
    5. Return GraphResponse
    """
```

Rules:
- Systems where `source_system` or `destination_system` is NULL/empty are excluded
- Self-loops (source == destination) are included but visually flagged
- Direction is preserved: source → destination (graph is directed)

---

## Frontend

### New page — `apps/web/app/projects/[projectId]/graph/page.tsx`

Client Component (the graph requires browser interaction).

### Install D3.js

```bash
cd apps/web && npm install d3 @types/d3
```

D3 is the only new dependency permitted. It is used exclusively for force simulation
layout computation — not for DOM manipulation (React handles the DOM).

---

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  [Sidebar nav]  │  Integration Map                        [Controls] │
│                 │                                                      │
│                 │  ┌─────────────────────────────────────────────┐   │
│                 │  │                                             │   │
│                 │  │           SVG GRAPH CANVAS                  │   │
│                 │  │           (fills available height)          │   │
│                 │  │                                             │   │
│                 │  └─────────────────────────────────────────────┘   │
│                 │                                                      │
│                 │  ┌─────────────────────────────────────────────┐   │
│                 │  │  DETAIL PANEL (shows on node/edge click)    │   │
│                 │  └─────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Controls Bar (top-right of graph area)

- **Filter: Business Process** — multi-select dropdown (fetches unique BPs from graph meta)
- **Filter: Brand** — multi-select dropdown
- **Filter: QA Status** — checkboxes: OK / REVISAR / PENDING
- **Color mode** — toggle: "By QA Status" / "By Business Process"
- **Layout** — toggle: Force / Hierarchical (top-to-bottom)
- **Zoom controls** — + / - / Reset buttons
- **Export PNG** — captures the SVG canvas as a PNG download

---

### Graph Rendering — `apps/web/components/integration-graph.tsx`

Client Component. Uses D3 force simulation for layout, React + SVG for rendering.

```typescript
// Props:
//   nodes: GraphNode[]
//   edges: GraphEdge[]
//   colorMode: 'qa' | 'business_process'
//   onNodeClick: (node: GraphNode) => void
//   onEdgeClick: (edge: GraphEdge) => void

// Implementation:
// 1. On mount and when nodes/edges change:
//    - Initialize d3.forceSimulation()
//    - Forces: forceLink (edges), forceManyBody (repulsion), forceCenter
//    - Run simulation for 300 ticks, then freeze (no animation — instant layout)
//    - Store final (x, y) positions in React state
// 2. Render SVG:
//    - <defs> — arrowhead markers for directed edges
//    - Edges as <line> or <path> elements with curved paths for parallel edges
//    - Nodes as <circle> elements sized by integration_count
//    - Node labels as <text> elements below each circle
//    - Edge labels as <text> on path midpoint for business_process (optional, toggle)
// 3. Interactivity:
//    - onClick node → calls onNodeClick, highlights connected edges
//    - onClick edge → calls onEdgeClick, highlights involved nodes
//    - Mouse wheel → zoom (transform the SVG viewBox)
//    - Drag nodes → update position in state (re-render without re-running simulation)
```

#### Visual encoding

**Node size**: proportional to `integration_count` — min radius 20px, max 50px

**Node color** (qa mode):
- All OK: `#22c55e` (green)
- Mixed OK/REVISAR: `#eab308` (yellow)
- All REVISAR: `#f97316` (orange)
- Has PENDING: `#6b7280` (gray)

**Node color** (business_process mode):
- Assign a distinct Tailwind color per unique business process (cycle through 8 colors)
- Nodes shared across BPs get a striped fill (two colors)

**Edge width**: proportional to `integration_count` — min 1.5px, max 6px

**Edge color**:
- `dominant_qa_status === 'OK'` → `#86efac` (green-300)
- `dominant_qa_status === 'REVISAR'` → `#fde047` (yellow-300)
- `dominant_qa_status === 'PENDING'` → `#d1d5db` (gray-300)

**Edge arrow**: directed arrowhead at destination node

**Self-loop edges**: render as a small loop arc above the node

---

### Detail Panel — `apps/web/components/graph-detail-panel.tsx`

Renders below the graph canvas. Hidden by default. Opens when node or edge is clicked.

**Node click — shows system detail:**
```
┌─────────────────────────────────────────┐
│  SAP ECC                                │
│  ─────────────────────────────────────  │
│  As source:       12 integrations       │
│  As destination:   5 integrations       │
│  Business processes: Finance, HR, SCM   │
│  Brands: BrandA, BrandB                 │
│                                         │
│  Connected to:                          │
│  → Oracle ATP  (8 integrations)         │
│  → Salesforce  (4 integrations)         │
│  ← OCI Streaming (5 integrations)       │
│                                         │
│  [View in Catalog →]                    │
└─────────────────────────────────────────┘
```

**Edge click — shows integration list:**
```
┌─────────────────────────────────────────┐
│  SAP ECC → Oracle ATP                   │
│  8 integrations                         │
│  ─────────────────────────────────────  │
│  QA: 2 OK  /  6 REVISAR  /  0 PENDING  │
│  Patterns: #02 Batch, #05 Replication   │
│  Business processes: Finance, SCM       │
│                                         │
│  INTEGRATIONS:                          │
│  • INT-001  Material Master Sync  REVISAR│
│  • INT-002  Vendor Replication    OK    │
│  • INT-007  FI Document Transfer  REVISAR│
│  ...                                    │
│                                         │
│  [View all in Catalog →]               │
└─────────────────────────────────────────┘
```

"View all in Catalog →" navigates to `/projects/{projectId}/catalog?source_system=SAP+ECC&destination_system=Oracle+ATP`

---

### Navigation update

Add "Map" link to the sidebar under the current project navigation (after Catalog).
Icon: a network/graph icon from lucide-react (`Network` or `GitFork`).

---

### Export PNG — `apps/web/components/graph-export-button.tsx`

```typescript
// 1. Get reference to the SVG element
// 2. Serialize SVG to string
// 3. Create a canvas element, draw SVG onto it via Image
// 4. Call canvas.toDataURL('image/png')
// 5. Trigger download as 'integration-map-{projectId}-{date}.png'
// No external library needed — pure browser APIs
```

---

## Definition of Done

- [ ] `GET /api/v1/catalog/{projectId}/graph` returns nodes + edges + meta
- [ ] With 144 loaded integrations, graph has at least 2 nodes and 1 edge
- [ ] Filters (business_process, brand, qa_status) narrow the graph correctly
- [ ] Graph renders in browser at `/projects/{projectId}/graph`
- [ ] Nodes sized by integration count, colored by qa_status mode
- [ ] Edges show direction (arrowhead), width by integration count
- [ ] Clicking a node opens the detail panel with connected systems + integration counts
- [ ] Clicking an edge opens the detail panel with integration list
- [ ] "View in Catalog" link from detail panel navigates with correct filters pre-applied
- [ ] Color mode toggle (QA / Business Process) works without page reload
- [ ] Zoom controls (+ / - / reset) work
- [ ] Export PNG downloads the current graph as a file
- [ ] D3 simulation produces non-overlapping layout for graphs up to 30 nodes
- [ ] Parity tests: 26 passed
- [ ] TypeScript: 0 errors
- [ ] ruff: 0 errors

---

## Design Constraints

- D3 is used only for force simulation math — never for DOM manipulation
- All DOM elements are React JSX + SVG, not D3-rendered
- No graph layout library other than D3 force simulation
- The graph must be readable at 20 nodes without overlap
- If node count exceeds 50, display a warning and suggest applying a filter first
