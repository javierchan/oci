## Workbook Gap Analysis — ADN Workbook to Codebase Roadmap

**Date:** 2026-04-15  
**Workbook analyzed:** `Catalogo_Integracion_ADN_WIP.xlsx`  
**Workbook tabs used:** `TPL - Catálogo`, `TPL - Patrones`, `TPL - Diccionario`,
`TPL - Supuestos`, `TPL  - Enhancements`, `TPL - Prompts`, `TLP - PRD`

### Purpose

This report converts workbook findings into implementation milestones for the
OCI DIS Blueprint codebase. The goal is not to restate workbook content, but to
identify where the workbook still contains richer or more accurate behavior
than the application, then turn those gaps into sequenced, testable milestones.

### Key workbook findings already validated

The workbook confirms the following user-reported findings:

1. `TPL - Catálogo` still defines business meaning by header names, not just by
   positions. In particular, `Interfaz` and `Alcance Inicial` are meaningful
   source columns and must not surface as generic `Column N` labels.
2. `TPL - Patrones` contains richer metadata than the current seed data:
   description/tagline, OCI components, when-to-use guidance, anti-patterns,
   a five-step technical flow, and business value.
3. `TPL - Diccionario` contains governed combination groups `G01`–`G18` and
   explicitly distinguishes core tools, proxy tools, and architectural overlays.
4. `TPL - Supuestos` contains a larger technical limit set than the current
   `AssumptionSet v1.0.0`, including Queue, Streaming, Functions, DI, BYOL,
   and billing summaries.
5. `TPL  - Enhancements` captures unresolved quality issues in the workbook
   model itself, including QA activation, confidence of forecasting, and
   coverage gaps.
6. Workbook frequency semantics are stricter than the current code. `FQ15`
   (`Tiempo Real`) is modeled as **24 executions/day** as a batch-equivalent
   proxy, not as a per-minute trigger.

### Additional high-value findings for the codebase

The workbook also exposes several codebase-relevant gaps beyond the six already
identified.

#### 1. Trigger vocabulary drift is real and already visible in code

Workbook evidence:
- `TPL - Catálogo` uses capture values such as `Scheduled` and `REST Trigger`.
- `TPL - Prompts` describes trigger derivation rules for `REST Trigger`,
  `SOAP Trigger`, `Event Trigger`, and `Scheduled`.

Current code drift:
- `packages/calc-engine/src/engine/qa.py` only accepts:
  `Scheduled`, `REST`, `Event`, `FTP/SFTP`, `DB Polling`, `JMS`, `Kafka`,
  `Webhook`, `SOAP`.
- This means workbook-valid trigger labels can be rejected as invalid.

Why it matters:
- QA can produce false `INVALID_TRIGGER_TYPE`.
- Import fidelity suffers because valid workbook capture terminology is treated
  as non-governed.

Actionable outcome:
- Fold trigger vocabulary reconciliation into **M22**.

#### 2. Pattern metadata storage already exists, but the seed is underfilled

Workbook evidence:
- `TPL - Patrones` contains the full business and technical metadata for every
  pattern row.

Current code state:
- `apps/api/app/models/governance.py` already supports:
  `description`, `oci_components`, `when_to_use`, `when_not_to_use`,
  `technical_flow`, and `business_value`.
- `apps/api/app/migrations/seed.py` seeds only `pattern_id`, `name`, and
  `category`.

Why it matters:
- This is a low-schema-risk improvement because the model is already ready.
- The biggest missing work is enrichment of seed content and use in UI/API.

Actionable outcome:
- Fold full pattern enrichment into **M19**.

#### 3. Tool taxonomy is richer than the current `TOOLS` dictionary category

Workbook evidence:
- `TPL - Diccionario` distinguishes:
  - individual tools with IDs (`T01`, `T02`, ...)
  - direct vs proxy volumetric behavior
  - standard combinations `G01`–`G18`
  - architectural overlays (`AO`)
- The sheet also documents when a tool is quantifiable vs architectural only.

Current code drift:
- `DictionaryOption` supports `code`, `description`, and `is_volumetric`,
  but `apps/api/app/migrations/seed.py` leaves most of that unused.
