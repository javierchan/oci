# Codex Task — Canvas, Graph, Theme, Column Mapping, and Template Fixes

## Situation

A UX review of the running application identified 5 distinct issues across the
Integration Design Canvas, System Dependency Map, theme selector, raw column
display, and the import template workflow. This task resolves all of them.

No new database schema migrations. No new npm packages unless explicitly listed.
All code comments, variable names, and commit messages must be in English (US).
User-facing Spanish strings (labels, status values, UI text) are exempt.

---

## Pre-flight reads

Read these files before writing any code:

1. `apps/web/components/integration-canvas.tsx`
2. `apps/web/components/integration-patch-form.tsx`
3. `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx`
4. `apps/web/components/integration-graph.tsx`
5. `apps/web/components/graph-controls.tsx`
6. `apps/web/app/projects/[projectId]/graph/page.tsx`
7. `apps/web/lib/use-theme.ts`
8. `apps/web/app/layout.tsx`
9. `apps/web/components/import-upload.tsx`
10. `apps/web/app/projects/[projectId]/import/page.tsx`
11. `apps/web/lib/types.ts`
12. `apps/api/app/services/import_service.py` — understand raw column storage
13. `apps/api/app/services/export_service.py` — understand template generation

---

## ISSUE 1 — Raw column values: unnamed columns + non-editable inline

### 1a. Unnamed columns ("Column 4", "Column 10")

**Problem:** The integration detail page shows "Column 4" and "Column 10" as field
names in the RAW COLUMN VALUES table. These are positional fallbacks assigned by
the import engine when an Excel header does not map to a known schema field. The
user sees "Column 4" instead of the actual Excel header that was in row 1 of the
source file.

**Root cause to verify:** In `import_service.py`, when building `raw_column_values`,
check whether the code reads the actual header string from the source row or falls
back to `f"Column {index}"`. It should always store the actual header text, not a
positional label.

**Fix:**

In `import_service.py`, when constructing the raw column values dict for a row,
ensure the key is the actual Excel column header text (from the first row of the
sheet), not a generated `"Column N"` string. If the header cell is empty or None,
fall back to `f"Column {index + 1}"` (1-based is friendlier than 0-based).

If the actual header is already stored and "Column 4" is the real header text in
the workbook, then the display layer in the frontend should detect the pattern
`/^Column \d+$/` and render it in a muted italic style with a tooltip:
`"Header not recognized — rename in source file"`. This signals to the user that
the column has no semantic name.

### 1b. Raw column values must be editable inline

**Problem:** The RAW COLUMN VALUES table is read-only. Users need to correct import
errors or override values without re-importing the whole file.

**Fix in `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx`:**

Replace the static `<td>` cells in the raw column values table with inline-editable
cells. Requirements:

- Each value cell renders as plain text by default.
- On click (or focus), it becomes a single-line `<input>` with the current value
  pre-filled. Apply the existing dark-mode input baseline styles (from globals.css).
- On blur or Enter key: call `PATCH /api/v1/catalog/{project_id}/integrations/{integration_id}`
  with `{ raw_column_values: { ...existingValues, [fieldKey]: newValue } }` — or
  whatever the existing patch shape expects for raw values. Read the patch router
  and schema to confirm the exact field name.
- On Escape: cancel and revert to original value.
- Show a subtle pencil icon on row hover to signal editability.
- Show a brief "Saved" toast confirmation on success.
- Do not make the FIELD (key) column editable — only the SOURCE VALUE column.

---

## ISSUE 2 — Integration Design Canvas: allow repeated tool types + payload routing

### 2a. Current constraint

**Problem:** The canvas prevents placing more than one instance of the same tool
type (e.g., two OCI Functions nodes, two OCI Queue nodes). This makes it impossible
to design multi-step architectures like a fan-out/dispatcher pattern, which requires:

