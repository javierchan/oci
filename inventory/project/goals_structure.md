**Inventory Project — Functional Goals and Implementation Mapping**

Overview
-
This document captures the functional goals for the `inventory` codebase and explains, at a technical level, how the repository implements each goal. It serves as a product-level specification and evidence map showing where behavior is implemented and how it is validated.

1) Discover Cloud Resources (Inventory Collection)
-
- Goal: Provide a reliable, region-scoped, compartment-scoped read-only discovery that enumerates OCI resources and writes a stable record stream for downstream processing.
- How implemented: discovery and client orchestration live under [src/oci_inventory/oci](src/oci_inventory/oci). The discovery engine is implemented in [src/oci_inventory/oci/discovery.py](src/oci_inventory/oci/discovery.py) and uses typed client factories in [src/oci_inventory/oci/clients.py](src/oci_inventory/oci/clients.py) to create service-specific clients.
- Key behaviors: compartment + region scoping, pagination helpers in [src/oci_inventory/util/pagination.py](src/oci_inventory/util/pagination.py), and tenancy/identity wiring in [src/oci_inventory/auth/providers.py](src/oci_inventory/auth/providers.py).
- Evidence: CLI run command implemented in [src/oci_inventory/cli.py](src/oci_inventory/cli.py) supports `--regions` and `--query` flags and produces `out/<timestamp>/inventory.jsonl`.

2) Enrich Discovered Records with Service Metadata
-
- Goal: For every discovered resource, attach normalized metadata and optional service-specific enrichment (e.g., Log Analytics entity details) without mutating any OCI resources.
- How implemented: Enrichment subsystem under [src/oci_inventory/enrich](src/oci_inventory/enrich). The base enrichment flow is in [src/oci_inventory/enrich/base.py](src/oci_inventory/enrich/base.py), default behaviors in [src/oci_inventory/enrich/default.py](src/oci_inventory/enrich/default.py), and service-specific enrichers (e.g., Log Analytics fixes) in [src/oci_inventory/enrich/oci_metadata.py](src/oci_inventory/enrich/oci_metadata.py).
- Notable technical fixes: Log Analytics entity enricher was corrected to call `list_namespaces` with the tenancy OCID and to call `get_log_analytics_entity(namespace_name, entity_ocid)`; this fixed runtime errors produced by an earlier incorrect call signature.
- Evidence: unit tests under `tests/` exercise enrichers (e.g., `tests/test_default_enricher.py`, `tests/test_missing_type_enrichers.py`) and the runtime inventory runs show enrichment errors eliminated for LogAnalyticsEntity.

3) Export and Reporting (CSV, JSONL, Parquet, Graph)
-
- Goal: Persist normalized inventories in multiple export formats and optionally produce graph/relationship outputs for analysis.
- How implemented: Export adapters are in [src/oci_inventory/export]: `jsonl.py`, `csv.py`, `parquet.py`, and `graph.py`. Parquet support is optional and gated by a preflight check in `preflight.sh` that verifies `pyarrow` when parquet is requested.
- Evidence: export code used by CLI run flow ([src/oci_inventory/cli.py](src/oci_inventory/cli.py)); tests for serialization and parquet in `tests/test_serialization.py` and `tests/test_parquet.py`.

4) Detect and Report Diffs Between Runs
-
- Goal: Provide efficient change detection across successive inventory runs and render diffs for auditing.
- How implemented: The diff engine is in [src/oci_inventory/diff](src/oci_inventory/diff.py) and the hashing utilities used for deterministic object identity are in [src/oci_inventory/diff/hash.py](src/oci_inventory/diff/hash.py). CLI exposes a `diff` command via [src/oci_inventory/cli.py](src/oci_inventory/cli.py).
- Evidence: unit tests in `tests/test_diff.py` and example CLI usage in README.

5) CLI and Non-interactive Automation
-
- Goal: Offer a scriptable CLI that supports runs, diffs, region/compartment filtering, and optional features like GenAI summaries.
- How implemented: The main CLI entrypoint is [src/oci_inventory/cli.py](src/oci_inventory/cli.py). It defines handlers such as `cmd_run`, `cmd_diff`, `cmd_enrich_coverage`, and `cmd_genai_chat` to integrate GenAI flows.
- Evidence: the `.venv`-based CLI is invoked in CI and by developers in the README examples; the terminal run in the workspace shows successful runs with `--genai-summary` enabled.

