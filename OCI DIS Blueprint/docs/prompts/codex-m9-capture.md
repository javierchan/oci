# Codex Task — M9: Integration Capture Interface

## Context

Phase 1 (M1-M8) is complete. The current import flow is XLSX-only: engineers upload
the workbook, the engine parses it, and 144 rows land in the catalog. That works for
the initial migration. It does not work for ongoing discovery sessions with clients
where integrations are identified verbally, on whiteboards, or in interviews — not
pre-populated in a spreadsheet.

This milestone adds a guided capture interface so architects and analysts can enter
new integrations directly into the catalog during discovery workshops, with real-time
OIC cost estimation and QA validation as they type.

**Read before touching any code:**
1. `AGENTS.md` — coding conventions, RBAC, audit requirements
2. `apps/api/app/models/project.py` — CatalogIntegration full field list
3. `apps/api/app/routers/catalog.py` — existing endpoints (no POST yet)
4. `apps/api/app/routers/dictionaries.py` — governed dropdown source
5. `apps/api/app/routers/patterns.py` — 17 OIC patterns
6. `packages/calc-engine/src/engine/volumetry.py` — formulas to preview

---

## Backend Changes Required

### 1. New schema — `apps/api/app/schemas/catalog.py`

Add `ManualIntegrationCreate`:

```python
class ManualIntegrationCreate(BaseModel):
    # Identity
    interface_id: Optional[str] = None         # client-assigned ID or None
    brand: str                                  # required — governs the integration owner
    business_process: str                       # required
    interface_name: str                         # required
    description: Optional[str] = None

    # Source
    source_system: str                          # required
    source_technology: Optional[str] = None
    source_api_reference: Optional[str] = None
    source_owner: Optional[str] = None

    # Destination
    destination_system: str                     # required
    destination_technology: Optional[str] = None
    destination_owner: Optional[str] = None

    # Technical
    type: Optional[str] = None                 # validated against dictionaries TRIGGER_TYPE
    frequency: Optional[str] = None            # validated against dictionaries FREQUENCY
    payload_per_execution_kb: Optional[float] = None
    complexity: Optional[str] = None           # validated against dictionaries COMPLEXITY
    uncertainty: Optional[str] = None

    # Pattern (optional at capture time — can be assigned later)
    selected_pattern: Optional[str] = None
    pattern_rationale: Optional[str] = None
    core_tools: Optional[list[str]] = None

    # Governance
    tbq: str = "Y"                             # default Y — captured integrations are in scope
    initial_scope: Optional[str] = None
    owner: Optional[str] = None
```

### 2. New service method — `apps/api/app/services/catalog_service.py`

```python
async def manual_create_integration(
    project_id: str,
    data: ManualIntegrationCreate,
    actor_id: str,
    db: AsyncSession,
) -> CatalogIntegration:
    """
    Creates a SourceIntegrationRow (immutable source record) and a CatalogIntegration
    from manually entered form data. Mirrors what import_service does for XLSX rows.

    Steps:
    1. Generate a synthetic source_row_number (max existing + 1 for the project)
    2. Create SourceIntegrationRow with raw_data from the form fields, included=True
    3. Compute executions_per_day via calc_engine.volumetry.executions_per_day()
    4. Compute payload_per_hour_kb via calc_engine.volumetry.payload_per_hour_kb()
    5. Evaluate qa_status via calc_engine.qa.evaluate_qa()
    6. Create CatalogIntegration — tbq=Y, source=manual_capture
    7. Emit AuditEvent(event_type='manual_capture', actor_id=actor_id)
    8. Return CatalogIntegration
    """
```

### 3. New endpoint — `apps/api/app/routers/catalog.py`

```python
@router.post("/{project_id}", response_model=CatalogIntegrationResponse, status_code=201)
async def create_integration(
    project_id: str,
    body: ManualIntegrationCreate,
    db: AsyncSession = Depends(get_db),
):
    return await catalog_service.manual_create_integration(
        project_id, body, actor_id="ui-capture", db=db
    )
```

