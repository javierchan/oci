# Full App Visual + Functional Audit — 2026-06-07

## Scope

Audited the live OCI DIS Blueprint app through a real Chromium browser against:

- Web: `http://localhost:3000`
- API: `http://localhost:8000`
- Project: `20a23466-dd52-4d5a-a3f5-1bc66f659c78`
- Integration: `55d40a1b-bad5-4426-af01-606074e3b857`
- Existing synthetic job detail: `7e586f64-f142-46b5-b96e-74aaac836760`
- New synthetic smoke job: `7c000b20-f9a1-402e-9f43-65960c033866`

Artifacts:

- Browser audit JSON: `output/playwright/full-app-audit-2026-06-07T0434Z/data/full-app-audit-results.json`
- Browser audit script: `output/playwright/full-app-audit-2026-06-07T0434Z/full_app_audit.cjs`
- Screenshots: `output/playwright/full-app-audit-2026-06-07T0434Z/screens/`

## Browser Coverage

Final Playwright run:

- Desktop routes: 19
- Mobile routes: 7
- Safe interaction checks: 14
- Screenshots: 33
- Route failures: 0
- Interaction failures: 0
- Dark mode failures: 0

Routes covered:

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
- `/admin/synthetic/7e586f64-f142-46b5-b96e-74aaac836760`

Safe interactions covered:

- Projects filter.
- Catalog drawer tabs: Overview, Canvas, Volumetry, QA, History.
- Catalog rows-per-page select accessible label.
- Capture wizard empty action stays inside governed form.
- Graph topology SVG render and full-topology/all-systems state.
- Admin pattern editor open.
- Admin dictionary editor open.
- Admin assumptions version editor open.
- Synthetic job detail render.
- Dark-mode dashboard capture.

## Technical Validation

- API health inside container: `{"status":"ok","version":"1.0.0"}`
- Web build without Docker cache: passed.
  - `npm ci`: passed, 0 vulnerabilities reported for the web dependency build.
  - `next build`: compiled successfully.
  - Next lint/type validation step: passed.
  - Static page generation: 12/12 passed.
- Backend focused tests: `app/tests/test_synthetic_service.py` passed 6/6.
- Admin Synthetic Lab smoke:
  - `ok: true`
  - job `7c000b20-f9a1-402e-9f43-65960c033866`
  - terminal status `cleaned_up`
  - catalog count `18/18`
  - distinct systems `32/12`
  - patterns covered `#01` through `#17`

## Findings

No blocking functional or visual failures remain in the audited surfaces.

Observed but non-blocking:

- The production web container does not include devDependencies, so `npm run lint` and `npm run type-check` are not valid against the runtime image. The correct validation path is the Docker builder stage, confirmed with `docker compose build --no-cache web`.
- Synthetic Lab still displays historical failed jobs from earlier validation runs. The current smoke job and latest corrected flow pass and clean up successfully.
- The invalid project route intentionally returns HTTP 404 while rendering the user-friendly unavailable-project page. The audit treats this as expected behavior.

## Status

Current status: validated.

No product code changes were required after this audit pass; only the audit script/report artifacts were added for traceability.

## Addendum — AI Value Pack Follow-Up

After the original full-app audit, the AI Review and Import intelligence surfaces were expanded and revalidated on the same live Docker stack.

Additional browser checks covered:

- Dashboard AI Review provider/quota, project job execution, history comparison, and Markdown export link.
- Import Data Quality Assistant for batch `688346bb-fca9-49f5-be56-a1642d56a16c`.
- Integration Canvas "Review canvas with AI" entry point and integration-scoped history comparison.
- Catalog drawer tabs using the accessible `role="tab"` contract.
- Topology dependency-path co-pilot using graph context and project-scoped history comparison.

Additional validation:

- `docker compose build web` passed.
- `docker compose exec -T api pytest app/tests/test_ai_reviews_api.py app/tests/test_import_service.py app/tests/test_exports_api.py -v` passed 18/18.
- `docker compose exec -T api ruff check ...` passed.
- `apps/api/scripts/export_openapi.py --check` passed after regenerating `docs/api/openapi.yaml`.
- Browser console and API/web logs showed no unexpected errors.
