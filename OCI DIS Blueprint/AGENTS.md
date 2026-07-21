# AGENTS.md — OCI DIS Blueprint
> Read this file in full before touching any code.
> This file is the primary contract between the engineering team and OpenAI Codex (or any AI agent working on this repo).

---

## What this product is

**OCI DIS Blueprint** is an API-first web application that replaces the `Catalogo_Integracion.xlsx` workbook.
It enables architects and analysts to import, govern, calculate volumetry, and export OCI integration catalogs aligned with Oracle Integration Cloud (OIC Gen3) patterns.

The workbook is the **source of truth for behavior**. Phase 1 requires exact parity with the workbook — no redesign, no new features — before any productization.

Full requirements are in `TLP - PRD` tab of `Catalogo_Integracion.xlsx` (PRD-001 through PRD-066).

---

## Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Web app | Next.js 15 + TypeScript (Node.js 26.0.0) | `apps/web/` |
| API | FastAPI (Python 3.12) | `apps/api/` |
| Database | PostgreSQL 16 | via Docker |
| Job queue | Celery + Redis | import and recalc jobs |
| Object storage | MinIO (local) / OCI Object Storage (deployed) | imports, exports, rate cards, synthetic artifacts |
| Calc engine | Pure Python (no DB, no HTTP) | `packages/calc-engine/` |
| Web API types | TypeScript contract projections | `apps/web/lib/types.ts` |

**All services run in Docker Desktop on macOS.** No host-level dependencies.
Spin up everything with `docker compose up --build`.

---

## Repo layout

```
apps/
  api/                  FastAPI server
    app/
      main.py           Entry point — router mounting + lifespan
      core/config.py    Settings from env vars
      models/           SQLAlchemy models (project, snapshot, governance)
      routers/          One file per route group (/projects, /imports, /catalog …)
      services/         Business logic (called by routers)
      workers/          Celery tasks (import_worker, recalc_worker)
      migrations/       Alembic migrations
    Dockerfile
    requirements-runtime.txt  Production-only dependencies
    requirements-quality.txt  Test and static-analysis dependencies
    requirements.txt          Complete CI dependency aggregate
  web/                  Next.js app
    app/                App Router pages (dashboard, catalog, imports …)
    components/         Shared UI components
    lib/                API client, utils
    Dockerfile
    package.json

packages/
  calc-engine/          Pure Python — deterministic volumetry engine
    src/engine/
      volumetry.py      All OIC/DI/Functions/Streaming calculations
      qa.py             Row-level QA logic
      importer.py       XLSX/CSV parser + inclusion rules
    src/tests/          Pytest parity tests — MUST pass before milestone done
  test-fixtures/        Seed data, benchmark files, parity snapshots

docs/
  adr/                  Architecture Decision Records
  architecture/         System diagrams and design docs
  api/                  OpenAPI spec (openapi.yaml)

AGENTS.md               ← you are here
README.md               Human-readable setup guide
docker-compose.yml      Local dev stack
.env.example            Template — copy to .env, never commit .env
.gitignore              Excludes *.xlsx, .env, node_modules, __pycache__
```

---

## Milestones (implement in order — PRD-049)

Each milestone ends with **passing tests and a written diff**. Never skip ahead.

### M1 — Schema + Migrations
- [x] Define all SQLAlchemy models (already scaffolded in `app/models/`)
- [x] Write Alembic migrations for all tables
- [x] Seed `PatternDefinition` (17 patterns from workbook `TPL - Patrones`)
- [x] Seed `DictionaryOption` (frequency, trigger types, tools from `TPL - Diccionario`)
- [x] Seed `AssumptionSet` v1 (from `TPL - Supuestos`)
- [x] **Exit criteria**: `docker compose run api alembic upgrade head` succeeds; seed data queryable via API

### M2 — Import Engine
- [x] Implement `app/services/import_service.py` using `packages/calc-engine/src/engine/importer.py`
- [x] Wire `POST /api/v1/imports/{project_id}` to Celery worker
- [x] Persist `ImportBatch`, `SourceIntegrationRow`, and `CatalogIntegration` (from included rows)
- [x] Apply frequency normalization + audit events per row
- [x] **Exit criteria**: `test_importer.py` passes; benchmark: 157 TBQ=Y rows → 13 excluded → 144 loaded in order

### M3 — Catalog Grid API
- [x] Implement `GET /api/v1/catalog/{project_id}` with pagination, filter, search
- [x] Implement `PATCH /api/v1/catalog/{project_id}/{id}` for architect fields + audit
- [x] Implement `POST /api/v1/catalog/{project_id}/bulk-patch`
- [x] Implement `GET /api/v1/catalog/{project_id}/{id}/lineage`
- [x] Compute QA status using `packages/calc-engine/src/engine/qa.py`
- [x] **Exit criteria**: API returns 144 rows with correct QA status; lineage traces to source row

### M4 — Calculation Engine
- [x] Implement Celery recalculation task calling `packages/calc-engine/src/engine/volumetry.py`
- [x] Persist `VolumetrySnapshot` with row-level and consolidated results
- [x] Wire `POST /api/v1/recalculate/{project_id}`
- [x] Compute derived fields `executions_per_day` and `payload_per_hour_kb` on every catalog write
- [x] **Exit criteria**: `test_volumetry.py` passes; OIC msgs, DI workspace, Functions units match workbook output

### M5 — Dashboard API
- [x] Implement `GET /api/v1/dashboard/{project_id}/snapshots/{id}`
- [x] Default mode: technical only — no cost data (PRD-036)
- [x] KPI strip: OIC msgs/month, peak packs/hr, DI active, DI GB, Functions GB-s
- [x] Chart data: coverage, completeness, pattern mix, payload distribution, risks
- [x] **Exit criteria**: Dashboard values match workbook `TPL - Dashboard` for benchmark project

### M6 — Justification Narratives
- [x] Implement deterministic narrative assembly (no AI in phase 1)
- [x] Wire approve/override endpoints
- [x] **Exit criteria**: Methodology blocks render; approve emits AuditEvent

### M7 — Exports
- [x] XLSX export (catalog + volumetry)
- [x] JSON snapshot export
- [x] PDF dashboard export (phase 1 basic)
- [x] **Exit criteria**: Exported XLSX matches benchmark workbook row count and column structure

### M8 — Admin + Governance
- [x] Dictionary CRUD (admin role only)
- [x] Assumption set versioning
- [x] Prompt versioning (for M6 narrative templates)
- [x] **Exit criteria**: Admin can update frequency map; recalculation picks up new values

### M9 — Integration Capture Wizard
- [x] Add the guided five-step capture flow for manual catalog entry
- [x] Validate required source, destination, and technical fields before submit
- [x] Support duplicate checks, review, and submission into the governed catalog flow
- [x] **Exit criteria**: architects can create a new integration through the wizard without bypassing catalog governance

### M10 — System Dependency Map
- [x] Add the project graph view for source-to-destination system topology
- [x] Render node and edge metadata from the catalog graph payload
- [x] Support detail drill-through from graph selections into catalog context
- [x] **Exit criteria**: the dependency map loads project topology correctly and supports investigation workflows

### M11 — Navigation + Theme
- [x] Add persistent navigation context with reusable breadcrumbs across project and admin surfaces
- [x] Implement light, dark, and system themes with no-flash initialization and durable storage
- [x] Apply semantic theme tokens to shared UI surfaces, badges, and tables
- [x] **Exit criteria**: theme selection persists across navigation and shared surfaces stay readable in both modes

### M12 — Source Lineage + Template
- [x] Expose human-readable source-lineage labels and import batch context on integration detail pages
- [x] Add the downloadable workbook template for offline capture with governed headers and validations
- [x] Improve import UX so users can retrieve the template directly from the import workflow
- [x] **Exit criteria**: integration detail shows readable lineage and import users can download the governed template

### M13 — Integration Design Canvas
- [x] Add the interactive integration design surface for source, tools, and destination flow modeling
- [x] Surface tool selection and route context directly in the integration-detail workflow
- [x] Show immediate technical context such as payload and OIC estimate hints without waiting for a full save cycle
- [x] **Exit criteria**: architects can design and review the intended integration route from the detail page

