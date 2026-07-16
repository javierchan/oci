# OCI DIS Blueprint Status Report

**Validated:** 2026-07-16
**Branch:** `main`
**Detailed remediation:** `milestone-progress-20260710-140234.md`

## Current Status

| Area | Status | Evidence |
|---|---|---|
| Backend and deterministic engines | complete | 206 tests passed: 133 API, 49 calc-engine, and 24 pricing-engine |
| Frontend | complete | TypeScript, ESLint, 68 tests, and production build passed |
| Browser workflows | complete | Pattern certification passed on desktop light/dark and 390 px mobile with zero overflow or console errors; Pricing/BOM terminal E2E and the broader 18-test regression remain recorded by the canonical quality workflow |
| Dependency security | complete | npm audit 0; Docker Scout 0 HIGH/CRITICAL for API and web images |
| Database | complete | Alembic at `20260716_0032`; 21/21 patterns are certified, canvas governance exposes 9 overlays and 27 combinations, and 20/20 Service Products retain normalized commercial policy |
| Object Storage | complete | MinIO ready; 54 legacy artifacts migrated; import/recalc/export/delete smoke passed |
| Runtime | complete | 8 Compose services running; API, database, Redis, MinIO, workers, beat, and web healthy |
| Effective CI | complete | one root workflow covers code, browser, build, and image gates |

## Planned Backlog

- **M51 — Full OCI Public Catalog Commercial Coverage** is planned, not part of
  the current validated production scope. It extends the completed 20-product DIS
  coverage to every SKU returned by the OCI public Cloud Estimator endpoints.
- The measured 2026-07-15 baseline is 668 unique SKUs, 728 USD price rows, 123
  service categories, 234 metrics, and 117 product presets. The current approved
  App snapshot contains 652 SKUs and 712 price rows; 34 governed mappings cover
  32 SKUs in the DIS-focused product model.
- Autonomous implementation is estimated at 8–12 working days / 60–90 effective
  hours, followed by a focused one-to-two-day OCI Pricing review. The complete
  scope and acceptance criteria are in
  `docs/architecture/oci-full-catalog-commercial-coverage-plan.md`.
- Its mandatory order is: atomically import products, metrics, and presets;
  generate draft mappings by price family and metric; classify commercial
  behavior deterministically; route exceptions to human review; and pass
  independent quotation fixtures before approving any rule family.

## Governed Rule Ownership

- Service Product Library normalized tables are the operational source for
  service profiles, interoperability, evidence, findings, and 137 active limits.
- Assumption sets contain client/business workload inputs only. Versions
  `1.0.0` and `1.0.1` contain no migrated OIC or Queue service-limit keys.
- Calc-engine static defaults remain deterministic fallbacks for pure isolated
  execution; API recalculation overlays the versioned normalized rule bundle.
- New dashboard, export, and AI-review evidence carries the effective rule
  bundle version and freshness metadata.

## Governed Offline Capture Workbook

- Import downloads the official template `v3.0.0` from one backend-owned column
  and version contract, with 500 blank capture rows and no example data in the
  import surface.
- Twelve workbook sheets provide novice instructions, an executive dashboard,
  editable client catalogs, preflight checks, guided examples, field definitions,
  patterns, OCI products, limits, interoperability, evidence freshness, and
  official source URLs.
- Named validation ranges and a very-hidden manifest keep dropdowns, headers,
  source counts, generation time, and compatibility metadata deterministic.
- Existing unversioned v1 and governed v2 workbooks remain supported; future major
  versions, changed v3 headers, and formulas are rejected.
- A generated workbook is filled and imported through the production service path
  with exact field mapping, including the v3 operational-design fields. All twelve
  sheets are rendered and the App metadata plus downloaded filename are verified.

## Governed Pattern Certification

- One deterministic registry certifies patterns `#01`–`#21` under contract
  `v1.0.0`, including sizing strategy, required evidence, approved core-tool
  compositions, required overlays, commercial services, external dependencies,
  controls, and an architect-facing summary.
- Import, capture, catalog patches, recalculation, Architecture Review, exports,
  Pattern Library, integration detail, canvas, and the offline workbook consume
  the same certification projection. Unknown custom patterns remain explicitly
  unverified and cannot produce certified readiness evidence.
- Canvas governance now exposes 9 overlays (`AO01`–`AO09`) and 27 certified
  combinations (`G01`–`G27`). Non-volumetric identity, observability, catalog,
  AI, and mesh overlays remain selectable because architectural certification is
  independent from volumetric ownership.
- The active 480-row project was recalculated through job
  `d339944d-cdf0-44f0-b5e8-56cbf46a92cb`, producing snapshot
  `76287de1-d78b-4dca-adbe-eba33e1aea2c`. All used patterns are certified;
  60 rows are truthfully flagged for missing composition evidence and require
  architect data remediation rather than a code fallback.