```
OIC → Queue (price-update-input) → OCI Function (fn-dispatcher)
  → fan-out: 2200 messages
  → Queue (price-update-workers) → OCI Function (fn-price-updater) [×N parallel]
    → DB Tienda (per store)
    → Dead Letter Queue
  → OCI Logging
  → OCI Monitoring → OCI Notifications
```

### 2b. Fix: instance-based node model

Read `integration-canvas.tsx` carefully. Find where new nodes are added and where
the constraint preventing duplicate types lives (likely a check like
`nodes.find(n => n.type === newTool.type)`). Remove that uniqueness constraint.

Change the node identity model so that each node is identified by a generated
`instanceId` (UUID), not by its tool type. A node shape should be:

```typescript
interface CanvasNode {
  instanceId: string   // crypto.randomUUID() at creation time
  type: string         // tool type key, e.g. "oci-function", "oci-queue"
  label: string        // user-editable display label, defaults to tool name
  x: number
  y: number
}
```

Multiple nodes of the same `type` are allowed as long as `instanceId` is unique.

### 2c. Fix: editable node labels

Each node on the canvas must have an editable label field so the user can name
instances distinctly (e.g., "fn-dispatcher" vs "fn-price-updater" for two OCI
Function nodes). Double-click on a node label opens an inline text input. On blur
or Enter the label is saved to canvas state.

### 2d. Fix: payload fan-out edges

**Problem:** Currently edges likely enforce a 1:1 connection (one source → one
target). Payload routing requires 1:N fan-out from a single node.

Allow multiple outgoing edges from a single node. Each edge is uniquely identified
by `{ sourceInstanceId, targetInstanceId }`. Do not limit outgoing edge count.

Add an optional edge label field (e.g., "2,200 msgs", "DLQ", "logs") that renders
as small text along the edge midpoint. The label should be editable on edge click.

### 2e. Payload distribution annotation

Add a lightweight "payload note" to each node — a small secondary text field below
the label (e.g., "120 KB → split ÷ 2,200"). This is free-form text, not computed.
It renders in a muted font size below the node label on the canvas.

### 2f. Persistence

The canvas state (nodes with instanceIds, labels, payload notes, and edges with
labels) must be persisted via the existing integration patch endpoint. Confirm the
field name used to store canvas state in `integration-patch-form.tsx` and ensure
the updated node/edge model is serialized to that field. Do not change the API
schema — adapt the frontend model to fit the existing storage shape.

---

## ISSUE 3 — System Dependency Map: oversized arrows + canvas interaction block

### 3a. Arrow/marker size

**Problem:** The SVG arrowhead markers on graph edges are rendering very large
relative to the edges and nodes, making the graph hard to read (visible in
browser screenshots: chevron-style markers are oversized).

**Fix in `integration-graph.tsx`:**

Find the `<marker>` SVG element definition. It likely has `markerWidth` and
`markerHeight` values that are too large (e.g., 10–20). Reduce them:

```svg
<marker
  id="arrowhead"
  markerWidth="6"
  markerHeight="6"
  refX="5"
  refY="3"
  orient="auto"
>
  <path d="M0,0 L0,6 L6,3 z" fill="currentColor" />
</marker>
```

Adjust `refX` so the arrowhead tip aligns precisely with the edge endpoint and
does not overlap the target node circle. Test with different zoom levels.

Also reduce the `stroke-width` of edges if it is currently above 2px at 100% zoom.
Edge width should encode connection count (as the legend states) but the baseline
(1 connection) should be `stroke-width="1.5"`, scaling up to a max of `4` for
high-count edges.

### 3b. Canvas interaction block

**Problem:** The graph canvas has a "block" — panning and/or interaction does not
respond correctly. Possible causes:

1. An invisible overlay `div` sits on top of the SVG with `pointer-events: auto`,
   capturing all mouse events before they reach the SVG.
2. The `onMouseDown`/`onMouseMove` pan handlers are attached to the wrong element
   (e.g., a wrapper div instead of the SVG itself).