### M14 — Map Pan + Visual Improvements
- [x] Improve graph navigation with pan, zoom, and keyboard shortcuts
- [x] Add richer graph labeling, hover states, legend context, and visual emphasis for analysis
- [x] Preserve reachability and usability of the graph route under the improved interaction model
- [x] **Exit criteria**: the map is navigable and visually readable for real project analysis

### M15 — UX Overhaul P0: Core Workflow Fixes
- [x] Integration Design Canvas rebuilt as SVG flow diagram with draggable nodes,
      connectable edges (with arrowheads), pan, and zoom
- [x] Multiple instances of same tool type allowed (instance-based node model)
- [x] Catalog table paginated at 20 rows/page with Prev/Next and rows-per-page selector
- [x] Invalid project ID renders graceful not-found page (no Next.js dev error overlay)
- [x] **Exit criteria**: Canvas renders a working flow; catalog paginates; 404 shows
      a user-friendly message; all 5 quality gates green

### M16 — UX Overhaul P1: Data Accuracy + Surface Completeness
- [x] Interface Name shows descriptive name from source workbook (not Interface ID)
- [x] QA Reasons rendered as human-readable cards with title + actionable hint
- [x] Dashboard renders pattern mix, payload distribution, risks, and maturity
      from the full backend payload (not just KPI strip)
- [x] Graph auto-fits all nodes on load with no nodes cut off below viewport
- [x] Graph edges have directional arrowheads (source → destination)
- [x] "View in Catalog" from graph node panel pre-filters catalog by system name
- [x] **Exit criteria**: No integration detail shows ID as name; dashboard uses
      full backend payload; graph fits viewport; all quality gates green

### M17 — UX Overhaul P2: Layout + Polish
- [x] Architect Patch Save button visible without scrolling (sticky panel or top placement)
- [x] Audit Trail entries show field names instead of array index notation
- [x] Capture wizard step pills numbered (1–5) with progress line and completed state
- [x] Import page required columns list shows all columns without truncation
- [x] Projects list has text filter and archived-projects toggle
- [x] Graph has "filter by system" dropdown to highlight a system and its neighbors
- [x] Admin hub shows "Last modified" date per governance category
- [x] **Exit criteria**: All checklist items visually confirmed; no regressions;
      all quality gates green

### M18 — Workbook Import Fidelity: Header Semantics + Source Traceability
- [x] Resolve source columns by workbook header name first, not fallback position,
      for both `Catálogo de Integraciones` and `TPL - Catálogo`
- [x] Map workbook headers such as `Interfaz` → `interface_name` and
      `Alcance Inicial` → `initial_scope` even when the source header row starts
      at row 5 with leading blank columns
- [x] Preserve real workbook header labels in lineage and raw-column rendering so
      named fields do not degrade into `Column N` unless the workbook header is blank
- [x] Align import normalization with the workbook operating rules documented in
      `TPL - Prompts`: preserve source order, include `Duplicado 1`, exclude only
      `Duplicado 2`, and retain `TBD` and payload `0`
- [x] Normalize split destination technologies and trigger capture semantics
      conservatively from workbook evidence without inventing missing values
- [x] **Exit criteria**: ADN workbook imports with descriptive Interface Name and
      Initial Scope, raw column tables show workbook headers, and importer tests
      cover workbook alias/header policy cases

### M19 — Governed Reference Data 2.0: Patterns, Frequencies, and Tool Taxonomy
- [x] Seed all 17 patterns with full workbook metadata: description/tagline,
      OCI components, when-to-use, anti-pattern, technical flow, and business value
- [x] Expand the frequency dictionary to workbook codes `FQ01`–`FQ16` with exact
      executions/day semantics and alias normalization
- [x] Correct `Tiempo Real` semantics to the workbook proxy (`24` exec/day) where
      the workbook explicitly models it as batch-equivalent rather than per-minute
- [x] Expand the tool dictionary with tool IDs, direct/proxy volumetric flags,
      descriptions, and the allowed Architectural Overlay (`AO`) catalog
- [x] Expose enriched pattern, frequency, and tool metadata through API and admin
      surfaces without breaking existing governance CRUD
- [x] **Exit criteria**: reference endpoints return workbook-grade metadata, admin
      can review/edit it, and calc + UI helpers consume the same governed frequency rules

### M20 — Canvas Intelligence: Standard Combinations + Overlay Governance
- [x] Seed workbook combinations `G01`–`G18` with supported flow, compatible
      patterns, activated metrics, recommended overlays, and usage guidance
- [x] Separate volumetric core tools (`AN`) from architectural overlays (`AO`) in
      the saved canvas semantics and patch payloads
- [x] Teach the canvas to suggest compatible combinations and pattern candidates
      based on the tools actually placed in the flow
- [x] Validate that the designed pipeline connects source to destination while
      preventing unsupported shortcut edges from acting as the effective design
- [x] Reflect real pipeline composition in the processing summary and future
      volumetry hints instead of implying fixed OIC-only processing
- [x] **Exit criteria**: the canvas can explain supported tool stacks, recommend
      matching patterns/groups, and persist core tools vs overlays distinctly

### M21 — Volumetry Assumption Parity: Service Limits + Unit Governance
- [x] Compare `AssumptionSet v1.0.0` against `TPL - Supuestos` and add the missing
      technical service constraints for OIC, Streaming, Queue, Functions,
      Data Integration, and Data Integrator proxy usage
- [x] Align OIC billing rules with workbook guidance for inbound triggers,
      scheduling, thresholding, and BYOL vs non-BYOL pack sizes
- [x] Enforce explicit KB/MB normalization so workbook values captured in MB cannot
      silently distort KB-based formulas or previews
- [x] Centralize remaining hardcoded technical limits across calc, dashboard,
      export, and preview paths behind versioned assumptions
- [x] Preserve pricing and service references as governed assumption metadata
      without forcing the default dashboard into commercial mode
- [x] **Exit criteria**: assumptions are workbook-complete, technical previews use
      shared governed limits, and unit handling is explicit and test-covered

### M22 — QA Coverage + Confidence Signals
- [x] Decouple QA activation from formal ID presence so every active source row is
      evaluated even when the formal integration ID is blank
- [x] Align trigger vocabulary and QA checks with workbook capture semantics such
      as `Scheduled`, `REST Trigger`, `SOAP Trigger`, and `Event Trigger`
- [x] Add completeness indicators for payload, pattern, ID, trigger, and fan-out
      coverage so QA and dashboard surfaces communicate confidence, not just status
- [x] Add low-confidence forecast messaging when billing is extrapolated from sparse
      payload coverage or other weak source inputs
- [x] Preserve evidence gaps without inventing field values merely to turn QA green
- [x] **Exit criteria**: QA no longer hides active rows behind missing formal IDs,
      and forecast surfaces clearly communicate uncertainty when coverage is weak

### M23 — Pattern Coverage 03–17: End-to-End Operationalization
- [x] Decide and document whether patterns `#03`–`#17` are fully supported in phase
      parity or explicitly out of scope beyond reference-library status
- [x] For every supported pattern, implement sizing inputs, QA hints, narrative
      branches, dashboard grouping, and export behavior
- [x] Ensure unsupported patterns are clearly marked in UI/admin instead of acting
      like generic placeholders with misleading confidence
- [x] Use workbook anti-pattern guidance to improve QA hints and pattern selection support
- [x] **Exit criteria**: supported patterns have end-to-end app behavior, and any
      unsupported patterns are explicitly documented and surfaced as such

### M24 — Admin Synthetic Lab: Governed Test Project Generation
- [x] Add a reusable synthetic-generation service layer in `apps/api/app/services/`
      that can build deterministic enterprise-scale datasets without placing any
      orchestration logic inside `packages/calc-engine/`
- [x] Create an executable script at
      `apps/api/scripts/seed_synthetic_enterprise_project.py` that uses the real
      project/import/catalog/recalc/dashboard/justification/export flows to seed
      one governed synthetic project from the current codebase state