- Current tool capture collapses too much into a plain string list.

Why it matters:
- The canvas can suggest and validate much better if the taxonomy is modeled.
- `AN` vs `AO` separation is currently under-governed.

Actionable outcome:
- Split the work across **M19** and **M20**.

#### 4. `Tiempo Real` semantics are inconsistent across the stack

Workbook evidence:
- `TPL - Diccionario` row `FQ15`: `Tiempo Real = 24 exec/day`.
- `TPL - Supuestos` repeats that `Tiempo Real` is modeled as a batch-equivalent
  of 24/day and requires architectural confirmation.

Current code drift:
- `apps/api/app/migrations/seed.py`: `Tiempo real = 1440 executions/day`
- `packages/calc-engine/src/engine/volumetry.py`: `Tiempo real = 1440`
- `apps/web/components/integration-canvas.tsx`: `Tiempo real = 1440`

Why it matters:
- This is a material sizing error multiplier.
- OIC preview, calc-engine outputs, and persisted governed frequencies can all
  drift together in the wrong direction.

Actionable outcome:
- Fix and test this in **M19** and validate downstream effects in **M21**.

#### 5. Workbook prompts contain operational import policy that should be codified

Workbook evidence:
- `TPL - Prompts` contains detailed accepted import rules:
  preserve source order, include `Duplicado 1`, exclude only `Duplicado 2`,
  keep `TBD`, keep uncertainty, keep payload `0`, do not invent fan-out,
  preserve `TBQ Audit`, and split destination technologies conservatively.

Current code drift:
- The code implements parts of this behavior, but not as a fully explicit,
  versioned import policy.
- Some normalization expectations from the prompt are not represented in tests
  or named policy objects.

Why it matters:
- Workbook prompts currently hold production logic in documentation form.
- The app should move that logic into tested, versioned code behavior.

Actionable outcome:
- Treat this as part of **M18**.

#### 6. Forecast confidence needs to become first-class, not implied

Workbook evidence:
- `TPL  - Enhancements` flags that the workbook scales to 289 integrations from
  only 13 payload-informed rows (4.5% coverage).

Current code drift:
- The dashboard can show forecast-like metrics without clearly signaling low
  confidence when payload coverage is sparse.

Why it matters:
- Forecast precision can be overstated even if formulas are technically correct.
- Technical dashboards need confidence indicators, not just totals.

Actionable outcome:
- Fold this into **M22**.

#### 7. Pattern support is still functionally partial, not just editorially partial

Workbook evidence:
- `TPL  - Enhancements` states that 17 patterns are documented, but only
  `#01`, `#02`, and `#05` are operationalized end-to-end in workbook logic.

Current code drift:
- The application has made progress in UI and pattern capture, but there is
  still a design decision to make:
  - either fully support `#03`–`#17`
  - or explicitly classify them as library-only / unsupported for parity mode

Why it matters:
- A pattern library that looks complete but behaves generically is misleading.

Actionable outcome:
- Address this explicitly in **M23**.

### Proposed milestone sequence

The milestones added to `AGENTS.md` and `README.md` are sequenced to reduce
risk and unlock future work in the right order.

#### M18 — Workbook Import Fidelity: Header Semantics + Source Traceability

Why first:
- It fixes data correctness at the ingestion boundary.
- It removes ambiguity from raw lineage and source semantics before downstream
  QA, dashboard, or canvas logic depend on them.

Primary code touchpoints:
- `packages/calc-engine/src/engine/importer.py`
- `apps/api/app/services/import_service.py`
- `apps/web/components/raw-column-values-table.tsx`
- import tests and fixture coverage

Workbook evidence:
- `TPL - Catálogo`
- `TPL - Prompts`

#### M19 — Governed Reference Data 2.0: Patterns, Frequencies, and Tool Taxonomy

Why second:
- The data model already supports most of the missing metadata.
- Enriched reference data becomes the source for admin, QA hints, capture,
  canvas intelligence, and narratives.

Primary code touchpoints:
- `apps/api/app/migrations/seed.py`
- `apps/api/app/models/governance.py`
- `apps/api/app/services/reference_service.py`
- admin web pages and shared types

