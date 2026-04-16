# Codex Task — M21 Completion: Volumetry Assumption Parity

## Situation

The workbook `TPL - Supuestos` contains a broader and more precise technical limit
set than the current `AssumptionSet v1.0.0`. Several critical service limits and
unit rules are either incomplete, inconsistently applied, or still hardcoded in
multiple layers of the application.

This milestone makes technical assumptions workbook-complete and version-governed.
The calc engine, previews, exports, and dashboard helpers must all consume the
same normalized assumption rules, including explicit KB/MB handling and corrected
OIC billing thresholds.

No default pricing dashboard work. Keep the dashboard in technical mode unless an
existing surface explicitly supports governed commercial metadata.

**Read before writing any code:**
1. `AGENTS.md` — calc engine and governance rules
2. `docs/reports/workbook-gap-analysis-adn-20260415.md`
3. `apps/api/app/models/governance.py` — AssumptionSet model
4. `apps/api/app/migrations/seed.py` — default assumption seed
5. `packages/calc-engine/src/engine/volumetry.py` — formula consumers
6. `apps/api/app/services/recalc_service.py`
7. `apps/api/app/services/export_service.py`
8. `apps/web/components/oic-estimate-preview.tsx` and related preview helpers
9. `apps/web/lib/types.ts` if assumption DTOs need extension

Do not scatter new hardcoded limits across multiple files. Centralize them behind governed assumptions.

---

## Task 1 — Compare `AssumptionSet v1.0.0` against workbook service limits

### Workbook evidence to incorporate

The workbook explicitly documents service constraints such as:
- OIC inbound billing threshold: `50 KB`
- OIC non-BYOL pack size: `5,000 msgs/hour`
- OIC BYOL pack size: `20,000 msgs/hour`
- OCI Queue billing unit: `64 KB per request`
- OCI Functions max timeout: `300 seconds`

There may be additional limits for:
- Streaming
- Data Integration
- proxy/direct tool behavior
- scheduling or threshold summaries

### What to change

Audit `apps/api/app/models/governance.py` and `apps/api/app/migrations/seed.py`:
- add missing assumption fields only if the existing model cannot represent them
- prefer extending the governed assumption schema over sprinkling constants elsewhere
- seed the workbook-complete default assumption version idempotently

If the current model already supports generic metadata storage, use that before adding columns.

---

## Task 2 — Align OIC billing and pack semantics across the stack

### Current drift

The workbook confirms technical pack rules and billing thresholds that should drive:
- OIC monthly message projections
- peak packs per hour
- preview panels
- export reference sheets

### What to change

In `packages/calc-engine/src/engine/volumetry.py` and related services:
- replace remaining hardcoded OIC thresholds with governed assumption lookups
- support BYOL vs non-BYOL pack sizes where the current data model already allows it
- ensure the same assumptions drive recalculation, previews, and exports

Audit for duplicated constants in:
- calc engine formulas
- API services
- web preview components
- export template/reference content

### Verification

Add or update tests showing that changing the governed assumption values changes
the downstream calculations and previews consistently.

---

## Task 3 — Enforce explicit KB/MB normalization

### Current risk

The workbook enhancement notes warn that volumetry inputs can be captured in MB
while formulas and headers operate in KB. This creates a silent `1024x` error risk.

### What to change

At the ingestion or calc boundary, make unit normalization explicit:
- define where payload values become canonical KB
- preserve the original unit only if the current model supports it
- never let formulas guess whether the input was KB or MB

Possible implementation locations:
- import normalization in `apps/api/app/services/import_service.py`
- calc-engine helper functions in `packages/calc-engine/src/engine/volumetry.py`
- preview helpers in the web app

### Verification

Add tests covering:
- KB input stays unchanged
- MB input is converted to KB exactly once
- dashboard/export/previews all use the normalized value

---

## Task 4 — Centralize remaining service limits behind assumptions

### What to change

Audit the following for hardcoded technical limits:
- `packages/calc-engine/src/engine/volumetry.py`
- `apps/api/app/services/recalc_service.py`
- `apps/api/app/services/export_service.py`
- web estimate or preview helpers

Replace local literals with governed lookups wherever the behavior is assumption-driven.
If some values are purely UI defaults and not technical service rules, leave them alone.

### Verification

There should be a clear single source of truth for:
- OIC thresholds
- pack sizes
- queue billing unit
- functions timeout
- other workbook-defined service constraints used by formulas or technical previews

---

## Task 5 — Preserve source references without forcing commercial mode

### What to change

If the workbook or assumption metadata includes source references, preserve them as governed metadata
so administrators can trace where the default values came from.

Do not:
- switch the dashboard into pricing mode by default
- add new pricing screens
- surface commercial data on technical-only pages unless it already belongs there

The milestone is about technical parity and governance traceability, not new pricing UX.

---

## Task 6 — Tests and regression safety

### Required validation

Add or update tests for:
- assumption loading and default version behavior
- OIC threshold semantics
- queue/functions limits if formulas consume them
- KB/MB normalization
- preview parity where applicable

If an assumption schema change is required, include migration coverage and seed verification.

---

## Final Verification

Run all of the following:

```bash
./.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -10
./.venv/bin/python -m ruff check . 2>&1 | tail -10
./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary 2>&1 | tail -10
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -10; cd ../..
cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0 2>&1 | tail -10; cd ../..
```

Manual verification:
- confirm technical previews use the governed assumption values
- confirm no 1024x drift when payload units differ
- confirm assumption changes propagate through recalculation and exports

---

## Definition of Done

M21 is complete only when all of the following are true:

- `AssumptionSet` covers the workbook technical limits needed by the app
- OIC pack and billing rules are governed, not hardcoded drift
- KB/MB normalization is explicit and tested
- Calc, preview, export, and dashboard helpers share the same assumption source
- All five quality gates remain green

