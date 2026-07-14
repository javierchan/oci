# OCI DIS Blueprint Status Report

**Validated:** 2026-07-13
**Branch:** `main`
**Detailed remediation:** `milestone-progress-20260710-140234.md`

## Current Status

| Area | Status | Evidence |
|---|---|---|
| Backend and deterministic engines | complete | 172 tests passed: 108 API, 42 calc-engine, and 22 pricing-engine |
| Frontend | complete | TypeScript, ESLint, 64 tests, and production build passed |
| Browser workflows | complete | 16 Playwright E2E tests passed, including provider telemetry and contextual AI |
| Dependency security | complete | npm audit 0; Docker Scout 0 HIGH/CRITICAL for API and web images |
| Database | complete | Alembic at `20260712_0023`; seed idempotent |
| Runtime | complete | 8 Compose services running; no recent error signatures |
| Effective CI | complete | one root workflow covers code, browser, build, and image gates |

## Governed Rule Ownership

- Service Product Library normalized tables are the operational source for
  service profiles, interoperability, evidence, findings, and 131 active limits.
- Assumption sets contain client/business workload inputs only. Versions
  `1.0.0` and `1.0.1` contain no migrated OIC or Queue service-limit keys.
- Calc-engine static defaults remain deterministic fallbacks for pure isolated
  execution; API recalculation overlays the versioned normalized rule bundle.
- New dashboard, export, and AI-review evidence carries the effective rule
  bundle version and freshness metadata.

## Governed Offline Capture Workbook

- Import downloads template `v2.0.0` from one backend-owned column and version
  contract, with 500 blank capture rows and no example data in the import surface.
- Ten workbook sheets provide novice instructions, preflight checks, guided
  examples, field definitions, patterns, OCI products, limits, interoperability,
  evidence freshness, and official source URLs.
- Named validation ranges and a very-hidden manifest keep dropdowns, headers,
  source counts, generation time, and compatibility metadata deterministic.
- Existing unversioned v1 workbooks remain supported with a legacy warning;
  future major versions, changed v2 headers, and formulas are rejected.
- A generated workbook was filled and imported through the production service
  path with exact field mapping. All ten visible sheets rendered without formula
  errors, and Playwright verified the App metadata and downloaded filename.

## Monthly Consumption Ramps

- New deployment scenarios capture explicit quantities per environment, product,
  billing metric, and month instead of treating percentage as a universal unit.
  Historical percentage scenarios remain readable but are not used for new plans.
- Governed SKU mappings define packaged, fixed-capacity, hourly, continuous, and
  manual-monthly behavior, including quantity unit, minimum, and increment.
- The pure Decimal engine prices every contract month independently, and immutable
  BOM line periods preserve quantity, hours, price tier, amount, warnings, formula,
  and provenance for XLSX/JSON/PDF exports.
- The App exposes monthly run rate, cumulative commitment, first active month,
  stabilization month, peak, timing effect, environment/product composition,
  activation timeline, top drivers, and monthly snapshot comparison.
- The standard editor supports constant and linear real-unit ramps; its monthly
  matrix edits the same normalized plan and contract-duration changes safely
  resize period values without preserving invisible payload rows.
- Browser and Playwright validation completed an approved two-environment,
  fourteen-metric scenario, persisted exact OIC package quantities, reached a
  terminal BOM job, rendered monthly insights, and exercised the editable matrix
  with no page overflow or console errors.

## Explainable Governed AI Reviews

- Architecture Review now leads with the current decision and separates what was
  found, why it matters, and the next concrete action before review history or
  technical evidence.
- One bounded narrative renderer converts optional OCI Generative AI output and
  malformed historical Markdown tables into readable headings, paragraphs, and
  actions without changing persisted evidence.
- Import Quality, BOM Scenario, Service Verification, and the contextual Assistant
  use the same explanatory hierarchy while deterministic findings, service rules,
  quantities, prices, and totals remain authoritative.
- The contextual Assistant resolves project dossiers from the current route,
  attached context, recent user questions, or the sole active project. Exact
  portfolio counts and BOM totals remain deterministic; ambiguous portfolios
  require selection, and unresolved placeholders fail output grounding.
- Browser inspection covered real Project Review, Import Quality, and BOM data in
  light, dark, desktop, and mobile layouts with no console errors. Frontend lint,
  64 tests, the Node 26 production build, 111 API tests, Ruff, mypy,
  healthy production services, and `git diff --check` passed.

