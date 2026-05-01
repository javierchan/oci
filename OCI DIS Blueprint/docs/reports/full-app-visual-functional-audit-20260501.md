# Full App Visual + Functional Audit — 2026-05-01

## Scope

Audited the live OCI DIS Blueprint application end to end using Playwright against:

- Web: `http://localhost:3000`
- API health: `http://localhost:8000/api/v1/health`
- Demo project: `20a23466-dd52-4d5a-a3f5-1bc66f659c78`
- Representative integration: `55d40a1b-bad5-4426-af01-606074e3b857`
- Representative synthetic job: `7e2ff2be-9b62-4fa7-8b9a-812f8501cdcf`

Screenshots and machine-readable audit outputs were saved under:

`output/playwright/full-app-audit-20260501/`

## Validation Summary

- Playwright version: `1.59.1`
- App status: `home:200 final:http://localhost:3000/projects`
- API status: `api:200`
- Screenshots generated: `52`
- Base route captures: `31`
- Corrected extra route captures: `2`
- Safe interaction checks: `19`
- Unexpected app crashes: `0`
- Unexpected page JavaScript errors: `0`
- Critical blockers found: `0`

The initial `/admin/assumptions/v1.0.0` capture produced a 404 because that was an audit-route typo. The app correctly serves `/admin/assumptions/1.0.0` with no console errors. The invalid project route intentionally returns the user-friendly not-found surface.

Next.js `_rsc` `net::ERR_ABORTED` entries were observed across pages. They appear to be normal App Router prefetch/navigation aborts, not failed product requests, because all target pages rendered and subsequent route captures passed.

## Routes Covered

- `/`
- `/projects`
- `/projects/20a23466-dd52-4d5a-a3f5-1bc66f659c78`
- `/projects/20a23466-dd52-4d5a-a3f5-1bc66f659c78/import`
- `/projects/20a23466-dd52-4d5a-a3f5-1bc66f659c78/capture`
- `/projects/20a23466-dd52-4d5a-a3f5-1bc66f659c78/capture/new`
- `/projects/20a23466-dd52-4d5a-a3f5-1bc66f659c78/catalog`
- `/projects/20a23466-dd52-4d5a-a3f5-1bc66f659c78/catalog/55d40a1b-bad5-4426-af01-606074e3b857`
- `/projects/20a23466-dd52-4d5a-a3f5-1bc66f659c78/graph`
- `/projects/00000000-0000-0000-0000-000000000000`
- `/admin`
- `/admin/patterns`
- `/admin/assumptions`
- `/admin/assumptions/1.0.0`
- `/admin/dictionaries`
- `/admin/dictionaries/FREQUENCY`
- `/admin/dictionaries/TOOLS`
- `/admin/synthetic`
- `/admin/synthetic/7e2ff2be-9b62-4fa7-8b9a-812f8501cdcf`

Core surfaces were also captured in mobile viewport and dark mode.

## Safe Functional Flows Covered

- Projects list search/filter.
- Dashboard AI Review modal open/close without starting a job.
- Catalog search/filter chips.
- Catalog pagination state.
- Integration detail load, patch panel visibility, canvas visibility.
- Capture wizard empty-state validation, without submitting.
- Import page guidance/template area, without uploading.
- Graph route load and canvas click.
- Admin patterns page and New Pattern editor open, without saving.
- Admin dictionary category and New Option editor open, without saving.
- Admin delete confirmation modal open, without confirming.
- Admin assumptions New Version editor open, without saving.
- Synthetic job detail load.
- Command palette open/filter via keyboard.
- Theme toggle to dark mode.
- Mobile navigation drawer open/close coverage.

## Findings Summary

- Critical: `0`
- High: `2`
- Medium: `5`
- Low: `3`
- Total: `10`

## Findings

### FINDING-001 — Canvas governance taxonomy is polluted by uncoded core-tool records

- Severity: High
- Dimension: Functional governance / canvas validation
- Evidence:
  - Screenshot: `output/playwright/full-app-audit-20260501/screens/15b_admin_dictionary_tools_correct.png`
  - Screenshot: `output/playwright/full-app-audit-20260501/screens/07_integration_detail.png`
  - API: `GET /api/v1/dictionaries/TOOLS` returns `OCI API Gateway`, `Oracle Functions`, `Oracle ORDS`, `ATP`, `Oracle DB`, `SFTP`, `OCI Object Storage`, and `OCI APM` as active `TOOLS` entries with `code=null` and `description=null`.
