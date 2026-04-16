# Codex Task — UX Overhaul: Canvas, Catalog, Dashboard, Graph, and Detail Page

## Context

A full visual browser inspection identified 25 issues across all major surfaces.
This prompt addresses every finding grouped by impact tier. No new database schema
migrations. No new npm packages unless explicitly listed. All code comments,
variable names, and commit messages must be in English (US). User-facing Spanish
strings are exempt.

**Pre-flight reads — do this before writing any code:**

1. `apps/web/components/integration-canvas.tsx`
2. `apps/web/components/integration-patch-form.tsx`
3. `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx`
4. `apps/web/app/projects/[projectId]/catalog/page.tsx`
5. `apps/web/components/catalog-table.tsx`
6. `apps/web/app/projects/[projectId]/page.tsx` (dashboard)
7. `apps/web/components/integration-graph.tsx`
8. `apps/web/components/graph-detail-panel.tsx`
9. `apps/web/app/projects/[projectId]/capture/new/page.tsx`
10. `apps/web/app/projects/[projectId]/import/page.tsx`
11. `apps/web/lib/use-theme.ts`
12. `apps/web/app/not-found.tsx` or `apps/web/app/projects/[projectId]/not-found.tsx`

---

## TIER P0 — Breaks core workflow

### P0-1: Integration Design Canvas is a checkbox grid, not a canvas

**Finding:** The "Integration Design Canvas" is a 2-column grid of checkboxes
(OIC Gen3, OCI Queue, Oracle Functions, etc.). There are no positions, no edges,
no connections, and no visual flow. It is not a canvas.

**Required fix — replace with a flow-diagram canvas:**

The canvas must allow the user to design an integration flow from extraction to
insertion. Minimum viable implementation:

**Node model:**
```typescript
interface CanvasNode {
  instanceId: string        // crypto.randomUUID()
  toolKey: string           // e.g. "oci-queue", "oracle-functions"
  label: string             // editable, defaults to tool display name
  payloadNote: string       // free-form e.g. "120 KB ÷ 2,200"
  x: number
  y: number
}
```

**Edge model:**
```typescript
interface CanvasEdge {
  edgeId: string
  sourceInstanceId: string
  targetInstanceId: string
  label: string             // e.g. "fan-out 2,200 msgs"
}
```

**Canvas behavior:**
- Render an SVG canvas (minimum 800×500px) with a white/dark background
- Render a toolbar on the left or top with all available tools as draggable
  chips: OIC Gen3, OCI API Gateway, OCI Streaming, OCI Queue, Oracle Functions,
  OCI Data Integration, Oracle ORDS, ATP, Oracle DB, SFTP, OCI Object Storage,
  OCI APM
- Drag a tool chip onto the canvas to create a new node instance with a
  generated `instanceId`. Multiple instances of the same tool are allowed.
- Each node renders as a rounded rectangle with: tool icon (use a simple letter
  abbreviation if no icon is available), editable label (double-click to edit),
  and optional payload note below label in muted text
- **Connections:** when user hovers a node, show 4 connection handles (top, right,
  bottom, left) as small circles. Dragging from a handle to another node creates
  an edge. Render edges as SVG `<path>` lines with an arrowhead at the target end.
- **Edge labels:** click an edge to select it; show a small input to set an
  optional label rendered at the edge midpoint
- **Selection + delete:** click a node or edge to select it (highlight border).
  Press `Delete` or `Backspace` to remove selected element.
- **Pan:** click-and-drag on empty canvas background to pan
- **Zoom:** scroll wheel to zoom between 50%–200%
- Replace the old checkbox grid entirely. Compute `core_tools` for the patch
  payload as the unique set of `toolKey` values from all nodes in the canvas.

**Persistence:** serialize `{ nodes: CanvasNode[], edges: CanvasEdge[] }` to the
existing canvas state field in the integration patch endpoint. Read the current
field name from `integration-patch-form.tsx`.

### P0-2: Catalog renders all rows with no pagination

**Finding:** The catalog table renders all 144 rows in a single scrolling list.
No page controls are visible. This is a performance and usability issue at scale.