- [x] Generate a large, realistic synthetic enterprise project with governed
      metadata and validation targets:
      approximately 72 distinct systems, at least 480 catalog integrations,
      a mixed import/manual capture profile, excluded import rows for traceability,
      full use of patterns, core tools, overlays, canvas state, architect
      rationale, retries, comments, justifications, snapshots, audit, and exports
- [x] Ensure imported synthetic rows traverse the real workbook parser path:
      create a workbook with supported headers, persist `ImportBatch` and
      `SourceIntegrationRow`, preserve inclusion/exclusion evidence, and only then
      materialize `CatalogIntegration`
- [x] Ensure manual synthetic rows traverse the governed capture path:
      use the manual catalog service, preserve lineage, and then apply follow-up
      architect patches only through supported service-layer mutations
- [x] Validate synthetic scale and truthfulness deterministically:
      `catalog_count >= 480`, `distinct_systems >= 70`, and all 17 pattern IDs
      covered in the final governed catalog
- [x] Persist and validate downstream artifacts from supported product routes:
      at least one volumetry snapshot, at least one dashboard snapshot,
      persisted justifications, and generated XLSX/JSON/PDF exports
- [x] Write machine-readable and human-readable run reports to governed Object
      Storage under `synthetic/{project_id}/reports/`, summarizing counts,
      pattern/tool coverage, snapshot IDs, export artifacts, and smoke-test URLs
- [x] Document the productization path for the future Admin Synthetic Lab without
      implementing the full admin module yet. The design doc must cover:
      reusable service extraction, persisted `SyntheticGenerationJob`, Alembic
      migration expectations, admin-only router, service-layer authorization,
      Celery execution, governed presets and inputs, synthetic project metadata,
      UI placement under `apps/web/app/admin/`, API/type updates, labeling,
      validation rules, testing strategy, and operational runbooks
- [x] Preserve the current architecture contract:
      thin routers, service-owned business logic, async DB access in the API,
      calc-engine purity, auditable writes, and conservative no-reset data handling
- [x] **Exit criteria**: the repo contains the documented `M24` plan, the
      synthetic generation service and script run successfully against the real
      stack, one final synthetic project is queryable through the supported API/UI
      routes, generated reports exist on disk, focused backend validation and
      smoke tests pass, and all required quality gates are green

### M25 — Production Quality Gates + Service Rule Ownership
- [x] Remove vulnerable npm resolutions and enforce `npm audit` in CI
- [x] Run API and all calc-engine tests, frontend tests/build, browser E2E,
      PostgreSQL migrations, and production image scanning in the effective workflow
- [x] Make normalized Service Product limits and interoperability rules the
      authoritative runtime source for canvas, recalculation, dashboard, AI Review, and exports
- [x] Restrict AssumptionSet and its UI to client workload inputs; migrate legacy service keys out
- [x] Validate terminal synthetic-job states and cleanup through Playwright
- [x] Remove duplicate CI definitions and nonexistent npm workspaces
- [x] **Exit criteria**: dependency audit is clean; backend, calc-engine, frontend,
      migration, browser, and image gates execute from one canonical CI contract

### M27 — Governed OCI Pricing + Bill of Materials
- [x] Add immutable public and contractual price catalogs with hash-based sync,
      approval, audit, and normalized OCI SKU price tiers
- [x] Add a pure Decimal pricing engine with workbook-parity fixtures and tests
- [x] Add project deployment scenarios that separate logical integration demand
      from physical environments, availability, licensing, and service sizing
- [x] Add governed Service Product-to-SKU mappings and block unresolved coverage
- [x] Add terminal Celery BOM jobs, immutable line-level provenance, review,
      publication, deterministic comparison, and XLSX/JSON/PDF exports
- [x] Add Admin Pricing and project BOM workspaces without exposing commercial
      totals on the default technical dashboard
- [x] Use OCI Generative AI only for advisory scenario summaries; deterministic
      services remain the sole authority for quantities, prices, and totals
- [x] **Exit criteria**: migrations, backend/engine/frontend suites, OpenAPI,
      browser workflows, exports, RBAC, and light/dark responsive views validate
      the governed list-price and authorized CSV rate-card paths

### M33 — OCI Generative AI Provider Consolidation
- [x] Standardize AI synthesis on OCI OpenAI-compatible Responses-first inference,
      with governed Chat fallback for `openai.gpt-oss-20b` in `us-chicago-1`
- [x] Mount the OCI Generative AI `sk-` secret from a read-only file, copy it with
      mode `0400`, and never expose it through `.env`, frontend contracts, or logs
- [x] Route Architecture Review and BOM scenario assistance through one redacted,
      evidence-only provider while preserving deterministic results as authority
- [x] Capture sanitized OCI request IDs and token usage for operational diagnostics
- [x] Remove superseded provider configuration, auth mounts, wire parsing, and runtime dependencies
- [x] **Exit criteria**: provider tests, real OCI smoke, full backend/frontend gates,
      OpenAPI, Docker runtime, and browser AI workflows pass

### M34 — Governed Enterprise AI Agents
- [x] Add a versioned registry for Architecture Review, Service Verification,
      Import Quality, Integration Design, Topology Investigation, and BOM Scenario agents
- [x] Persist auditable agent runs, steps, evidence artifacts, approvals, provider
      diagnostics, cancellation, and terminal states
- [x] Execute agents in a dedicated production Docker `agent-worker` that consumes
      only the Celery `agents` queue
- [x] Use OCI Responses-first Function Calling with one typed, allowlisted deterministic
      evidence boundary per agent, governed Chat fallback, and app-owned decision,
      proposal, and validation stages with no SQL, shell, Docker, or arbitrary URL access
- [x] Preserve existing specialized UI contracts while linking Architecture Review
      and Service Verification jobs to the common runtime
- [x] Add contextual Import and BOM agent actions plus an Admin Agent Operations surface
- [x] Launch a real project Architecture Review directly from the global command
      palette, including explicit active-project selection outside project context
- [x] Distinguish configured, verified, and degraded OCI provider states from
      persisted execution evidence instead of presenting configuration as availability
- [x] Remove visible command and top-bar affordances that have no executable product behavior
- [x] **Exit criteria**: migration head `20260712_0021`, backend/calc/pricing/frontend
      quality gates, OpenAPI, Docker stack, browser flows, and real OCI Function Calling
      smoke pass with a configured `OCI_GENAI_PROJECT_ID`

### M35 — Session-Isolated Contextual App Assistant
- [x] Add a read-only `support_assistant` definition that runs in the dedicated
      Docker agent worker with one typed App-context tool
- [x] Persist conversations, messages, component attachments, citations, and
      AgentRun linkage under migration `20260712_0022`
- [x] Isolate every conversation by an opaque browser UUID and return 404 for
      cross-session conversation access
- [x] Reject unrelated questions deterministically before OCI inference
- [x] Derive current project, integration, topology, import, governance, and BOM
      context from App routes and let users pin multiple views across navigation
- [x] Mount a responsive floating assistant in the root layout so open state,
      history, pending work, and attachments survive App Router navigation
- [x] **Exit criteria**: migration head `20260712_0022`, backend/frontend/OpenAPI
      gates, real OCI support answer, out-of-scope refusal, cross-route persistence,
      dark/light visual validation, and browser console pass

### M36 — OCI GenAI Resilience + Safety
- [x] Prefer the OCI Responses API for synthesis and Function Calling while caching
      model-level endpoint incompatibility before governed Chat fallback
- [x] Add bounded exponential backoff with full jitter and `Retry-After` support for
      transient inference and Guardrails failures
- [x] Send an HMAC-derived `safety_identifier` for every model request without
      exposing user, session, project, or integration identifiers
- [x] Evaluate inputs and outputs with OCI Guardrails for prompt injection, harmful
      content, and PII; redact PII and fail closed on blocked or unavailable checks
- [x] Expose transport capability, retry policy, and safety configuration through
      typed provider-status contracts and truthful UI labels
- [x] **Exit criteria**: focused resilience tests, full API/calc/pricing/frontend gates,
      OpenAPI, real OCI synthesis and Function Calling, Guardrails refusal, Docker
      runtime, and light/dark browser validation pass