## Prescriptive Integration Recommendations

- Integration-scope reviews now derive up to three governed alternatives from the
  saved canvas, patterns, G01-G18 combinations, normalized Service Product limits,
  interoperability, payload, trigger, and frequency evidence.
- Each alternative explains the exact canvas diff, implementation sequence,
  prerequisites, validation plan, trade-offs, confidence, and cost boundary. OCI
  Generative AI compares only these candidates; deterministic engines remain the
  authority for topology validity, volumetry, quantities, and cost.
- Selecting `Preview on canvas` writes an audit decision but does not mutate the
  integration. The canvas displays a dashed candidate overlay, and `Apply to draft`
  changes only unsaved local state until the architect explicitly saves.
- Canvas nodes expose governed role, summary, SLA, pricing basis, and key limit
  context in a persistent editor. Direction markers are clearer and modeled-flow
  animation communicates direction without claiming runtime telemetry.
- Validation passed 108 API, 42 calc-engine, 22 pricing-engine, and 64 frontend
  tests, plus focused AI Review contracts, Ruff, mypy, TypeScript, and ESLint.

## Portfolio Recommendations And Draft Simulation

- Project Review, Topology Investigation, and BOM now share a typed action
  workspace that leads with the proposed change, implementation sequence,
  validation, expected impact, evidence, confidence, and the affected App route.
- Integration Canvas can evaluate a connected unsaved draft before the architect
  commits it. Saved and proposed designs run through the same in-memory volumetry
  service used by recalculation jobs; no catalog row or snapshot is mutated.
- When an approved deployment scenario exists, the same deterministic BOM engine
  computes current and proposed monthly series and derives monthly run-rate,
  contractual, and ramp timing deltas. Incomplete pricing is reported as blocked.
- Explicit-unit demand remains the commercial authority. Existing quantities are
  preserved and a product introduced only by the draft is identified as a sizing
  requirement rather than assigned an inferred client quantity.
- Focused validation passed 108 API, 42 calc-engine, 22 pricing-engine, and 64
  frontend tests, plus Ruff, mypy, TypeScript, ESLint, and OpenAPI generation.
- Production browser validation exercised integration candidate preview, local
  draft application, technical/commercial simulation, Project and Topology action
  workspaces, and BOM recommendations. Desktop light, desktop dark, and 390 px
  mobile views remained readable with no page overflow or browser console errors.
- The controlled draft simulation left persisted evidence unchanged at 14
  volumetry snapshots, 21 BOM snapshots, and 983 audit events; candidate preview
  remains the separately audited architect decision defined by M43.

## Production Runtime

- Compose builds API, worker, beat, and web exclusively from production targets.
- API code, calc engine, and OpenAPI artifacts are packaged into immutable
  images; runtime source-code bind mounts and hot reload are not present.
- API, worker, and beat share one non-root API image. The OCI GenAI override
  mounts the API key only into API and worker, copies it internally with mode
  `0400`, and immediately drops both runtime processes to `app:10001`.
- API and worker share only the persistent `uploads_data` volume required for
  imports and exports; source code never enters that writable volume.

## Production Dependency Cleanup

- Python dependencies are separated into production runtime and non-deployable
  quality sets. The CI aggregate installs both, while the production image
  installs only `requirements-runtime.txt`.
- The API production image excludes pytest, mypy, Ruff, aiosqlite, API tests,
  calc-engine tests, generated reports, and dependency manifests. It retains an
  empty writable `generated-reports` runtime directory required by Synthetic Lab.
- The API production image now uses `python:3.12-alpine`. Docker inspect reports
  approximately 194 MB of image content for API and 73 MB for web; Docker
  Desktop reports approximately 689 MB and 302 MB of local virtual size,
  respectively. Web contains only the standalone Next.js runtime.
- Removed the unused `python-jose`/`ecdsa` dependency and replaced the vulnerable
  Go-based `gosu` binary with Alpine `su-exec`. The OCI GenAI secret bootstrap
  starts as root only long enough to copy the mounted API key, then API and worker
  run as UID/GID `10001`.
- Celery startup broker retry behavior is explicit and regression-tested for
  forward compatibility with Celery 6.
