# OCI DIS Blueprint

**API-first web application for OCI integration design assessment.**

Replaces `Catalogo_Integracion.xlsx` with a governed platform enabling architects and analysts to:
- Import integration inventories (XLSX/CSV)
- Govern catalog metadata with full audit trail
- Calculate volumetry (OIC, Data Integration, Functions, Streaming)
- Generate deterministic technical dashboards and justification narratives
- Export results for delivery teams and clients
- Download a self-documenting governed workbook for offline capture and safe re-import
- Apply versioned certification contracts to all 21 governed integration patterns
- Refresh official OCI public prices and produce governed, traceable Bills of Materials
- Ask a session-isolated contextual assistant about App workflows and governed architecture evidence

**Source of truth for behavior:** `Catalogo_Integracion.xlsx` → tab `TLP - PRD`
**Agent instructions (Codex):** [`AGENTS.md`](./AGENTS.md)

---

## Stack

- **API:** FastAPI (Python 3.12) — `apps/api/`
- **Web:** Next.js 15 (TypeScript, Node.js 26.0.0) — `apps/web/`
- **Database:** PostgreSQL 16
- **Jobs:** Celery + Redis
- **Object storage:** MinIO locally / OCI Object Storage when deployed, through one S3-compatible artifact service
- **Calc engine:** `packages/calc-engine/` (pure Python, no I/O)
- **Pricing engine:** `packages/pricing-engine/` (pure Decimal calculations, no I/O)
- **Service rules:** normalized Service Product tables; Assumptions contain client workload inputs only

All services run in **production mode** on Docker Desktop — no host Python or
Node.js dependencies and no source-code bind mounts.

---

## Quick Start

```bash
# 1. Clone and enter the project
cd "OCI DIS Blueprint"

# 2. Copy environment template
cp .env.example .env

# 3. Build and start the production stack
docker compose up -d --build --wait

# 4. Apply database migrations (first time)
docker compose exec -T api alembic upgrade head

# 5. Seed reference data (patterns, dictionary, assumptions)
docker compose exec -T api python -m app.migrations.seed
```

**Access:**
- Web app: http://localhost:3000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (minio / minio123)

## OCI Generative AI for Governed Reviews

AI Review and the BOM scenario assistant use OCI Generative AI with
`OpenAI gpt-oss-20b` in `us-chicago-1`. Deterministic services remain the source
of truth; OCI GenAI receives only redacted, governed evidence and prioritizes
typed decision alternatives instead of calculating architecture, usage, or price.

```bash
# Configure these non-secret values and the secret-file path in .env first:
# OCI_GENAI_PROJECT_ID=ocid1.generativeaiproject...
# OCI_GENAI_COMPARTMENT_ID=ocid1.compartment...
# OCI_GENAI_API_KEY_FILE_HOST=/absolute/path/to/.oci-genai/api_key  # optional override
docker compose up -d --build --wait
```