### M37 — OCI GenAI Operational Telemetry
- [x] Count all OCI inference and Guardrails requests through the centralized retry transport
- [x] Aggregate retries, `429`, `5xx`, transport failures, Guardrails blocks/failures,
      Responses fallbacks, and terminal provider degradations across API and agent workers
- [x] Store only fixed-cardinality counters in Redis with a process-local fallback;
      never attach actor, session, project, prompt, or response dimensions
- [x] Expose the counters through a role-restricted typed endpoint and the Admin
      Agent Operations workspace with truthful shared-runtime/fallback labeling
- [x] Expire inactive metric state after the configured retention interval and keep
      telemetry failure outside the inference availability path
- [x] **Exit criteria**: exact counter tests for `429`, `5xx`, retries, fallback and
      Guardrails blocking; OpenAPI, backend/frontend gates, Redis aggregation,
      real OCI smoke, Docker runtime, and light/dark browser validation pass

### M38 — Contextual Assistant UX + App-wide Grounding
- [x] Replace the overlapping support panel with a responsive chat layout that
      separates header, scrollable conversation, explicit context, and composer controls
- [x] Rename view attachment to `Add context` and preserve up to eight governed
      App contexts across project and admin navigation
- [x] Expand bounded read-only evidence across App navigation, governance, patterns,
      Service Products, projects, imports, integrations, ordered business processes,
      Dashboard, topology context, deployment scenarios, and BOM
- [x] Treat previous user questions as dialogue continuity while excluding prior
      model answers from authoritative architecture evidence
- [x] Add an output-grounding gate that rejects unsupported sensitive claims,
      invented approval/deployment actions, tables, and excessive verbosity, then
      returns a concise deterministic brief with auditable fallback state
- [x] **Exit criteria**: backend and frontend gates, Node 26 production build,
      healthy Docker stack, real OCI contextual answer, grounding fallback,
      cross-route persistence, mobile/desktop light/dark visuals, and console pass

### M40 — Monthly Consumption Ramps + Cost Insights
- [x] Normalize deployment environments and service-aware activation phases; do
      not retain the legacy scenario JSON as a second runtime source
- [x] Expand step and linear phases in the pure Decimal pricing engine and price
      every contract month independently
- [x] Persist immutable BOM line periods with quantity, tier, unit price, amount,
      formula, warnings, and provenance
- [x] Expose monthly series, peak, first active month, steady state, and phased
      activation timing effect through typed API, comparison, assistant, and exports
- [x] Add the multi-environment ramp editor, environment/product composition,
      cumulative cost, activation timeline, top drivers, and contract bridge
- [x] **Exit criteria**: migration head `20260712_0023`, engine/API/frontend tests,
      OpenAPI, production Docker stack, phased BOM E2E, XLSX/JSON/PDF exports, and
      desktop/mobile light/dark browser validation pass

### M39 — Session-Isolated Assistant History Clearing
- [x] Add a typed DELETE endpoint that clears only messages and attached contexts
      owned by the current conversation and opaque browser-session UUID
- [x] Preserve governed AgentRun, step, and artifact records while emitting an
      AuditEvent containing counts only and no prompt or response content
- [x] Reject cross-session clearing with `404` and block clearing with `409` while
      an assistant response remains pending
- [x] Add a discoverable header command, explicit destructive confirmation,
      keyboard-safe cancellation, pending/empty disabled states, and truthful copy
- [x] Preserve the active empty conversation across App navigation and reload so
      a cleared transcript cannot reappear from stale client state
- [x] **Exit criteria**: focused backend tests, Ruff, mypy, frontend tests,
      TypeScript/ESLint, Node 26 production build, regenerated OpenAPI, healthy
      Docker stack, desktop/mobile Playwright, light/dark visual inspection,
      persisted audit evidence, and browser console pass

### M41 — Explainable Governed AI Review UX
- [x] Render current Architecture Review results before historical jobs and organize
      the decision into what was found, why it matters, and the next concrete action
- [x] Normalize optional OCI Generative AI narratives, including malformed historical
      Markdown tables, into bounded headings, paragraphs, and scan-friendly actions
- [x] Keep provider diagnostics and raw technical evidence progressively disclosed
      while preserving deterministic findings as the authoritative decision record
- [x] Apply the same explanatory hierarchy to Import Quality, BOM Scenario, Service
      Verification, and the contextual App Assistant without changing their data contracts
- [x] Replace the orphan Service Rules metric card with a full-width provenance statement
      and keep evidence metrics aligned across desktop, mobile, light, and dark modes
- [x] **Exit criteria**: Architecture Review prompt-contract tests, 63 frontend tests,
      TypeScript/ESLint, Node 26 production build, healthy production Docker services,
      real project/import/BOM browser inspection, responsive light/dark screenshots,
      normalized historical narratives, and zero browser console errors pass

### M42 — Governed Real-Unit Consumption Planning
- [x] Replace percentage as the universal planning input for new scenarios with
      explicit environment, product, billing metric, period, and quantity units
- [x] Govern packaged, fixed-capacity, hourly, continuous, and manual-monthly
      quantity behavior with SKU-level increments, minimums, and display units
- [x] Store standard constant/linear ramps and an exact editable monthly matrix
      through one normalized phase and period-quantity model
- [x] Preserve historical percentage scenarios as read-only-compatible
      `legacy_share` inputs while defaulting new scenarios to `explicit_units`
- [x] Price governed real quantities independently per contract month and expose
      the same quantities through BOM provenance, timeline, assistant, and exports
- [x] **Exit criteria**: migration head `20260713_0024`, 108 API, 42 calc-engine,
      22 pricing-engine, and 64 frontend tests; OpenAPI, Node 26 production build,
      pricing/BOM E2E, healthy Docker stack, persisted monthly evidence, responsive
      overflow checks, dark theme readability, and zero browser console errors pass

### M43 — Prescriptive Integration Recommendation Workspace
- [x] Generate at most three typed integration-design candidates from the saved
      Canvas V4 route, G01-G18 combinations, patterns, normalized Service Product
      limits, interoperability, trigger, payload, and frequency evidence
- [x] Keep OCI Generative AI bounded to comparing and explaining deterministic
      candidates; never let synthesis invent a topology, limit, quantity, or price
- [x] Expose what to change, how to implement it, prerequisites, validation steps,
      trade-offs, confidence, evidence IDs, and truthful BOM recalculation boundaries
- [x] Audit candidate selection without mutating the catalog and render a read-only
      canvas overlay before an architect applies it to an unsaved local draft
- [x] Improve canvas usability with larger directional markers, reduced-motion-aware
      modeled-flow animation, readable service context, and a persistent component editor
- [x] **Exit criteria**: AI Review API contract, Ruff, mypy, API/calc/pricing/frontend
      suites, TypeScript/ESLint, generated OpenAPI, Node 26 production build, healthy
      Docker stack, and real-browser preview/apply/discard validation pass

### M44 — Portfolio Recommendations + Draft Impact Simulation
- [x] Extract side-effect-free project volumetry and BOM calculation services so
      previews and persisted jobs execute the same deterministic formulas
- [x] Simulate an unsaved connected integration canvas against the saved design
      without writing catalog rows, volumetry snapshots, BOM snapshots, or audit events
- [x] Report saved-versus-proposed technical metrics plus approved-scenario monthly,
      contract, and ramp cost deltas with explicit pricing and quantity boundaries
- [x] Extend typed prescriptive actions to Project Review, Topology Investigation,
      and BOM workspaces with implementation, validation, impact, evidence, and deep links
- [x] Preserve governed explicit-unit demand as authoritative and identify newly
      introduced products as sizing requirements instead of inventing client quantities
- [x] **Exit criteria**: 108 API, 42 calc-engine, 22 pricing-engine, and 64 frontend
      tests; Ruff, mypy, TypeScript/ESLint, generated OpenAPI, Node 26 production build,
      healthy Docker stack, mutation-free API smoke, and responsive browser validation pass

### M45 — Environment-Specific Commercial Product Variants
- [x] Persist the exact approved SKU mapping on each environment, product, and
      billing-metric consumption phase instead of applying one scenario-wide edition
- [x] Expose every approved mapping variant generically, including edition,
      license predicates, part number, unit behavior, increment, and minimum
