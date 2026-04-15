# Codex Task — M11-M14: UI Enhancement Suite

## Situation

The application is functionally complete (M1-M10). This task focuses exclusively on
user experience quality: navigation, visual design, accessibility, and two new
high-value features (integration design canvas and offline capture template).

**Read before writing any code:**
1. `AGENTS.md` — conventions, stack constraints
2. `apps/web/lib/types.ts` — all TypeScript types
3. `apps/web/lib/api.ts` — existing API client
4. `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx` — detail page
5. `apps/web/app/projects/[projectId]/graph/page.tsx` — graph page
6. `apps/web/components/integration-graph.tsx` — current graph component
7. `apps/api/app/routers/exports.py` — exports router to extend

Do not touch backend services outside what is explicitly specified below.
Do not change database models. Do not add new npm packages beyond those listed.

---

## M11 — Navigation + Color System + Light/Dark Theme

### 11A — Contextual Navigation

Add navigation buttons that connect related entities so users never hit a dead end.

**Breadcrumb component — `apps/web/components/breadcrumb.tsx`**

```typescript
// Props: items: Array<{ label: string; href?: string }>
// Renders: Home > Projects > {project name} > Catalog > {integration name}
// Last item: no link (current page), previous items: clickable links
// Style: small text, muted color, chevron separator
```

Add `<Breadcrumb />` to the top of every page below the page heading.

| Page | Breadcrumb path |
|------|----------------|
| Projects list | Home |
| Project dashboard | Home > Projects > {name} |
| Import | Home > Projects > {name} > Import |
| Catalog | Home > Projects > {name} > Catalog |
| Integration detail | Home > Projects > {name} > Catalog > {interface_name} |
| Capture | Home > Projects > {name} > Capture |
| Capture new | Home > Projects > {name} > Capture > New |
| Graph | Home > Projects > {name} > Map |
| Admin | Home > Admin |
| Admin patterns | Home > Admin > Patterns |
| Admin dictionaries | Home > Admin > Dictionaries > {category} |
| Admin assumptions | Home > Admin > Assumptions |

**Contextual action buttons — add to these pages:**

Integration detail page — add below the page title:
```
← Back to Catalog   |   View Source Row →   |   View Audit Trail →
```
- "Back to Catalog" → `/projects/{pid}/catalog`
- "View Source Row" → links to import batch rows for this integration's `source_row_number`
- "View Audit Trail" → `/projects/{pid}/catalog/{id}#audit` (anchor to audit section)

Catalog page — add row action on each table row (rightmost column):
```
[View] [Edit]
```
- "View" → navigates to integration detail
- "Edit" → navigates to detail page with patch form pre-focused

Graph page — add in detail panel:
```
[View in Catalog →]   already exists — verify it passes source+destination filter
```

Import page — after successful upload:
```
[View imported rows →]   → /catalog?batch_id={batch_id}
```

Admin patterns page — after creating a custom pattern:
```
[View integrations using this pattern →]   → /projects/{pid}/catalog?pattern={pattern_id}
```

---

### 11B — Color System + Contrast

Replace all badge and status colors with a WCAG AA compliant soft palette.
Every color must achieve ≥ 4.5:1 contrast ratio against its background.
Use CSS custom properties defined in `apps/web/app/globals.css` so dark mode
overrides work from a single location.

**Define semantic color tokens in `globals.css`:**

