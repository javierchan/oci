# Product Readiness Audit - 2026-06-04

Workspace: `/Users/javierchan/Documents/GitHub/oci/OCI DIS Blueprint`
Git state at audit start: `main...origin/main [ahead 1]`, clean worktree, commit `945d611d0ccd7e2c13d373c08e802b3fdebca6d3`.

## Executive Summary

OCI DIS Blueprint is in strong demo and phase-parity shape: the stack rebuilds, core backend and frontend quality gates pass, the live seed project contains the expected enterprise-scale dataset, and the main UI surfaces are visually coherent on desktop, mobile, and dark mode.

It is not production-ready yet. The main blockers are product security and operationalization, not basic feature completeness:

1. Real authentication and role enforcement are missing. The API trusts client-supplied actor headers, and the frontend sends a hardcoded Admin identity.
2. The deployment posture is still local-development oriented: default credentials, development API target, hot reload mounts, exposed infrastructure ports, and no production secrets/TLS/backup story.
3. The Admin Synthetic Lab smoke path currently fails end-to-end because generated smoke canvases violate Queue payload governance. The UI E2E test misses this because it stops at `202 pending`.
4. AI review is present as an app surface but needs explicit production boundaries: authz, provider configuration, quotas, audit semantics, and unavailable-provider UX.
5. Python dependency and container security governance is not yet at production level, even though `npm audit` is clean.

Recommended productization stance: treat this as a high-quality functional prototype / internal demo. Before external or production use, close the P0 security and deployment items, then make synthetic smoke and E2E terminal validation blocking CI gates.

## Validated Strengths

- Full stack rebuilt successfully with Docker Compose.
- API migrations applied successfully with `alembic upgrade head`.
- Backend regression suite passed: `95 passed in 2.12s`.
- API lint passed: `ruff check .` -> `All checks passed!`.
- API type check passed: `mypy app --ignore-missing-imports --no-error-summary`.
- OpenAPI artifact is current: `apps/api/scripts/export_openapi.py --check`.
- Web production build passed under `node:26.0.0-alpine`.
- Web TypeScript check passed under Node 26 after build completed.
- Web lint passed with the ESLint CLI script.
- Web unit tests passed: 4 files, 19 tests.
- `npm audit` passed with `found 0 vulnerabilities`.
- Runtime health passed: `GET /health` -> `{"status":"ok","version":"1.0.0"}`.
- Web root redirects correctly: `/` -> `/projects`.
- Visual audit captured 30 route/viewport screenshots across desktop and mobile.
- Dark mode audit covered dashboard, catalog, detail, graph, and Admin Synthetic surfaces.
- Live enterprise project is coherent:
  - `catalog_integrations`: 480
  - `source_integration_rows`: 516
  - `pattern_definitions`: 17
  - graph nodes: 72
  - graph edges: 338
  - dashboard snapshots: 3
  - volumetry snapshots: 3
  - justifications: 480

## Functional/API Smoke Coverage

Representative live API probes returned HTTP 200 and expected shapes:

