## Purpose

Admin Synthetic Lab defines how OCI DIS Blueprint can generate governed synthetic
projects that exercise the real import, catalog, volumetry, dashboard,
justification, audit, graph, and export flows end to end. The goal is not mock
data for screenshots. The goal is a deterministic enterprise-scale test asset
that is large enough to validate product behavior, performance, governance, and
demo readiness without relying on customer workbooks.

## Why It Fits This Codebase

The current product already has the right primitives:

- `Project`, `ImportBatch`, `SourceIntegrationRow`, and `CatalogIntegration`
  provide traceable source-to-governed catalog lineage.
- `VolumetrySnapshot`, `DashboardSnapshot`, `JustificationRecord`, and
  `AuditEvent` already persist the downstream artifacts the synthetic project
  needs to exercise.
- `app/services/` already owns import, catalog mutation, recalculation,
  dashboard, export, and justification behavior.
- `apps/web/app/admin/` already exists as the governance surface and is the
  correct home for the admin-only synthetic lab.

Because those primitives already exist, the synthetic capability should be
implemented as a governed orchestration layer on top of existing services, not
as a separate bypass path.

## Placement In Product Structure

The feature belongs in the governance/admin slice, not in the architect or
analyst workflow. Synthetic generation creates system-scale test artifacts,
touches reference data assumptions, and can produce large volumes of records and
exports. That makes it an administrative capability with explicit safeguards.

Current delivery slice:

- reusable backend generation service
- executable script for deterministic seeding
- generated reports for validation and traceability
- admin-only API
- persisted job tracking
- async worker execution
- full admin UI

Later extension slice:

- additional governed presets beyond the default enterprise reference template
- richer preset management and policy authoring
- expanded operational runbooks and scheduled synthetic refresh workflows

## Frontend Placement Real

Implemented home in the current Next.js app:

- `apps/web/app/admin/page.tsx`
  Add a clear entry point card for Synthetic Lab.
- `apps/web/app/admin/synthetic/page.tsx`
  New admin landing page for presets, job submission, and recent runs.
- `apps/web/app/admin/synthetic/[jobId]/page.tsx`
  Job detail page for progress, validation, artifacts, and cleanup actions.

The UI should reuse existing admin patterns: cards, governance summaries,
explicit status labels, and links back into real project surfaces instead of
duplicating catalog or dashboard rendering inside the admin page.

## Backend Placement Real

Implemented backend layout:

- `apps/api/app/services/synthetic_service.py`
  Source of truth for deterministic dataset construction and orchestration.
- `apps/api/app/schemas/synthetic.py`
  Pydantic request/response models for future admin API exposure.
- `apps/api/app/routers/admin_synthetic.py`
  Admin-only router once productized.
- `apps/api/app/workers/synthetic_worker.py`
  Celery task wrapper for long-running generation jobs.
- `apps/api/scripts/seed_synthetic_enterprise_project.py`
  Current executable entrypoint that reuses the service layer.

This keeps routers thin, preserves async SQLAlchemy use in the API, and avoids
placing orchestration inside the calc engine.

## Recommended Route Set

Implemented admin-only API surface:

- `POST /api/v1/admin/synthetic/jobs`
  Submit a governed generation request.
- `GET /api/v1/admin/synthetic/jobs`
  List recent synthetic generation jobs.
- `GET /api/v1/admin/synthetic/jobs/{job_id}`
  Inspect one job, validations, artifacts, and linked project.
- `POST /api/v1/admin/synthetic/jobs/{job_id}/retry`
  Re-run a failed job with the same governed inputs.
- `POST /api/v1/admin/synthetic/jobs/{job_id}/cleanup`
  Archive and remove synthetic artifacts created by that job when allowed.
- `GET /api/v1/admin/synthetic/presets`
  List governed presets/templates.

The created synthetic project itself must continue to be consumed through the
existing supported routes:

- `/api/v1/projects/{id}`
- `/api/v1/catalog/{id}`
- `/api/v1/catalog/{id}/graph`
- `/api/v1/dashboard/{id}/snapshots`
- `/api/v1/volumetry/{id}/snapshots`
- `/api/v1/justifications/{id}`
- `/api/v1/audit/{id}`
- `/api/v1/exports/{id}/...`

## Worker Orchestration Flow

1. Admin submits a governed job request.
2. Router validates and normalizes inputs through Pydantic schemas.
3. Service layer authorizes admin access and persists `SyntheticGenerationJob`.
4. Celery worker executes generation in phases:
   create project, generate workbook, run import, create manual rows, apply
   architect patches, create snapshots, persist justifications, create exports,
   write reports, validate counts.
5. Job status, progress metadata, and validation results are persisted after
   each phase.
6. Admin UI polls job state and links into the resulting project/artifacts.

