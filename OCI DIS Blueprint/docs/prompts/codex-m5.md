# Codex Task — M5: Next.js Frontend

## Situation

Backend M1-M4 is fully validated and running in Docker:
- API: http://localhost:8000 (FastAPI, all M1-M4 endpoints live)
- Web: http://localhost:3000 (Next.js 14, currently a blank shell)
- DB seeded: 17 patterns, 1 assumption set, 40 dictionary options
- Import tested: 144 loaded / 13 excluded / 157 TBQ=Y

Your job: build the frontend. Connect it to the live API. Ship real, functional UI.

**Do not touch the backend.** Do not add API endpoints. Do not modify `apps/api/`.
Do not refactor `packages/calc-engine/`. Frontend only.

---

## Before Writing Code

Read these files first:
1. `AGENTS.md` — stack, conventions, RBAC model, milestone definitions
2. `apps/api/app/routers/` — all 12 router files so you know the exact endpoint shapes
3. `apps/api/app/schemas/` — all Pydantic schemas = your TypeScript type source of truth
4. `packages/test-fixtures/benchmarks/parity-expectations.json` — numbers to display

---

## Tech Stack (do not deviate)

- Next.js 14 App Router (already installed)
- TypeScript strict mode
- Tailwind CSS for all styling — no additional CSS files, no CSS modules
- `fetch()` for all API calls — no axios, no react-query, no SWR
- Server Components by default; use `'use client'` only where interaction requires it
- API base URL: `process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'`

---

## What to Build

### File structure

```
apps/web/
  app/
    layout.tsx                          # root layout — nav sidebar + header
    page.tsx                            # redirect to /projects
    projects/
      page.tsx                          # project list + create
      [projectId]/
        page.tsx                        # project dashboard
        import/
          page.tsx                      # file upload
        catalog/
          page.tsx                      # catalog grid
          [integrationId]/
            page.tsx                    # integration detail + patch
    globals.css                         # Tailwind directives only
  lib/
    api.ts                              # typed fetch wrapper
    types.ts                            # TypeScript types from API schemas
  components/
    nav.tsx                             # sidebar navigation
    catalog-table.tsx                   # catalog grid (client component)
    integration-patch-form.tsx          # patch form (client component)
    import-upload.tsx                   # file upload dropzone (client component)
    volumetry-card.tsx                  # OIC/DI/Functions/Streaming metrics card
    qa-badge.tsx                        # QA status pill (OK/REVISAR/PENDING)
    pattern-badge.tsx                   # pattern pill (#01 Request-Reply etc.)
```

---

## API Client — `apps/web/lib/api.ts`

```typescript
const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API ${res.status} ${path}: ${body}`)
  }
  return res.json()
}

export const api = {
  // Projects
  listProjects: () => apiFetch<ProjectList>('/api/v1/projects/'),
  createProject: (body: { name: string; owner_id: string }) =>
    apiFetch<Project>('/api/v1/projects/', { method: 'POST', body: JSON.stringify(body) }),

  // Imports
  uploadWorkbook: (projectId: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return apiFetch<ImportBatch>(`/api/v1/imports/${projectId}`,
      { method: 'POST', headers: {}, body: fd })
  },
  listImports: (projectId: string) =>
    apiFetch<ImportBatchList>(`/api/v1/imports/${projectId}`),

  // Catalog
  listCatalog: (projectId: string, params: CatalogParams) => {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return apiFetch<CatalogPage>(`/api/v1/catalog/${projectId}?${q}`)
  },
  getIntegration: (projectId: string, id: string) =>
    apiFetch<IntegrationDetail>(`/api/v1/catalog/${projectId}/${id}`),
  patchIntegration: (projectId: string, id: string, body: IntegrationPatch) =>
    apiFetch<Integration>(`/api/v1/catalog/${projectId}/${id}`,
      { method: 'PATCH', body: JSON.stringify(body) }),

  // Patterns
  listPatterns: () => apiFetch<PatternList>('/api/v1/patterns/'),

  // Recalculate + Volumetry
  recalculate: (projectId: string) =>
    apiFetch<VolumetrySnapshot>(`/api/v1/recalculate/${projectId}`, { method: 'POST' }),
  getConsolidated: (projectId: string, snapshotId: string) =>
    apiFetch<ConsolidatedMetrics>(
      `/api/v1/volumetry/${projectId}/snapshots/${snapshotId}/consolidated`),

  // Audit
  listAudit: (projectId: string) =>
    apiFetch<AuditPage>(`/api/v1/audit/${projectId}`),
}
```

---

## TypeScript Types — `apps/web/lib/types.ts`

Mirror the API Pydantic schemas exactly. Minimum required:

```typescript
export interface Project {
  id: string
  name: string
  owner_id: string
  status: string
  created_at: string
}