```css
:root {
  /* QA Status */
  --color-qa-ok-bg: #dcfce7;        /* green-100 */
  --color-qa-ok-text: #15803d;      /* green-700 */
  --color-qa-ok-border: #86efac;    /* green-300 */

  --color-qa-revisar-bg: #fef9c3;   /* yellow-100 */
  --color-qa-revisar-text: #92400e; /* amber-800  */
  --color-qa-revisar-border: #fde047;/* yellow-300 */

  --color-qa-pending-bg: #f1f5f9;   /* slate-100 */
  --color-qa-pending-text: #475569; /* slate-600 */
  --color-qa-pending-border: #cbd5e1;/* slate-300 */

  /* Pattern categories */
  --color-pat-sync-bg: #dbeafe;     /* blue-100  */
  --color-pat-sync-text: #1e40af;   /* blue-800  */

  --color-pat-async-bg: #ede9fe;    /* violet-100 */
  --color-pat-async-text: #5b21b6;  /* violet-800 */

  --color-pat-both-bg: #fae8ff;     /* fuchsia-100 */
  --color-pat-both-text: #86198f;   /* fuchsia-800 */

  /* Complexity */
  --color-complexity-alto-bg: #fee2e2;   /* red-100   */
  --color-complexity-alto-text: #991b1b; /* red-800   */
  --color-complexity-medio-bg: #ffedd5;  /* orange-100*/
  --color-complexity-medio-text: #9a3412;/* orange-800*/
  --color-complexity-bajo-bg: #f0fdf4;   /* green-50  */
  --color-complexity-bajo-text: #166534; /* green-800 */

  /* Table */
  --color-table-header-bg: #f8fafc;  /* slate-50  */
  --color-table-row-hover: #f1f5f9;  /* slate-100 */
  --color-table-border: #e2e8f0;     /* slate-200 */

  /* App surface */
  --color-surface: #ffffff;
  --color-surface-2: #f8fafc;
  --color-surface-3: #f1f5f9;
  --color-text-primary: #0f172a;     /* slate-900 */
  --color-text-secondary: #475569;   /* slate-600 */
  --color-text-muted: #94a3b8;       /* slate-400 */
  --color-border: #e2e8f0;           /* slate-200 */
  --color-accent: #3b82f6;           /* blue-500  */
  --color-accent-hover: #2563eb;     /* blue-600  */
}

.dark {
  --color-qa-ok-bg: #052e16;
  --color-qa-ok-text: #86efac;
  --color-qa-ok-border: #166534;

  --color-qa-revisar-bg: #422006;
  --color-qa-revisar-text: #fde047;
  --color-qa-revisar-border: #854d0e;

  --color-qa-pending-bg: #1e293b;
  --color-qa-pending-text: #94a3b8;
  --color-qa-pending-border: #334155;

  --color-pat-sync-bg: #1e3a5f;
  --color-pat-sync-text: #93c5fd;

  --color-pat-async-bg: #2e1065;
  --color-pat-async-text: #c4b5fd;

  --color-pat-both-bg: #4a044e;
  --color-pat-both-text: #f0abfc;

  --color-complexity-alto-bg: #450a0a;
  --color-complexity-alto-text: #fca5a5;
  --color-complexity-medio-bg: #431407;
  --color-complexity-medio-text: #fdba74;
  --color-complexity-bajo-bg: #052e16;
  --color-complexity-bajo-text: #86efac;

  --color-surface: #0f172a;
  --color-surface-2: #1e293b;
  --color-surface-3: #334155;
  --color-text-primary: #f8fafc;
  --color-text-secondary: #94a3b8;
  --color-text-muted: #475569;
  --color-border: #334155;
  --color-accent: #60a5fa;
  --color-accent-hover: #93c5fd;
}
```

**Update `<QaBadge />`** to use CSS variables:
```tsx
const styles = {
  OK:      'bg-[var(--color-qa-ok-bg)] text-[var(--color-qa-ok-text)] border border-[var(--color-qa-ok-border)]',
  REVISAR: 'bg-[var(--color-qa-revisar-bg)] text-[var(--color-qa-revisar-text)] border border-[var(--color-qa-revisar-border)]',
  PENDING: 'bg-[var(--color-qa-pending-bg)] text-[var(--color-qa-pending-text)] border border-[var(--color-qa-pending-border)]',
}
```

**Update `<PatternBadge />`** — derive color from pattern category:
```tsx
function patternColor(category: string) {
  if (category === 'SÍNCRONO') return 'bg-[var(--color-pat-sync-bg)] text-[var(--color-pat-sync-text)]'
  if (category === 'ASÍNCRONO') return 'bg-[var(--color-pat-async-bg)] text-[var(--color-pat-async-text)]'
  return 'bg-[var(--color-pat-both-bg)] text-[var(--color-pat-both-text)]'
}
```

**New `<ComplexityBadge />` component** — `apps/web/components/complexity-badge.tsx`:
Apply same pattern as QaBadge using complexity color tokens.
Add to catalog table as a new column between Frequency and QA Status.

**Table improvements:**
- Header row: `bg-[var(--color-table-header-bg)]`, `text-[var(--color-text-secondary)]`,
  `text-xs uppercase tracking-wide font-semibold`
- Data rows: `text-[var(--color-text-primary)]`, hover `bg-[var(--color-table-row-hover)]`
- Muted secondary text (interface_id, source_row_number):
  `text-[var(--color-text-muted)] text-sm`
- All borders: `border-[var(--color-border)]`

---

### 11C — Light/Dark Theme

**1. Install no new packages.** Tailwind's `darkMode: 'class'` is sufficient.

**Verify `tailwind.config.js`** has:
```js
darkMode: 'class',
```
If not, add it.

**2. Create theme hook — `apps/web/lib/use-theme.ts`**