- [x] Allow QA, DEV, Production, and DR to select different commercial variants
      of the same product while retaining scenario defaults only for initial drafting
- [x] Price each environment from its persisted mapping and carry the commercial
      identity through BOM provenance, activation timeline, line items, and exports
- [x] Preserve historical scenarios through governed default resolution when an
      older phase has no explicit SKU mapping
- [x] **Exit criteria**: migration head `20260714_0025`, 112 API, 42 calc-engine,
      22 pricing-engine, and 64 frontend tests; mixed-environment SKU calculation,
      API schema checks, Ruff, mypy, frontend lint/build,
      OpenAPI, production Docker migration, and light/dark browser validation pass

### M56 — Governed External Workbook Intake
- [x] Stage any non-official workbook as immutable source evidence before it can
      create Catalog, QA, topology, dashboard, or BOM records.
- [x] Require an explicit, auditable source-column contract with evidence-only
      handling for unmapped values and user decisions for ambiguous semantics.
- [x] Let the Import Correction Agent explain mapping risks and minimum business
      decisions, without selecting or approving mappings on the user's behalf.
- [x] Support reusable, project-scoped mapping profiles only after approval and
      only for an exact header fingerprint.
- [x] Preserve external workbook formulas as non-executable evidence, classify
      derived-demand and commercial expressions, and protect formula rows or
      columns from silently populating operational fields.
- [x] Restore the newest unresolved mapping review, source rows, questions, and
      agent guidance when the user returns to Import without an explicit batch ID.
- [x] **Exit criteria**: migration head `20260717_0039`; external workbooks cannot materialize without approval;
      approved mappings materialize once; official templates retain direct import;
      API/frontend tests, migration, Docker workflow, and browser validation pass.

### M57 — Active Project Official Template Export
- [x] Export every active project's governed catalog directly into the canonical
      en-US offline capture workbook rather than creating a second export format.
- [x] Preserve all defined integrations, including `TBQ=N` technical-only rows,
      while retaining the same governed headers, validations, documentation,
      patterns, service evidence, and preflight sheets used for offline capture.
- [x] Pre-populate project-specific client catalog suggestions and expand the
      capture range when a project's catalog exceeds the standard template capacity.
- [x] Block archived projects from export to prevent an offline edit path outside
      the active-project governance lifecycle.
- [x] Expose project export in a distinct Offline Export area, separate from the
      blank capture template and upload steps, and validate download, round-trip
      semantics, runtime migration state, frontend, and browser behavior.

### M58 — Governed Service Rule Semantics + Current BOM Agent Context
- [x] Classify every active Service Product rule with deterministic applicability,
      constraint kind, enforcement, unit, and approved value in one normalized registry.
- [x] Treat OIC 50 KB as calculable billing granularity rather than a universal
      payload hard limit; preserve adapter-specific hard limits as separate rules.
- [x] Let Service Verification retrieve only allowlisted Oracle evidence and propose
      value or unit changes while preventing it from changing applicability,
      constraint kind, enforcement, or runtime state without Admin acceptance.
- [x] Make Canvas, recalculation, Dashboard, Architecture Review, BOM evidence, and
      exports consume the same governed service-rule registry.
- [x] Resolve the current approved or published BOM before the BOM Scenario Agent
      creates alternatives; a current 100%-covered BOM produces a keep-baseline
      recommendation, zero invented client questions, and no mutation proposal.
- [x] **Exit criteria**: migration head `20260717_0040`; focused and full backend,
      calc-engine, pricing-engine, frontend, OpenAPI, Docker, real agent, BOM API,
      responsive browser, and console validation pass.

### M59 — Governed OCI Product Coverage Proposals
- [x] Generate one isolated profile, policy, and SKU-mapping proposal for every
      product in the captured OCI taxonomy without activating BOM behavior.
- [x] Derive quantity semantics only from governed SKU terms and fixture-passed
      commercial rule families; never infer pricing behavior with free-form AI.
- [x] Gate promotion on active-release membership, approved term and rule status,
      passed fixtures, and the absence of open exceptions or unresolved relations.
- [x] Require an explicit Admin rationale before materializing approved capability,
      policy, and mapping records in one idempotent transaction.
- [x] Expose a paginated Admin Pricing review queue with lazy details, per-SKU
      blockers, readiness filters, and disabled approval for non-promotable products.
- [x] Preserve terminal review decisions across refreshes and keep existing BOM
      mappings unchanged until an individual product passes every gate and is approved.
- [x] **Exit criteria**: migration head `20260721_0049`; 444 real product proposals;
      blocked approval returns `409`; approved mapping count remains unchanged by
      generation; 255 API, 55 calc-engine, 35 pricing-engine, and 102 frontend tests;
      Ruff, mypy, TypeScript, ESLint, OpenAPI, Node 26 production build, migration
      symmetry, production Docker health, and responsive browser validation pass.

### M60 — Safe Commercial Coverage Advancement
- [x] Resolve commercial exceptions in bulk only through the explicit
      `PRODUCT_IDENTITY_VARIANCE` low-severity allowlist; dependency, medium, and
      high-severity evidence remains an individual human-review decision.
- [x] Preserve individual and batch exception semantics through one shared,
      auditable mutation helper with required rationale, dry-run preview,
      idempotence, and transactional execution.
- [x] Reuse the existing deterministic catalog finalization and release-promotion
      gates instead of introducing a second approval path or bypass.
- [x] Report the advancement funnel truthfully, distinguishing commercially
      approved part numbers from the narrower SKU allowlist currently enabled for
      BOM calculation through approved Service Product mappings.
- [x] Add an Admin Pricing preview-and-confirm workflow with explicit blocker
      summaries and optional release promotion.
- [x] Preserve all existing BOM mappings and calculations until their independent
      product-coverage gate is satisfied; this milestone adds no migration.
- [x] **Exit criteria**: focused commercial-catalog, pricing-BOM, and product-
      coverage tests; Ruff, mypy, frontend tests, TypeScript, ESLint, OpenAPI,
      Node 26 production build, production Docker health, and browser preview
      validation pass without mutating the active commercial catalog.

### M46 — Connected BOM Rollout Explorer
- [x] Replace the flat activation list with an executive rollout summary, coordinated
      monthly chart, progressive product/environment timeline, and product inspector
- [x] Distinguish constant, linear, exact-monthly, packaged, and included consumption
      shapes while preserving governed snapshot and scenario calculations
- [x] Connect commercial driver, chart, timeline, SKU evidence, and scenario-edit
      interactions through one product selection model
- [x] Use commercial product names, restrained environment color, and responsive
      timeline/inspector tabs without introducing a second data source
- [x] **Exit criteria**: focused frontend tests, TypeScript/ESLint, Node 26 production
      build, healthy production Docker stack, targeted BOM E2E, and desktop/mobile
      light/dark browser validation pass

### M47 — Authoritative Object Storage Artifacts
- [x] Make one S3-compatible service authoritative for import workbooks, exports,
      contractual rate cards, Synthetic Lab workbooks, and generated reports
- [x] Use project-owned prefixes, canonical `s3://` references, bounded temporary
      generation files, and lifecycle cleanup when imports, jobs, or projects are deleted
- [x] Run MinIO in the production Docker topology while retaining the same client
      contract for OCI Object Storage deployments
- [x] Migrate resolvable legacy upload/export artifacts idempotently and retain
      local-path reads only as a bounded migration compatibility path
- [x] Remove the shared uploads volume, generated report directories, stale
      filesystem test contracts, and versioned runtime artifacts
- [x] **Exit criteria**: migration head `20260714_0026`, API/calc/pricing/frontend
      gates, OpenAPI, production Docker health, real import/recalc/export lifecycle,
      MinIO prefix cleanup, and zero runtime writes to persistent container paths pass

### M48 — Governed Commercial Quantity Policies + BOM Product Navigation
- [x] Separate measured service demand from the commercial quantity carried into
      the BOM, preserving both values and the applied rounding rule in provenance
- [x] Add governed usage basis, quote rounding, explicit-input requirements,
      entry guidance, and reusable quantity presets to SKU mappings