- Validation passed 133 API, 49 calc-engine, 24 pricing-engine, and 68 frontend
  tests; Ruff, mypy, TypeScript, ESLint, npm audit, OpenAPI, the Node 26
  production build, migration head `20260716_0032`, and all eight production
  services passed. Playwright observed 21/21 certified cards, 9/9 overlays, zero
  console errors, and zero horizontal overflow at 390 px.

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

## Commercial Quantity Policies

- Governed SKU mappings distinguish source demand, canonical billable quantity, and
  an optional non-billable planning envelope,
  usage basis, rounding policy, explicit-input requirements, guidance, and presets.
- API Gateway retains the exact measured million-call fraction as the canonical
  billable quantity because Oracle prorates partial million-call units. A rounded
  whole-million planning envelope is optional context and never changes the BOM total.
- SKU mappings now carry aggregation window, proration policy, Free Tier scope,
  minimum runtime, billing increment, and structured metering evidence into both
  line-level and monthly-period provenance.
- Tenancy-level Free Tier is allocated once per SKU and month across environments;
  the rollout comparison consumes that same allocation instead of restarting it per line.
- Data Integration processed GB remains traffic-derived. Workspace running hours
  and Pipeline Operator execution hours are independent explicit inputs; neither
  is inferred from the environment's maximum runtime.
- Data Integration Workspace provides 160-hour business, 360-hour extended, and
  744-hour always-on shortcuts. Selecting 744 renders a confirmation warning rather
  than treating the workbook convention as the default client workload.
- Queue quantities require evidenced push/get/delete/update operations with 64 KB
  request-block rounding. Streaming transfer and storage require explicit PUT/GET
  and retention inputs; no generic operation multiplier or retention default is quoted.
- The BOM editor groups metrics by product, supports product/metric/SKU search,
  exposes commercial policy only when expanded, and groups the monthly matrix by
  product. Browser validation covered desktop light/dark and 430 px mobile views.

## Full Service Product Commercial Coverage

- All 20 governed Service Products now have an explicit commercial classification,
  readiness state, publication policy, required-input contract, and entry guidance.
- Product detection is independent from SKU mappings. A used but unmapped product is
  reported as blocked instead of being omitted from scenario assistance or the BOM.
- The normalized catalog contains 34 approved mappings: 22 required defaults and
  12 optional add-ons. Optional IAM and observability meters are never selected by
  default; dependent products require approved architecture inputs.
- Events remains visible as included/non-billable evidence. Process Automation is
  gated by OIC edition and contractual entitlement. Both are normalized Library
  products with version, limits, official evidence, interoperability, and mappings.
  Data Flow, GoldenGate Data Transforms, and Connector Hub require their governed
  dependencies; Enterprise Data Quality requires an approved external rate card.
- Library, Service Product detail, Pricing Admin, BOM coverage, exports, and assistant
  evidence expose the same policy and meter ownership contract.
- Validation passed 125 API, 42 calc-engine, 24 pricing-engine, and 66 frontend tests,
  OpenAPI consistency, npm audit, the Node 26 production build, healthy Docker runtime,
  and the terminal Pricing/BOM browser E2E with responsive and console assertions.

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

## Governed Agent Outcomes

- All seven agents now pass through one backend-owned output contract before their
  synthesis is persisted or rendered. Meta-reasoning, Markdown tables, internal
  placeholders, unsupported material numbers, unverified mutation claims, and
  source-verification assertions without source evidence trigger a deterministic fallback.
- Every run now carries a structured brief with the finding, why it matters, next
  actions, validation, evidence identifiers, confidence, and auditable output-quality state.
- Service Verification, Import Quality, Topology Investigation, and BOM Scenario
  definitions were tightened to produce bounded what/why/how/validate answers.
  Existing M43-M44 integration, project, topology, and BOM action workspaces remain
  the typed prescriptive authority and were not duplicated.
- Agent Operations separates OCI resilience counters from product outcome signals.
  The latest-50 window reports grounding, evidence completeness, actionable briefs,
  human acceptance, post-approval reruns, and median runtime without inventing
  unmeasured time savings.
- Validation passed 132 API, 42 calc-engine, 24 pricing-engine, and 68 frontend
  tests, plus Ruff, mypy, TypeScript, ESLint, and regenerated OpenAPI.

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
- API and workers use MinIO through the S3-compatible artifact service; no shared
  writable filesystem volume is used for imports, exports, rate cards, or reports.

## Production Dependency Cleanup

- Python dependencies are separated into production runtime and non-deployable
  quality sets. The CI aggregate installs both, while the production image
  installs only `requirements-runtime.txt`.
- The API production image excludes pytest, mypy, Ruff, aiosqlite, API tests,
  calc-engine tests, generated reports, and dependency manifests. Synthetic Lab
  persists workbooks and reports to Object Storage.
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
- Agent Operations retains the latest 50 terminal executions globally. Pending,
  running, and approval-waiting work is never purged; retained support transcripts
  are detached from expired runs before dependent steps, artifacts, approvals, and
  correlated execution-audit records are removed transactionally. The API applies
  the same idempotent policy before accepting traffic and after every terminal
  agent transition, so existing and newly produced history stay bounded.
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
