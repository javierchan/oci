# Codex Task — M18 Completion: Workbook Import Fidelity

## Situation

The workbook gap analysis confirmed that import fidelity is still the highest-risk
boundary in the application. The current stack partially relies on positional
column fallbacks, which causes named workbook fields to degrade into generic
`Column N` labels and allows critical business columns such as `Interfaz` and
`Alcance Inicial` to bypass the intended semantic mapping.

This milestone closes that gap. The import path must resolve source columns by
header name first, preserve the real workbook headers in lineage and raw-column
storage, and codify the import operating rules documented in `TPL - Prompts`.

No new product features. No schema redesign unless strictly required by an
existing storage gap. Preserve source order and workbook semantics exactly.

**Read before writing any code:**
1. `AGENTS.md` — milestone order, parity rules, definition of done
2. `docs/reports/workbook-gap-analysis-adn-20260415.md` — validated workbook drift
3. `packages/calc-engine/src/engine/importer.py` — workbook parser and inclusion logic
4. `apps/api/app/services/import_service.py` — persistence + normalization layer
5. `packages/calc-engine/src/engine/qa.py` — downstream consumers of imported fields
6. `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx` — detail page raw-column rendering
7. `apps/web/lib/types.ts` — raw column and lineage client types
8. `packages/calc-engine/src/tests/` — parity tests and importer coverage

Do not invent workbook values. If a source value is blank, preserve blank unless
the workbook explicitly defines a fallback rule.

---

## Task 1 — Resolve workbook fields by header name first

### Workbook evidence

`TPL - Catálogo` and the ADN workbook use meaningful header strings, even when:
- the effective header row starts below leading blank rows
- the workbook contains duplicate or partially empty columns
- exported data includes leading empty cells before the semantic header row

Validated examples:
- `Interfaz` contains the descriptive integration name
- `Alcance Inicial` contains rollout scope values such as `Ya existe` and `Wave 1`

### What to change

In `packages/calc-engine/src/engine/importer.py`:

1. Replace pure positional resolution with a header-first resolver.
2. Build a normalized header index map from the actual workbook header row.
3. Resolve canonical fields from header aliases first, then fall back to position
   only when the workbook truly has no usable header.

Suggested pattern:

```python
HEADER_ALIASES = {
    "interface_id": ["id de interfaz", "interface id", "#"],
    "interface_name": ["interfaz", "interface name", "nombre interfaz"],
    "initial_scope": ["alcance inicial", "initial scope"],
    "trigger_type": ["tipo trigger oic", "trigger type"],
}
```

Implementation requirements:
- header matching must be case-insensitive
- trim whitespace
- preserve accent-insensitive comparison if the current importer already strips accents
- do not break benchmark workbook support if one workbook variant still depends on fallback position

### Verification

Add or update importer tests that prove:
- `Interfaz` maps to `interface_name`
- `Alcance Inicial` maps to `initial_scope`
- a workbook with blank header cells still falls back to `Column N`
- the importer still preserves source row order

---

## Task 2 — Preserve real header labels in raw-column storage and lineage

### Current problem

The application currently renders `Column 5`, `Column 11`, and similar generic
labels for fields that already have real workbook headers. This breaks traceability
and makes the detail page harder to trust.

### What to change

In `apps/api/app/services/import_service.py`:

1. When building `raw_column_values`, use the actual workbook header text as the key.
2. Only fall back to `Column {index + 1}` when the source header cell is empty or `None`.
3. Preserve the original header spelling from the workbook for display and lineage.

If the service currently consumes importer output that lacks header metadata, extend
the importer result object so the API layer receives both:
- the resolved canonical fields
- the original raw header/value pairs

In the web detail page:
- keep generic `Column N` rendering only for truly unnamed source columns
- if a header matches `^Column \\d+$`, render it in a muted style and add a tooltip
  that explains the source file did not provide a recognized header

### Verification

Manual verification target:
- open an integration detail that previously showed `Column 5`
- confirm the row now shows `Interfaz`
- if the workbook truly has an unnamed column, confirm it still shows `Column N`

---

## Task 3 — Align import operating rules with `TPL - Prompts`

### Workbook policy to codify