- [x] Preserve API Gateway measured demand and expose whole 1M-call planning units
      only as a conservative envelope pending authoritative metering alignment
- [x] Stop inferring Data Integration workspace and operator runtime from a generic
      744-hour environment ceiling; require explicit quantities and expose bounded
      business-hours, extended-hours, and always-on planning shortcuts
- [x] Replace the flat BOM product form with searchable, grouped, progressively
      disclosed product sections and a product-grouped monthly matrix
- [x] **Exit criteria**: migration head `20260715_0027`, 118 API, 42 calc-engine,
      23 pricing-engine, and 66 frontend tests; OpenAPI, Node 26 production build,
      pricing/BOM E2E policy assertions, healthy Docker stack, and desktop/mobile
      light/dark visual inspection pass

### M49 — OCI Metering Policy Alignment
- [x] Separate measured usage, canonical billable quantity, and optional planning
      envelope so advisory capacity reserves never change deterministic totals
- [x] Correct API Gateway `B92072` to preserve exact prorated million-call usage
      while displaying a whole-million reserve only as non-billable planning context
- [x] Govern aggregation window, proration, Free Tier scope, minimum runtime,
      increments, and metering evidence on every Service Product-to-SKU mapping
- [x] Allocate tenancy-level Free Tier once per SKU and contract month across all
      ordered environment lines and apply the same allocation to rollout comparisons
- [x] Require explicit Queue operation evidence, Streaming PUT/GET and retention
      evidence, Data Integration runtime, and GoldenGate runtime/OCPU inputs instead
      of applying workbook convenience assumptions as billable facts
- [x] Surface the policies in the scenario assistant, BOM editor, Admin Pricing,
      immutable line provenance, period provenance, and typed frontend contracts
- [x] **Exit criteria**: migration head `20260715_0028`, 122 API, 42 calc-engine,
      24 pricing-engine, and 66 frontend tests; Ruff, mypy, TypeScript, ESLint,
      Node 26 production build, terminal pricing/BOM E2E, healthy Docker stack,
      exact API scenario evidence, and real-browser functional/visual inspection pass

### M50 — Full Service Product Commercial Coverage
- [x] Classify all 20 governed Service Products with an explicit commercial path:
      direct metering, included non-billable capability, dependent cost, external
      rate card, or explicit metric selection
- [x] Detect the project product footprint independently from existing SKU mappings
      so missing commercial governance is blocked instead of silently omitted
- [x] Separate required default meters from optional add-ons and dependency-owned
      meters; optional IAM and observability products never enter a scenario implicitly
- [x] Keep included products visible as zero-amount BOM evidence and require design
      inputs before pricing dependent or externally licensed products
- [x] Surface product coverage, required inputs, publication policy, governed meter
      count, and quote guidance in Library, product detail, BOM, Pricing Admin,
      assistant evidence, exports, and typed API contracts
- [x] Normalize OCI Events and Oracle Integration Process Automation as first-class
      Service Products with versions, limits, official evidence, interoperability,
      commercial policy, and non-orphaned SKU mappings; no mapping-owned fallback remains
- [x] **Exit criteria**: migration head `20260715_0030`, 125 API, 42 calc-engine,
      24 pricing-engine, and 66 frontend tests; Ruff, mypy, TypeScript, ESLint,
      npm audit, OpenAPI, Node 26 production build, terminal Pricing/BOM E2E,
      healthy eight-service Docker stack, and desktop/mobile light/dark browser
      inspection pass

### M50A — Governed Agent Outcomes + Observable Value
- [x] Apply one backend-owned output contract to all seven agents with bounded
      normalization, meta-reasoning and Markdown-table rejection, numeric grounding,
      mutation-claim blocking, and deterministic fallback
- [x] Persist an explainable brief for every run with what was found, why it matters,
      next actions, validation, confidence, and evidence identifiers
- [x] Strengthen Service Verification, Import Quality, Topology Investigation, and
      BOM Scenario prompt contracts without weakening deterministic tool authority
- [x] Measure only observable value signals across the retained execution window:
      synthesis, grounding, evidence completeness, actionable briefs, human decisions,
      approval follow-up, and median runtime; do not invent time-saved estimates
- [x] Separate provider resilience telemetry from outcome quality in Agent Operations
- [x] **Exit criteria**: shared output-contract tests, 132 API, 42 calc-engine,
      24 pricing-engine, and 68 frontend tests; Ruff, mypy, TypeScript, ESLint,
      OpenAPI, Node 26 production build, Docker runtime, and responsive browser
      validation pass

### M51 — Full OCI Public Catalog Commercial Coverage
- [x] Import the complete official products, metrics, and product-presets sources
      as one atomic immutable catalog snapshot; partial refreshes must retain the
      previous approved snapshot
- [x] Generate versioned draft mappings by deterministic price family and metric;
      every source SKU must receive one candidate or an explicit unmapped exception
- [x] Automatically classify every product as directly metered, included
      non-billable, dependent entitlement, external rate card, or blocked pending
      explicit input
- [x] Route ambiguous BYOL, edition, entitlement, private-rate, dependency, tier,
      metric, and source-drift cases to auditable human review; generated mappings
      must never self-approve
- [x] Execute independent quotation fixtures for boundaries, tiers, proration,
      Free Tier, predicates, environments, ramps, provenance, and exports before
      approving each rule family
- [x] Govern all public `HOUR`, `HOUR_UTILIZED`, `MONTH`, `DAY`, and `PER-ITEM`
      products, including tiers, proration, minimums, Free Tier, dependencies,
      editions, licenses, and explicit-input requirements
- [x] Extend Library, Pricing, BOM, exports, assistant evidence, agents, and audit
      to use one consistent full-catalog product identity without adding irrelevant
      SKUs to project-scoped architecture flows
- [x] **Exit criteria**: every public SKU has an approved disposition or
      truthful blocked state; source counts and hashes reconcile; deterministic
      formula-family, tier, migration, backend, frontend, OpenAPI, export, E2E,
      visual, security, and production-image gates pass; OCI Pricing review records
      approval or an explicit exception
- [x] Publish a truthful App-scoped release for 27 of 32 currently mapped SKUs;
      keep `B88299`, `B88406`, `B92993`, `B93496`, and `B93497` excluded until their
      official commercial dependencies are resolved
- [x] Add an independent Commercial Consistency Test Agent contract, separate from
      the App's read-only Official Source Governance Agent, to validate implementation
      semantics against documentary evidence and recommend recurring deterministic controls
- [x] Promote global release `commercial-20260720043236` with terminal dispositions
      for all 1,182 candidates: 229 quote-ready and 953 truthfully blocked with
      governed reasons; retain the exact App BOM allowlist at 27 of 32 mapped SKUs
- [x] Record the independent OCI Pricing review as
      `codex-m51-global-catalog-review` and reconcile the completion evidence in
      `docs/architecture/oci-full-catalog-commercial-coverage-plan.md`

### M52 — Governed Pattern Certification
- [x] Certify all 21 system patterns through one versioned deterministic registry
      covering evidence, sizing, approved compositions, OCI services, external
      dependencies, and validation controls
- [x] Evaluate certification evidence and canvas composition during import,
      capture, patch, recalculation, Architecture Review, and export workflows
- [x] Expand canvas governance with the overlays and combinations required by
      Zero Trust, Data Mesh, AI, Integration Mesh, batch, correlation, Claim Check,
      DLQ/replay, and event-contract patterns
- [x] Expose the certification contract in Pattern Library, integration detail,
      canvas, narratives, snapshots, offline workbook, and typed API contracts
- [x] Keep unknown custom patterns explicitly unverified and prevent them from
      producing certified sizing or architecture-readiness evidence
- [x] **Exit criteria**: migration head `20260716_0032`; all 21 profiles have
      deterministic fixtures; API, calc-engine, frontend, OpenAPI, Docker,
      export, browser, light/dark, and console validation pass

### M53 — Continuous OCI Source Verification + Quotation Regression Governance
- [x] Retrieve the public price catalog, Cloud Estimator products, metrics, and
      presets as one atomic official-source verification; a partial failure keeps
      the previous approved evidence authoritative
