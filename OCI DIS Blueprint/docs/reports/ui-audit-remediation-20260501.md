# UI Audit Remediation Report - 2026-05-01

## Scope

Remediated the 10 findings from `full-app-visual-functional-audit-20260501.md` against the live Docker stack at:

- Web: `http://localhost:3000`
- API: `http://localhost:8000/api/v1`
- Demo project: `20a23466-dd52-4d5a-a3f5-1bc66f659c78`
- Representative integration: `55d40a1b-bad5-4426-af01-606074e3b857`

## Remediation Status

| Finding | Status | Resolution |
| --- | --- | --- |
| FINDING-001 | Resolved | Canvas governance now filters to active, coded, described, volumetric `TOOLS` and `OVERLAYS`; existing uncoded `TOOLS` records were deactivated by Alembic migration `20260501_0009`; active API payload returns 7 governed core tools only. |
| FINDING-002 | Resolved | Integration detail now shows a mobile fallback summary below `640px` instead of exposing the draggable canvas in an unusable narrow viewport. |
| FINDING-003 | Resolved | Frequency, tool, and overlay governance descriptions were translated to English US in seed data and migrated into the live database. |
| FINDING-004 | Resolved | Graph controls now label the selector as `Focus System`, focused mode announces `Focused View: <system>`, and the primary action is `Show full topology`. |
| FINDING-005 | Resolved | Catalog table now has 7 primary columns and starts with the preview drawer collapsed; selecting a row opens the drawer intentionally. |
| FINDING-006 | Resolved | Admin pattern cards now include a read-only `View details` modal with description, when-to-use, avoid, OCI components, technical flow, and business value. |
| FINDING-007 | Resolved | Dashboard parity card is now labeled `Phase 1 Workbook Benchmark` and explicitly states those values are not current project totals. |
| FINDING-008 | Resolved | Singular `/admin/dictionaries/TOOL` is normalized to `/admin/dictionaries/TOOLS`; API also returns canonical category `TOOLS`. |
| FINDING-009 | Resolved | Catalog page-size selector now has `aria-label="Rows per page"`. |
| FINDING-010 | Resolved | Route validation was corrected in the remediation Playwright script by using actual route values and excluding the previously incorrect assumptions version path. |

## Live Data Verification

- `GET /api/v1/dictionaries/TOOLS` returns 7 active tools: OIC Gen3, OCI Streaming, OCI Queue, OCI Functions, OCI Data Integration, Data Integrator, Oracle GoldenGate.
- `GET /api/v1/dictionaries/TOOLS?include_inactive=true` still exposes inactive legacy records for admin auditability.
- `GET /api/v1/dictionaries/canvas-governance` returns only governed core tools, overlays, and 18 canvas combinations.
- `/admin/dictionaries/TOOL` redirects client-side to `/admin/dictionaries/TOOLS`.

## Screenshots

Remediation screenshots were generated under:

`output/playwright/remediation-20260501/`

Files:

- `01_admin_tools_active_only.png`
- `02_admin_tool_alias_redirect.png`
- `03_catalog_collapsed_preview.png`
- `04_catalog_preview_open.png`
- `05_dashboard_benchmark_copy.png`
- `06_graph_focus_context.png`
- `07_pattern_detail_modal.png`
- `08_mobile_canvas_fallback.png`

## Validation

- Web type-check: `cd apps/web && npx tsc --noEmit --skipLibCheck` passed.
- Web lint: `cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0` passed.
- Web unit tests: `cd apps/web && npm test` passed, 19 tests.
- API lint: `docker compose exec -T api ruff check .` passed.
- API + calc tests: `docker compose exec -T api python -m pytest app/tests /calc-engine/src/tests -q` passed, 87 tests.
- Focused backend tests: `docker compose exec -T api python -m pytest app/tests/test_reference_api.py app/tests/test_reference_seed.py app/tests/test_catalog_api.py -q` passed, 13 tests.
- Docker production build: `docker compose up -d --build web` passed and recreated the production-mode web container.
- Playwright remediation smoke: passed with 8 screenshots and zero console/page errors.

## Residual Risk

No open audit findings remain from the 2026-05-01 full-app visual/functional audit. The inactive legacy dictionary records remain available only when explicitly requesting inactive options, preserving governance auditability without exposing them to active workflows.