6) Interactive Wizard for Guided Runs
-
- Goal: Provide an optional interactive wizard for non-technical operators to configure runs, including coverage checks and toggles (e.g., `include_terminated`).
- How implemented: Wizard code under [src/oci_inventory/wizard] provides a menu and plan builder: `cli.py` (menu wiring), `plan.py` (plan construction, including `build_coverage_plan`), `runner.py` (in-process execution), and `config_file.py` (plan serialization/deserialization).
- Evidence: unit tests `tests/test_wizard_plan.py` and `tests/test_wizard_config_file.py` validate the wizard flows and config parsing.

7) GenAI Executive Summary Integration
-
- Goal: Optionally produce an executive summary (two-pass insertion) for each run while redacting sensitive data and respecting configurable model settings.
- How implemented: GenAI hooks are integrated into the run flow (`--genai-summary`) in [src/oci_inventory/cli.py]. Configuration precedence is implemented: environment override → `~/.config/oci-inv/genai.yaml` → `inventory/.local/genai.yaml`. Redaction and prompt hygiene occur prior to submitting content to the GenAI provider.
- Evidence: README documents GenAI precedence; `preflight.sh` detects presence of GenAI config files during environment checks.

8) Configurable Authentication and Secure Defaults
-
- Goal: Support standard OCI authentication methods (config file, instance principals, etc.) and ensure all network calls are read-only.
- How implemented: Authentication providers live in [src/oci_inventory/auth/providers.py] and the CLI accepts `--auth` and `--profile` flags. Senior-level safety guardrails were enforced in the repo policies ensuring only read-only SDK usage for inventory/discovery.
- Evidence: `AGENTS.md` enumerates safety guardrails and read-only constraints; auth tests in `tests/test_auth_errors.py` validate error handling.

9) Preflight Checks and Runtime Validation
-
- Goal: Provide a preflight script that validates the environment, optional runtime deps (pyarrow), and GenAI config detection prior to long-running runs.
- How implemented: `preflight.sh` at repository root verifies Python environment, optional parquet dependency, and reports GenAI config path detection.
- Evidence: preflight script updated and executed in validation runs; its output reports `~/.config/oci-inv/genai.yaml` when present.

10) Testing, Determinism, and CI-readiness
-
- Goal: Maintain a comprehensive, fast unit test suite that validates enrichers, exports, diffing, wizard, and serialization logic. Tests must be deterministic and offline when possible.
- How implemented: Tests are under `tests/` and cover the main subsystems: `test_enrichers`, `test_diff`, `test_serialization`, `test_pagination`, `test_parquet`, and wizard tests. The test harness uses fixtures and mocked SDK responses to keep tests fast and deterministic.
- Evidence: Local test runs show full suite passing (`pytest -q`), and individual test files assert expected behavior for corrected logic (e.g., LogAnalytics entity call shape).

11) Observability, Logging, and Debugging Support
-
- Goal: Emit structured logs and support `--log-level` debug runs to troubleshoot enrichment and discovery issues.
- How implemented: Logging utilities under [src/oci_inventory/logging.py](src/oci_inventory/logging.py) are used by CLI and core components; CLI exposes `--log-level` and writes run artifacts into `out/<timestamp>/` for per-run inspection.

Outstanding Work & Next Priorities
-
- Remaining notable gap: `MediaAsset` enricher is intentionally deferred and remains the largest `NOT_IMPLEMENTED` enrichment group observed in run artifacts. Implementing it requires mapping Media Services clients and safe read-only getters (likely under `src/oci_inventory/oci/clients.py` + `src/oci_inventory/enrich/oci_metadata.py`).
- Suggested next steps:
	- Implement `MediaAsset` enricher using the pattern in `oci_metadata.py` (tenant-aware namespace resolution if required).
	- Add targeted unit tests `tests/test_media_asset_enricher.py` that mock Media Services responses.
	- Optionally expose an operation mode in the wizard to drive only enrichment-coverage scans.