- [x] Persist immutable, hash-addressed source artifacts and record counts in
      Object Storage while keeping only typed governance references in PostgreSQL
- [x] Schedule daily Celery verification behind a Redis lease, bounded source
      retries, and terminal no-change, review, blocked, or promoted states
- [x] Classify source drift and identify affected approved SKUs and Service Products
      before an administrator can accept changed commercial evidence
- [x] Execute deterministic quotation fixtures for every approved commercial
      family and block promotion or new public-list BOMs when regression coverage
      fails or verified evidence exceeds the configured freshness window
- [x] Expose source health, drift, impact, regression coverage, review decisions,
      and recent executions in the responsive Admin Pricing Verification Center
- [x] **Exit criteria**: migration head `20260716_0034`; 139 API, 50 calc-engine,
      24 pricing-engine, and 70 frontend tests; Ruff, mypy, TypeScript, ESLint,
      OpenAPI, Node 26 production build, eight-service Docker runtime, real Oracle
      4-source sync, 20/20 quotation families, Object Storage artifacts, scheduled
      no-change execution, post-verification BOM, responsive light/dark browser
      validation, and zero console errors pass

### M54 — Governed Agentic Decision Workspaces
- [x] Replace single-pass agent summaries with a four-stage runtime for evidence,
      deterministic alternatives, grounded OCI synthesis, and governed proposals
- [x] Give Architecture, Source Governance, Import, Integration Design, Topology,
      BOM, and Support agents explicit decision responsibilities and typed capabilities
- [x] Persist up to three alternatives with what changes, expected impact, missing
      inputs, implementation, validation, confidence, and completion contracts
- [x] Separate proposal approval from execution, make execution idempotent, and
      persist bounded post-validation evidence plus audit correlation
- [x] Keep canvas changes as reversible simulations until explicit architect save;
      create BOM alternatives only as draft deployment scenarios
- [x] Expose decision workspaces in Agent Operations, Architecture Review, Import,
      Service Verification, Integration Design, and BOM without replacing existing
      deterministic candidate, pricing, or governance authorities
- [x] Measure created proposals, approved executions, post-validations, and execution
      rate in the retained operational window without inventing labor savings
- [x] **Exit criteria**: migration head `20260716_0035`; backend, calc-engine,
      pricing-engine, frontend, OpenAPI, Node 26 production build, eight-service
      Docker runtime, real OCI decision generation, approval, execution,
      post-validation, dark/light responsive browser, and console checks pass

### M55 — Technical Inclusion + en-US Capture Contract
- [x] Include both `TBQ=Y` and `TBQ=N` source rows in technical governance while
      deriving commercial eligibility exclusively from the persisted TBQ value
- [x] Keep `TBQ=N` integrations in Catalog, QA, topology, Canvas, and technical
      volumetry, but exclude them from deployment scenarios, BOM, and pricing
- [x] Reject `Duplicado 2` only as a known source-workbook defect and retain the
      rejected row solely as immutable source-lineage evidence
- [x] Remove Uncertainty and the duplicated Due Diligence Business Process from
      active schemas, QA, capture, exports, and UI while accepting and ignoring
      those columns in historical workbooks
- [x] Publish the governed offline workbook as en-US template `v3.1.0`, including
      English sheet names, headers, definitions, examples, validations, and lists
- [x] **Exit criteria**: migration head `20260717_0036`; calc-engine, API,
      frontend, OpenAPI, production Docker, round-trip current/legacy workbook,
      BOM eligibility, and responsive browser validation pass

### M26 — Topology Decision Workspace
- [x] Separate statistical majority from conservative edge risk so mixed paths
      cannot render as healthy when review or pending integrations are present
- [x] Add governed edge metrics, coverage, interaction mode, owners,
      technologies, actionable integration summaries, and real freshness metadata
- [x] Replace the dense default graph with priority-path disclosure while keeping
      all paths available and restoring every adjacent path during system focus
- [x] Add searchable process-family and system controls, ranked architecture
      triage, domain and three-stage flow layouts, adaptive legends, and metric modes
- [x] Make nodes and edges keyboard operable and expose meaningful accessible names
- [x] Replace the empty mobile fallback with a searchable risk and system explorer
      that does not render the desktop SVG outside its supported breakpoint
- [x] Make node and path detail panels actionable with catalog drill-through,
      complete expandable lists, governed metrics, ownership, and change context
- [x] Generate reliable styled PNG exports with visible completion/error state
- [x] **Exit criteria**: graph API tests, frontend topology tests, production build,
      desktop investigation E2E, PNG download E2E, and mobile explorer E2E pass

### M26 — Governed Offline Capture Workbook 2.0
- [x] Replace the importable example row with a blank 500-row capture surface
- [x] Add novice-oriented instructions, preflight checks, guided examples, and a field dictionary
- [x] Export governed patterns, OCI products, limits, interoperability, evidence freshness, and official sources
- [x] Use one backend-owned column/version contract and named validation ranges
- [x] Add structured pattern applicability examples, selection questions, and required inputs
- [x] Preserve v1 import compatibility while rejecting formulas, future versions, and modified v2 headers
- [x] Validate download-fill-upload round trip and render every visible workbook sheet
- [x] **Exit criteria**: the App download is self-documenting, contains no importable examples,
      maps one captured row exactly, exposes governed metadata in Import UI, and passes all quality gates

### M27 — Topology Review Ergonomics + Accessible Controls
- [x] Replace the one-shot highest-risk action with a browser-session review queue
      that advances deterministically without mutating governed QA state
- [x] Persist session review progress per project, expose progress in the command bar
      and triage queue, and provide explicit start, continue, next, and restart states
- [x] Render topology context as a non-modal drawer from tablet through laptop widths
      and as the existing side panel on wide desktop so details remain immediately visible
- [x] Replace native datalist filters with searchable ARIA combobox/listbox controls,
      keyboard navigation, visible options, invalid-search feedback, and clear actions
- [x] Add announced pressed states to segmented controls, visible hover tooltips to
      icon commands, active-filter counts, and one clear-filter action
- [x] Separate governed data filters from map-display controls and preserve the
      list-first mobile dependency explorer
- [x] **Exit criteria**: Node 26 production build, TypeScript/ESLint, frontend unit
      tests, npm audit, desktop review progression E2E, PNG export E2E, and mobile
      topology E2E pass; visual checks cover 1280×720, 1600×900, and 390×844

### M28 — Complete Dashboard Product Footprint + Action Harmony
- [x] Derive the Dashboard product inventory from core tools, architectural overlays,
      and saved canvas nodes without hiding capture-only taxonomy entries
- [x] Count each product once per integration and expose product role, usage count,
      coverage ratio, and Service Product Library identifier when available
- [x] Preserve compatibility for historical dashboard snapshots created before the
      product-footprint contract existed
- [x] Replace the fixed five-service presentation with the complete captured inventory
      while keeping calculated service sizing as a separate technical section
- [x] Standardize Dashboard actions with shared button classes, consistent dimensions,
      familiar Lucide icons, command hierarchy, and responsive wrapping
- [x] **Exit criteria**: the enterprise snapshot represents 9 of 9 products across
      480 of 480 catalog rows; API tests, Ruff, frontend tests, TypeScript/ESLint,
      Node 26 production build, desktop/mobile Playwright, and visual inspection pass

### M29 — Contextual AI Actions + Catalog and Frequency Governance
- [x] Make every visible AI launcher identify its actual review scope: project,
      integration, current saved canvas, selected system, or dependency path
- [x] Persist dirty Canvas evidence before opening its review and keep the backend
      compatible with V4 endpoint positions without dropping the saved layout
- [x] Expose selected graph context inside the review board and filter persisted
      deterministic evidence to the selected system or dependency path
- [x] Standardize Catalog pattern, complexity, QA, core-tool, and overlay labels on
      one shared badge geometry while retaining semantic status colors
- [x] Enforce uppercase `FQNN` frequency codes in UI and API, reject invalid or
      duplicate active codes, and remove all superseded `FREQ-*` records by migration
- [x] Prevent topology review actions while filtered graph data is refreshing so
      the queue never opens against stale dependency paths