**Fix in `catalog-table.tsx`:**
- Implement client-side pagination: 20 rows per page by default
- Add Prev / Next buttons and a "Page X of Y" indicator in the table footer
- Add a rows-per-page selector with options: 20, 50, 100
- Preserve current filter and search state across page changes
- When filters change, reset to page 1

### P0-3: Non-existent project shows Next.js dev error overlay

**Finding:** Navigating to `/projects/[invalid-uuid]` triggers an unhandled
runtime error overlay showing the raw stack trace from `lib/api.ts`.

**Fix:**
- In `apps/api/app/routers/projects.py` confirm the endpoint returns HTTP 404
  for unknown project IDs (it does, based on the error body showing
  `PROJECT_NOT_FOUND`)
- In the Next.js project page, wrap the API call in a try/catch and redirect to
  a custom not-found page if the error code is `PROJECT_NOT_FOUND`
- Create `apps/web/app/projects/[projectId]/not-found.tsx` with a simple
  message: "Project not found" and a link back to `/projects`
- Alternatively, use Next.js `notFound()` helper in the page's `generateMetadata`
  or data-fetching function

---

## TIER P1 — Significantly degrades usability

### P1-1: Integration detail page — Interface Name shows Interface ID

**Finding:** The SOURCE DATA section shows `Interface Name: NW-001` which is the
same value as `Interface ID: NW-001`. The actual descriptive name ("Store Master
Sync") is stored in an unmapped raw column ("Column 5").

**Fix in the import service:**
Read `apps/api/app/services/import_service.py` and find where `interface_name` is
mapped from the source row. If the mapping falls back to the Interface ID when no
dedicated name column exists, check whether a column like "Interfaz" or "Interface"
in the source workbook contains the descriptive name. Update the column mapping to
read the correct source column for `interface_name`. Verify by checking the raw
column values table for NW-001: "Column 5" = "Store Master Sync" — that value
should be the interface name.

After fixing the mapping, confirm the Source Data section renders the descriptive
name, and that the Catalog grid `INTERFACE NAME` column also shows the descriptive
name.

### P1-2: Integration detail page — QA reasons are raw error codes

**Finding:** QA REASONS shows `INVALID_TRIGGER_TYPE`, `INVALID_PATTERN`,
`MISSING_RATIONALE`, `MISSING_CORE_TOOLS` — raw machine codes with no explanation.

**Fix:** Create a human-readable QA reason map. In the frontend, replace raw codes
with descriptive text:

```typescript
const QA_REASON_LABELS: Record<string, { title: string; hint: string }> = {
  INVALID_TRIGGER_TYPE: {
    title: 'Trigger type not recognized',
    hint: 'The trigger type value does not match any known OIC trigger. Check the Trigger Type field.',
  },
  INVALID_PATTERN: {
    title: 'Pattern not assigned',
    hint: 'Select an OIC integration pattern from the Pattern dropdown on the right.',
  },
  MISSING_RATIONALE: {
    title: 'Pattern rationale missing',
    hint: 'Add a brief explanation for the selected pattern in the Pattern Rationale field.',
  },
  MISSING_CORE_TOOLS: {
    title: 'No tools selected in canvas',
    hint: 'Use the Integration Design Canvas to add at least one tool to this integration.',
  },
}
```

Render each QA reason as a card with the title in bold, the hint below in muted
text, and an amber left border. If a code is not in the map, render the raw code
as a fallback.

### P1-3: Dashboard — backend payload not rendered

**Finding:** `dashboard_service.py` generates `kpi_strip`, `coverage`,
`completeness`, `pattern_mix`, `payload_distribution`, `risks`, and `maturity`.
The dashboard page only renders `kpi_strip` and the parity benchmark. The bottom
~60% of the page is blank.

**Fix in `apps/web/app/projects/[projectId]/page.tsx`:**

Fetch the full dashboard snapshot and render the additional sections:

**Pattern Mix** — a horizontal bar chart or proportional chip list showing the
breakdown of integration patterns (Request-Reply, Scheduled, Event-Driven, etc.)
and their counts. Use `recharts` `BarChart` or simple inline proportion bars.

**Payload Distribution** — a simple table or bar chart showing payload size
buckets (< 100KB, 100–500KB, > 500KB) and the count/percentage in each.

**Risks** — render the `risks` array as a list of risk cards. Each risk should
show severity (color-coded), title, and description.

**Maturity** — render the maturity score as a progress bar or percentage circle
with a label (e.g., "Governance Maturity: 68%").

Group these into a second row below the existing KPI strip. Use the existing
`app-card` class for each section. Do not change the API — only the frontend
consumption.

### P1-4: Graph — no auto-fit on load + no directional arrows

**Finding (a):** On initial load, nodes cluster at the top of the SVG canvas and
several nodes are cut off below the viewport. The graph never auto-centers.

**Fix:** After the D3 force simulation ticks settle (on `simulation.on('end')`),
compute the bounding box of all nodes and apply a translate+scale transform to
fit all nodes within the visible SVG viewport with 40px padding on all sides.

**Finding (b):** Edges are dashed lines without arrowheads. Direction of
integration flow (source → destination) is not visible.

**Fix:** Add SVG marker arrowheads. In the `<defs>` section of the SVG:

```svg
<marker id="arrow-revisar" markerWidth="6" markerHeight="6"
        refX="5" refY="3" orient="auto">
  <path d="M0,0 L0,6 L6,3 z" fill="#f97316" />
</marker>
<marker id="arrow-ok" markerWidth="6" markerHeight="6"
        refX="5" refY="3" orient="auto">
  <path d="M0,0 L0,6 L6,3 z" fill="#22c55e" />
</marker>
<marker id="arrow-mixed" markerWidth="6" markerHeight="6"
        refX="5" refY="3" orient="auto">
  <path d="M0,0 L0,6 L6,3 z" fill="#eab308" />
</marker>
```

Apply `marker-end="url(#arrow-{status})"` on each edge path. Shorten each edge
endpoint by the node radius + 4px so the arrowhead doesn't overlap the node circle.

### P1-5: Graph detail panel — "View in Catalog" should pre-filter

**Finding:** Clicking "View in Catalog" from the node selection panel navigates
to `/projects/[id]/catalog` without any filter applied. The user has to manually
search for the system.

**Fix:** Update the "View in Catalog" link to append a `?system=SystemName` query
parameter. In `catalog-table.tsx`, read the `system` query parameter on mount and
pre-populate the search field or apply a system filter.

---

## TIER P2 — UX polish with meaningful impact

### P2-1: Integration detail page — layout restructure

**Finding:** The right column (Architect Patch) is very long. Save button requires
scrolling past all checkboxes + QA reasons + audit trail to reach.

**Fix:**
- Make the Architect Patch panel sticky within the viewport: add
  `position: sticky; top: 1rem; max-height: calc(100vh - 2rem); overflow-y: auto`
  to the right column container
- Move the Save and Remove Integration buttons to the **top** of the right panel,
  below the "Assign pattern and governed tools" heading, so they are always visible
  without scrolling

### P2-2: Integration detail page — Audit Trail readable format

**Finding:** "Source lineage updated" entries show raw array index notation:
`0: 1`, `1: NW-001`, `2: Northwind Retail` — unreadable.

**Fix:** Map the array positions to field names using the known column order:
```typescript
const SOURCE_ROW_FIELD_NAMES = [
  '#', 'Interface Name', 'Brand', 'Business Process', 'Interface',
  'Description', 'Trigger Type', 'Status', 'Complexity', 'Initial Scope', ...
]
```
Render each entry as `FieldName: Value` instead of `0: Value`. If the column
count exceeds the known field list, fall back to `Column N: Value`.

### P2-3: Capture wizard — numbered step indicator with progress

**Finding:** Step pills (IDENTITY | SOURCE | DESTINATION | TECHNICAL | REVIEW)
have no step numbers, no connecting progress line, and no completed/pending
visual state.

**Fix:**
- Add a step number badge (1–5) inside each pill
- Connect pills with a thin horizontal line between them
- Completed steps (steps before the current step): filled background + checkmark
- Current step: blue border, bold label
- Pending steps: muted text, no border

### P2-4: Import page — required columns list not truncated

**Finding:** The "REQUIRED COLUMNS (IN ORDER)" list ends with "..." and does not
show all columns.

**Fix:** Remove the truncation. Show all columns in a horizontal scrollable
container or wrap to multiple lines. Users need the complete list to validate
their workbook before importing.

### P2-5: Admin hub — add recent activity summary

**Finding:** The Admin hub shows 3 count cards (17 patterns, 5 dictionaries,
2 assumptions) but no indication of recent changes or whether any require
attention.

**Fix:** Below each count card, add a "Last modified: [date]" line sourced from
the most recently updated record in each category. This requires reading
`updated_at` from the patterns/dictionaries/assumptions API responses.

### P2-6: Projects list — visual clutter from duplicate test projects

**Finding:** The projects list shows many "Docker Smoke #XXXX" entries that
clutter the list and make it hard to find real projects.

**Fix:**
- Add a text search/filter at the top of the projects list to filter by name
- Add an "Archived" toggle that shows/hides archived projects (Archive action
  already exists per row — just needs the visibility toggle)
- Sort projects by Created date descending by default (most recent first)

### P2-7: Graph — add filter by system node

**Finding:** No way to filter the graph to show only integrations connected to
a specific system. This is the most common use case for a dependency map.

**Fix:** Add a "System" filter dropdown to the graph controls bar, populated with
all unique system names (nodes) in the current graph. When a system is selected,
dim all nodes and edges not directly connected to that system (set opacity to 0.2),
and highlight the selected system and its neighbors.

---

## TASK — Register milestones in AGENTS.md and README.md

This UX overhaul work must be tracked as formal milestones in the project
documentation so the audit skill can assess completion on every run.

### Step A — Add milestones to AGENTS.md

In `AGENTS.md`, locate the `## Milestones` section (after M8). Append the
following three milestone definitions in the same format as M1–M8:

```markdown
### M15 — UX Overhaul P0: Core Workflow Fixes
- [ ] Integration Design Canvas rebuilt as SVG flow diagram with draggable nodes,
      connectable edges (with arrowheads), pan, and zoom
- [ ] Multiple instances of same tool type allowed (instance-based node model)
- [ ] Catalog table paginated at 20 rows/page with Prev/Next and rows-per-page selector
- [ ] Invalid project ID renders graceful not-found page (no Next.js dev error overlay)
- [ ] **Exit criteria**: Canvas renders a working flow; catalog paginates; 404 shows
      a user-friendly message; all 5 quality gates green

### M16 — UX Overhaul P1: Data Accuracy + Surface Completeness
- [ ] Interface Name shows descriptive name from source workbook (not Interface ID)
- [ ] QA Reasons rendered as human-readable cards with title + actionable hint
- [ ] Dashboard renders pattern mix, payload distribution, risks, and maturity
      from the full backend payload (not just KPI strip)
- [ ] Graph auto-fits all nodes on load with no nodes cut off below viewport
- [ ] Graph edges have directional arrowheads (source → destination)
- [ ] "View in Catalog" from graph node panel pre-filters catalog by system name
- [ ] **Exit criteria**: No integration detail shows ID as name; dashboard uses
      full backend payload; graph fits viewport; all quality gates green

### M17 — UX Overhaul P2: Layout + Polish
- [ ] Architect Patch Save button visible without scrolling (sticky panel or top placement)
- [ ] Audit Trail entries show field names instead of array index notation
- [ ] Capture wizard step pills numbered (1–5) with progress line and completed state
- [ ] Import page required columns list shows all columns without truncation
- [ ] Projects list has text filter and archived-projects toggle
- [ ] Graph has "filter by system" dropdown to highlight a system and its neighbors
- [ ] Admin hub shows "Last modified" date per governance category
- [ ] **Exit criteria**: All checklist items visually confirmed; no regressions;
      all quality gates green
```

### Step B — Update README.md milestone table

In `README.md`, locate the `## Milestones` table. Add three new rows:

```markdown
| M15 | UX Overhaul P0 — Canvas + Pagination + Error Handling | 🔲 Pending |
| M16 | UX Overhaul P1 — Data Accuracy + Surface Completeness | 🔲 Pending |
| M17 | UX Overhaul P2 — Layout + Polish | 🔲 Pending |
```

The status will be updated to ✅ Complete by each milestone's completion step.

### Step C — Update README.md milestone table status after each tier

After completing all P0 fixes (TIER P0 tasks above), update M15 → ✅ Complete.
After completing all P1 fixes, update M16 → ✅ Complete.
After completing all P2 fixes, update M17 → ✅ Complete.

### Step D — Append to docs/progress.md

After each milestone tier is complete, append an entry to `docs/progress.md`:

```markdown
## M15 — UX Overhaul P0: Core Workflow Fixes (YYYY-MM-DD)

**Status:** ✅ Complete

- Canvas rebuilt as SVG flow diagram with draggable tool nodes, connectable
  directed edges, pan, and zoom
- Catalog paginated at 20 rows/page
- Invalid project ID shows graceful not-found page

## M16 — UX Overhaul P1: Data Accuracy + Surface Completeness (YYYY-MM-DD)

**Status:** ✅ Complete

- Interface Name now resolved from correct source column
- QA Reasons rendered as human-readable guidance cards
- Dashboard renders pattern mix, payload distribution, risks, maturity
- Graph auto-fits on load with directed arrowheads
- "View in Catalog" pre-filters by system

## M17 — UX Overhaul P2: Layout + Polish (YYYY-MM-DD)

**Status:** ✅ Complete

- Architect Patch save button moved to top of right panel (sticky)
- Audit Trail shows field names
- Wizard step pills numbered with progress line
- All remaining polish items applied
```

Replace `YYYY-MM-DD` with the actual completion date.

---

## TASK — Verification

After all fixes, run:

```bash
./.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -5
./.venv/bin/python -m ruff check . 2>&1 | tail -5
./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary 2>&1 | tail -10
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -10; cd ../..
cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0 2>&1 | tail -10; cd ../..
```

All five gates must pass clean.

---

## Final Report — Required Before Task Close

Before finishing, produce a structured report with exactly these sections:

### Completed
List each fix applied with the file(s) changed and one line describing the change.

### Deferred
List any item NOT applied, with a specific reason:
- BLOCKER: [what is blocking it]
- RISK: [why it was skipped]
- DEPENDENCY: [what must happen first]

If nothing was deferred, write "None."

### Regressions Introduced
List any gate that was green before this task and is now failing.
If none: write "None."

### Gates
| Gate   | Before | After |
|--------|--------|-------|
| pytest | ✅     | ?     |
| ruff   | ✅     | ?     |
| mypy   | ✅     | ?     |
| tsc    | ✅     | ?     |
| eslint | ✅     | ?     |

Paste the actual terminal output for each gate verbatim — do not summarize.

---

## Success criteria

- [ ] Canvas renders SVG with draggable tool nodes, connectable edges, pan, zoom
- [ ] Multiple instances of the same tool type are allowed on canvas
- [ ] Catalog table paginates at 20 rows/page with Prev/Next controls
- [ ] Navigating to invalid project ID shows graceful not-found page, not dev overlay
- [ ] Interface Name shows descriptive name (not Interface ID) in Source Data
- [ ] QA Reasons render as human-readable cards with title + hint text
- [ ] Dashboard renders pattern mix, payload distribution, risks, and maturity
- [ ] Graph auto-fits all nodes on load with no nodes cut off
- [ ] Graph edges have directional arrowheads
- [ ] "View in Catalog" from graph node panel pre-filters by system name
- [ ] Architect Patch panel Save button is visible without scrolling
- [ ] Audit Trail entries show field names instead of array indices
- [ ] Capture wizard step pills have numbers, progress line, completed state
- [ ] Required columns list on Import page shows all columns without truncation
- [ ] Projects list has text filter and archived toggle
- [ ] All five quality gates green after changes