- Removed the unused `@testing-library/react` dependency and moved D3 type
  declarations to frontend development dependencies. `npm audit` remains at zero.
- Removed approximately 1.15 GB of ignored host artifacts, including `.venv`,
  `node_modules`, `.next`, caches, temporary uploads, and test outputs. Versioned
  audit evidence was preserved. Temporary quality and Playwright images were
  deleted after validation; no dangling OCI DIS Blueprint images remain.

## Terminal Job Evidence

- Playwright creates one ephemeral job and asserts final `cleaned_up` state.
- Playwright creates one retained job, asserts `completed`, validates critical
  project surfaces, then cleans it and asserts final `cleaned_up` state.
- PostgreSQL had 0 jobs in `pending` or `running` after the suite.
- Historical `failed` jobs are terminal records retained for audit, not stuck work.

## Runtime Recalculation

- The only active project (`OCI DIS Blueprint Demo Enterprise 2026`) was
  recalculated after the rule-source migration and evidence refresh.
- Recalculation job `1ffe6943-9769-4906-a775-cb201a12a7ae` completed and created
  volumetry snapshot `93aa4451-55c1-477f-9539-8955441067be` plus dashboard
  snapshot `6b1bc014-5fb0-4ec8-8922-e8e61b6380e2`.
- The current snapshot records `service-rules-f349865c8d38e84f` from
  `normalized_service_products`, with `freshness_status=current`, zero stale
  evidence, and zero open findings; historical snapshots remain immutable.

## Service Product Verification

- Governed verification jobs `b27ca6b8-7ec9-40aa-bc70-eacc8f1f7110` and
  `866a1239-29b0-423d-a615-a25cb614b69f` refreshed all 62 previously stale
  evidence records against official Oracle sources.
- One retired OIC documentation URL returned HTTP 404. Alembic revision
  `20260710_0015` replaces it with the canonical
  `message-pack-usage-synchronous-requests.html` source for existing databases,
  and the reference seed now uses the same URL.
- Follow-up verification job `b101426f-e8ee-41bb-9581-839a0ad0bc9b` received
  HTTP 200 and found no content or governed-limit changes. The historical 404
  finding is reviewed with an audit note; no limit update was accepted.
- Final state: 81 of 81 evidence sources verified, zero stale or due sources,
  zero open findings, zero verification alerts, and zero active jobs.
- Browser validation confirmed the Library counters and Verification Agent state
  with no console warnings or errors.

## Residual Risk

- No current evidence-freshness risk is open. Scheduled governed verification
  remains required as each source reaches its configured review interval.
- OCI GenAI credentials, Project metadata, and `openai.gpt-oss-20b` are operational.
  The runtime attempts Responses first and temporarily caches endpoint-level
  unavailability before using governed Chat Completions. Real synthesis, Function
  Calling, persisted AgentRun, and AI Review validation completed successfully;
  OCI Guardrails and bounded retry now wrap both paths.
- OCI GenAI operational counters aggregate through Redis across API and agent
  workers, with a privacy-safe process fallback. Agent Operations exposes retries,
  Guardrails blocks, `429`, `5xx`, Responses fallbacks, and provider degradations
  without storing identity or prompt dimensions.
- Dated reports and files under `docs/prompts/` are historical evidence and are
  explicitly non-normative; this report and the repository contracts above are current.

## Release UI Truthfulness

- `Search or jump` launches Architecture Review directly instead of navigating to
  a Dashboard placeholder. Outside project context it lists active projects and
  requires explicit selection.
- Removed the decorative Notifications button and the permanently disabled active-project
  Delete affordance; remaining disabled controls express real workflow preconditions.
- Provider banners distinguish configured, verified, degraded, deterministic-only,
  and misconfigured states from persisted jobs and agent runs.
- Production Docker validation passed 106 API, 42 calc-engine, 19 pricing-engine,
  60 frontend unit tests, strict TypeScript, ESLint, Ruff, mypy, OpenAPI check,
  Node 26 production build, and 16 of 16 Playwright flows. Real OCI validation
  covered synthesis, allowlisted Function Calling, and Guardrails prompt-injection
  refusal. Trivy reported zero high or critical findings in both production images.
- In-app browser inspection loaded 17 production routes without framework overlays
  or console warnings/errors; Map resolved to 480 integrations and 72 systems.