```typescript
'use client'
import { useState, useEffect } from 'react'

type Theme = 'light' | 'dark' | 'system'

export function useTheme() {
  const [theme, setTheme] = useState<Theme>('system')

  useEffect(() => {
    const stored = localStorage.getItem('theme') as Theme | null
    if (stored) setTheme(stored)
  }, [])

  useEffect(() => {
    const root = document.documentElement
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    const isDark = theme === 'dark' || (theme === 'system' && prefersDark)
    root.classList.toggle('dark', isDark)
    if (theme !== 'system') localStorage.setItem('theme', theme)
  }, [theme])

  return { theme, setTheme }
}
```

**3. Theme toggle component — `apps/web/components/theme-toggle.tsx`**

```tsx
'use client'
// Three-state toggle: Light | System | Dark
// Icons: Sun / Monitor / Moon (from lucide-react)
// Renders as a small segmented button group
// Position: bottom of sidebar nav, above version badge
```

**4. Update root layout** — wrap body with theme initialization script to prevent
flash of wrong theme:

```tsx
// In apps/web/app/layout.tsx, add inside <head>:
<script dangerouslySetInnerHTML={{ __html: `
  (function() {
    var theme = localStorage.getItem('theme') || 'system';
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (theme === 'dark' || (theme === 'system' && prefersDark)) {
      document.documentElement.classList.add('dark');
    }
  })();
` }} />
```

**5. Apply theme-aware colors to all layout surfaces:**

Sidebar: `bg-[var(--color-surface-2)] border-r border-[var(--color-border)]`
Main content: `bg-[var(--color-surface)]`
Cards/panels: `bg-[var(--color-surface-2)] border border-[var(--color-border)]`
All text: `text-[var(--color-text-primary)]` (primary) / `text-[var(--color-text-secondary)]` (labels)

---

## M12 — Source Lineage Column Names + Excel Capture Template

### 12A — Source Lineage Column Names

**Problem:** `SourceIntegrationRow.raw_data` is stored as `{"0": "SAP", "1": "REST", ...}`
(column index → value). The frontend renders these as "Column 0", "Column 1" etc.
The ImportBatch has a `header_map` that maps canonical field names → column indices.
Inverting this gives us column index → field name.

**Backend fix — extend lineage response**

In `apps/api/app/schemas/catalog.py`, update `LineageDetail`:

```python
class LineageDetail(BaseModel):
    source_row_number: int
    raw_data: dict[str, Any]
    column_names: dict[str, str]   # NEW: column_index_str → human_readable_name
    normalization_events: list[NormalizationEvent]
    import_batch_id: str
    import_batch_date: datetime
```

In `apps/api/app/services/catalog_service.py`, update `get_lineage()`:

```python
# 1. Fetch the SourceIntegrationRow for this integration
# 2. Fetch the ImportBatch that created it (via import_batch_id)
# 3. Invert header_map: {field_name: col_idx} → {col_idx: field_name}
# 4. Build human-readable label map using FIELD_LABELS dict below
# 5. Return LineageDetail with column_names populated

FIELD_LABELS = {
    "seq_number": "#",
    "interface_id": "Interface ID",
    "brand": "Brand",
    "business_process": "Business Process",
    "interface_name": "Interface Name",
    "description": "Description",
    "type": "Trigger Type",
    "interface_status": "Interface Status",
    "complexity": "Complexity",
    "initial_scope": "Initial Scope",
    "status": "Status",
    "mapping_status": "Mapping Status",
    "source_system": "Source System",
    "source_technology": "Source Technology",
    "source_api_reference": "Source API Reference",
    "source_owner": "Source Owner",
    "destination_system": "Destination System",
    "destination_technology": "Destination Technology",
    "destination_owner": "Destination Owner",
    "frequency": "Frequency",
    "payload_per_execution_kb": "Payload (KB)",
    "tbq": "TBQ",
    "patterns": "Patterns",
    "uncertainty": "Uncertainty",
    "owner": "Owner",
    "identified_in": "Identified In",
    "business_process_dd": "Business Process (DD)",
    "slide": "Slide",
}

# For columns not in header_map (extra columns in source):
# label as "Column {N}"
```

**Frontend fix — integration detail page**

In the Source Lineage section, replace:
```tsx
// Before:
Object.entries(lineage.raw_data).map(([col, val]) => (
  <tr><td>Column {col}</td><td>{val}</td></tr>
))

// After:
Object.entries(lineage.raw_data).map(([col, val]) => {
  const name = lineage.column_names?.[col] ?? `Column ${col}`
  return <tr><td className="font-medium">{name}</td><td>{String(val ?? '—')}</td></tr>
})
```

Table layout for Source Lineage:

```
┌──────────────────────┬────────────────────────────────┐
│ Field                │ Source Value                   │
├──────────────────────┼────────────────────────────────┤
│ Interface ID         │ INT-001                        │
│ Brand                │ Oracle                         │
│ Business Process     │ Finance & Accounting           │
│ Interface Name       │ GL Journal Entry Sync          │
│ Source System        │ SAP ECC                        │
│ Destination System   │ Oracle ATP                     │
│ Frequency            │ Una vez al día                 │
│ Payload (KB)         │ 150                            │
│ TBQ                  │ Y                              │
└──────────────────────┴────────────────────────────────┘
```

Show only columns where value is not null/empty. Collapse the rest under
"Show all columns ({N})" expandable toggle.

---

### 12B — Excel Capture Template Export

A downloadable XLSX pre-formatted for offline integration capture.
Users fill it in Excel/Numbers, then upload via the Import page.

**New backend endpoint — `apps/api/app/routers/exports.py`**

```python
@router.get("/template/xlsx")
async def download_capture_template(db: AsyncSession = Depends(get_db)):
    """
    Returns a pre-formatted XLSX file ready for offline integration capture.
    No project_id required — the template is project-agnostic.
    """
```

**New service — `apps/api/app/services/export_service.py`** (add method):

```python
async def generate_capture_template(db: AsyncSession) -> bytes:
    """
    Builds an XLSX workbook that:
    1. Rows 1-4: Instructions sheet metadata
    2. Row 5: Headers (matching HEADER_ALIASES in importer.py)
    3. Row 6: Example row with placeholder values
    4. Row 7+: Empty rows with data validation dropdowns
    5. Column widths: auto-fit to header + 20%
    6. Frozen row 5 (header row)
    7. Excel dropdown validation for governed columns
    Returns workbook as bytes.
    """
```

Template structure:

**Row 1:** Title cell: "OCI DIS Blueprint — Integration Capture Template"
**Row 2:** Instructions: "Fill from row 7 onwards. Do not modify rows 1-5.
            Required fields marked with *. TBQ column must be Y for import."
**Row 3:** Version: "Template v1.0 — generated {date}"
**Row 4:** Empty

**Row 5 headers** (matching importer.py HEADER_ALIASES exactly):

| Column | Header | Required | Color |
|--------|--------|----------|-------|
| A | # | No | Gray |
| B | ID de Interfaz | No | Gray |
| C | Marca | Yes | Blue |
| D | Proceso de Negocio | Yes | Blue |
| E | Interfaz | Yes | Blue |
| F | Descripción | No | Gray |
| G | Tipo | No | Yellow |
| H | Estado Interfaz | No | Gray |
| I | Complejidad | No | Yellow |
| J | Alcance Inicial | No | Gray |
| K | Estado | No | Gray |
| L | Estado de Mapeo | No | Gray |
| M | Sistema de Origen | Yes | Blue |
| N | Tecnología de Origen | No | Yellow |
| O | API Reference | No | Gray |
| P | Propietario de Origen | No | Gray |
| Q | Sistema de Destino | Yes | Blue |
| R | Tecnología de Destino | No | Yellow |
| S | Propietario de Destino | No | Gray |
| T | Frecuencia | Yes | Blue |
| U | Tamaño KB | No | Yellow |
| V | TBQ | Yes | Blue |
| W | Patrones | No | Gray |
| X | Incertidumbre | No | Gray |
| Y | Owner | No | Gray |

Header row styling:
- Required (Blue): `fill=4472C4, font=white, bold`
- Optional governed (Yellow): `fill=FFC000, font=black, bold`
- Optional free-text (Gray): `fill=808080, font=white, bold`

**Row 6 — Example row** (italic, gray text, pre-filled):
```
1 | INT-001 | Oracle | Finance & Accounting | GL Journal Entry Sync |
Nightly GL sync from SAP to Oracle ATP | Scheduled | En Progreso | Medio |
Si | En Progreso | Pendiente | SAP ECC | REST | /api/v1/gl |
Finance Team | Oracle ATP | REST | ATP Team | Una vez al día | 150 | Y |
#02 | | Finance Architect
```

**Excel data validation dropdowns** (rows 7-200):

Load values from DB at generation time:
- Column T (Frecuencia): dropdown from `dictionary_options WHERE category='FREQUENCY'` values
- Column G (Tipo): dropdown from `TRIGGER_TYPE` values
- Column I (Complejidad): dropdown from `COMPLEXITY` values
- Column V (TBQ): dropdown `Y,N`

Use `openpyxl.worksheet.datavalidation.DataValidation` for each governed column.

Response headers:
```python
return Response(
    content=xlsx_bytes,
    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    headers={"Content-Disposition": "attachment; filename=oci-dis-capture-template.xlsx"}
)
```

**Frontend — add download button to Import page**

In `apps/web/app/projects/[projectId]/import/page.tsx`, add above the upload zone:

```tsx
<div className="flex items-center justify-between mb-4">
  <h2>Upload Integration Workbook</h2>
  <a
    href={`${API_BASE}/api/v1/exports/template/xlsx`}
    download="oci-dis-capture-template.xlsx"
    className="flex items-center gap-2 text-sm px-3 py-2 rounded border
               border-[var(--color-border)] text-[var(--color-text-secondary)]
               hover:bg-[var(--color-surface-2)] transition-colors"
  >
    <Download className="w-4 h-4" />
    Download capture template
  </a>
</div>
```

---

## M13 — Integration Design Canvas

When core tools are selected in the integration patch form, render a visual
flow diagram below the form showing how the integration would be implemented
using the selected OCI components.

### New component — `apps/web/components/integration-canvas.tsx`

```typescript
// Props:
//   sourceSystem: string
//   sourceTechnology: string | null
//   destinationSystem: string | null
//   destinationTechnology: string | null
//   selectedPattern: string | null       // e.g. "#05"
//   coreTools: string[]                  // e.g. ["OCI Gen3", "Oracle ATP"]
//   payloadKb: number | null
//   frequency: string | null
//   patternCategory: 'SÍNCRONO' | 'ASÍNCRONO' | 'SÍNCRONO + ASÍNCRONO' | null

// Renders: SVG/HTML flow diagram of the integration architecture
```

### Canvas layout

```
┌────────────────────────────────────────────────────────────────────┐
│  Integration Design Canvas                                         │
│                                                                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────────┐  │
│  │ SAP ECC  │───▶│ OIC Gen3 │───▶│ Transform│───▶│ Oracle ATP │  │
│  │  (REST)  │    │  Adapter │    │  Engine  │    │   (JDBC)   │  │
│  └──────────┘    └──────────┘    └──────────┘    └────────────┘  │
│                                                                    │
│  Payload: 150 KB/exec  →  2 billing msgs/exec  →  Stored in ATP  │
│  Pattern: #05 Data Replication  |  Frequency: Una vez al día      │
│  Estimated OIC msgs/month: 2                                       │
└────────────────────────────────────────────────────────────────────┘
```

### Node types

Render nodes as rounded rectangles with icons. Map each item to a node type:

```typescript
type NodeKind = 'system' | 'oic' | 'streaming' | 'functions' | 'gateway' | 'storage' | 'db'

const TOOL_KINDS: Record<string, NodeKind> = {
  'OCI Gen3':           'oic',
  'OCI API Gateway':    'gateway',
  'OCI Streaming':      'streaming',
  'OCI Queue':          'streaming',
  'Oracle Functions':   'functions',
  'OCI Data Integration': 'oic',
  'Oracle ORDS':        'db',
  'ATP':                'db',
  'Oracle DB':          'db',
  'SFTP':               'storage',
  'OCI Object Storage': 'storage',
  'OCI APM':            'oic',
}

// Node colors per kind (use CSS variables for dark mode):
const KIND_COLORS = {
  system:    { bg: '#dbeafe', border: '#3b82f6', icon: '🏢' },
  oic:       { bg: '#ede9fe', border: '#8b5cf6', icon: '⚙️' },
  streaming: { bg: '#fef3c7', border: '#f59e0b', icon: '⚡' },
  functions: { bg: '#dcfce7', border: '#22c55e', icon: 'λ' },
  gateway:   { bg: '#e0f2fe', border: '#0ea5e9', icon: '🔀' },
  storage:   { bg: '#fce7f3', border: '#ec4899', icon: '📦' },
  db:        { bg: '#fff7ed', border: '#f97316', icon: '🗄️' },
}
```

### Node ordering algorithm

Build the flow left → right:

```
[Source System] → [Gateway? if gateway in tools] → [OCI Gen3 / DI] →
[Streaming / Queue? if in tools] → [Functions? if in tools] →
[Storage? if in tools] → [Destination System]
```

Rules:
1. Always start with Source System, always end with Destination System
2. Insert tool nodes between in canonical OCI architecture order:
   `Gateway → OIC Adapter → Streaming → Functions → DB/Storage`
3. If a tool appears in coreTools, include its node
4. Draw directional arrows between consecutive nodes

### Payload annotations below the diagram

```tsx
<div className="mt-3 grid grid-cols-3 gap-4 text-sm text-[var(--color-text-secondary)]">
  <div>
    <span className="font-medium text-[var(--color-text-primary)]">Input</span>
    <p>{payloadKb ?? '?'} KB / execution</p>
    <p>{frequency ?? 'unknown frequency'}</p>
  </div>
  <div>
    <span className="font-medium text-[var(--color-text-primary)]">OIC Processing</span>
    <p>{billingMsgs} billing msg{billingMsgs !== 1 ? 's' : ''} / execution</p>
    <p>Pattern: {selectedPattern ?? 'unassigned'}</p>
  </div>
  <div>
    <span className="font-medium text-[var(--color-text-primary)]">Output</span>
    <p>→ {destinationSystem ?? 'unknown'}</p>
    <p>{destinationTechnology ?? ''}</p>
  </div>
</div>
```