- Expected: The core-tools dictionary should contain only governed volumetric core tools. Edge protection and observability items should remain overlays; endpoint technologies should not be selectable as core route tools unless explicitly modeled and coded.
- Actual: The design canvas "Core Tools" palette includes overlay and endpoint/runtime technologies, including duplicated concepts such as `OCI Functions` and `Oracle Functions`.
- Impact: Canvas interoperability and combination validation can classify a route as governed using the wrong taxonomy. This weakens the core-tools vs overlays separation introduced for governed design validation.
- Fix hint:
  - Clean existing `DictionaryOption(category="TOOLS")` records with null code/metadata.
  - Canonicalize duplicates, especially `Oracle Functions` to `OCI Functions`.
  - Keep `OCI API Gateway`, `Process Automation`, and `OCI Events` in `OVERLAYS`.
  - Do not place endpoint technologies such as `ATP`, `Oracle DB`, `SFTP`, and `OCI Object Storage` in `TOOLS` unless a new governed category is introduced.
  - Add a migration or cleanup service that enforces category uniqueness and non-null code/description for active governance options.
  - Add tests around `reference_service.get_canvas_governance()` and `catalog_service._load_canvas_validation_context()`.

### FINDING-002 — Integration Design Canvas is not practically usable on mobile

- Severity: High
- Dimension: Mobile workflow / design canvas usability
- Evidence:
  - Screenshot: `output/playwright/full-app-audit-20260501/screens/m04_integration_mobile.png`
  - DOM overflow metrics flagged the integration detail mobile route.
- Expected: On mobile, either the design canvas should provide a usable focused/mobile interaction model or show a clear larger-screen fallback like the graph page does.
- Actual: The canvas renders inside the mobile integration detail page but the route is horizontally clipped; the user sees only the left part of the flow and must manage nested horizontal scrolling, zoom, and pan inside a very narrow viewport.
- Impact: Mobile users can review metadata but cannot reliably inspect or edit the design route. This is a broken workflow if mobile editing/review is considered supported.
- Fix hint:
  - Prefer the graph-page pattern: show a mobile read-only summary and a "Use desktop/tablet to edit canvas" fallback below `640px`.
  - Alternatively, add a dedicated mobile canvas mode with vertical route stacking, zoom controls outside the scroll region, and a visible mini-map.
  - Ensure the canvas toolbar and palette do not create nested horizontal scroll traps.

### FINDING-003 — Tool dictionary metadata still contains Spanish/internal terms

- Severity: Medium
- Dimension: English US / governed metadata
- Evidence:
  - Screenshot: `output/playwright/full-app-audit-20260501/screens/15b_admin_dictionary_tools_correct.png`
  - Static source: `apps/api/app/migrations/reference_seed_data.py`
- Expected: Admin/governance metadata visible in the UI should be English US.
- Actual: Tool descriptions include Spanish abbreviations/terms such as `Msgs/mes`, `particiones`, `Complemento`, `Invocaciones`, `GB procesados`, and `Cambios/mes`.
- Impact: The app UI is mostly English, but governance metadata still leaks Spanish source terminology and looks inconsistent in the admin surface.
- Fix hint:
  - Translate seeded dictionary descriptions in `apps/api/app/migrations/reference_seed_data.py`.
  - Add/update a seed migration that patches existing dictionary option descriptions.
  - Add a simple UI/data smoke test asserting no Spanish governance strings in active admin dictionary payloads.

### FINDING-004 — Graph opens in focused large-topology mode by default

- Severity: Medium
- Dimension: Information architecture / discoverability
- Evidence:
  - Screenshot: `output/playwright/full-app-audit-20260501/screens/08_graph.png`
  - Screenshot: `output/playwright/full-app-audit-20260501/screens/m05_graph_mobile.png`
- Expected: First load should make it clear whether the user is seeing the full topology or a filtered/focused topology.
- Actual: The graph opens with `Finance Inventory Service` selected in the System filter and a "Large topology mode" focus cluster active. This is helpful for readability, but can look like the app is hiding the complete graph.
- Impact: Users may assume the map is incomplete or biased to one system unless they notice the `Clear focus` control.
- Fix hint:
  - Add a stronger mode header, e.g. `Focused view: Finance Inventory Service`.
  - Consider defaulting the system filter to `All` and then offering "Auto-focus largest cluster" as an explicit action.
  - If auto-focus remains default, place `Clear focus / Show full topology` as the primary action.

### FINDING-005 — Catalog desktop drawer competes with table width

- Severity: Medium
- Dimension: Desktop visual hierarchy
- Evidence:
  - Screenshot: `output/playwright/full-app-audit-20260501/screens/06_catalog.png`
- Expected: The catalog table and selected-row drawer should feel intentionally balanced.
- Actual: The persistent drawer consumes substantial horizontal space. Several table columns are therefore aggressively truncated even at 1440px.
- Impact: The table is functional, but scanning many integrations is harder than it should be. Users get a good detail preview at the cost of primary table readability.
- Fix hint:
  - Make the drawer collapsible or convert it to an overlay drawer after row selection.
  - Increase table priority for `Integration`, `Flow`, `Pattern`, and `QA`; move payload and ID into the drawer.
  - Persist drawer collapsed/expanded preference per session.