### 4. New endpoint — duplicate detection

```python
@router.get("/{project_id}/duplicates")
async def check_duplicate(
    project_id: str,
    source_system: str,
    destination_system: str,
    business_process: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns existing integrations that match the same source+destination+business_process.
    Used by the frontend to warn before submission.
    """
```

### 5. New endpoint — system catalog (autocomplete source)

```python
@router.get("/{project_id}/systems")
async def list_systems(project_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """
    Returns all unique system names (source_system + destination_system combined)
    already in the catalog for this project. Used to power autocomplete in the form.
    """
```

### 6. New endpoint — live OIC estimate (no DB write)

```python
@router.post("/{project_id}/estimate")
async def estimate_oic_cost(
    project_id: str,
    body: OICEstimateRequest,   # frequency, payload_per_execution_kb, response_kb=0
    db: AsyncSession = Depends(get_db),
) -> OICEstimateResponse:
    """
    Computes OIC billing metrics for preview without persisting anything.
    Used by the capture form to show live cost as the user types.
    """
```

---

## Frontend

### New pages

```
apps/web/app/projects/[projectId]/capture/
  page.tsx                     # entry point — shows recent captures + "New Integration" button
  new/
    page.tsx                   # multi-step wizard
```

### Wizard — `apps/web/app/projects/[projectId]/capture/new/page.tsx`

Client Component. 5 steps with a progress indicator at the top.

#### Step layout

```
[Step 1] → [Step 2] → [Step 3] → [Step 4] → [Step 5: Review]
  Identity    Source   Destination Technical    Submit
```

Progress bar shows current step. "Back" and "Next" buttons. Fields validate with Zod
before advancing to the next step.

#### Step 1 — Identity

Fields:
- **Brand** (required) — text input with autocomplete from existing catalog brands
- **Business Process** (required) — text input with autocomplete from existing business_process values
- **Interface Name** (required) — text input
- **Interface ID** (optional) — text input, placeholder "Assigned by client (optional)"
- **Description** (optional) — textarea

After "Next": checks `GET /api/v1/catalog/{projectId}/duplicates?source_system=...&destination_system=...&business_process=...`. If duplicates found, shows warning card:
> "⚠ {N} integration(s) already exist for this business process. Review before continuing."
Shows duplicate names in an expandable list. User can continue or cancel.

#### Step 2 — Source System

Fields:
- **Source System** (required) — text input with autocomplete from `GET /api/v1/catalog/{projectId}/systems`
  - Dropdown suggests existing system names as you type
  - Can enter a new system name not in the list
- **Source Technology** (optional) — dropdown: REST, SOAP, JDBC, SFTP, Kafka, JMS, ORDS, File, Custom
- **Source API Reference** (optional) — text input
- **Source Owner** (optional) — text input

#### Step 3 — Destination System

Same pattern as Step 2:
- **Destination System** (required) — autocomplete from systems list
- **Destination Technology** (optional) — same dropdown as source
- **Destination Owner** (optional) — text input

**Duplicate check fires again** when both source and destination are set. Inline warning if exact source→destination pair already exists.

#### Step 4 — Technical Parameters

Fields:
- **Trigger Type** (optional) — dropdown from `GET /api/v1/dictionaries/TRIGGER_TYPE`
- **Frequency** (optional) — dropdown from `GET /api/v1/dictionaries/FREQUENCY` (13 options)
- **Payload per Execution (KB)** (optional) — numeric input, min 0
- **Complexity** (optional) — radio buttons: Bajo / Medio / Alto
- **OIC Pattern** (optional) — searchable dropdown of 17 patterns from `/api/v1/patterns/`
  - Shows pattern ID + name + category
  - "Assign later" option (leaves unset)
- **Core Tools** (optional) — multi-select checkboxes from `GET /api/v1/dictionaries/TOOLS`

**Live OIC Cost Preview** — renders as the user fills frequency + payload:

```
┌─────────────────────────────────────────┐
│  OIC Cost Estimate (live)               │
│  Billing msgs/execution    ██ 2 msgs    │
│  Billing msgs/month       ███ 60 msgs   │
│  Peak packs/hour            █ 1 pack    │
└─────────────────────────────────────────┘
```

Calls `POST /api/v1/catalog/{projectId}/estimate` on debounce (300ms) whenever
frequency or payload changes. Shows "--" if either field is empty.

**QA Preview** — shows which QA checks will pass/fail with current data:

```
  ✓ Has source system
  ✓ Has destination system
  ✗ Interface ID missing (will flag as MISSING_ID_FORMAL)
  ✗ Pattern not assigned (will flag as INVALID_PATTERN)
  ✗ Core tools not selected (will flag as MISSING_CORE_TOOLS)
```

Status badge: `REVISAR` (red) or `OK` (green) based on preview.

#### Step 5 — Review + Submit

Full summary of all entered fields in two columns:
- Left: Identity + Source + Destination
- Right: Technical + Pattern + QA preview

"Submit Integration" button → calls `POST /api/v1/catalog/{projectId}`.

On success:
- Shows green confirmation card: "✓ Integration captured — {interface_name}"
- Two options: "View in Catalog" (link) or "Capture Another" (resets wizard to Step 1)

On error:
- Shows API error message in red
- Stays on Step 5, user can go back and correct

### Capture History Page — `apps/web/app/projects/[projectId]/capture/page.tsx`

Shows:
- "New Integration" button → `/capture/new`
- Table of manually captured integrations (filtered by `source=manual_capture` in audit trail)
  - Interface name, brand, business process, source→destination, QA status, created date
- Count badge: "X manually captured integrations"

### Navigation update

Add "Capture" link to the sidebar under the current project navigation, between "Import" and "Catalog".

---

## New component — `apps/web/components/oic-estimate-preview.tsx`

```typescript
// Props: frequency, payloadKb, projectId
// Behavior: debounced fetch to /estimate, shows metrics or loading skeleton
// Used in Step 4 of the wizard
```

## New component — `apps/web/components/qa-preview.tsx`

```typescript
// Props: formData (partial ManualIntegrationCreate)
// Behavior: client-side QA rule evaluation (mirror of calc_engine/qa.py logic in TS)
// Shows checklist of passing/failing rules in real time (no API call needed)
```

For `qa-preview.tsx`, implement these checks client-side (matching `apps/api/packages/calc-engine/src/engine/qa.py`):
- `MISSING_ID_FORMAL`: interface_id is null or empty
- `INVALID_TRIGGER_TYPE`: type not in known trigger types
- `INVALID_PATTERN`: selected_pattern is null
- `MISSING_RATIONALE`: selected_pattern set but pattern_rationale empty
- `MISSING_CORE_TOOLS`: core_tools is null or empty
- `MISSING_PAYLOAD`: payload_per_execution_kb is null
- `TBD_UNCERTAINTY`: uncertainty === 'TBD'

---

## Definition of Done

- [ ] `POST /api/v1/catalog/{projectId}` creates a CatalogIntegration + SourceIntegrationRow + AuditEvent
- [ ] `GET /api/v1/catalog/{projectId}/systems` returns unique system list from catalog
- [ ] `GET /api/v1/catalog/{projectId}/duplicates` returns existing matches
- [ ] `POST /api/v1/catalog/{projectId}/estimate` returns OIC billing preview without persisting
- [ ] Wizard renders all 5 steps with validation between steps
- [ ] Autocomplete works for brand, business_process, source_system, destination_system
- [ ] Duplicate warning fires on Step 1 and Step 3
- [ ] Live OIC estimate updates on debounce in Step 4
- [ ] QA preview shows correct pass/fail per rule in Step 4
- [ ] Submit creates the integration and shows confirmation
- [ ] "Capture Another" resets the wizard cleanly
- [ ] Manually captured integration appears in Catalog grid
- [ ] Parity tests still pass: 26 passed
- [ ] TypeScript: 0 errors
- [ ] ruff: 0 errors
