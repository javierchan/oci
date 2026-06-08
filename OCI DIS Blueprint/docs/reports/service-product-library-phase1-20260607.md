# Service Product Library Phase 1 Validation

Date: 2026-06-07

## Scope

Phase 1 adds a governed Service Product Library under Admin without changing the semantics of Integration Patterns.

Integration Patterns remain tool-agnostic. Service Products describe concrete product capabilities, limits, evidence sources, and interoperability rules for implementation choices.

Scope decision: Service Products remains Oracle-only for now. Non-Oracle tools are intentionally excluded from the current library and verification allowlist.

## Implemented

- Added normalized service product governance tables for versions, limits, evidence sources, interoperability rules, verification jobs, and verification findings.
- Reused `service_capability_profiles` as the backward-compatible product base so existing Canvas/service consumers remain stable.
- Seeded product versions, normalized limits, official evidence sources, and an initial interoperability matrix.
- Added read APIs for product list, product detail, service limits, interoperability matrix, and verification jobs.
- Added Admin Library `Service Products` entry.
- Renamed visible admin card from `OIC Patterns` to `Integration Patterns`.
- Added Service Product list and detail pages.
- Regenerated `docs/api/openapi.yaml`.
- Expanded the Oracle Data Integration product portfolio with OCI Data Flow, OCI Data Catalog,
  OCI GoldenGate Data Transforms, Oracle Data Integrator, Oracle Stream Analytics, and
  Oracle Enterprise Data Quality.
- Added bounded Verification Agent execution with Oracle source allowlist, HTTP fetch, content
  hashing, evidence status updates, persisted jobs, persisted findings, and manual finding review.
- Added asynchronous Verification Agent dispatch through Celery. The public API is async-only; deterministic worker execution is covered at the service layer.
- Added conservative source-claim extraction for governed service-limit diffs and deprecation review signals.
- Added accepted-finding application for service-limit updates with audit events; no internet-derived rule mutates automatically.
- Added verification alert queue for stale evidence and open findings.
- Added Verification Agent UI controls on Service Products list and product detail pages.

## Validation

- `docker compose exec -T api pytest app/tests/test_service_products_api.py -v`
  - Result: 8 passed.
- `docker compose exec -T api ruff check app/routers/service_products.py app/services/service_product_service.py app/schemas/service_products.py app/workers/service_verification_worker.py app/workers/celery_app.py app/tests/test_service_products_api.py`
  - Result: all checks passed.
- `docker compose build web`
  - Result: Next.js production build, lint, and type checks passed.
- `docker compose exec -T api alembic upgrade head`
  - Result: migration `20260607_0012` applied.
- `docker compose exec -T api python -m app.migrations.seed`
  - Result: `service_product_library=181`.
- Live API smoke:
  - Initial Phase 1 products: 12.
  - Initial Phase 1 matrix rules: 12.
  - First product detail returned limits and evidence.
- Expanded portfolio smoke:
  - Products: 18.
  - Matrix rules: 22.
  - Oracle Data Integration portfolio products present:
    `DATA_INTEGRATION`, `DATA_FLOW`, `DATA_CATALOG`, `GOLDENGATE`,
    `GOLDENGATE_DATA_TRANSFORMS`, `ODI`, `STREAM_ANALYTICS`, and
    `ENTERPRISE_DATA_QUALITY`.
- Verification Agent smoke:
  - Live async `POST /api/v1/service-products/verification-jobs` scoped to `DATA_CATALOG`.
  - Result after worker execution: completed, `sources_checked=1`, `changes_detected=0`, `findings=0`.
  - Live all-products UI run completed through polling with `sources_checked=8`, `changes_detected=0`, `findings=0`.
  - Celery beat service starts successfully with schedule state stored under `/tmp`.
- Browser validation:
  - `/admin` shows `Integration Patterns` and `Service Products`.
  - `/admin/services` shows product cards and the interoperability matrix.
  - `/admin/services` shows Verification Alerts and Open Findings summary.
  - `/admin/services/OIC3` shows limits, evidence, and interoperability.
  - `/admin/services/DATA_FLOW` shows limits, evidence, and interoperability.
  - `/admin/services/DATA_CATALOG` shows the Verification Agent panel.
  - Verification Agent run from the browser completed on both list and scoped product pages.
  - Mobile viewport 390px renders without horizontal overflow.
  - No browser console errors.
  - No global horizontal overflow detected at the default 1280px viewport.

## Remaining

- Decide whether the scheduled stale-source scan should be enabled by default in production or kept opt-in with `SERVICE_VERIFICATION_SCHEDULE_ENABLED`.
- Improve claim extraction beyond conservative existing-limit diffs if future evidence sources require richer parsers for capabilities or interoperability.
- Add an admin runbook for evidence-source operations and approval ownership.

## Production Readiness Cleanup

- Retired the legacy public `/api/v1/services` route group from the mounted FastAPI app.
- Promoted `/api/v1/service-products` as the only public Service Product Library contract.
- Removed `execution_mode` from the public verification-job request schema; sync execution remains an internal service-layer test path only.
- Updated the Integration Design Canvas to consume service limits from governed Service Product detail responses rather than the retired raw service-profile endpoint.
- Hardened Admin-governed mutation routes so `X-Actor-Role` is required instead of defaulting silently to `Admin`.
