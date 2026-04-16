# Codex Task — M19 Completion: Governed Reference Data 2.0

## Situation

The workbook contains significantly richer governed reference data than the current
application seed layer exposes. The models are already capable of storing most of
this information, but the seed data and API surfaces remain underfilled.

This milestone upgrades the governed metadata backbone so patterns, frequencies,
tools, and overlays match workbook-grade semantics. The outcome should be a single
reference layer that admin pages, QA hints, capture flows, the canvas, and the
calc engine can all consume consistently.

No new packages. No redesign of governance CRUD unless required to expose existing
model fields cleanly.

**Read before writing any code:**
1. `AGENTS.md` — milestone sequencing and governance rules
2. `docs/reports/workbook-gap-analysis-adn-20260415.md` — validated workbook drift
3. `apps/api/app/migrations/seed.py` — current seed content and idempotence strategy
4. `apps/api/app/models/governance.py` — PatternDefinition, DictionaryOption, AssumptionSet
5. `apps/api/app/routers/patterns.py` and `apps/api/app/routers/dictionaries.py`
6. `apps/api/app/services/reference_service.py` — governed reference reads/writes
7. `apps/web/app/admin/page.tsx` and related admin surfaces
8. `apps/web/lib/api.ts` and `apps/web/lib/types.ts`
9. `packages/calc-engine/src/engine/volumetry.py` — frequency semantics consumers

Preserve idempotent seed behavior. Do not require destructive reseeding.

---

## Task 1 — Seed all 17 patterns with full workbook metadata

### Workbook evidence

`TPL - Patrones` contains more than ID, name, and category. Each pattern has:
- description or tagline
- OCI components
- when-to-use guidance
- when-not-to-use / anti-pattern guidance
- technical flow
- business value

### What to change

In `apps/api/app/migrations/seed.py`:
- enrich all 17 seeded patterns with the full workbook metadata
- use the fields already supported by `PatternDefinition`
- keep the seed idempotent so reruns update existing rows instead of duplicating them

In the API layer:
- confirm pattern list/detail endpoints serialize the enriched fields
- if any schema omits them, extend the response schema rather than using raw dicts

In admin surfaces:
- show the enriched metadata so it can be reviewed and edited

### Verification

After reseeding, `GET /api/v1/patterns/` and pattern detail responses must expose:
- description
- OCI components
- when-to-use
- when-not-to-use
- technical flow
- business value

---

## Task 2 — Expand frequencies to workbook `FQ01`–`FQ16`

### Current drift

The workbook frequency dictionary is stricter than the current seed and helper logic.
The most important mismatch already confirmed is:

- workbook `FQ15` / `Tiempo Real` = `24 executions/day`
- current codebase uses `1440`

### What to change

In `apps/api/app/migrations/seed.py`:
- expand the frequency dictionary to include workbook `FQ01`–`FQ16`
- preserve code, label, executions/day semantics, and alias coverage
- correct `Tiempo Real` to `24`

In downstream consumers:
- update any hardcoded frequency maps in the API, calc engine, or web app so they
  consume the governed dictionary semantics instead of shadow constants

Files to audit at minimum:
- `packages/calc-engine/src/engine/volumetry.py`
- `apps/web/components/integration-canvas.tsx`
- any capture or preview helpers still defining local frequency maps

### Verification

Add tests proving:
- `Tiempo Real` resolves to `24`
- frequency aliases normalize to the correct governed code
- the calc engine and web previews use the same semantics as the seed

---

## Task 3 — Expand tool taxonomy and overlay governance

### Workbook evidence

`TPL - Diccionario` distinguishes:
- tool IDs such as `T01`–`T07`
- volumetric vs non-volumetric tools
- direct vs proxy behavior
- architectural overlays (`AO`)

### What to change

Use the existing governance model if possible. Preferred implementation:
- seed tool dictionary entries with code, label, description, and volumetric metadata
- encode overlay and proxy/direct metadata in existing supported fields or governed metadata
- avoid creating a new table unless the current model cannot represent the workbook semantics cleanly

Goals:
- tools exposed through the API must be identifiable, not just plain strings
- overlay options must be governed, not hardcoded in the UI
- admin users must be able to review the same metadata the canvas and calc helpers consume

### Verification

Confirm the reference endpoints expose:
- tool code
- display label
- description
- volumetric flag
- overlay or proxy/direct metadata if supported by the chosen schema

---

## Task 4 — Expose enriched reference data through API and admin surfaces

### What to change

In the API and frontend:
- extend `apps/web/lib/types.ts` to match the enriched pattern/frequency/tool responses
- extend `apps/web/lib/api.ts` helpers if fields are missing from the current client
- update admin pages to show the richer metadata without breaking existing CRUD flows

UI expectation:
- patterns show more than name and category
- dictionary entries surface codes and execution semantics
- tools and overlays are understandable without reading seed code

Do not add a new admin information architecture unless the current pages are unable
to display the metadata at all.

---

## Task 5 — Keep reference consumers aligned

### What to change

Audit consumers that currently rely on local constants instead of governed data:
- calc-engine frequency normalization
- canvas helper chips or preview text
- QA hint surfaces that need pattern metadata
- capture wizard selectors if they shadow old frequency values

Replace local drift with shared reference lookups where practical. If a local cache
is still needed in the web app, generate it from the API payload or shared constants
that match the seed exactly.

### Verification

Confirm there is no remaining `Tiempo real = 1440` drift in:
- seed data
- calc-engine helpers
- web components

---

## Task 6 — Tests, seed safety, and documentation

### Required validation

Add or update tests for:
- seed idempotence
- pattern metadata presence
- frequency semantics, especially `FQ15`
- reference endpoint response shape

If this milestone updates admin behavior materially, append the corresponding
completion note to `docs/progress.md` only after the seed, API, and UI are verified.

---

## Final Verification

Run all of the following:

```bash
# Seed / API validation
./.venv/bin/python -m pytest apps/api -q 2>&1 | tail -10
./.venv/bin/python -m pytest packages/calc-engine/src/tests -q 2>&1 | tail -10

# Ruff
./.venv/bin/python -m ruff check . 2>&1 | tail -10

# mypy
./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary 2>&1 | tail -10

# TypeScript
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -10; cd ../..

# ESLint
cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0 2>&1 | tail -10; cd ../..
```

Manual checks:
- pattern detail shows workbook-grade metadata
- admin can review the richer pattern and dictionary content
- `Tiempo Real` surfaces as `24 executions/day` everywhere

---

## Definition of Done

M19 is complete only when all of the following are true:

- All 17 patterns are seeded with workbook metadata, not only name/category
- Frequency governance covers workbook `FQ01`–`FQ16`
- `Tiempo Real` is corrected to `24 executions/day`
- Tool and overlay metadata are governed and exposed through API/admin surfaces
- Seed reruns remain idempotent
- All five quality gates remain green