Workbook evidence:
- `TPL - Patrones`
- `TPL - Diccionario`
- `TPL - Supuestos`

#### M20 — Canvas Intelligence: Standard Combinations + Overlay Governance

Why third:
- The new canvas exists, but it still needs workbook-grade semantics.
- This milestone turns the canvas from a visual editor into a governed design aid.

Primary code touchpoints:
- `apps/web/components/integration-canvas.tsx`
- `apps/web/components/integration-design-canvas-panel.tsx`
- catalog patch APIs
- potential reference endpoints for combination metadata

Workbook evidence:
- `TPL - Diccionario` combinations `G01`–`G18`

#### M21 — Volumetry Assumption Parity: Service Limits + Unit Governance

Why fourth:
- Once import fidelity and governed reference data are correct, the technical
  math can be aligned without mixing source ambiguity with calculation errors.

Primary code touchpoints:
- `packages/calc-engine/src/engine/volumetry.py`
- `apps/api/app/services/recalc_service.py`
- `apps/api/app/migrations/seed.py`
- OIC previews and export reference sheets

Workbook evidence:
- `TPL - Supuestos`
- `TPL - Volumetría`

#### M22 — QA Coverage + Confidence Signals

Why fifth:
- QA and dashboard confidence depend on both correct import semantics and
  corrected governed reference data.
- This milestone makes the system honest about both readiness and uncertainty.

Primary code touchpoints:
- `packages/calc-engine/src/engine/qa.py`
- dashboard services and UI
- catalog/detail UX where readiness is surfaced

Workbook evidence:
- `TPL  - Enhancements`
- `TPL - Catálogo`
- `TPL - Supuestos`

#### M23 — Pattern Coverage 03–17: End-to-End Operationalization

Why last:
- It is the broadest milestone and depends on all prior governance, import,
  and assumption work.
- It should not begin before the reference model and QA behavior are trustworthy.

Primary code touchpoints:
- calc-engine
- dashboard grouping
- justification narratives
- exports
- admin and pattern UI

Workbook evidence:
- `TPL - Patrones`
- `TPL  - Enhancements`

### Recommended implementation order inside the codebase

1. **M18** first
   - This removes the most visible data-quality bugs (`Column N`, wrong Interface Name,
     wrong Initial Scope, partial trigger semantics).
2. **M19** next
   - This gives the app the governed metadata backbone it is currently missing.
3. **M20** after that
   - This lets the canvas consume real workbook knowledge instead of hardcoded hints.
4. **M21** next
   - This corrects technical limits and unit handling with the new governance baseline.
5. **M22** next
   - This makes readiness and forecast confidence truthful.
6. **M23** last
   - This is the largest scope expansion and should start from a stable parity foundation.

### Explicit code drifts worth fixing early

These are specific drifts already confirmed during analysis:

- `apps/api/app/migrations/seed.py`
  - patterns seeded with minimal metadata only
  - frequency catalog is missing workbook `FQ` coverage and uses `Tiempo real = 1440`
- `packages/calc-engine/src/engine/volumetry.py`
  - `Tiempo real = 1440`, which conflicts with workbook proxy semantics
- `apps/web/components/integration-canvas.tsx`
  - local frequency helper also treats `Tiempo real` as `1440`
- `packages/calc-engine/src/engine/qa.py`
  - valid trigger vocabulary is narrower than workbook capture semantics
- `apps/api/app/services/import_service.py`
  - import still relies on fallback column indexes and partial normalization for
    workbook-rich semantics

### What should not be done prematurely

- Do not add pricing-led dashboards as a default mode just because the workbook
  contains pricing references.
- Do not broaden pattern support without first deciding whether parity mode truly
  supports those patterns end-to-end.
- Do not add new database tables for combinations unless the existing governance
  model cannot express them cleanly; `DictionaryOption` metadata or a governed
  JSON seed may be enough initially.

### Deliverable created from this analysis

This analysis has been converted into:

- new pending milestones `M18`–`M23` in `AGENTS.md`
- matching pending rows in the `README.md` milestone table
- this report as the detailed evidence trail for future execution