The production Compose contract mounts the OCI Generative AI `sk-` secret from
`$HOME/.oci-genai/api_key` by default (or `OCI_GENAI_API_KEY_FILE_HOST` when set) read-only under
`/oci-genai-host`. The production entrypoint copies it to
`/tmp/oci-dis-home/.oci-genai/api_key` with mode `0400`, then immediately drops
API and worker execution to `app:10001`. Never store the secret in `.env` or Git.
Use OCI Vault or an equivalent approved secret mount in the deployed environment.
The integration follows Oracle's official
[OpenAI-compatible endpoint](https://docs.oracle.com/en-us/iaas/Content/generative-ai/openai-compatible-api.htm)
and [OCI Generative AI API key](https://docs.oracle.com/en-us/iaas/Content/generative-ai/api-keys.htm)
contracts.

`OCI_GENAI_PROJECT_ID` and `OCI_GENAI_COMPARTMENT_ID` are non-secret OCI resource
identifiers. New inference uses the OpenAI-compatible Responses API first and
falls back to Chat Completions only when OCI reports Responses unavailable for
the configured model. Requests use bounded retry with jitter, HMAC-derived
`safety_identifier` values, and OCI Guardrails for prompt injection, harmful
content, and PII. The dedicated `agent-worker` consumes only the `agents` queue.
Agent tools are typed calls into existing deterministic services; no model
receives SQL, shell, Docker, or arbitrary network access.

Provider telemetry uses fixed-cardinality counters shared through Redis across
the API and agent workers. Admin Agent Operations exposes retries, Guardrails
blocks, `429`, `5xx`, Responses fallbacks, and terminal degradation counts. No
prompt, response, actor, session, project, or integration identity is used as a
metric dimension. If Redis is unavailable, inference remains operational and
the endpoint truthfully reports process-local fallback metrics.

Every agent answer also passes one repository-owned outcome contract. The API
rejects provider meta-reasoning, unsupported material numbers, unknown SKU or price
claims, claims that a proposal was applied, and source-verification claims without
retrieved evidence. The contextual assistant can render bounded Markdown tables,
lists, emphasis, and same-origin App links. Rejected synthesis is replaced by a deterministic brief that
always separates the finding, why it matters, next actions, validation, evidence,
and confidence. Agent Operations reports provider health and observed outcome
quality separately; value signals come only from retained executions and human
decisions, never estimated time savings.

Specialized agents run four governed stages: load evidence, compare valid
alternatives, synthesize the decision, and prepare approval-gated proposals.
Approval never executes a change. A separate idempotent execution command creates
only an auditable draft or simulation and records post-validation. Saved Canvas
designs, approved scenarios, source rules, and published BOMs still require their
existing explicit domain actions.
See [`docs/architecture/oci-agent-runtime.md`](./docs/architecture/oci-agent-runtime.md).

The global OCI DIS App Assistant persists across navigation, understands the
current integration and its ordered business process as well as project,
governance, import, BOM, and topology evidence, accepts explicitly added App
contexts, and redirects unrelated questions toward useful App capabilities. OCI
Generative AI authors normal responses from a labeled `verified_facts` contract and
executable `next_actions`; deterministic answers are reserved for provider or grounding
failure. Model history is not evidence, and an output-grounding gate replaces unsupported synthesis with a concise governed brief. See
[`docs/architecture/contextual-support-assistant.md`](./docs/architecture/contextual-support-assistant.md).
The executable product boundary, CI drift gate, deterministic fallback, and
human-reviewed Knowledge Maintenance Agent are documented in
[`docs/architecture/app-knowledge-base.md`](./docs/architecture/app-knowledge-base.md).
Users can clear their current browser-session transcript from the assistant header;
the App removes messages and attached contexts while retaining sanitized AgentRun
audit evidence.

## Offline Capture Workbook

The Import workflow downloads the en-US official template `v3.1.0` as
`oci-dis-import-template-v3.1.0.xlsx` directly from the API. The workbook includes
a blank governed capture sheet, an executive dashboard, editable client catalogs,
novice instructions, preflight checks, field guidance, pattern examples, and
current Service Product Library references. Its `_Lists` manifest records the
template/importer contract and governed-source freshness. Examples are never
placed in the importable sheet.

Existing unversioned v1, governed v2, and Spanish v3.0 workbooks remain importable.
Legacy `Uncertainty` and Due Diligence Business Process columns are retained only
as immutable source evidence and ignored by the active catalog. Template v3.1
rejects formulas and changed headers so offline capture cannot hide logic or
silently drift from the App contract. See
[`docs/architecture/offline-capture-workbook-v3.md`](./docs/architecture/offline-capture-workbook-v3.md).
Pattern certification semantics are documented in
[`docs/architecture/pattern-certification-matrix.md`](./docs/architecture/pattern-certification-matrix.md).

## Governed OCI Pricing And BOM

`BOM & Cost` converts an approved technical snapshot plus an approved physical
deployment scenario into an immutable OCI planning estimate. Admin `Pricing`
refreshes the documented Oracle public product-price endpoint, reviews immutable
price snapshots, imports authorized contractual CSV rate cards, and governs
Service Product-to-SKU mappings. Every BOM line preserves formula, demand,
environment, mapping, price-item, and snapshot provenance.

Deployment scenarios also own a normalized monthly activation calendar. Each
environment can start in a different contract month, ramp linearly or in steps,
and override the default schedule for a specific OCI service. BOM snapshots
persist every monthly quantity, selected price tier, unit price, amount, and
provenance record. The connected Rollout Explorer visualizes monthly run rate,
cumulative commitment, environment/product mix, activation timing, commercial
drivers, product-level SKU evidence, steady state, and the timing effect versus
day-one full capacity. Product, chart, driver, and inspector selections remain
coordinated; that timing effect is explicitly not labeled as a negotiated saving.

The technical dashboard remains cost-free. Commercial totals are visible only
inside the explicit BOM workflow, and publication is blocked until pricing
coverage reaches 100%. XLSX, JSON, and PDF exports are planning artifacts, not
Oracle quotes. See
[`docs/architecture/oci-pricing-bom-plan.md`](./docs/architecture/oci-pricing-bom-plan.md)
and [`docs/architecture/oci-pricing-parity-spec.md`](./docs/architecture/oci-pricing-parity-spec.md).

M51 full-catalog coverage follows a mandatory five-stage strategy:
atomic official-source import, draft mapping generation by price family and
metric, deterministic commercial classification, auditable human exception
review, and independent quotation fixtures before rule-family approval. The current
global release records a terminal disposition for all 1,182 catalog candidates:
229 are quote-ready and 953 remain truthfully blocked with governed reasons. The
App BOM allowlist remains narrower by design: 27 of 32 mapped SKUs are enabled and
five unresolved commercial dependencies remain excluded. Global coverage means
every SKU is governed, not that every public OCI SKU is quote-ready. See
[`docs/architecture/oci-full-catalog-commercial-coverage-plan.md`](./docs/architecture/oci-full-catalog-commercial-coverage-plan.md).

Admin Pricing also exposes a governed OCI Coverage queue for all 444 captured
products. Generation proposes capability profiles, policies, and SKU mappings but
does not activate them. Only products whose complete quoteable SKU scope passes
the approved-release, term, deterministic fixture, exception, and relationship
gates can be explicitly promoted by an Admin. Project detection and scenario
composition now remain separate decisions: integration tools seed the baseline,
while an architect can search and add any active product with an approved policy
and mapping to a specific environment. Explicit additions preserve SKU, real-unit
quantity, activation, release, and evidence provenance through the same governed
BOM path; unapproved products never appear in the selector.

Continuous source governance keeps the currently approved commercial families
current without self-approving source drift. Celery verifies the Oracle public
price feed plus Cloud Estimator products, metrics, and presets every day as one
atomic source set; raw evidence is hash-addressed in Object Storage, every one of
the 20 governed commercial families runs deterministic quotation fixtures, and
changed evidence requires explicit Admin approval. New public-list BOMs are
blocked when the latest verified evidence is older than 72 hours or a regression
fails. A separate Service Verification Agent checks the dynamic set of allowlisted
Oracle product documents and may propose value or unit updates, but deterministic
rule semantics and explicit Admin acceptance remain authoritative. See
[`docs/architecture/oci-continuous-source-governance.md`](./docs/architecture/oci-continuous-source-governance.md).

---

## Running Tests

```bash
# Build the non-deployable API quality image once
docker build --target quality -t ocidisblueprint-api-quality:local \
  -f apps/api/Dockerfile .

# API integration tests (Object Storage is replaced by an in-memory fixture)
docker run --rm ocidisblueprint-api-quality:local \
  python -m pytest -p no:cacheprovider app/tests -q

# Pure calc-engine parity tests
docker run --rm -w /calc-engine ocidisblueprint-api-quality:local \
  python -m pytest -p no:cacheprovider src/tests -q

# Pure Decimal pricing-engine tests
docker run --rm -e PYTHONPATH=/pricing-engine/src -w /pricing-engine \
  ocidisblueprint-api-quality:local \
  python -m pytest -p no:cacheprovider tests -q

# API static analysis as the non-root image user
docker run --rm ocidisblueprint-api-quality:local \
  ruff check --no-cache app /calc-engine/src /pricing-engine/src
docker run --rm ocidisblueprint-api-quality:local \
  mypy app --ignore-missing-imports --no-error-summary \
  --cache-dir=/tmp/mypy-cache

# Web tests and static checks, using non-runtime Docker build targets
docker build --target test --output type=cacheonly -f apps/web/Dockerfile .
docker build --target lint --output type=cacheonly -f apps/web/Dockerfile .

# Verify the OpenAPI artifact packaged in the production image
docker run --rm ocidisblueprint-api:latest \
  python scripts/export_openapi.py --check

# Production build and dependency audit
docker build --target production -t ocidisblueprint-web:latest \
  -f apps/web/Dockerfile .
docker run --rm -v "$PWD":/workspace -w /workspace node:26.0.0-alpine \
  npm audit --audit-level=high
```

Persistent application artifacts never use container filesystems or shared file
volumes. Imports, exports, contractual rate cards, Synthetic Lab workbooks, and
generated reports use the S3-compatible storage service: MinIO in this Docker
stack and OCI Object Storage when deployed. Local files are allowed only as
bounded temporary generation buffers and are deleted after upload. The OCI
Generative AI API key remains a read-only mounted secret and is not an artifact.

## Schema-Dependent Admin Smoke Check

When the Admin Synthetic Lab schema, router, worker, or UI changes, run this
against the live production-mode stack before calling the feature validated:

```bash
# Ensure the running API container has the latest DB schema.
docker compose exec -T api alembic upgrade head

# Confirm API health.
curl -sf http://localhost:8000/health

# Confirm the synthetic admin endpoints are readable with admin headers.
curl -sf \
  -H 'X-Actor-Id: web-admin' \
  -H 'X-Actor-Role: Admin' \
  http://localhost:8000/api/v1/admin/synthetic/presets

curl -sf \
  -H 'X-Actor-Id: web-admin' \
  -H 'X-Actor-Role: Admin' \
  'http://localhost:8000/api/v1/admin/synthetic/jobs?limit=20'
```

Then reload `http://localhost:3000/admin/synthetic` and confirm the page shows
the preset form or empty-state jobs table, not `Failed to fetch`.

If the synthetic worker flow or cleanup policy changed, prefer the automated
bounded smoke script:

```bash
docker compose exec -T api \
  python scripts/smoke_admin_synthetic_lab.py
```

This validates health, preset discovery, job creation, polling, recent-job
visibility, and the `cleaned_up` terminal contract for the
`ephemeral-smoke` preset.

Existing synthetic projects created before the current pattern-certification
contract can be repaired in place with the governed, synthetic-only helper:

```bash
docker compose exec -T api \
  python scripts/remediate_synthetic_pattern_certification.py \
  --project-id <synthetic-project-id>
```

The helper validates every row-specific canvas, rejects newly introduced
blockers, emits an audit event only for a changed canvas, and recalculates the
project once. A completed repair must report `issues_after: 0`; an immediate
second run must also report `repaired_canvases: 0`. It intentionally preserves
independent payload, connectivity, deployment-context, and service-limit
warnings for architect review.

To validate explicit cleanup on a retained small project instead of the
ephemeral auto-clean path:

```bash
docker compose exec -T api \
  python scripts/smoke_admin_synthetic_lab.py --preset-code retained-smoke
```

That retained run must reach `completed`, invoke the cleanup route, and finish
as `cleaned_up` in the same script execution.

Manual fallback:

```bash
curl -sf \
  -X POST \
  -H 'X-Actor-Id: web-admin' \
  -H 'X-Actor-Role: Admin' \
  -H 'Content-Type: application/json' \
  http://localhost:8000/api/v1/admin/synthetic/jobs \
  -d '{"preset_code":"ephemeral-smoke"}'
```

The created job should terminate as `cleaned_up` with
`cleanup_policy = ephemeral_auto_cleanup`, `project_id = null`, and populated
`cleanup_removed_paths`.

To validate retry end to end on a controlled failed job without inventing a
new product preset:

```bash
docker compose exec -T api \
  python scripts/smoke_admin_synthetic_retry.py
```

That helper seeds a bounded failed source job through the service layer, calls
the real retry API, waits for the retried job to finish, and then cleans up the
seeded failed source job.

To validate the admin synthetic pages through a repo-owned browser E2E path:

```bash
cd apps/web
npm run test:e2e:install
npm run test:e2e
```

The Playwright suite covers the Synthetic Lab landing page, terminal cleanup
for `ephemeral-smoke`, terminal completion plus explicit cleanup for
`retained-smoke`, and dashboard, catalog preview tabs, integration canvas,
topology, Service Products, and Assumptions.

Containerized browser runs can set `PLAYWRIGHT_OUTPUT_DIR=/tmp/playwright-results`
so traces and failure screenshots remain ephemeral.

---

## Project Structure

```
apps/api/          FastAPI backend
apps/web/          Next.js frontend
packages/
  calc-engine/     Deterministic volumetry + QA engine
  test-fixtures/   Benchmark data and parity expectations
docs/
  adr/             Architecture Decision Records
  architecture/    System diagrams
  api/             OpenAPI spec
  reports/         Current status plus dated audit evidence
  prompts/         Historical execution prompts; not active contracts
AGENTS.md          Codex implementation guide
docker-compose.yml Local dev stack
.env.example       Environment template
```

The only effective CI definition is the repository-root workflow at
`.github/workflows/oci-dis-blueprint-quality.yml`. It runs API and calc tests,
Ruff, mypy, migrations, OpenAPI drift, frontend types/lint/tests/build, npm
audit, browser E2E, and production image scans.

---

## Milestones

See [`AGENTS.md`](./AGENTS.md#milestones-implement-in-order--prd-049) for the full ordered build plan.

| Milestone | Description | Status | Completed |
|-----------|-------------|--------|-----------|
| M1 | Schema + Migrations | ✅ Complete | 2026-04-13 |
| M2 | Import Engine | ✅ Complete | 2026-04-13 |
| M3 | Catalog Grid API | ✅ Complete | 2026-04-13 |
| M4 | Calculation Engine | ✅ Complete | 2026-04-13 |
| M5 | Dashboard API | ✅ Complete | 2026-04-13 |
| M6 | Justification Narratives | ✅ Complete | 2026-04-13 |
| M7 | Exports | ✅ Complete | 2026-04-13 |
| M8 | Admin + Governance | ✅ Complete | 2026-04-14 |
| M9 | Integration Capture Wizard | ✅ Complete | 2026-04-14 |
| M10 | System Dependency Map | ✅ Complete | 2026-04-14 |
| M11 | Navigation + Theme | ✅ Complete | 2026-04-14 |
| M12 | Source Lineage + Template | ✅ Complete | 2026-04-14 |
| M13 | Integration Design Canvas | ✅ Complete | 2026-04-14 |
| M14 | Map Pan + Visual Improvements | ✅ Complete | 2026-04-14 |
| M15 | UX Overhaul P0 — Canvas + Pagination + Error Handling | ✅ Complete | 2026-04-15 |
| M16 | UX Overhaul P1 — Data Accuracy + Surface Completeness | ✅ Complete | 2026-04-15 |
| M17 | UX Overhaul P2 — Layout + Polish | ✅ Complete | 2026-04-15 |
| M18 | Workbook Import Fidelity — Header Semantics + Source Traceability | ✅ Complete | 2026-04-15 |
| M19 | Governed Reference Data 2.0 — Patterns + Frequencies + Tool Taxonomy | ✅ Complete | 2026-04-15 |
| M20 | Canvas Intelligence — Standard Combinations + Overlay Governance | ✅ Complete | 2026-04-15 |
| M21 | Volumetry Assumption Parity — Service Limits + Unit Governance | ✅ Complete | 2026-04-15 |
| M22 | QA Coverage + Confidence Signals | ✅ Complete | 2026-04-16 |
| M23 | Pattern Coverage 03–17 — End-to-End Operationalization | ✅ Complete | 2026-04-16 |
| M24 | Admin Synthetic Lab — Governed Test Project Generation | ✅ Complete | 2026-04-16 |
| M25 | Production Quality Gates + Service Rule Ownership | ✅ Complete | 2026-07-10 |
| M26 | Governed Offline Capture Workbook 2.0 | ✅ Complete | 2026-07-10 |
| M27 | Governed OCI Pricing + Bill of Materials | ✅ Complete | 2026-07-12 |
| M33 | OCI Generative AI Provider Consolidation | ✅ Complete | 2026-07-12 |
| M34 | Governed Enterprise AI Agents | ✅ Complete | 2026-07-12 |
| M35 | Session-Isolated Contextual App Assistant | ✅ Complete | 2026-07-12 |
| M36 | OCI GenAI Resilience + Safety | ✅ Complete | 2026-07-12 |
| M37 | OCI GenAI Operational Telemetry | ✅ Complete | 2026-07-12 |
| M38 | Contextual Assistant UX + App-wide Grounding | ✅ Complete | 2026-07-12 |
| M39 | Session-Isolated Assistant History Clearing | ✅ Complete | 2026-07-12 |
| M40 | Monthly Consumption Ramps + Cost Insights | ✅ Complete | 2026-07-12 |
| M41 | Explainable Governed AI Review UX | ✅ Complete | 2026-07-13 |
| M42 | Governed Real-Unit Consumption Planning | ✅ Complete | 2026-07-13 |
| M43 | Prescriptive Integration Recommendation Workspace | ✅ Complete | 2026-07-13 |
| M44 | Portfolio Recommendations + Draft Impact Simulation | ✅ Complete | 2026-07-13 |
| M45 | Environment-Specific Commercial Product Variants | ✅ Complete | 2026-07-14 |
| M46 | Connected BOM Rollout Explorer | ✅ Complete | 2026-07-14 |
| M47 | Authoritative Object Storage Artifacts | ✅ Complete | 2026-07-14 |
| M48 | Governed Commercial Quantity Policies + BOM Product Navigation | ✅ Complete | 2026-07-15 |
| M49 | OCI Metering Policy Alignment | ✅ Complete | 2026-07-15 |
| M50 | Full Service Product Commercial Coverage | ✅ Complete | 2026-07-15 |
| M51 | Full OCI Public Catalog Commercial Coverage | ✅ Complete | 2026-07-20 |
| M52 | Governed Pattern Certification | ✅ Complete | 2026-07-16 |
| M53 | Continuous OCI Source Verification + Quote Regression Governance | ✅ Complete | 2026-07-16 |
| M54 | Governed Agentic Decision Workspaces | ✅ Complete | 2026-07-16 |
| M55 | Technical Inclusion + en-US Capture Contract | ✅ Complete | 2026-07-17 |
| M56 | Governed External Workbook Intake | ✅ Complete | 2026-07-17 |
| M57 | Active Project Official Template Export | ✅ Complete | 2026-07-17 |
| M58 | Governed Service Rule Semantics + Current BOM Agent Context | ✅ Complete | 2026-07-17 |
| M59 | Governed OCI Product Coverage Proposals | ✅ Complete | 2026-07-21 |
| M60 | Safe Commercial Coverage Advancement | ✅ Complete | 2026-07-21 |
| M61 | Governed External Rate Card Coverage | ✅ Complete | 2026-07-21 |
| M62 | Governed OCI Product Selection in BOM Scenarios | ✅ Complete | 2026-07-21 |
| Browser QA | Bug fixes + UX enhancements from live browser test | ✅ Complete | 2026-04-14 |

## Validation Snapshot

Phase 1 parity has been validated in Docker against the benchmark workbook rules:

- Import policy: all non-defect rows load in source order; `TBQ=N` remains in the
  technical catalog and is excluded only from BOM/pricing, while `Duplicado 2`
  remains immutable rejected-source evidence
- Reference seed data: `21` certified patterns, `9` architectural overlays, `27` governed canvas combinations, client-only assumption sets, governed dictionaries, and `20` normalized service products
- Synthetic enterprise validation: deterministic governed project with `480` catalog rows, `72` distinct systems, full `#01`–`#17` pattern coverage, persisted snapshots, justifications, audit, and XLSX/JSON/PDF exports
- Backend + calc-engine + pricing-engine: `213 passed` (`139` API, `50` calc-engine, `24` pricing-engine)
- Frontend: `70 passed`, strict TypeScript, ESLint, and production build green
- Pricing/BOM E2E: real 4-source Oracle verification, scheduled no-change verification,
  and post-verification BOM jobs reach terminal `completed` states
- Continuous commercial governance: `4/4` official sources preserved in Object
  Storage, `20/20` quotation families passing, and `100%` regression coverage
- Production images: Trivy reports `0 HIGH` and `0 CRITICAL` for API and web
- Browser E2E: `18 passed`, including OCI provider telemetry refresh, contextual AI,
  workbook download, terminal job state, BOM, topology, and cleanup validation
- Dependency audit: `0` vulnerabilities
- Web and API stack: all eight production services running and healthy in Docker Compose
- Pattern certification browser contract: `21/21` certified cards, `9/9` governed overlays, desktop light/dark and `390 px` mobile views, zero horizontal overflow, and zero console errors

`AGENTS.md`, this README, the root workflow, and the current architecture
documents define the active operational contract. Dated audit reports,
implementation prompts, and rendered diagrams are intentionally excluded from
Git and belong in local or external artifact storage.

---

## Key References

- OIC Gen3 Service Limits: https://docs.oracle.com/en/cloud/paas/application-integration/oracle-integration-oci/service-limits.html
- OCI Pricing: https://www.oracle.com/cloud/price-list/
- Full PRD: `Catalogo_Integracion.xlsx` → `TLP - PRD`