Appendix — Quick file map (implementation pointers)
- Discovery & clients: [src/oci_inventory/oci/discovery.py](src/oci_inventory/oci/discovery.py), [src/oci_inventory/oci/clients.py](src/oci_inventory/oci/clients.py)
- Enrichment: [src/oci_inventory/enrich/base.py](src/oci_inventory/enrich/base.py), [src/oci_inventory/enrich/oci_metadata.py](src/oci_inventory/enrich/oci_metadata.py)
- Exports: [src/oci_inventory/export/jsonl.py](src/oci_inventory/export/jsonl.py), [src/oci_inventory/export/parquet.py](src/oci_inventory/export/parquet.py)
- Diffing: [src/oci_inventory/diff/diff.py](src/oci_inventory/diff/diff.py), [src/oci_inventory/diff/hash.py](src/oci_inventory/diff/hash.py)
- CLI & Wizard: [src/oci_inventory/cli.py](src/oci_inventory/cli.py), [src/oci_inventory/wizard/cli.py](src/oci_inventory/wizard/cli.py), [src/oci_inventory/wizard/plan.py](src/oci_inventory/wizard/plan.py)
- Auth & preflight: [src/oci_inventory/auth/providers.py](src/oci_inventory/auth/providers.py), [preflight.sh](preflight.sh)
- Tests: directory `tests/` with per-subsystem tests (e.g., `tests/test_diff.py`, `tests/test_parquet.py`, `tests/test_wizard_plan.py`)

Document history
- Author: Senior product + engineering agent (generated).
- Date: 2026-01-08

-----

WORKSPACE SCOPE (HARD CONSTRAINT)

This task is strictly scoped to the directory:

/Users/javierchan/Documents/GitHub/oci/inventory

Rules:
- You MUST treat this directory as the repository root for this task.
- You MUST NOT read, list, modify, refactor, import from, or reference any files outside this directory.
- You MUST NOT assume any shared code, configuration, or utilities exist outside this directory.
- All paths in documentation, imports, tooling, and examples must be relative to this directory.
- If a dependency would normally be shared at repo root, recreate it locally inside this directory.

Violation of these rules is considered an error.

You are CLINE. Create a production-ready Python repository for an Oracle Cloud Infrastructure (OCI) inventory pipeline.

PROJECT VISION (Target End-State)
Build a CLI tool that:
1) Discovers resources across an OCI tenancy using Resource Search (Structured Search).
2) Enriches discovered resources with deep per-service SDK calls (Compute, Networking, Database, etc.).
3) Exports inventory as JSONL (default), CSV, and Parquet (optional).
4) Produces diffs between executions (added/removed/changed/unchanged) by OCID + stable hash.
5) Supports performance controls: parallelism by region and by enrichment workers, with retry/backoff and safe rate-limit handling.

PHASE 1 SCOPE (Implement Now)
Implement ONLY:
- Tenancy-wide discovery using Resource Search with the default query: "query all resources"
- Enricher registry + DefaultEnricher (no per-service enrichers yet)
- Exports (JSONL + CSV; Parquet optional)
- Diffs + hashing
- Coverage metrics
- Tests, docs, CI, tooling

NON-FUNCTIONAL REQUIREMENTS (Senior Dev Best Practices)
- Clear package structure, typed code (mypy-friendly), docs, tests.
- Secrets/auth handled safely (no creds in repo).
- Configurable via CLI flags + env vars + optional YAML/JSON config file.
- Structured logging, consistent error handling, and exit codes.
- Deterministic output ordering where possible; stable hashing for diffs.
- CI-ready (lint + unit tests).
- Provide examples and a minimal “quickstart”.

AUTH REQUIREMENTS
Support multiple OCI auth methods:
A) API Key via ~/.oci/config (profile selection)
B) Instance Principals (when running in OCI)
C) Resource Principals (Functions, OKE workloads, etc.)
D) Security Token session profile (if configured)
The tool should auto-detect when possible, but allow explicit selection.
Never print secrets. Include guidance in docs.

DESIGN / ARCHITECTURE
Use a modular, extensible design:
- Discovery layer: uses ResourceSearchClient structured search per region.
- Enrichment layer: pluggable “enrichers” keyed by resourceType; each enricher returns:
  - details: full SDK object dict (or selected normalized fields)
  - relationships: optional graph edges (source_ocid, target_ocid, relation_type)
- Normalization layer: canonical record schema:
  - ocid, resourceType, displayName, compartmentId, region, lifecycleState, timeCreated,
    definedTags, freeformTags, collectedAt, enrichStatus, enrichError, details, relationships
- Export layer: JSONL, CSV (report fields), Parquet (pyarrow optional).
- Diff layer: compare current vs previous run JSONL to create diff.json and diff_summary.