Billing msgs computed client-side:
```typescript
function estimateBillingMsgs(payloadKb: number | null): number | null {
  if (!payloadKb) return null
  const THRESHOLD = 50  // KB per billing message
  return Math.ceil(payloadKb / THRESHOLD)
}
```

### Integration into detail page

In `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx`:

In the right column (patch form), after the core tools multi-select:

```tsx
{/* Show canvas whenever source system is known */}
{integration.source_system && (
  <div className="mt-6 border border-[var(--color-border)] rounded-lg p-4
                  bg-[var(--color-surface-2)]">
    <h3 className="text-sm font-semibold text-[var(--color-text-secondary)]
                   uppercase tracking-wide mb-3">
      Integration Design Canvas
    </h3>
    <IntegrationCanvas
      sourceSystem={integration.source_system}
      sourceTechnology={integration.source_technology}
      destinationSystem={integration.destination_system}
      destinationTechnology={integration.destination_technology}
      selectedPattern={patchForm.selected_pattern ?? integration.selected_pattern}
      coreTools={patchForm.core_tools ?? integration.core_tools ?? []}
      payloadKb={integration.payload_per_execution_kb}
      frequency={integration.frequency}
      patternCategory={patternCategory}
    />
  </div>
)}
```

Canvas updates reactively as the architect selects/deselects core tools
in the patch form — no save required to see the diagram update.

---

## M14 — Map: Pan Navigation + Visual Improvements

### 14A — Pan Mode (Hand Tool)

Add two interaction modes to the graph:

```typescript
type GraphMode = 'select' | 'pan'
```

**Toolbar addition** (in `apps/web/components/graph-controls.tsx`):

```tsx
<div className="flex items-center gap-1 border border-[var(--color-border)] rounded p-1">
  <button
    onClick={() => setMode('select')}
    title="Select (V)"
    className={mode === 'select' ? 'bg-[var(--color-accent)] text-white rounded p-1' : 'p-1'}
  >
    <MousePointer className="w-4 h-4" />
  </button>
  <button
    onClick={() => setMode('pan')}
    title="Pan (H)"
    className={mode === 'pan' ? 'bg-[var(--color-accent)] text-white rounded p-1' : 'p-1'}
  >
    <Hand className="w-4 h-4" />
  </button>
</div>
```

Keyboard shortcuts: `V` → select mode, `H` → pan mode.

**Pan behavior in `apps/web/components/integration-graph.tsx`:**

Add viewport state:
```typescript
const [viewport, setViewport] = useState({ x: 0, y: 0, scale: 1 })
```

In pan mode:
- SVG wrapper cursor: `cursor-grab` (idle), `cursor-grabbing` (dragging)
- `onMouseDown` → start tracking drag
- `onMouseMove` → update `viewport.x` and `viewport.y`
- `onMouseUp` → stop drag
- Apply to SVG: `transform={`translate(${viewport.x}, ${viewport.y}) scale(${viewport.scale})`}`

Mouse wheel: always zooms (regardless of mode), centered on cursor position:
```typescript
function handleWheel(e: WheelEvent) {
  e.preventDefault()
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  const newScale = Math.min(Math.max(viewport.scale * delta, 0.2), 4)
  // Adjust x/y to zoom toward cursor position
  const rect = svgRef.current.getBoundingClientRect()
  const cx = e.clientX - rect.left
  const cy = e.clientY - rect.top
  setViewport(v => ({
    scale: newScale,
    x: cx - (cx - v.x) * (newScale / v.scale),
    y: cy - (cy - v.y) * (newScale / v.scale),
  }))
}
```

Zoom buttons (+/-/reset) update `viewport.scale` and reset x/y on reset.

---

### 14B — Dynamic Visual Improvements

**Animated edge arrows** — indicate flow direction with a moving dash:

```css
/* In globals.css */
@keyframes flow {
  from { stroke-dashoffset: 20; }
  to   { stroke-dashoffset: 0; }
}

.graph-edge-animated {
  stroke-dasharray: 6 4;
  animation: flow 1.5s linear infinite;
}

/* Pause animation on hover for readability */
.graph-edge-animated:hover {
  animation-play-state: paused;
  stroke-width: 3;
}
```

