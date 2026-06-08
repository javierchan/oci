# Production Readiness Cleanup

Date: 2026-06-07

## Scope

This pass removed legacy Service Product surfaces from the active app contract, hardened the affected governance mutations, and validated the changed flows functionally and visually in Docker.

## Changed

- Retired the public legacy `/api/v1/services` route group from the mounted FastAPI app.
- Renamed the router and tests from generic `services` naming to `service_products`.
- Promoted `/api/v1/service-products` as the only public Service Product Library API contract.
- Removed `execution_mode` from the public Verification Agent request schema.
- Kept Verification Agent deterministic execution covered through the service layer instead of exposing sync execution over HTTP.
- Updated the Integration Design Canvas to load governed Service Product detail responses and derive its service-limit map from normalized `limits`.
- Made Admin role headers required on assumptions, patterns, and Service Product finding review mutations.
- Fixed mobile horizontal overflow on Service Product detail pages by containing wide table layouts inside responsive columns.
- Regenerated `docs/api/openapi.yaml`.

## Validation

- `docker compose exec -T api ruff check app/`
  - Result: passed.
- `docker compose exec -T api pytest app/tests -v`
  - Result: 65 passed.
- `docker compose build web`
  - Result: Next.js production build, lint, and type checks passed.
- `docker build --target development -t ocidisblueprint-web-test -f apps/web/Dockerfile .`
  - Result: passed.
- `docker run --rm ocidisblueprint-web-test npm test`
  - Result: 4 files passed, 19 tests passed.
- `docker compose run --rm -v "$PWD:/workspace" -w /workspace -e PYTHONPATH=/workspace/apps/api:/workspace/packages/calc-engine/src api python apps/api/scripts/export_openapi.py --check`
  - Result: OpenAPI artifact is up to date.
- Live API smoke:
  - `/health` returned 200.
  - `/api/v1/service-products` returned 200.
  - `/api/v1/services/` returned 404.
  - Live Verification Agent job creation returned `pending` with clean request payload and completed through the worker without error.
- Browser desktop smoke:
  - `/admin`, `/admin/services`, `/admin/services/DATA_CATALOG`, integration detail/canvas, and topology graph loaded without console errors or global horizontal overflow.
  - Service Products UI created a Verification Agent job through the visible `Run agent` control and returned to a completed state.
- Browser mobile smoke at 390x844:
  - `/admin/services`, `/admin/services/DATA_CATALOG`, and the integration detail/canvas loaded without console errors.
  - Service Product detail mobile overflow regression was fixed; global horizontal overflow is now 0.

## Current Status

The app's changed Service Product Library, Verification Agent, and Integration Design Canvas flows are validated in the Docker runtime and no longer depend on the legacy public services API.

## Remaining Production Risks

- Real identity is still not implemented in this repo. Several mutating web flows send `X-Actor-Id` and `X-Actor-Role` from the frontend helper. This is acceptable only if production deployment is behind a trusted identity-aware gateway that strips client-supplied role headers and injects verified actor headers.
- `docker-compose.yml` remains a local Docker Desktop runtime, not a production deployment manifest.
- `SECRET_KEY` and local service defaults still require environment-specific secret management for production.
- Verification Agent internet access depends on production network egress policy and the allowlisted Oracle evidence sources.

## Next Required Production Step

Define the production identity boundary before external deployment:

- Either implement first-party session/JWT validation in the API and remove client-authored role headers.
- Or formally deploy behind a trusted auth proxy/API gateway that injects signed actor headers and blocks direct API access.