PERFORMANCE / RELIABILITY
- Parallelize discovery by region (ThreadPoolExecutor).
- Parallelize enrichment by batches (ThreadPoolExecutor), with max workers configurable.
- Use OCI SDK retry strategy (DEFAULT_RETRY_STRATEGY) plus local safeguards.
- Ensure pagination for Search (opc-next-page).

OUTPUT / DATA CONTRACT
- Output directory structure per run:
  out/<timestamp>/
    inventory.jsonl
    inventory.csv
    inventory.parquet (optional)
    relationships.jsonl (optional)
    diff.json (optional, if previous run provided)
    run_summary.json
- Ensure JSONL lines are stable JSON (sorted keys) for reproducibility.

CLI
Provide a top-level command, e.g.:
  oci-inv run --outdir ... --auth auto --profile DEFAULT --parquet --prev out/<prev>/inventory.jsonl \
              --workers-region 6 --workers-enrich 24 --include-terminated \
              --query "query all resources"

Also support:
  oci-inv diff --prev ... --curr ...
  oci-inv validate-auth
  oci-inv list-regions
  oci-inv list-compartments

TECH STACK
- Python 3.11+
- oci SDK
- pyarrow optional extra: `pip install .[parquet]`
- logging: standard logging module with optional JSON logs

REPO STRUCTURE (CREATE THIS)
- pyproject.toml (PEP 621) using hatch or poetry (prefer hatch)
- src/oci_inventory/
    __init__.py
    cli.py
    config.py
    logging.py
    auth/
      __init__.py
      providers.py
    oci/
      __init__.py
      clients.py
      discovery.py
      compartments.py
      regions.py
    enrich/
      __init__.py
      base.py
      default.py
      # placeholders for future: compute.py, network.py, database.py, oke.py, storage.py, iam.py, lb.py
    normalize/
      __init__.py
      schema.py
      transform.py
    export/
      __init__.py
      jsonl.py
      csv.py
      parquet.py
    diff/
      __init__.py
      diff.py
      hash.py
    util/
      __init__.py
      concurrency.py
      pagination.py
      time.py
      errors.py
- tests/
    test_hash.py
    test_diff.py
    test_default_enricher.py
    test_registry.py
    test_config.py
- docs/
    quickstart.md
    architecture.md
    auth.md
- .github/workflows/ci.yml (pytest + ruff)
- .gitignore
- README.md
- LICENSE (Apache-2.0 unless already set)
- pre-commit config (ruff)

PHASE 1 IMPLEMENTATION DETAILS (MUST)
1) Discovery (default query)
- Default query MUST be: "query all resources"
- Support custom query flag, but default must be the above.
- Run discovery per region (list_region_subscriptions).
- Inject the discovery region into each discovered record explicitly (record["region"]=<region_loop_value>).
- Support pagination until opc-next-page is empty.
- Store a minimal normalized record for each result.

2) Enrichment registry
- Implement an Enricher registry keyed by Search resourceType string.
- Implement a DefaultEnricher used when no specific enricher exists.

3) DefaultEnricher behavior (MUST)
- Must never call any per-service API.
- Must never raise; it returns the record with:
    enrichStatus = "NOT_IMPLEMENTED"
    enrichError = None
    details = {"searchSummary": <the Search summary dict>}
    relationships = []
- This ensures the output contains ALL resources returned by "query all resources".

4) Coverage metrics (MUST)
- run_summary.json must include:
  - total_discovered
  - enriched_ok
  - not_implemented
  - errors
  - counts_by_resource_type (discovered counts per resourceType)
  - counts_by_enrich_status

5) Exports (MUST)
- Always produce inventory.jsonl.
- Produce inventory.csv with report fields only.
- Parquet is optional behind a flag; if pyarrow missing, show actionable error.

6) Stability (MUST)
- JSONL lines must be stable JSON (sorted keys).
- Hashing for diffs must exclude collectedAt.

7) Tests (MUST)
- Unit tests for:
  - default enricher behavior
  - registry selection (specific vs default)
  - stable hashing excluding collectedAt
  - diff logic basics

IMPORTANT
- Do not hardcode tenancy OCID or any secrets.
- Keep code clean, typed, documented.
- If something is ambiguous, choose sensible defaults and document them rather than asking questions.

Proceed to generate the repository accordingly.