export interface ProjectList { projects: Project[]; total: number }

export interface ImportBatch {
  id: string
  project_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  loaded_count: number
  excluded_count: number
  tbq_y_count: number
  source_row_count: number
  created_at: string
}

export interface ImportBatchList { batches: ImportBatch[]; total: number }

export interface Integration {
  id: string
  project_id: string
  seq_number: number
  interface_id: string | null
  brand: string | null
  business_process: string | null
  interface_name: string | null
  type: string | null
  interface_status: string | null
  complexity: string | null
  frequency: string | null
  payload_per_execution_kb: number | null
  selected_pattern: string | null
  pattern_rationale: string | null
  qa_status: 'OK' | 'REVISAR' | 'PENDING'
  qa_reasons: string[]
  source_system: string | null
  destination_system: string | null
  source_row_number: number
}

export interface IntegrationDetail extends Integration {
  raw_data: Record<string, unknown>
  normalization_events: NormalizationEvent[]
}

export interface NormalizationEvent {
  field: string
  old_value: unknown
  new_value: unknown
  rule: string
}

export interface IntegrationPatch {
  selected_pattern?: string
  pattern_rationale?: string
  comments?: string
  core_tools?: string[]
}

export interface CatalogPage {
  integrations: Integration[]
  total: number
  page: number
  page_size: number
}

export interface CatalogParams {
  page?: number
  page_size?: number
  qa_status?: string
  search?: string
  pattern?: string
  brand?: string
}

export interface PatternDefinition {
  pattern_id: string
  name: string
  category: string
}

export interface PatternList { patterns: PatternDefinition[]; total: number }

export interface VolumetrySnapshot {
  id: string
  snapshot_id?: string
  project_id: string
  created_at: string
}

export interface OICMetrics {
  total_billing_msgs_month: number
  peak_billing_msgs_hour: number
  peak_packs_hour: number
  row_count: number
}

export interface ConsolidatedMetrics {
  oic: OICMetrics
  data_integration: Record<string, unknown>
  functions: Record<string, unknown>
  streaming: Record<string, unknown>
}

export interface AuditEvent {
  id: string
  event_type: string
  entity_type: string
  entity_id: string
  actor_id: string
  old_value: unknown
  new_value: unknown
  created_at: string
}