The workbook prompts document production import rules that must become tested code:
- preserve source order
- include `Duplicado 1`
- exclude only `Duplicado 2`
- preserve `TBD`
- preserve uncertainty
- preserve payload `0`
- do not invent fan-out or missing technical values
- retain `TBQ Audit`
- split destination technologies conservatively from workbook evidence only

### What to change

Audit `packages/calc-engine/src/engine/importer.py` and `apps/api/app/services/import_service.py`
for any normalization that:
- drops rows too aggressively
- rewrites uncertainty into certainty
- rewrites `0` payload into null
- excludes rows other than explicit `Duplicado 2`

Create named helper functions or policy constants instead of burying this behavior
in ad hoc conditionals.

Example shape:

```python
def should_include_row(status_fields: SourceStatusFields) -> bool:
    """Preserve workbook import policy exactly."""
```

### Verification

Add focused tests covering:
- `Duplicado 1` included
- `Duplicado 2` excluded
- `TBD` preserved in raw data
- zero payload preserved
- source order unchanged from workbook order

---

## Task 4 — Normalize trigger and destination semantics conservatively

### Current risk

The workbook stores richer trigger capture text than the app currently normalizes.
Import should not destroy valid workbook evidence just to fit a narrower vocabulary.

### What to change

In the importer and import service:
- preserve the original trigger text in raw data
- normalize only when the workbook clearly maps it
- treat `REST Trigger`, `SOAP Trigger`, `Event Trigger`, and `Scheduled` as
  first-class workbook-valid values
- split multi-technology destination cells conservatively; never fabricate missing tools

Do not broaden QA here beyond what is needed to keep source fidelity intact.
Full QA vocabulary work belongs to M22, but import must stop degrading valid source data.

### Verification

Add tests showing:
- `REST Trigger` survives import as a recognizable trigger value
- `SOAP Trigger` survives import
- multi-destination text is preserved in raw data even if canonical normalization is partial

---

## Task 5 — Surface the corrected semantics in catalog and detail views

### What to change

In the detail page and catalog data flow:
- ensure `interface_name` now renders the descriptive workbook value, not the formal ID
- ensure the raw column table reflects real workbook header text
- ensure lineage uses readable field labels where available

If the API response shape already supports this, do not redesign it. Adapt the
frontend only where the corrected import payload requires it.

### Verification

Use an imported ADN project and confirm:
- `Interface Name` shows the descriptive value from `Interfaz`
- `Initial Scope` reflects `Alcance Inicial`
- the raw-column table no longer hides those fields behind `Column N`

---

## Task 6 — Tests and parity coverage

### Required test updates

Add or update tests in the calc engine and API layer for:
- header-name resolution
- fallback behavior for blank headers
- row inclusion/exclusion policy
- preservation of source order
- preservation of raw header labels

If there is already a workbook fixture that contains `Interfaz` and `Alcance Inicial`,
reuse it. Otherwise add the smallest possible fixture that demonstrates the drift.

### Do not do

- Do not add a migration unless an existing persisted structure truly cannot store
  header-aware raw data
- Do not translate workbook Spanish headers into English in the raw trace
- Do not change business logic outside import fidelity

---

## Final Verification

Run all of the following after the implementation is complete:

```bash
# Import and parity-focused tests
./.venv/bin/python -m pytest packages/calc-engine/src/tests -q 2>&1 | tail -10

# API tests if import coverage lives there
./.venv/bin/python -m pytest apps/api -q 2>&1 | tail -10

# Ruff
./.venv/bin/python -m ruff check . 2>&1 | tail -10

# mypy
./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary 2>&1 | tail -10

# TypeScript
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -10; cd ../..

# ESLint
cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0 2>&1 | tail -10; cd ../..
```

Manual verification:
- import the ADN workbook or a minimal equivalent fixture
- confirm `Interfaz` and `Alcance Inicial` resolve correctly
- confirm raw-column keys show real headers instead of `Column N`
- confirm source order remains unchanged

---

## Definition of Done

M18 is complete only when all of the following are true:

- The importer resolves workbook fields by header name first, with safe fallback
- `Interfaz` maps to `interface_name`
- `Alcance Inicial` maps to `initial_scope`
- Real workbook headers are preserved in raw-column storage and lineage
- Import policy from `TPL - Prompts` is codified in tests
- Trigger/source fidelity is preserved without inventing missing values
- All five quality gates remain green