- [x] **Exit criteria**: migration head `20260711_0018`, 16 of 16 Frequency rows use
      `FQ01`–`FQ16`, OCI GenAI provider status is live, API/calc/frontend quality gates
      pass, and contextual AI, Catalog, Frequency, Dashboard, and Map Playwright pass

### M30 — Dashboard Feedback + Semantic Review Brief + macOS Dark Mode
- [x] Move recalculation progress and completion feedback into the global toast system
      so asynchronous jobs do not resize or reflow the Dashboard action toolbar
- [x] Keep the Recalculate command width stable across idle and pending labels and
      expose its busy state to assistive technology
- [x] Compare canvas baselines by governed core tools and overlays instead of raw
      serialized node positions or storage-version metadata
- [x] Render historical canvas evidence as concise plan-versus-current values and
      identify layout-only legacy differences without presenting them as actionable drift
- [x] Reframe Review Project around an executive decision, decision agenda, blockers,
      material drift, next action, and progressively disclosed supporting evidence
- [x] Replace warm dark-mode surfaces with neutral graphite hierarchy, system-blue
      accent controls, semantic label colors, and status colors reserved for status
- [x] Keep Dashboard risk cards on graphite surfaces in dark mode while preserving
      severity through restrained semantic borders and titles rather than light fills
- [x] **Exit criteria**: API, calc-engine, frontend unit tests, Ruff, mypy,
      TypeScript/ESLint, Node 26 production build, live recalculation, completed review
      history, browser console, and desktop visual inspection pass in the Docker stack

### M31 — Sidebar Ergonomics + Functional Command Launcher
- [x] Reduce the sidebar theme selector to a balanced segmented control and place
      context plus application version in one compact metadata row
- [x] Connect the sidebar Search or jump control to the same command palette owned
      by the workspace top bar instead of rendering a decorative duplicate
- [x] Preserve `Command-K`, add dialog and keyboard shortcut semantics to the sidebar
      launcher, autofocus the real query field, and keep route filtering navigable
- [x] **Exit criteria**: frontend unit tests, TypeScript/ESLint, Node 26 production
      build, live sidebar launch, query filtering, result navigation, focus state,
      browser console, and dark-mode visual inspection pass in the Docker stack

### M32 — Integration Detail Dark-Mode Legibility + Control Harmony
- [x] Add dark table tokens so lineage headers, row separators, and hover states use
      the same graphite hierarchy as the rest of the integration detail workspace
- [x] Standardize Save and Remove controls on shared 40px button geometry, Lucide
      icons, no-wrap labels, and a restrained dark destructive treatment
- [x] Replace warm pattern and coverage panels with neutral dark surfaces plus
      semantic borders, titles, and readable secondary text
- [x] Keep raw-lineage edit actions visible, keyboard focusable, and explicitly
      named for assistive technology instead of revealing them only on hover
- [x] **Exit criteria**: frontend unit tests, TypeScript/ESLint, Node 26 production
      build, exact reference integration, Review Integration, destructive-confirm
      cancel flow, table contrast, edit affordances, and browser console pass in Docker

---

## Coding rules

### General
- **TypeScript strict mode** everywhere in `apps/web/`
- **Python type hints** on every function signature in `apps/api/` and `packages/calc-engine/`
- No `any` in TypeScript. No untyped function args in Python.
- Every new file must have a module docstring explaining its purpose.

### FastAPI conventions
- Routers in `app/routers/` — one file per route group, thin (delegate to `app/services/`)
- Services in `app/services/` — all business logic, DB access, worker dispatch
- Models in `app/models/` — SQLAlchemy only, no Pydantic here
- Schemas in `app/schemas/` — Pydantic request/response DTOs, never raw dicts in endpoints
- Every mutating endpoint emits an `AuditEvent` via `app/services/audit_service.py`
- Never put calculation logic in routers or services — call `packages/calc-engine/`

### Calc engine rules (critical)
- `packages/calc-engine/` is **pure Python** — no SQLAlchemy, no HTTP, no Celery imports
- Every public function returns a `CalcResult` (value, unit, formula, inputs, reason)
- No global mutable state — pass `Assumptions` explicitly
- Round only at output boundary, never mid-calculation
- Every new formula needs a test in `src/tests/`

### Database
- All migrations via Alembic — no manual schema changes
- Use `async` SQLAlchemy sessions everywhere in the API
- Never expose raw SQL in routers — use service + repository pattern
- `SourceIntegrationRow.raw_data` is immutable after insert — never UPDATE it

### Audit trail
- Every write (insert, update, delete) on `CatalogIntegration`, `JustificationRecord`,
  `AssumptionSet`, `DictionaryOption`, `PatternDefinition` must emit an `AuditEvent`
- `AuditEvent` must include: actor_id, event_type, entity_type, entity_id, old_value, new_value
- Use correlation IDs for multi-step operations (import batch, recalculation job)

### Testing
- API tests: `pytest` with `httpx.AsyncClient` against a test DB (separate from dev DB)
- Calc engine tests: `pytest` — pure, no DB, no HTTP
- Parity tests must reproduce workbook benchmark numbers exactly
- Never mark a test as `xfail` to make a milestone pass — fix the code

---

## Environment and Docker

All commands run inside Docker containers — no local Python or Node required on macOS host.

```bash
# First time setup
cp .env.example .env
docker compose up -d --build --wait

# Build the non-deployable quality image, then run API and calc-engine tests
docker build --target quality -t ocidisblueprint-api-quality:local \
  -f apps/api/Dockerfile .
docker run --rm ocidisblueprint-api-quality:local \
  python -m pytest -p no:cacheprovider app/tests -q
docker run --rm -w /calc-engine ocidisblueprint-api-quality:local \
  python -m pytest -p no:cacheprovider src/tests -q

# Apply migrations
docker compose exec -T api alembic upgrade head

# Seed reference data
docker compose exec -T api python -m app.migrations.seed

# Open API docs
open http://localhost:8000/docs

# Open web app
open http://localhost:3000

# MinIO console (local Object Storage runtime)
open http://localhost:9001  # user: minio / pass: minio123

```

---

## API contract

OpenAPI 3.1 spec lives at `docs/api/openapi.yaml` and is served at `http://localhost:8000/openapi.json`.

Route groups (PRD-043):
```
/api/v1/projects
/api/v1/imports
/api/v1/catalog
/api/v1/patterns
/api/v1/dictionaries
/api/v1/assumptions
/api/v1/recalculate
/api/v1/volumetry
/api/v1/dashboard
/api/v1/justifications
/api/v1/audit
/api/v1/exports
/api/v1/service-products
/api/v1/admin/synthetic
/api/v1/ai-reviews
/api/v1/agents
/api/v1/support
/api/v1/pricing
/api/v1/projects/{project_id}/deployment-scenarios
/api/v1/projects/{project_id}/bom-jobs
/api/v1/projects/{project_id}/bom-snapshots
```

---

## Definition of done (PRD-050)

A milestone is **not done** until:
1. All parity tests pass (`pytest -v`)
2. API smoke tests pass (key endpoints return correct shape)
3. No TypeScript errors (`tsc --noEmit`)
4. No linting errors (`ruff check app/`)
5. A written summary of changes (diff) is produced
6. Benchmark comparison to workbook outputs is documented
7. Frontend unit tests and production build pass
8. Playwright critical-flow E2E reaches terminal job states and cleans up fixtures
9. `npm audit --audit-level=high` and production image scans pass

---

## RBAC roles (PRD-005 to PRD-008)

| Role | Permissions |
|------|------------|
| Admin | Full access: dictionaries, assumptions, prompts, audit, exports |
| Architect | Edit: pattern, rationale, comments, retry, core tools, overlays, overlays; approve justifications |
| Analyst | Import, bulk edit, filter, compare, resolve mapping issues |
| Viewer | Read-only: dashboard, exports |

Enforce at the service layer using project-scoped authorization. Never trust role claims from the request body.

---

## What is out of scope for Phase 1 (PRD-055)

- Contract quote generation
- Live source-system connectors
- AI-generated narratives (optional layer — must not replace deterministic text)
- Commercial pricing dashboard (cost data stays isolated)
- Portfolio analytics