export interface AuditPage { events: AuditEvent[]; total: number }
```

---

## Pages

### Root Layout — `apps/web/app/layout.tsx`

Dark sidebar layout. Sidebar contains:
- App title: **OCI DIS Blueprint**
- Nav links: Projects, (when inside a project: Dashboard, Import, Catalog)
- Bottom: stack version badge (v1.0.0)

Use Tailwind. No external component libraries.

### Projects Page — `apps/web/app/projects/page.tsx`

Server Component. Fetches `GET /api/v1/projects/`.

Shows:
- Table: project name, status, created date, row count (link to catalog)
- "New Project" button → inline form (name field, submit)
- Empty state if no projects

### Project Dashboard — `apps/web/app/projects/[projectId]/page.tsx`

Server Component. Fetches in parallel:
- Latest import batch (`GET /api/v1/imports/{projectId}`)
- Catalog count (`GET /api/v1/catalog/{projectId}?page=1&page_size=1`)
- Latest volumetry snapshot consolidated metrics

Shows 4 metric cards:
- **Integrations loaded** — `loaded_count` from latest import
- **Excluded (Duplicado 2)** — `excluded_count`
- **OIC Peak Packs/hour** — from consolidated metrics
- **OIC Billing msgs/month** — from consolidated metrics

Shows QA status breakdown (OK / REVISAR / PENDING counts).

"Run Recalculation" button (client component) — calls `POST /api/v1/recalculate/{projectId}`, refreshes metrics on completion.

### Import Page — `apps/web/app/projects/[projectId]/import/page.tsx`

Client Component.

File upload dropzone:
- Accepts `.xlsx` only
- Drag-and-drop or click to browse
- Shows file name + size after selection
- "Upload & Import" button → calls `api.uploadWorkbook()`
- Shows progress: pending → processing → completed
- On completion: shows counts (loaded / excluded / tbq_y)
- On error: shows error message from API

Import history table below: batch ID, date, loaded, excluded, status.

### Catalog Grid — `apps/web/app/projects/[projectId]/catalog/page.tsx`

Client Component (filters make this interactive).

Toolbar:
- Search input (free text → `search` param)
- Filter: QA Status dropdown (All / OK / REVISAR / PENDING)
- Filter: Pattern dropdown (All / #01 Request-Reply / ... / #17)
- Filter: Brand dropdown (unique brands from catalog)
- Row count badge: "144 integrations"

Table columns:
| # | Interface ID | Brand | Interface Name | Pattern | Frequency | Payload KB | QA Status |
|---|---|---|---|---|---|---|---|

- Click any row → navigate to `/projects/[projectId]/catalog/[integrationId]`
- `QA Status` column shows colored `<QaBadge />` pill
- `Pattern` column shows `<PatternBadge />` pill or "—" if unassigned
- Pagination: 50 rows/page, prev/next buttons, "Page X of Y"

### Integration Detail — `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx`

Two-column layout:

**Left column — read-only source data:**
- Interface ID, brand, business process, source system, destination system, frequency, payload KB, type, complexity, status
- "Source lineage" section: source row number, original raw column values
- Normalization events list (if any)

**Right column — architect patch form (`<IntegrationPatchForm />`):**
- Pattern selector: dropdown of all 17 patterns (fetched from `/api/v1/patterns/`)
- Pattern rationale: textarea
- Comments: textarea
- Core tools: multi-select checkboxes
- "Save" button → `PATCH /api/v1/catalog/{projectId}/{integrationId}`
- On success: show updated QA status + qa_reasons list
- QA reasons displayed as warning list if `qa_status === 'REVISAR'`

Audit trail section at bottom: table of recent audit events for this integration.

---

## Components

### `<QaBadge status />` — `apps/web/components/qa-badge.tsx`

```
OK      → green pill
REVISAR → yellow pill
PENDING → gray pill
```

### `<PatternBadge patternId name />` — `apps/web/components/pattern-badge.tsx`

```
#01 → blue pill with "#01 Request-Reply"
unassigned → gray "—"
```

### `<VolumetryCard />` — `apps/web/components/volumetry-card.tsx`

Compact metric card: label, large number, unit. Used on dashboard.

---

## Environment

Add to `apps/web/.env.local` (create if missing):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The Docker Compose `web` service already has `NEXT_PUBLIC_API_URL` in environment.
The web container calls the API via the Docker network name `api`, not `localhost`.
So in `docker-compose.yml`, verify:
```yaml
web:
  environment:
    - NEXT_PUBLIC_API_URL=http://api:8000
```
And for local `npm run dev`, `localhost:8000` works because the API port is exposed.

---

## Definition of Done

You are done when ALL of the following are true:

- [ ] `docker compose build web` exits 0
- [ ] `docker compose up -d` → web container is `Up`, no restart loops
- [ ] `http://localhost:3000/projects` loads — shows project list or empty state
- [ ] Creating a project via the UI works — project appears in list
- [ ] Navigating to Import page and uploading a `.xlsx` file returns loaded/excluded counts
- [ ] Catalog page at `/projects/{id}/catalog` shows the table with correct row count
- [ ] Filters (search, qa_status, pattern) update the table without page reload
- [ ] Clicking a row opens the detail page with source data + patch form
- [ ] Patching a pattern in the form → saves → QA status updates in the UI
- [ ] Dashboard shows OIC Peak Packs/hour and billing msgs/month after recalculation
- [ ] `cd apps/web && npx tsc --noEmit` → 0 TypeScript errors
- [ ] `ruff check apps/api/app/` still passes (you didn't touch the backend)
- [ ] 26 calc-engine parity tests still pass

Do not stop until all 12 checkboxes are satisfied.
Do not add backend endpoints.
Do not install UI component libraries (shadcn, MUI, Ant Design, Chakra).
Use only Tailwind classes for all styling.