Apply `.graph-edge-animated` class to edge `<line>` elements.
On node or edge hover, pause all other edge animations and highlight:
- Hovered edge: `stroke-width * 1.5`, brighter color
- Connected nodes: `opacity: 1`, `filter: drop-shadow(0 0 6px currentColor)`
- Unconnected nodes: `opacity: 0.3`

**Node hover tooltip** — show on hover, positioned above node:

```tsx
{hoveredNode && (
  <g transform={`translate(${pos[hoveredNode].x}, ${pos[hoveredNode].y - nodeRadius - 8})`}>
    <rect x={-80} y={-44} width={160} height={44} rx={6}
          fill="var(--color-surface)" stroke="var(--color-border)"
          filter="drop-shadow(0 2px 8px rgba(0,0,0,0.15))" />
    <text textAnchor="middle" y={-26} fontSize={11} fontWeight="600"
          fill="var(--color-text-primary)">{hoveredNode}</text>
    <text textAnchor="middle" y={-10} fontSize={10}
          fill="var(--color-text-secondary)">
      {nodes.find(n => n.id === hoveredNode)?.integration_count} integrations
    </text>
  </g>
)}
```

**Edge label on hover** — show business process count when hovering an edge:

```tsx
{hoveredEdge && (
  <text
    x={(pos[hoveredEdge.source].x + pos[hoveredEdge.target].x) / 2}
    y={(pos[hoveredEdge.source].y + pos[hoveredEdge.target].y) / 2 - 8}
    textAnchor="middle" fontSize={10}
    fill="var(--color-text-secondary)"
    className="pointer-events-none select-none"
  >
    {hoveredEdge.integration_count} integration{hoveredEdge.integration_count > 1 ? 's' : ''}
  </text>
)}
```

**Graph legend** — fixed bottom-left of canvas:

```tsx
<div className="absolute bottom-4 left-4 bg-[var(--color-surface-2)]
                border border-[var(--color-border)] rounded-lg p-3 text-xs
                text-[var(--color-text-secondary)] space-y-1">
  <div className="font-semibold text-[var(--color-text-primary)] mb-2">Legend</div>
  <div className="flex items-center gap-2">
    <circle r={6} fill="#22c55e" /> All OK
  </div>
  <div className="flex items-center gap-2">
    <circle r={6} fill="#f97316" /> All REVISAR
  </div>
  <div className="flex items-center gap-2">
    <circle r={6} fill="#eab308" /> Mixed
  </div>
  <div className="mt-2 pt-2 border-t border-[var(--color-border)]">
    Node size = integration count
  </div>
  <div>Edge width = connection count</div>
</div>
```

**Node detail: integration count ring** — add a small count badge inside each node:

```tsx
// Inside the node <g>:
<circle r={nodeRadius} fill={nodeColor} />
<text textAnchor="middle" dominantBaseline="central"
      fontSize={nodeRadius * 0.55} fontWeight="700"
      fill="white">{node.integration_count}</text>
// System name below node:
<text textAnchor="middle" y={nodeRadius + 14}
      fontSize={11} fontWeight="500"
      fill="var(--color-text-primary)"
      className="select-none">{node.label}</text>
// Brand count below name (smaller, muted):
<text textAnchor="middle" y={nodeRadius + 26}
      fontSize={9} fill="var(--color-text-muted)"
      className="select-none">{node.brands.length} brand{node.brands.length > 1 ? 's' : ''}</text>
```

---

## Definition of Done

M11 — Navigation + Colors + Theme:
- [ ] Breadcrumb renders on all 10+ pages with correct path
- [ ] Back/contextual navigation buttons on integration detail page
- [ ] QA badges use CSS variable tokens, WCAG AA contrast verified visually
- [ ] Pattern badges colored by category (sync/async/both)
- [ ] Complexity badge added to catalog table
- [ ] Light mode looks correct on dashboard, catalog, detail, graph pages
- [ ] Dark mode toggle works — all surfaces and text switch correctly
- [ ] No flash of wrong theme on page load
- [ ] Theme preference persists across page refresh

M12A — Source Lineage:
- [ ] Lineage API response includes `column_names: dict[str, str]`
- [ ] Frontend shows "Interface ID", "Brand" etc. instead of "Column 0", "Column 1"
- [ ] Null/empty columns collapsed under "Show all columns" toggle

M12B — Excel Template:
- [ ] `GET /api/v1/exports/template/xlsx` returns valid XLSX file
- [ ] Template has correct headers at row 5 matching importer.py HEADER_ALIASES
- [ ] Frequency, Trigger Type, Complexity, TBQ columns have dropdown validation
- [ ] Required columns colored blue, optional governed yellow, optional free-text gray
- [ ] Row 6 contains an example row
- [ ] Template can be uploaded back via import and produces correct counts
- [ ] Download button visible on Import page

