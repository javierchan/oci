# Codex Task — M20 Completion: Canvas Intelligence

## Situation

The integration design canvas is now a real flow surface, but it still lacks the
governed semantics documented in the workbook. The workbook dictionary defines
standard combinations `G01`–`G18`, distinguishes volumetric core tools from
architectural overlays, and provides enough structure to recommend compatible
patterns based on the designed pipeline.

This milestone turns the canvas from a visual editor into a governed design aid.
It must explain supported tool stacks, persist core tools separately from overlays,
suggest likely combinations and patterns, and validate that the user-designed flow
actually connects source to destination.

No new schema migrations unless the current persistence shape truly cannot hold the
required metadata. Prefer adapting the frontend model to the existing patch payload.

**Read before writing any code:**
1. `AGENTS.md` — milestone sequencing and architecture rules
2. `docs/reports/workbook-gap-analysis-adn-20260415.md` — combination and overlay findings
3. `apps/web/components/integration-canvas.tsx` — current node/edge/canvas implementation
4. `apps/web/components/integration-patch-form.tsx` — patch payload and persistence shape
5. `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx` — detail page layout and summaries
6. `apps/web/lib/types.ts` and `apps/web/lib/api.ts`
7. `apps/api/app/migrations/seed.py` — current dictionary seed
8. `apps/api/app/services/reference_service.py` — reference metadata exposure

Do not reintroduce the old checkbox model. The canvas is already the design source of truth.

---

## Task 1 — Govern workbook combinations `G01`–`G18`

### Workbook evidence

`TPL - Diccionario` documents standard groups such as:
- fan-out with queue
- event backbone
- batch cloud-native
- other governed combinations with compatible tools and patterns

### What to change

Seed the combinations in a governed way that the canvas can consume. Preferred options:
- use `DictionaryOption` metadata if it can cleanly express group code, tool set,
  compatible patterns, overlays, and guidance
- otherwise use a governed JSON structure loaded by the reference service

Each combination should expose at minimum:
- group code, such as `G04`
- display name
- supported tool keys
- compatible pattern IDs
- whether the combination activates core volumetric metrics
- recommended overlays
- short usage guidance

### Verification

Reference data must be queryable by the canvas without hardcoded `G01`–`G18` lists.

---

## Task 2 — Separate core tools from overlays in saved canvas semantics

### Current problem

The workbook distinguishes volumetric tools from architectural overlays, but the
canvas persistence currently risks flattening everything into one generic list.

### What to change

In `apps/web/components/integration-canvas.tsx` and `apps/web/components/integration-patch-form.tsx`:
- derive `core_tools` from the actual pipeline nodes that participate in the flow
- persist overlays distinctly from volumetric core tools
- ensure the patch payload preserves the designed pipeline, not just a deduplicated label list

Important:
- the processing summary must reflect the tools actually placed on the canvas
- remove any fixed assumption that processing is always `OIC Gen3`
- do not allow overlays alone to satisfy the core-tools QA requirement

### Verification

If the user drags `OCI Queue` and `OCI Functions`, the saved design must show:
- those tools as the processing path
- overlays separated, if present
- no fallback summary that says only `OIC Gen3`

---

## Task 3 — Add governed combination and pattern suggestions

### What to change

When the user places or connects tools on the canvas:
- evaluate the current node set against the governed `G01`–`G18` combinations
- suggest likely combination matches
- suggest compatible pattern candidates based on the tool stack

The suggestions should be advisory, not destructive:
- do not auto-rewrite the pattern field
- do not mutate the flow without user action
- do surface why the suggestion appeared

Suggested UX:
- a side panel or inline hint area near the canvas
- “This flow resembles G04 Fan-out with Queue”
- “Compatible patterns: #02, #08, #17”

### Verification

Build a flow such as:
- source -> OIC Gen3 -> OCI Queue -> OCI Functions -> destination

Expected:
- the canvas identifies the corresponding governed combination
- pattern recommendations appear
- overlays do not cause false positives on their own

---

## Task 4 — Validate source-to-destination connectivity

### Current risk

The canvas must not allow the designed pipeline to be functionally empty while still
passing because of a legacy fixed source-to-destination line or a disconnected node set.

### What to change

In the canvas logic:
- validate that source and destination remain connected through the user-designed flow
- prevent a hidden fixed line from acting as the effective design
- ensure disconnected node islands do not count toward the effective processing path

Expected behavior:
- deleting the only real path should surface a validation error
- the user may remove or replace the legacy fixed line entirely
- a valid path can contain multiple branches, fan-out, and parallel segments

### Verification

Test these cases:
- source and destination connected through dragged tools -> valid
- tools placed but not connected to source/destination -> invalid
- overlays only -> invalid

---

## Task 5 — Reflect real pipeline composition in the integration summary

### What to change

On the integration detail page, update summaries so they describe the actual designed flow:
- source
- processing path from user-placed tools
- overlays if present
- destination

Do not show a fixed processing label when the user has modeled a richer path.
Text/figure proportions should remain readable and the canvas should use the available space effectively.

If an audit trail entry records canvas updates, ensure it captures meaningful design changes,
not only a raw JSON blob where avoidable.

---

## Task 6 — Tests and interaction validation

### Required validation

Add or update tests for:
- combination matching
- core-tools vs overlay persistence
- flow connectivity validation
- processing summary generation from real nodes

If there are no existing automated frontend tests for the canvas, add the smallest
possible unit or integration coverage around the pure logic pieces and complete the
rest with explicit manual verification steps.

Manual verification must include:
- drag tools into the canvas
- connect them with the intended flow
- confirm no blinking or unstable rerender behavior
- confirm suggestions update without runtime errors

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
- create a fan-out flow on the canvas
- confirm the design persists across reload
- confirm suggestions appear from governed combinations
- confirm source and destination must remain connected
- confirm the processing summary reflects dragged tools, not a fixed OIC label

---

## Definition of Done

M20 is complete only when all of the following are true:

- Workbook combinations `G01`–`G18` are governed and consumable by the canvas
- Core tools and overlays are persisted distinctly
- The canvas suggests compatible combinations and patterns from actual tool usage
- The effective design must connect source to destination
- Processing summaries reflect the real modeled pipeline
- All five quality gates remain green