### FINDING-006 — Admin pattern cards are visually polished but content is too compressed

- Severity: Medium
- Dimension: Admin content usability
- Evidence:
  - Screenshot: `output/playwright/full-app-audit-20260501/screens/10_admin_patterns.png`
- Expected: Pattern library cards should support quick evaluation of when-to-use and avoid guidance.
- Actual: Cards truncate most guidance and component text. The only way to see full content is likely entering edit mode, which is semantically wrong for read-only review.
- Impact: Admin governance review becomes edit-oriented instead of review-oriented.
- Fix hint:
  - Add a read-only pattern detail drawer/modal.
  - Keep cards concise, but add `View details` distinct from `Edit`.
  - Use expandable "When to use" and "Avoid" sections.

### FINDING-007 — Dashboard still mixes workbook-reference metrics with live synthetic scale

- Severity: Medium
- Dimension: Data interpretation / demo clarity
- Evidence:
  - Screenshot: `output/playwright/full-app-audit-20260501/screens/02_project_dashboard.png`
- Expected: Dashboard should clearly separate live project KPIs from historical workbook parity reference values.
- Actual: The dashboard shows live catalog values (`480`) alongside a "Workbook reference" card with `Loaded rows 144`, `TBQ=Y 157`, and `Expected QA review 144`.
- Impact: This is labeled as reference target, but in demos it can still confuse users because the current demo project has 480 rows.
- Fix hint:
  - Rename the section to `Phase 1 Workbook Benchmark`.
  - Add helper copy: `Reference values from the original parity workbook, not current project totals`.
  - Consider moving this card below a collapsed "Parity benchmark" section for non-parity demos.

### FINDING-008 — Singular dictionary category route renders a misleading empty page

- Severity: Low
- Dimension: Routing resilience
- Evidence:
  - Screenshot: `output/playwright/full-app-audit-20260501/screens/15_admin_dictionary_tool.png`
- Expected: `/admin/dictionaries/TOOL` should redirect to `/admin/dictionaries/TOOLS`, show a category-not-found state, or 404.
- Actual: `/admin/dictionaries/TOOL` renders a valid-looking empty category with "0 entries".
- Impact: This route is not linked from the app, but a manually entered or stale link can make users think tool metadata is missing.
- Fix hint:
  - Add category alias normalization for `TOOL -> TOOLS`.
  - Or validate category against the category list and render a category-not-found page.

### FINDING-009 — Catalog page-size selector has no programmatic accessible label

- Severity: Low
- Dimension: Accessibility
- Evidence:
  - Machine check: `output/playwright/full-app-audit-20260501/data/a11y-associated-label-results.json`
  - Static source: `apps/web/components/catalog-table.tsx`
- Expected: The page-size select should have an accessible label.
- Actual: The select is visually preceded by `Show`, but it is not wrapped in a `label`, has no `id/htmlFor`, and has no `aria-label`.
- Impact: Screen readers may announce only the selected number without context.
- Fix hint:
  - Add `aria-label="Rows per page"` to the select in `apps/web/components/catalog-table.tsx`.

### FINDING-010 — Invalid/audit route noise should be excluded from future automated reports

- Severity: Low
- Dimension: Audit tooling quality
- Evidence:
  - Initial route capture included `/admin/assumptions/v1.0.0`, which is not a valid app route.
- Expected: Audit scripts should discover actual route params from API/UI data before capture.
- Actual: A route typo created a false console error.
- Impact: No product issue, but future automated audits could waste time chasing false positives.
- Fix hint:
  - In future scripts, derive assumption detail routes from `GET /api/v1/assumptions/` and use the raw `version` value without display prefixes.

## What Looks Good

- No blank pages or runtime crashes were found across the inspected app surfaces.
- Production-mode web on port `3000` is responsive; the slowest audited route was integration detail at roughly `1.8s` in the Playwright run.
- Invalid project routing is graceful and user-readable.
- Command palette, theme switching, mobile navigation, admin forms, delete confirmation, AI Review modal, catalog filtering, capture validation, and synthetic job detail all functioned without destructive actions.
- Dark mode is broadly readable and cohesive.
- Graph mobile fallback is appropriate and avoids rendering an unusable topology canvas on narrow screens.
- Integration detail now has a substantially stronger design canvas than prior iterations, with visible arrows, service checks, and route summaries.

## Recommended Fix Order

1. Fix dictionary/canvas taxonomy pollution in `TOOLS` vs `OVERLAYS`.
2. Add mobile fallback or mobile-specific UX for Integration Design Canvas.
3. Translate remaining governance metadata to English US.
4. Clarify graph default focused mode.
5. Improve catalog table/drawer balance.
6. Add read-only pattern detail affordance.
7. Clarify dashboard workbook-reference card.
8. Canonicalize `/admin/dictionaries/TOOL`.
9. Add accessible label to catalog page-size selector.
10. Harden future audit route discovery.