The worker must never call private shortcuts that bypass the supported product
flows. The whole point of the feature is to validate the real platform.

## Data Model Of The Job

Recommended persisted model: `SyntheticGenerationJob`

Suggested fields:

- `id`
- `requested_by`
- `status`
- `preset_code`
- `input_payload`
- `normalized_payload`
- `project_id`
- `project_name`
- `seed_value`
- `catalog_target`
- `manual_target`
- `import_target`
- `excluded_import_target`
- `result_summary`
- `validation_results`
- `artifact_manifest`
- `error_details`
- `started_at`
- `finished_at`
- `created_at`
- `updated_at`

Recommended status values:

- `pending`
- `running`
- `completed`
- `failed`
- `cleaned_up`

## Input Model

Governed inputs should be explicit and bounded:

- `project_name`
- `preset_code`
- `target_catalog_size`
- `min_distinct_systems`
- `import_manual_split`
- `excluded_import_rows`
- `domain_coverage`
- `pattern_mix`
- `tool_mix`
- `payload_profile`
- `frequency_profile`
- `include_justifications`
- `include_exports`
- `include_design_warnings`
- `cleanup_policy`
- `seed_value`

The input model should allow customization, but only inside bounded,
review-friendly ranges. Free-form arbitrary generation rules would undermine
repeatability and governance.

## Governance Rules

- Only admins can create, retry, or clean up synthetic jobs.
- Synthetic jobs must stamp created projects with synthetic metadata in
  `Project.project_metadata`.
- Synthetic artifacts must be clearly labeled as synthetic in reports and admin
  surfaces.
- The generator must be deterministic for the same normalized inputs and seed.
- The generator must use governed patterns, dictionary options, assumptions, and
  current service constraints from the repository state.
- Failed partial jobs created by the feature may be cleaned up only through
  explicit safe flows. No destructive resets.
- Generation must validate minimum scale and coverage before marking the job
  successful.

## Service Boundaries

- `synthetic_service`
  Build deterministic datasets, workbook payloads, manual payloads, canvas
  state, reports, and orchestration.
- `import_service`
  Remains the source of truth for workbook import persistence.
- `catalog_service`
  Remains the source of truth for manual creation and architect patches.
- `recalc_service`
  Remains the source of truth for volumetry snapshots and design warnings.
- `dashboard_service`
  Remains the source of truth for technical dashboard snapshots.
- `justification_service`
  Remains the source of truth for deterministic narratives and approvals.
- `export_service`
  Remains the source of truth for XLSX, JSON, and PDF artifact generation.

No synthetic feature code should replicate the business rules already owned by
those services.

## Testing Strategy

Backend service tests:

- deterministic dataset generation
- scale validation (`>= 480` catalog rows, `>= 70` distinct systems)
- full 17-pattern coverage
- compact valid canvas serialization within current column limits

Backend integration tests:

- synthetic service runs against a test database
- imported rows create lineage plus included/excluded evidence
- manual rows create governed catalog entries
- snapshots, justifications, and exports are produced

Smoke tests against the running stack:

- project detail
- catalog list
- graph
- dashboard snapshots
- volumetry snapshots
- audit

Frontend tests for the admin UI:

- preset selection and validation
- job submission
- progress polling
- artifact access
- synthetic labeling visibility

## Schema-Dependent Runtime Validation Contract

The Admin Synthetic Lab depends on the persisted
`synthetic_generation_jobs` table introduced by Alembic migration
`20260428_0007`. Code-level quality gates are not enough on their own for this
feature. The running stack must also be schema-aligned before `/admin/synthetic`
or `/api/v1/admin/synthetic/jobs` are treated as validated.

Use this closeout sequence whenever the synthetic job model, router, or worker
changes:

```bash
# 1. Apply the latest API schema to the running dev stack.
docker compose exec -T api alembic upgrade head

# 2. Confirm the running API is healthy.
curl -sf http://localhost:8000/health

# 3. Smoke the read-only admin synthetic endpoints with admin headers.
curl -sf \
  -H 'X-Actor-Id: web-admin' \
  -H 'X-Actor-Role: Admin' \
  http://localhost:8000/api/v1/admin/synthetic/presets

curl -sf \
  -H 'X-Actor-Id: web-admin' \
  -H 'X-Actor-Role: Admin' \
  'http://localhost:8000/api/v1/admin/synthetic/jobs?limit=20'
```

Then reload the live browser page at `http://localhost:3000/admin/synthetic`
and confirm all of the following:

- the page does not show `Failed to fetch`
- the preset selector renders
- the `Project Name` field renders
- the `Create Synthetic Job` button renders in an enabled state
- the recent jobs table renders either real jobs or the empty-state message