M13 — Design Canvas:
- [ ] Canvas renders below core tools selector in integration detail
- [ ] Source and destination system nodes always visible
- [ ] OCI tool nodes rendered between them in correct order
- [ ] Canvas updates reactively when core tools are added/removed without saving
- [ ] Payload annotation bar shows KB, billing msgs, destination
- [ ] Canvas renders correctly in both light and dark mode

M14 — Map improvements:
- [ ] Hand tool button in toolbar switches to pan mode
- [ ] Drag pans the graph in pan mode; click selects in select mode
- [ ] Mouse wheel zooms centered on cursor position
- [ ] Keyboard shortcuts V (select) and H (pan) work
- [ ] Edge dash animation shows flow direction
- [ ] Hovered edge pauses animation and highlights; other edges dim
- [ ] Node hover tooltip shows name + integration count
- [ ] Edge hover label shows integration count
- [ ] Legend visible in bottom-left corner
- [ ] Node shows count inside circle + brand count below label

All milestones:
- [ ] 26 parity tests pass
- [ ] 0 TypeScript errors
- [ ] 0 ruff errors
- [ ] 6/6 Docker containers Up
- [ ] `docs/progress.md` updated after each milestone with status, date, and verification results
- [ ] `README.md` milestone table reflects current state

---

## Documentation Requirement — Mandatory After Each Milestone

After completing each milestone (M11, M12, M13, M14), before moving to the next one,
Codex **must** update two files. Do not batch these updates at the end — write them
immediately after the milestone's definition-of-done checklist passes.

---

### File 1 — `docs/progress.md`

Create this file if it does not exist. Append one section per completed milestone.
Never overwrite previous entries. Structure:

```markdown
## M{N} — {Milestone Name}

**Completed:** {YYYY-MM-DD}
**Status:** ✅ Complete

### What was implemented

- {bullet describing each significant file created or modified}

### Verification results

```text
{paste relevant snippet: tsc output, ruff output, test count, or endpoint check}
```

### Gaps / known limitations

{Any items that were deferred or could not be completed. "None" if clean.}

---
```

Example entry that Codex must write after M11 completes:

```markdown
## M11 — Navigation + Color System + Light/Dark Theme

**Completed:** 2026-04-14
**Status:** ✅ Complete

### What was implemented

- `apps/web/components/breadcrumb.tsx` — breadcrumb navigation for all pages
- `apps/web/lib/theme.ts` — `useTheme` hook with localStorage persistence
- `apps/web/app/layout.tsx` — no-flash theme script in `<head>`
- `apps/web/app/globals.css` — full CSS variable token system, dark mode overrides
- Breadcrumb added to all 10 pages
- Back/contextual navigation buttons on integration detail page
- QA and pattern badges updated to use CSS variable tokens

### Verification results

```text
TypeScript: 0 errors
ruff: All checks passed
26/26 parity tests passing
6/6 containers Up
```

### Gaps / known limitations

None

---
```

---

### File 2 — `README.md` milestone table

Find the milestone table in `README.md` (create a `## Milestones` section if absent)
and update the row for the completed milestone. The table format:

```markdown
## Milestones

| Milestone | Description | Status | Completed |
|-----------|-------------|--------|-----------|
| M1  | Schema + Migrations          | ✅ Complete | 2026-04-13 |
| M2  | Import Engine                | ✅ Complete | 2026-04-13 |
| M3  | Catalog Grid API             | ✅ Complete | 2026-04-13 |
| M4  | Calculation Engine           | ✅ Complete | 2026-04-13 |
| M5  | Next.js Frontend             | ✅ Complete | 2026-04-13 |
| M6  | Justification Narratives     | ✅ Complete | 2026-04-13 |
| M7  | Exports                      | ✅ Complete | 2026-04-13 |
| M8  | Admin + Governance           | ⚠ Partial  | —          |
| M9  | Integration Capture Wizard   | ⚠ Partial  | —          |
| M10 | System Dependency Map        | ⚠ Partial  | —          |
| M11 | Navigation + Theme           | 🔄 In Progress | —      |
| M12 | Source Lineage + Template    | ⏳ Pending | —          |
| M13 | Integration Design Canvas    | ⏳ Pending | —          |
| M14 | Map Pan + Visual Improvements| ⏳ Pending | —          |
```

Update each row as it completes: change status to `✅ Complete` and fill in the date.

---

### Commit convention for documentation updates

After updating both files, create a separate commit (distinct from the implementation commit):

```bash
git add docs/progress.md README.md
git commit -m "docs: M{N} complete — update progress log and milestone table"
```

This makes it easy to distinguish implementation commits from documentation commits
in the git log.