3. `touch-action: none` is missing on the SVG element, causing mobile/trackpad
   conflicts.

**Fix:**

- Audit the element hierarchy in `integration-graph.tsx`. Confirm the SVG element
  has `style={{ touchAction: 'none' }}` and that no sibling or parent element has
  a z-index or pointer-events override that absorbs events.
- Confirm the pan `onMouseDown` handler is attached directly to the `<svg>` element,
  not to a wrapper.
- If there is a stats/legend overlay `div` (Nodes / Edges / Integrations counts),
  ensure it has `pointer-events: none` so it does not block canvas interaction
  below it.
- Confirm that the graph-controls panel (filter dropdowns, zoom buttons) has
  `pointer-events: auto` explicitly set so it remains interactive.
- After changes, verify: click-and-drag on the canvas background pans the graph;
  scroll-wheel zooms; clicking a node opens the detail panel.

---

## ISSUE 4 — Theme selector: double active state + UUID context label

### 4a. Double active state on navigation

**Problem:** When the theme is set to "System" (which resolves to "light" on the
user's OS), navigating to another page causes both "System" and "Light" buttons to
appear simultaneously selected (highlighted).

**Root cause to verify in `use-theme.ts` and wherever the theme toggle renders:**

The active-state logic likely evaluates two conditions independently:
- `theme === 'system'` → highlights "System"
- `resolvedTheme === 'light'` → also highlights "Light"

When `theme` is `'system'` and the resolved value is `'light'`, both conditions
are true at the same time.

**Fix:**

Active state must be determined solely by `theme` (the user's explicit choice),
not by `resolvedTheme`. Only one button should ever have the active class:

```typescript
const isActive = (btn: Theme) => theme === btn
```

Do not mix `resolvedTheme` into the active-state comparison. `resolvedTheme` is
only for applying the visual dark/light class to `document.documentElement`.

Also audit the no-flash inline script in `layout.tsx`. Confirm it reads and applies
the same storage key (`oci-dis-theme`) and does not set a secondary class that the
hook later misreads as a different active theme.

### 4b. UUID displayed as context label in dark mode

**Problem:** The sidebar "CONTEXT" section shows the raw project UUID
(`E2622877 34fe 4a25 8d61 1a201a45aa50`) instead of the page name ("Graph") when
in dark mode. In light mode it correctly shows "Graph".

**Root cause to verify:** The context label is likely computed from a value that
is resolved differently depending on when the component hydrates. In dark mode, the
page may be rendering before the project data fetch completes, falling back to
`params.projectId` (the UUID) as the display string. Light mode may hydrate later,
after the fetch, and shows the correct name.

**Fix:**

- Find where the "CONTEXT" label is set in the sidebar or layout component.
- Ensure the label defaults to the static page name ("Graph", "Catalog", "Import",
  etc.) based on the current route segment — not from an async project fetch.
- If the project name is shown separately, keep it below the page name and add a
  loading skeleton while the fetch resolves so it never falls back to the UUID.
- Apply this pattern consistently across all project sub-pages.

---

## ISSUE 5 — Excel import template: discoverable download with correct format

### 5a. Current state

A template download endpoint exists (`GET /api/v1/exports/template` or similar in
`exports.py`). The download action exists in `import-upload.tsx`. However, it is
not prominently surfaced — the user must know to look for it.

### 5b. Fix: dedicated template download section on Import page

In `apps/web/app/projects/[projectId]/import/page.tsx`, add a clearly separated
section **above** the file upload area with the following structure:

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1 — Download the import template                      │
│                                                             │
│  Use this template to ensure your data matches the          │
│  expected column order and format.                          │
│                                                             │
│  [↓ Download Template (.xlsx)]    Last updated: v1.0.0      │
│                                                             │
│  Required columns (in order):                               │
│  #, Interface Name, Brand, Business Process, ...            │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  STEP 2 — Upload your completed file                        │
│  [existing upload dropzone]                                 │
└─────────────────────────────────────────────────────────────┘
```

### 5c. Template format requirements

Read `export_service.py` → `generate_capture_template` to understand the exact
columns and order the template generates. The template must:

1. Have a header row in row 1 with the exact column names the import engine expects
   (these must match the keys in `import_service.py`'s column mapping).
2. Have a sample data row in row 2 showing realistic values (not just "example").
3. Have frozen top row and auto-filter enabled.
4. Have column widths set to readable defaults (minimum 15 characters wide).
5. Have a second sheet named "Reference" with a data dictionary: each column name,
   its data type, accepted values (for enum fields like Status, TBQ, Complexity),
   and whether it is required or optional.

### 5d. Column order alignment

Verify that the column order in the generated template matches exactly the order
the import engine reads. Mismatches cause silent mapping errors. In
`import_service.py`, identify the ordered list of expected headers. In
`export_service.py`, ensure the template column order is identical. If there is a
drift, fix the template to match the importer — do not change the importer logic.

### 5e. Template filename convention

The downloaded file should be named:
`oci-dis-import-template-v{version}.xlsx`

where `{version}` comes from the app version constant (currently `1.0.0`). Do not
use timestamps in the template filename — it is a static artifact.

---

## TASK 6 — Full verification pass

After all fixes are applied:

```bash
# Backend tests still pass
./.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -5

# Ruff still clean
./.venv/bin/python -m ruff check . 2>&1 | tail -5

# mypy (expect same baseline or better)
./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary 2>&1 | tail -10

# TypeScript clean
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -10; cd ../..

# ESLint (must be zero warnings — do not introduce new ones)
cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0 2>&1 | tail -10; cd ../..
```

All five gates must be clean. Fix any regressions introduced by this task before
proceeding.

---

## TASK 7 — Update docs/progress.md

Append the following entry:

```markdown
## Canvas, Graph, Theme, Column & Template UX Fix (2026-04-15)

**Status:** ✅ Complete

- ISSUE 1: Raw column values now show actual Excel header text; cells are
  inline-editable via PATCH with optimistic update and toast confirmation.
- ISSUE 2: Integration Design Canvas allows multiple instances of the same tool
  type (instance-based model); node labels are editable; edges support fan-out
  (1:N); edge labels and node payload notes added.
- ISSUE 3: Graph arrowhead markers resized to markerWidth/Height=6; edge
  stroke-width baseline reduced; canvas pan/zoom interaction unblocked by fixing
  pointer-events on overlay elements.
- ISSUE 4: Theme active state driven exclusively by `theme` (user choice), not
  `resolvedTheme`; sidebar context label sources page name from route segment,
  never falls back to UUID.
- ISSUE 5: Import page now has a two-step layout with a prominent template
  download section; template includes sample row, Reference sheet, frozen headers,
  and column order aligned with importer.
```

---

## Success criteria

- [ ] RAW COLUMN VALUES shows actual Excel header text (or muted "Column N" with tooltip)
- [ ] Each value in the raw column table is inline-editable; edits persist via PATCH
- [ ] Canvas accepts multiple OCI Function nodes, multiple OCI Queue nodes, etc.
- [ ] Canvas nodes have editable labels; double-click activates label edit
- [ ] Canvas edges support fan-out (one node → multiple targets)
- [ ] Canvas edge labels are editable on edge click
- [ ] Graph arrowheads are proportionate to node and edge size
- [ ] Graph canvas pan and zoom respond correctly (no invisible overlay block)
- [ ] Theme toggle: exactly one button active at all times; never two simultaneously
- [ ] Sidebar context label shows page name ("Graph"), never a UUID
- [ ] Import page shows two-step layout: template download above upload dropzone
- [ ] Template file: correct column order, sample row, Reference sheet, frozen headers
- [ ] All five quality gates still green after changes