When the worker, preset normalization, or cleanup behavior changes, the
read-only smoke above is necessary but not sufficient. Run the governed live
smoke path as well:

Preferred automated path:

```bash
./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_lab.py
```

That script verifies the full bounded contract for the `ephemeral-smoke`
preset:

- API health
- preset catalog exposure
- admin job creation
- polling to a terminal state
- recent jobs list visibility
- `cleaned_up` terminal payload with populated `cleanup_removed_paths`
- bounded validation targets and full `#01` through `#17` pattern coverage

The same script also supports the retained bounded preset:

```bash
./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_lab.py --preset-code retained-smoke
```

For `retained-smoke`, the expected runtime sequence is:

- job reaches `completed`
- generated project remains present long enough to exercise the cleanup route
- cleanup endpoint is invoked by the script
- final job status becomes `cleaned_up`
- `cleanup_removed_paths` is populated in the final payload

Preferred retry-runtime path:

```bash
./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_retry.py
```

That script intentionally seeds a bounded failed source job through the real
service layer, calls `POST /api/v1/admin/synthetic/jobs/{job_id}/retry`, waits
for the retried job to settle, validates the bounded counts and pattern
coverage, and finally cleans up the seeded failed source job so the stack is
not left with a dangling failed runtime artifact.

Preferred browser E2E path:

```bash
cd apps/web
npm run test:e2e:install
npm run test:e2e
```

The Playwright smoke suite validates:

- the `/admin/synthetic` landing page renders governed presets
- the browser can submit a bounded `ephemeral-smoke` job from the UI
- the recent-jobs table renders the created job
- the matching `/admin/synthetic/{job_id}` detail page loads successfully

Operational note for local agent environments:

- on sandboxed macOS agent shells, Playwright browser launch may require an
  unsandboxed execution path because the browser runtime can fail with Mach-port
  permission errors before page navigation begins

Manual fallback:

```bash
# 4. If the synthetic worker code changed, restart the worker and confirm the
#    synthetic task is registered before submitting a live job.
docker compose restart worker
docker compose logs --tail=120 worker

# 5. Submit the bounded smoke preset.
curl -sf \
  -X POST \
  -H 'X-Actor-Id: web-admin' \
  -H 'X-Actor-Role: Admin' \
  -H 'Content-Type: application/json' \
  http://localhost:8000/api/v1/admin/synthetic/jobs \
  -d '{"preset_code":"ephemeral-smoke"}'

# 6. Poll the created job until it reaches a terminal status.
curl -sf \
  -H 'X-Actor-Id: web-admin' \
  -H 'X-Actor-Role: Admin' \
  http://localhost:8000/api/v1/admin/synthetic/jobs/<job_id>
```

Closeout expectations for the bounded smoke preset:

- job status reaches `cleaned_up`
- `normalized_payload.cleanup_policy = "ephemeral_auto_cleanup"`
- top-level `project_id = null` after cleanup
- `result_summary.cleanup_removed_paths` is populated
- validation meets the bounded targets:
  `catalog_count = 18`, `import_included_count = 12`, `manual_count = 6`,
  `excluded_import_count = 2`, `distinct_systems >= 12`
- the recent jobs table renders the cleaned-up run
- the job detail page renders normalized inputs, validation results, and
  cleanup metadata without browser console errors

If the DB schema is behind, the admin synthetic routes must now return a
structured `503` response with:

- `error_code: SYNTHETIC_SCHEMA_NOT_READY`
- `expected_migration: 20260428_0007`
- `recovery_hint: Run 'alembic upgrade head' for the API service and retry.`

That failure mode is intentional. It is preferable to an opaque browser-side
network error because it makes the migration dependency explicit and actionable.

## Delivery Slices

Slice 1:

- reusable backend service
- executable script
- generated reports
- validation and smoke testing

Slice 2:

- persisted `SyntheticGenerationJob` model + Alembic migration
- schemas and OpenAPI exposure
- admin-only API router
- Celery worker orchestration

Slice 3:

- full admin UI under `apps/web/app/admin/synthetic/`
- preset management
- progress and artifact views
- cleanup controls

## Completion Checklist

- M24 milestone documented in `AGENTS.md`
- architecture doc created
- reusable backend synthetic service implemented
- executable synthetic seed script implemented
- final deterministic synthetic project generated successfully
- reports written to `apps/api/generated-reports/`
- API smoke routes verified against the created project
- focused backend validation and quality gates green

## Definition Of Success

Success means a new engineer can clone the repo, run the reference seed, run the
synthetic generator, and immediately inspect a large realistic project through
the same product routes used by real users. The project must be governed,
traceable, reproducible, and large enough to exercise catalog, graph,
volumetry, dashboard, justifications, audit, and export behavior without custom
manual setup.