- `GET /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `GET /api/v1/catalog/{project_id}`
- `GET /api/v1/catalog/{project_id}/graph`
- `GET /api/v1/dashboard/{project_id}/snapshots`
- `GET /api/v1/volumetry/{project_id}/snapshots`
- `GET /api/v1/audit`
- `GET /api/v1/patterns`
- `GET /api/v1/dictionaries/TOOLS`
- `GET /api/v1/catalog/{project_id}/canvas/governance`
- `GET /api/v1/assumptions`
- `GET /api/v1/admin/synthetic/presets`
- `GET /api/v1/admin/synthetic/jobs`

Pattern metadata in the active database is English-facing for all 17 patterns.

## Visual Assessment

Overall visual readiness is good for an internal product:

- Desktop catalog is dense, readable, and operationally useful.
- Mobile catalog uses a card layout and avoids table overflow.
- Dashboard, graph, admin, import, capture, and invalid-project surfaces render without fatal errors.
- Graph view is visually readable and uses focused topology effectively.
- Dark mode is readable and coherent across the audited product surfaces.

Confirmed visual issue:

- Mobile integration detail has horizontal overflow at 390px viewport: `scrollWidth=424`, caused by the Source Data / card content width. This is polish-level, but should be fixed before production because detail pages are core review surfaces.

Screenshots and audit JSON were generated under:

- `output/playwright/product-readiness-audit-20260604/screens/`
- `output/playwright/product-readiness-audit-20260604/visual-audit-results.json`
- `output/playwright/product-readiness-audit-20260604/dark-mode-results.json`

## Findings

### P0 - Real auth and RBAC are not production-ready

Evidence:

- `apps/api/app/services/authz.py:8` checks only whether `actor_role` equals `Admin`.
- `apps/api/app/routers/assumptions.py:36`, `:68`, and `:86` default missing `X-Actor-Role` to `Admin`.
- `apps/api/app/routers/patterns.py:54`, `:67`, and `:79` default missing `X-Actor-Role` to `Admin`.
- `apps/api/app/routers/dictionaries.py` and `apps/api/app/routers/admin_synthetic.py` require the header but still trust the caller-supplied value.
- `apps/web/lib/api.ts:91` sends `X-Actor-Id: web-admin` and `X-Actor-Role: Admin` from the client wrapper.

Impact:

Any client that can reach the API can claim admin privileges by sending headers, and some admin mutation routes default to Admin when the header is absent. This is acceptable only for local/demo mode.

Required product work:

- Add real identity provider integration.
- Validate signed tokens server-side.
- Map authenticated users to project-scoped roles in the database.
- Enforce authorization in service-layer policies, not client headers.
- Remove Admin defaults from mutating routes.
- Add negative auth tests for anonymous, Viewer, Analyst, Architect, and Admin paths.

### P0 - Deployment, secrets, and infrastructure are local-development oriented

Evidence:

- `apps/api/app/core/config.py:13` defaults `ENVIRONMENT` to `development`.
- `apps/api/app/core/config.py:24` defaults `SECRET_KEY` to `change-me-in-production`.
- `docker-compose.yml:21-23` uses local DB credentials `dis/dis`.
- `docker-compose.yml:58` builds the API `development` target.
- `docker-compose.yml:77` mounts `./apps/api:/app` for hot reload.
- `docker-compose.yml:99` runs the worker from the development image.
- `docker-compose.yml:140` uses `minio/minio:latest`.
- `docker-compose.yml:144-145` uses local MinIO credentials `minio/minio123`.
- DB, Redis, MinIO, API, and web ports are exposed for local development.

Impact:

The repo has a good local stack, but no production deployment contract. There is no enforceable secrets flow, TLS ingress, managed database/storage plan, backup/restore procedure, migration release process, or container hardening baseline.

Required product work:

- Add production deployment manifests or IaC for the intended target platform.
- Use production API/worker image targets.
- Remove hot reload mounts outside local compose.
- Move secrets to a secret manager.
- Pin infrastructure images and scan them.
- Add TLS, network isolation, backups, restore drills, and migration runbooks.
- Define environment-specific CORS and host policies.

### P1 - Admin Synthetic Lab smoke generation currently fails end-to-end

Evidence:

- `apps/api/scripts/smoke_admin_synthetic_lab.py` failed for `ephemeral-smoke`.
- `apps/api/scripts/smoke_admin_synthetic_lab.py --preset-code retained-smoke` also failed.
- Latest DB job samples:
  - `ephemeral-smoke` -> `failed`
  - `retained-smoke` -> `failed`
- Error detail:

```text
Oracle-backed canvas blockers detected: Queue payload exceeds the documented message limit.
OCI Queue should carry a lightweight reference, not the full payload.
Payload 870 KB exceeds 256 KB.
```

Impact:

M24's operational validation path is not green. The failure is especially important because it comes from the app's own governed canvas validation, meaning the synthetic generator is producing invalid governed designs for smoke presets.

Required product work:

- Fix synthetic smoke generation so Queue-based rows use pointer/token semantics or payloads under the governed limit.
- Add a regression test at the service layer for Queue payload governance.
- Make the backend smoke script a blocking CI gate once the local stack is available.
- Decide whether existing failed smoke jobs should be cleaned or preserved as audit evidence.

### P1 - Admin Synthetic UI E2E gives a false-positive smoke signal

Evidence:

- `apps/web/e2e/admin-synthetic.spec.ts:38-52` asserts that POST returns `202` and status is `pending`.
- `apps/web/e2e/admin-synthetic.spec.ts:56-61` opens the detail page and checks static sections.
- It does not poll until terminal `completed` or `cleaned_up` state.
- The backend smoke script does poll terminal state at `apps/api/scripts/smoke_admin_synthetic_lab.py:136-149` and correctly fails on terminal `failed`.

Impact:

The UI E2E suite passes while the actual synthetic job fails moments later. This weakens confidence in production smoke coverage.

Required product work:

- Extend E2E to poll the job detail API until terminal state.
- Assert successful terminal state and expected counts.
- Surface failed job messages clearly in the UI and assert that path separately.

### P1 - AI review needs production boundaries before exposure

Evidence:

- `apps/api/app/core/config.py:38-47` has empty/default AI provider configuration.
- `apps/web/lib/api.ts` exposes AI review types and API calls through the same Admin header model.
- The app has visible AI review workflow surfaces, but local default provider state is not production-ready.

Impact:

If enabled for production, this surface needs stricter authz, provider availability handling, quota controls, data retention policy, and audit semantics. If not enabled, the UI should make unavailable status explicit instead of presenting it like a fully operational feature.

Required product work:

- Gate AI review by role and project policy.
- Add explicit provider health/configuration status.
- Add rate limits, request budgets, and audit events for AI actions.
- Define data handling and retention policy for external model/provider calls.
- Add negative tests for unauthorized AI review actions.

### P1 - Python dependency and container security governance is incomplete

Evidence:

- `npm audit` is clean after the Node/runtime update.
- Python dependencies are pinned directly in `apps/api/requirements.txt`, but there is no lock/constraints file for transitive dependencies.
- No `pip-audit`, `safety`, or container vulnerability scan was run as part of this audit.

Impact:

Frontend dependency posture is now measurable, but backend/container security is not yet equivalently governed.

Required product work:

- Add Python dependency locking or constraints.
- Add `pip-audit` or equivalent to CI.
- Add container image vulnerability scanning.
- Define patch cadence and exception process.

### P2 - Mobile integration detail overflow

Evidence:

- Visual audit at 390px mobile viewport found `scrollWidth=424`.
- The visible offender is the integration detail Source Data card/content block.

Impact:

This is not a functional blocker, but it reduces polish and confidence on a core review surface.

Required product work:

- Constrain Source Data/raw-column card width on mobile.
- Ensure long field labels and raw values wrap inside the card.
- Add a Playwright assertion for no horizontal overflow on integration detail.

### P2 - Product operations are not yet fully specified

Evidence:

The app has strong feature parity, but production operations are not yet represented as enforceable app contracts.

Required product work:

- User onboarding and organization/project membership.
- Project-level access boundaries and audit retention.
- Import file lifecycle and storage retention.
- Backup/restore and disaster recovery.
- Error monitoring, traces, metrics, and alerting.
- Release management and migration rollback policy.
- Support/admin workflows for failed jobs, imports, exports, and AI review requests.

## Productization Backlog

### P0 before production

1. Replace trusted actor headers with real authentication.
2. Implement project-scoped RBAC in the service layer.
3. Remove Admin defaults from mutating routes.
4. Add production deployment manifests/IaC.
5. Move all secrets to a managed secret store.
6. Define TLS, network isolation, CORS, backup, restore, and migration runbooks.
7. Fix Synthetic Lab smoke generation and make backend smoke terminal success required.

### P1 for production hardening

1. Add Python dependency locking and security scanning.
2. Add container vulnerability scanning.
3. Extend E2E smoke tests to terminal job state and expected counts.
4. Harden AI review with role gates, provider health, budgets, audit, and data policy.
5. Add observability: structured logs, correlation IDs in UI-visible failures, metrics, traces, and alerts.
6. Add operational admin views for failed jobs and cleanup actions.
7. Fix mobile integration detail overflow.

### P2 for product polish

1. Add guided first-run/onboarding flow for real users.
2. Improve mobile detail density for raw source and lineage sections.
3. Add accessibility checks to CI.
4. Add production copy review for empty, loading, error, and unavailable-provider states.
5. Add screenshot-based visual regression for the main project surfaces.

## Validation Command Log

Executed:

```bash
docker compose up -d --build
docker compose exec -T api alembic upgrade head
docker compose exec -T api python -m pytest app/tests /calc-engine/src/tests -q
docker compose exec -T api ruff check .
docker compose exec -T api mypy app --ignore-missing-imports --no-error-summary
./.venv/bin/python apps/api/scripts/export_openapi.py --check
docker run --rm --user 501:20 -e npm_config_cache=/tmp/npm-cache -v "$PWD:/workspace" -w /workspace node:26.0.0-alpine npm --prefix apps/web run build
docker run --rm --user 501:20 -e npm_config_cache=/tmp/npm-cache -v "$PWD:/workspace" -w /workspace node:26.0.0-alpine npm --prefix apps/web run type-check
docker run --rm --user 501:20 -e npm_config_cache=/tmp/npm-cache -v "$PWD:/workspace" -w /workspace node:26.0.0-alpine npm --prefix apps/web run lint
docker run --rm --user 501:20 -e npm_config_cache=/tmp/npm-cache -v "$PWD:/workspace" -w /workspace node:26.0.0-alpine npm --prefix apps/web test
docker run --rm --user 501:20 -e npm_config_cache=/tmp/npm-cache -v "$PWD:/workspace" -w /workspace node:26.0.0-alpine npm audit
curl -sf http://localhost:8000/health
npm --prefix apps/web run test:e2e:install
npm --prefix apps/web run test:e2e
./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_lab.py
./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_lab.py --preset-code retained-smoke
```

Results:

- All quality gates passed except the Admin Synthetic backend smoke checks.
- UI E2E passed but is incomplete because it does not wait for terminal job success.
- The first frontend type-check was run concurrently with a production build and failed due `.next/types` being regenerated; a subsequent isolated type-check passed.
- Node 26 Playwright E2E emitted a tooling deprecation warning for `module.register()`, but tests still passed.

## Remaining Risks and Assumptions

- This audit did not run `pip-audit`, container image scanning, or accessibility tooling.
- This audit did not validate production cloud deployment because the repo currently defines local Docker Compose as the executable environment.
- Smoke testing created failed synthetic job records in the local database. They were left in place as evidence.
- The conclusion is based on the current workspace only; no cross-workspace assumptions were used.
