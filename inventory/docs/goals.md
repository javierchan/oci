# OCI Inventory Codebase Report

## 3.1 Executive Summary Specific to oci-inventory
- OCI Inventory is a Python CLI that inventories OCI resources using Resource Search, with enrichment, deterministic exports, and diffs. (README.md:1)
- Architecture is a modular CLI plus a pipeline of discovery -> normalize -> enrich -> export -> diff -> report, with the CLI orchestrating the full run flow. (docs/architecture.md:3; docs/architecture.md:47; src/oci_inventory/cli.py:232)
- Languages/frameworks: Python 3.11+, OCI Python SDK, and PyYAML; optional pyarrow for Parquet and rich for the wizard; build backend is hatchling. (pyproject.toml:2; pyproject.toml:10; pyproject.toml:27; pyproject.toml:33; pyproject.toml:37)
- Key capabilities include multi-region Resource Search discovery with pagination, registry-based enrichment, deterministic JSONL/CSV/Parquet/graph exports, stable diff hashing, and optional GenAI summaries with redaction. (src/oci_inventory/oci/discovery.py:48; src/oci_inventory/util/pagination.py:8; src/oci_inventory/enrich/__init__.py:11; src/oci_inventory/export/jsonl.py:10; src/oci_inventory/diff/hash.py:9; src/oci_inventory/cli.py:350; src/oci_inventory/genai/redact.py:10)
- Key risks/tech debt observed: duplicated and conflicting cmd_genai_chat definitions, in-memory accumulation of all records during run, ocid-only diff indexing (records without ocid are skipped), and partial results when regions fail. (src/oci_inventory/cli.py:55; src/oci_inventory/cli.py:243; src/oci_inventory/diff/diff.py:21; src/oci_inventory/cli.py:277)

## 3.2 Architecture and Module Map (Pipeline-Oriented)

### cli
- Paths: `src/oci_inventory/cli.py`. (src/oci_inventory/cli.py:1)
- Responsibility: orchestrates inventory runs, diffs, auth validation, region/compartment listing, GenAI commands, and enrichment coverage; drives exports, reports, and optional GenAI summary. (src/oci_inventory/cli.py:232; src/oci_inventory/cli.py:390; src/oci_inventory/cli.py:403; src/oci_inventory/cli.py:429)
- Interfaces: subcommands `run`, `diff`, `validate-auth`, `list-regions`, `list-compartments`, `list-genai-models`, `genai-chat`, `enrich-coverage`. (src/oci_inventory/config.py:242; src/oci_inventory/config.py:272; src/oci_inventory/config.py:316)
- Internal dependencies: config parsing, auth resolution, discovery, enrichers, exports, diffs, report writer, and concurrency helpers. (src/oci_inventory/cli.py:9)
- External dependencies: standard library concurrency and filesystem utilities; OCI SDK is used indirectly via internal modules. (src/oci_inventory/cli.py:4; src/oci_inventory/oci/clients.py:8)
- Architectural pattern: CLI orchestration layer over pipeline modules; report generation is always attempted in a finally block. (src/oci_inventory/cli.py:232; src/oci_inventory/cli.py:346)

### config
- Paths: `src/oci_inventory/config.py`. (src/oci_inventory/config.py:1)
- Responsibility: defines RunConfig, parses CLI flags, loads YAML/JSON config files, merges config/env/CLI with explicit precedence, and builds derived defaults. (src/oci_inventory/config.py:47; src/oci_inventory/config.py:231; src/oci_inventory/config.py:236)
- Interfaces: `load_run_config` returns `(command, RunConfig)` and defines CLI subcommands and options. (src/oci_inventory/config.py:231; src/oci_inventory/config.py:244)
- Internal dependencies: standard library plus YAML parsing. (src/oci_inventory/config.py:3; src/oci_inventory/config.py:12)
- External dependencies: PyYAML. (pyproject.toml:27)

### auth
- Paths: `src/oci_inventory/auth/providers.py`. (src/oci_inventory/auth/providers.py:1)
- Responsibility: resolve OCI auth method into AuthContext, expose tenancy OCID helpers, and construct SDK clients with retry strategy. (src/oci_inventory/auth/providers.py:51; src/oci_inventory/auth/providers.py:128; src/oci_inventory/auth/providers.py:140)
- Interfaces: `resolve_auth`, `get_tenancy_ocid`, `make_client`. (src/oci_inventory/auth/providers.py:51; src/oci_inventory/auth/providers.py:128; src/oci_inventory/auth/providers.py:140)
- External dependencies: OCI SDK signers and retry strategy. (src/oci_inventory/auth/providers.py:9; src/oci_inventory/auth/providers.py:77; src/oci_inventory/auth/providers.py:147)

### oci
- Paths: `src/oci_inventory/oci/clients.py`, `src/oci_inventory/oci/discovery.py`, `src/oci_inventory/oci/regions.py`, `src/oci_inventory/oci/compartments.py`. (src/oci_inventory/oci/clients.py:1; src/oci_inventory/oci/discovery.py:1; src/oci_inventory/oci/regions.py:1; src/oci_inventory/oci/compartments.py:1)
- Responsibility: SDK client factories, subscribed-region lookup, compartment listing, and Resource Search discovery per region. (src/oci_inventory/oci/clients.py:26; src/oci_inventory/oci/regions.py:9; src/oci_inventory/oci/compartments.py:10; src/oci_inventory/oci/discovery.py:48)
- Interfaces:
  - `get_resource_search_client`, `get_identity_client`, and other service clients. (src/oci_inventory/oci/clients.py:26; src/oci_inventory/oci/clients.py:35)
  - `discover_in_region` for Structured Search with pagination and normalization. (src/oci_inventory/oci/discovery.py:48)
  - `get_subscribed_regions` and `list_compartments`. (src/oci_inventory/oci/regions.py:9; src/oci_inventory/oci/compartments.py:10)
- External dependencies: OCI SDK service clients and models. (src/oci_inventory/oci/clients.py:8; src/oci_inventory/oci/discovery.py:12)

### normalize
- Paths: `src/oci_inventory/normalize/schema.py`, `src/oci_inventory/normalize/transform.py`. (src/oci_inventory/normalize/schema.py:1; src/oci_inventory/normalize/transform.py:1)
- Responsibility: define the canonical normalized record schema, report fields, canonical field ordering, and transformation helpers. (src/oci_inventory/normalize/schema.py:12; src/oci_inventory/normalize/schema.py:30; src/oci_inventory/normalize/transform.py:17)
- Interfaces: `normalize_from_search_summary`, `canonicalize_record`, `sort_relationships`, `stable_json_dumps`, `report_rows`. (src/oci_inventory/normalize/transform.py:17; src/oci_inventory/normalize/transform.py:55; src/oci_inventory/normalize/transform.py:71; src/oci_inventory/normalize/transform.py:96; src/oci_inventory/normalize/transform.py:103)

### enrich
- Paths: `src/oci_inventory/enrich/base.py`, `src/oci_inventory/enrich/default.py`, `src/oci_inventory/enrich/oci_metadata.py`, `src/oci_inventory/enrich/coverage.py`, `src/oci_inventory/enrich/__init__.py`. (src/oci_inventory/enrich/base.py:1; src/oci_inventory/enrich/default.py:1; src/oci_inventory/enrich/oci_metadata.py:1; src/oci_inventory/enrich/coverage.py:1; src/oci_inventory/enrich/__init__.py:1)
- Responsibility: define enricher contract and results, provide safe DefaultEnricher, register per-resource-type metadata enrichers, and compute enrichment coverage. (src/oci_inventory/enrich/base.py:10; src/oci_inventory/enrich/default.py:8; src/oci_inventory/enrich/oci_metadata.py:53; src/oci_inventory/enrich/coverage.py:30)
- Interfaces: `Enricher` protocol, `EnrichResult`, `register_enricher`, `get_enricher_for`, `set_enrich_context`, `compute_enrichment_coverage`. (src/oci_inventory/enrich/base.py:18; src/oci_inventory/enrich/__init__.py:42; src/oci_inventory/enrich/__init__.py:46; src/oci_inventory/enrich/__init__.py:58; src/oci_inventory/enrich/coverage.py:30)
- External dependencies: OCI SDK clients via `oci_inventory.oci.clients`, used in metadata enrichers. (src/oci_inventory/enrich/oci_metadata.py:5)

### export
- Paths: `src/oci_inventory/export/jsonl.py`, `src/oci_inventory/export/csv.py`, `src/oci_inventory/export/parquet.py`, `src/oci_inventory/export/graph.py`. (src/oci_inventory/export/jsonl.py:1; src/oci_inventory/export/csv.py:1; src/oci_inventory/export/parquet.py:1; src/oci_inventory/export/graph.py:1)
- Responsibility: write deterministic JSONL and CSV exports, optional Parquet export, and graph artifacts (nodes/edges + Mermaid). (src/oci_inventory/export/jsonl.py:10; src/oci_inventory/export/csv.py:11; src/oci_inventory/export/parquet.py:25; src/oci_inventory/export/graph.py:113)
- Interfaces: `write_jsonl`, `write_csv`, `write_parquet`, `build_graph`, `write_graph`, `write_mermaid`. (src/oci_inventory/export/jsonl.py:10; src/oci_inventory/export/csv.py:11; src/oci_inventory/export/parquet.py:25; src/oci_inventory/export/graph.py:113; src/oci_inventory/export/graph.py:165; src/oci_inventory/export/graph.py:191)
- External dependencies: pyarrow for Parquet when enabled. (src/oci_inventory/export/parquet.py:14; pyproject.toml:33)

### diff
- Paths: `src/oci_inventory/diff/hash.py`, `src/oci_inventory/diff/diff.py`. (src/oci_inventory/diff/hash.py:1; src/oci_inventory/diff/diff.py:1)
- Responsibility: compute stable record hashes (excluding collectedAt) and diff two inventories by OCID. (src/oci_inventory/diff/hash.py:9; src/oci_inventory/diff/diff.py:32)
- Interfaces: `stable_record_hash`, `compute_diff`, `diff_files`, `write_diff`. (src/oci_inventory/diff/hash.py:26; src/oci_inventory/diff/diff.py:32; src/oci_inventory/diff/diff.py:94; src/oci_inventory/diff/diff.py:100)

### report
- Paths: `src/oci_inventory/report.py`. (src/oci_inventory/report.py:1)
- Responsibility: render and write run reports including configuration, regions, metrics, findings, and optional GenAI summary. (src/oci_inventory/report.py:28; src/oci_inventory/report.py:195)
- Interfaces: `render_run_report_md`, `write_run_report_md`. (src/oci_inventory/report.py:28; src/oci_inventory/report.py:195)

### genai
- Paths: `src/oci_inventory/genai/config.py`, `src/oci_inventory/genai/redact.py`, `src/oci_inventory/genai/chat_runner.py`, `src/oci_inventory/genai/executive_summary.py`, `src/oci_inventory/genai/list_models.py`, `src/oci_inventory/genai/chat_probe.py`. (src/oci_inventory/genai/config.py:1; src/oci_inventory/genai/redact.py:1; src/oci_inventory/genai/chat_runner.py:1; src/oci_inventory/genai/executive_summary.py:1; src/oci_inventory/genai/list_models.py:1; src/oci_inventory/genai/chat_probe.py:1)
- Responsibility: load GenAI config with safe precedence, redact OCIDs/URLs, execute chat and executive summary requests, and list models. (src/oci_inventory/genai/config.py:32; src/oci_inventory/genai/redact.py:10; src/oci_inventory/genai/chat_runner.py:13; src/oci_inventory/genai/executive_summary.py:55; src/oci_inventory/genai/list_models.py:24)
- External dependencies: OCI Generative AI clients and models. (src/oci_inventory/genai/chat_runner.py:33; src/oci_inventory/genai/executive_summary.py:81; src/oci_inventory/genai/list_models.py:34)

### wizard
- Paths: `src/oci_inventory/wizard/cli.py`, `src/oci_inventory/wizard/plan.py`, `src/oci_inventory/wizard/runner.py`, `src/oci_inventory/wizard/config_file.py`. (src/oci_inventory/wizard/cli.py:1; src/oci_inventory/wizard/plan.py:1; src/oci_inventory/wizard/runner.py:1; src/oci_inventory/wizard/config_file.py:1)
- Responsibility: interactive and non-interactive run/diff/coverage planning, command preview, and execution using the CLI command handlers. (src/oci_inventory/wizard/cli.py:155; src/oci_inventory/wizard/plan.py:9; src/oci_inventory/wizard/runner.py:63; src/oci_inventory/wizard/config_file.py:75)
- Interfaces: `WizardPlan`, `build_run_plan`, `build_diff_plan`, `execute_plan`, `load_wizard_plan_from_file`. (src/oci_inventory/wizard/plan.py:9; src/oci_inventory/wizard/plan.py:57; src/oci_inventory/wizard/plan.py:118; src/oci_inventory/wizard/runner.py:63; src/oci_inventory/wizard/config_file.py:75)
- External dependencies: rich (optional extra) for interactive UX. (src/oci_inventory/wizard/cli.py:19; pyproject.toml:37)

### util and logging
- Paths: `src/oci_inventory/util/serialization.py`, `src/oci_inventory/util/pagination.py`, `src/oci_inventory/util/concurrency.py`, `src/oci_inventory/util/errors.py`, `src/oci_inventory/util/time.py`, `src/oci_inventory/logging.py`. (src/oci_inventory/util/serialization.py:1; src/oci_inventory/util/pagination.py:1; src/oci_inventory/util/concurrency.py:1; src/oci_inventory/util/errors.py:1; src/oci_inventory/util/time.py:1; src/oci_inventory/logging.py:1)
- Responsibility: redaction and JSON-safe serialization, generic pagination, ordered concurrency helpers, error taxonomy with exit codes, time helpers, and optional JSON logging. (src/oci_inventory/util/serialization.py:25; src/oci_inventory/util/pagination.py:8; src/oci_inventory/util/concurrency.py:10; src/oci_inventory/util/errors.py:6; src/oci_inventory/util/time.py:6; src/oci_inventory/logging.py:69)

### Architectural pattern (cross-cutting)
- Pattern: layered separation of CLI/config/auth/OCI access and pipeline steps (normalize/enrich/export/diff/report) with deterministic ordering rules and concurrency controls. (docs/architecture.md:3; docs/architecture.md:47; src/oci_inventory/cli.py:268)

## 3.3 Data Model and Contracts

### Normalized inventory record
- Base schema fields include ocid, resourceType, displayName, compartmentId, region, lifecycleState, timeCreated, tags, collectedAt, enrichStatus, enrichError, details, and relationships. (src/oci_inventory/normalize/schema.py:12)
- Normalization pulls keys from Resource Search summaries (snake_case or camelCase), injects region, sets collectedAt, and initializes enrichment fields. (src/oci_inventory/normalize/transform.py:17; src/oci_inventory/normalize/transform.py:35)
- Canonical ordering for deterministic output is defined in `CANONICAL_FIELD_ORDER`; CSV export uses `CSV_REPORT_FIELDS`. (src/oci_inventory/normalize/schema.py:30; src/oci_inventory/normalize/schema.py:42)

### searchSummary handling
- Resource Search discovery attaches the raw summary to `searchSummary` for use by enrichers. (src/oci_inventory/oci/discovery.py:76; src/oci_inventory/oci/discovery.py:80)
- The enrichment step removes `searchSummary` from the final output record, keeping it transient. (src/oci_inventory/cli.py:179)
- DefaultEnricher and metadata enrichers include `searchSummary` inside `details` when present. (src/oci_inventory/enrich/default.py:24; src/oci_inventory/enrich/oci_metadata.py:41)

### Enrichment contract
- Enrichers implement the `Enricher` protocol and return an `EnrichResult` with `details`, `relationships`, `enrichStatus`, and `enrichError`. (src/oci_inventory/enrich/base.py:10; src/oci_inventory/enrich/base.py:19)
- DefaultEnricher is safe and non-throwing, returning NOT_IMPLEMENTED and preserving the search summary. (src/oci_inventory/enrich/default.py:8; src/oci_inventory/enrich/default.py:24)
- Metadata enrichers call per-service SDK `get_*` methods and store SDK output under `details.metadata` while keeping relationships empty by default. (src/oci_inventory/enrich/oci_metadata.py:53; src/oci_inventory/enrich/oci_metadata.py:76)

### Export contracts
- JSONL export writes canonicalized records in deterministic order by `(ocid, resourceType)` with stable JSON serialization. (src/oci_inventory/export/jsonl.py:10; src/oci_inventory/normalize/transform.py:96)
- CSV export writes only report fields in deterministic order by `(ocid, resourceType)`. (src/oci_inventory/export/csv.py:11; src/oci_inventory/normalize/schema.py:30)
- Parquet export is optional and uses canonicalized record order; it requires pyarrow. (src/oci_inventory/export/parquet.py:14; src/oci_inventory/export/parquet.py:25)
- Graph export builds nodes and edges (including implicit IN_COMPARTMENT edges), writes nodes/edges JSONL, and emits Mermaid diagrams. (src/oci_inventory/export/graph.py:113; src/oci_inventory/export/graph.py:165; src/oci_inventory/export/graph.py:191)

### Determinism and hashing
- Relationships are sorted deterministically by `(source_ocid, relation_type, target_ocid)` before export and hashing. (src/oci_inventory/normalize/transform.py:71; src/oci_inventory/export/jsonl.py:25)
- Stable record hashes exclude `collectedAt` and serialize with sorted keys. (src/oci_inventory/diff/hash.py:9; src/oci_inventory/diff/hash.py:31)

### Diff contract
- Diffing indexes records by `ocid`, computes added/removed/changed/unchanged lists, and returns a summary count plus per-ocid hashes. (src/oci_inventory/diff/diff.py:21; src/oci_inventory/diff/diff.py:32; src/oci_inventory/diff/diff.py:75)

## 3.4 Key Functional Flows in the Pipeline

### 1) `oci-inv run` (full pipeline)
- Entrypoint: `oci-inv run` parsed and dispatched via `load_run_config` and `cmd_run`. (src/oci_inventory/config.py:231; src/oci_inventory/cli.py:440)
- Config resolution: defaults < config file < env < CLI, then build RunConfig and timestamped outdir for runs. (src/oci_inventory/config.py:236; src/oci_inventory/config.py:224; src/oci_inventory/config.py:494)
- Auth: `resolve_auth` builds AuthContext; context is stored for enrichment use. (src/oci_inventory/cli.py:255; src/oci_inventory/enrich/__init__.py:58)
- Regions: subscribed regions from identity are sorted; `--regions` overrides. (src/oci_inventory/cli.py:258; src/oci_inventory/cli.py:263; src/oci_inventory/oci/regions.py:9)
- Discovery: Resource Search is executed per region in a ThreadPool; failures are recorded as excluded regions. (src/oci_inventory/cli.py:268; src/oci_inventory/cli.py:279)
- Normalization and searchSummary: each summary is normalized and `searchSummary` is attached for enrichment. (src/oci_inventory/oci/discovery.py:76; src/oci_inventory/oci/discovery.py:80)
- Enrichment: registry selects an enricher by resourceType; errors are captured into `enrichStatus` and `enrichError`; `searchSummary` is stripped from output. (src/oci_inventory/cli.py:163; src/oci_inventory/cli.py:173; src/oci_inventory/cli.py:179)
- Exports: JSONL and CSV always; optional Parquet with a warning on missing pyarrow; relationships and graph artifacts are written. (src/oci_inventory/cli.py:306; src/oci_inventory/cli.py:312; src/oci_inventory/cli.py:320; src/oci_inventory/cli.py:326)
- Coverage metrics: counts by resource type and enrich status are computed and written to run_summary.json. (src/oci_inventory/cli.py:185; src/oci_inventory/cli.py:322; src/oci_inventory/cli.py:208)
- Optional diff: when `--prev` is provided, diff.json and diff_summary.json are produced. (src/oci_inventory/cli.py:331; src/oci_inventory/diff/diff.py:100)
- Report: report.md is always attempted in a finally block; GenAI executive summary is appended when enabled and successful. (src/oci_inventory/cli.py:346; src/oci_inventory/cli.py:350; src/oci_inventory/report.py:195)
- Errors: region-level discovery errors are logged and excluded; diff and parquet errors become warnings; fatal exceptions set status FAILED but still attempt report output. (src/oci_inventory/cli.py:277; src/oci_inventory/cli.py:316; src/oci_inventory/cli.py:342)

### 2) `oci-inv diff`
- Entrypoint: `oci-inv diff` parsed by config and dispatched by `cmd_diff`. (src/oci_inventory/config.py:316; src/oci_inventory/cli.py:447)
- Flow: read prev/curr JSONL, compute diff by ocid, and write diff outputs to outdir. (src/oci_inventory/cli.py:390; src/oci_inventory/diff/diff.py:94; src/oci_inventory/diff/diff.py:100)

### 3) Auth validation and helper commands
- `validate-auth` resolves auth and lists subscribed regions to verify credentials. (src/oci_inventory/cli.py:403; src/oci_inventory/oci/regions.py:9)
- `list-regions` prints subscribed regions; `list-compartments` prints `ocid,name` for root and subtree. (src/oci_inventory/cli.py:413; src/oci_inventory/cli.py:421; src/oci_inventory/oci/compartments.py:10)

### 4) GenAI flows
- `genai-chat` builds a message (from `--message` or report text), uses run_genai_chat with AUTO/GENERIC/COHERE, and prints redacted output. (src/oci_inventory/cli.py:61; src/oci_inventory/cli.py:79; src/oci_inventory/genai/chat_runner.py:13)
- Executive summary in `run`: `generate_executive_summary` redacts OCIDs/URLs before sending, and fails safely if output is empty or unsafe. (src/oci_inventory/cli.py:350; src/oci_inventory/genai/executive_summary.py:138; src/oci_inventory/genai/executive_summary.py:592)
- `list-genai-models` loads GenAI config and outputs model data as CSV. (src/oci_inventory/cli.py:429; src/oci_inventory/genai/list_models.py:24; src/oci_inventory/genai/list_models.py:91)

## 3.5 Infrastructure, Deployment, and Operations
- Installation uses `pip install .` with optional extras (parquet, wizard); CLI entrypoints are `oci-inv` and `oci-inv-wizard`. (README.md:18; pyproject.toml:32; pyproject.toml:41)
- Preflight script prepares environments, creates a .venv, installs dependencies, and supports offline mode plus optional OCI CLI install. (README.md:25; preflight.sh:20; preflight.sh:80)
- Runtime requirements: Python 3.11+, OCI SDK, PyYAML; optional pyarrow for Parquet and rich for wizard. (pyproject.toml:10; pyproject.toml:27; pyproject.toml:33; pyproject.toml:37)
- Environment variables and config precedence are documented and implemented for query, output, auth, regions, and workers (including opt-in cost/export workers). (README.md:188; README.md:276; src/oci_inventory/config.py:236)
- Auth methods: config-file, instance principals, resource principals, security token, and auto fallback; tenancy OCID may be required for list-regions and list-compartments. (docs/auth.md:5; src/oci_inventory/auth/providers.py:51; src/oci_inventory/oci/clients.py:162)
- Read-only posture: CLI is documented as read-only and report notes reinforce no mutations; SDK calls are list/get style. (README.md:218; src/oci_inventory/report.py:189)
- Security hygiene: redaction for sensitive keys during serialization and OCID/URL redaction for GenAI. (src/oci_inventory/util/serialization.py:7; src/oci_inventory/genai/redact.py:5)
- Operational outputs: timestamped outdir for runs with report, inventory, graph, diff, and coverage artifacts. (README.md:223; src/oci_inventory/config.py:224; src/oci_inventory/cli.py:306)

## 3.6 Quality, Testing, and Standards
- Test suite covers config precedence and flags, hashing, diff computation, enrichers, coverage, serialization, graph export, parquet behavior, pagination, compartments, report rendering, GenAI utilities, and wizard plans. (tests/test_config.py:8; tests/test_hash.py:6; tests/test_diff.py:8; tests/test_default_enricher.py:8; tests/test_enrich_coverage.py:28; tests/test_serialization.py:8; tests/test_graph.py:6; tests/test_parquet.py:8; tests/test_pagination.py:6; tests/test_compartments.py:39; tests/test_report_md.py:9; tests/test_genai_chat_runner.py:49; tests/test_wizard_plan.py:13)
- GenAI-specific behaviors (redaction, list-models output, and executive summary fallback) are unit-tested with fake clients. (tests/test_genai_redaction.py:6; tests/test_genai_list_models.py:23; tests/test_genai_executive_summary.py:29)
- Standards/tooling: ruff for linting, pytest for tests, and hatchling build backend; typing and dataclasses are used in core modules. (pyproject.toml:1; pyproject.toml:51; pyproject.toml:66; src/oci_inventory/config.py:47)
- Coverage gaps (NOT VERIFIED beyond tests/ scope): there is no explicit test file targeting `cmd_run` or `discover_in_region`; current tests are unit-level for components listed above. (tests/test_config.py:1; tests/test_diff.py:1; tests/test_graph.py:1; tests/test_wizard_plan.py:1)

## 3.7 Risks, Technical Debt, and Potential Issues

### Architecture
- `cmd_run` aggregates auth, discovery, enrichment, export, diff, and reporting in one function, increasing coupling and making it harder to test in isolation. (src/oci_inventory/cli.py:232)
- Enricher registration is best-effort and suppresses exceptions, which can hide registration failures. (src/oci_inventory/enrich/__init__.py:69)
- `cmd_genai_chat` contains duplicated and conflicting implementations with unreachable code paths, raising maintainability risk. (src/oci_inventory/cli.py:55)

### Scalability and performance
- The run pipeline holds all discovered records and all enriched records in memory before export, which may be heavy for large tenancies. (src/oci_inventory/cli.py:243; src/oci_inventory/cli.py:287; src/oci_inventory/cli.py:300)
- Discovery uses fixed page size (limit=1000) with per-region ThreadPool execution; no streaming or backpressure is applied. (src/oci_inventory/oci/discovery.py:61; src/oci_inventory/cli.py:274)
- Ordered concurrency uses a list materialization for non-Sequence inputs, which can amplify memory use. (src/oci_inventory/util/concurrency.py:21)

### Reliability and resiliency
- Region discovery errors are logged and excluded, producing partial results; diff failures are warnings; report generation errors are swallowed to avoid failing the run. (src/oci_inventory/cli.py:279; src/oci_inventory/cli.py:336; src/oci_inventory/cli.py:384)
- Diffing skips records without ocid, which can hide malformed records from outputs. (src/oci_inventory/diff/diff.py:21)

### Security
- Redaction relies on substring matching for a fixed set of key names; sensitive fields outside this list are not automatically redacted. (src/oci_inventory/util/serialization.py:7; src/oci_inventory/util/serialization.py:18)
- GenAI redaction removes only OCIDs and URLs; other sensitive data types are not filtered by default. (src/oci_inventory/genai/redact.py:5)

### Maintainability
- The metadata enricher module is large and holds many service-specific fetchers and mappings, which can become unwieldy as coverage grows. (src/oci_inventory/enrich/oci_metadata.py:76; src/oci_inventory/enrich/oci_metadata.py:318)

## 3.8 Explicit Guide for Future AI Agents Modifying oci-inventory

### Design principles
- Preserve the pipeline order discovery -> normalize -> enrich -> export -> diff -> report, and keep CLI orchestration separate from core logic. (docs/architecture.md:47; src/oci_inventory/cli.py:232)
- Maintain deterministic outputs: stable key ordering, sorted relationships, and stable hashes excluding collectedAt. (src/oci_inventory/normalize/transform.py:55; src/oci_inventory/normalize/transform.py:71; src/oci_inventory/diff/hash.py:9)
- Keep all OCI operations read-only (list/get) and preserve the stated read-only posture. (README.md:218; src/oci_inventory/report.py:189)

### Rules for new enrichers
- Implement the Enricher protocol and always return EnrichResult (details, relationships, enrichStatus, enrichError). (src/oci_inventory/enrich/base.py:10; src/oci_inventory/enrich/base.py:19)
- Do not mutate the input record; follow DefaultEnricher behavior for safety and non-throwing semantics. (src/oci_inventory/enrich/base.py:20; src/oci_inventory/enrich/default.py:8)
- Register new enrichers via the registry and keep `details.metadata` as sanitized SDK output. (src/oci_inventory/enrich/__init__.py:42; src/oci_inventory/enrich/oci_metadata.py:41; src/oci_inventory/util/serialization.py:25)
- If you introduce relationships, keep them sorted and deterministic. (src/oci_inventory/normalize/transform.py:71)

### Rules for new exports
- Use canonicalized records and stable ordering (ocid, resourceType) for deterministic JSONL/CSV/Parquet outputs. (src/oci_inventory/export/jsonl.py:18; src/oci_inventory/export/csv.py:18; src/oci_inventory/export/parquet.py:33)
- Do not change hashing inputs without considering diff stability (collectedAt is excluded). (src/oci_inventory/diff/hash.py:9)

### Rules for GenAI features
- Always redact OCIDs and URLs before sending prompts and before emitting results. (src/oci_inventory/genai/redact.py:5; src/oci_inventory/genai/chat_runner.py:59)
- Load GenAI config from supported paths only; never hardcode secrets in code or repo. (src/oci_inventory/genai/config.py:32; docs/auth.md:12)

### Code location guidance
- Add new CLI subcommands in `load_run_config` and dispatch in `cli.main`. (src/oci_inventory/config.py:231; src/oci_inventory/cli.py:440)
- Add new RunConfig fields in `RunConfig` and wire them through config/env/CLI merges. (src/oci_inventory/config.py:47; src/oci_inventory/config.py:445)
- Place new enrichers under `src/oci_inventory/enrich/` and exports under `src/oci_inventory/export/`. (docs/architecture.md:23; docs/architecture.md:30)

### Testing requirements
- Add unit tests alongside existing patterns in `inventory/tests/` for any behavior change (config, enrichers, exports, diffs, GenAI, wizard). (tests/test_config.py:1; tests/test_default_enricher.py:1; tests/test_graph.py:1; tests/test_diff.py:1; tests/test_genai_chat_runner.py:1; tests/test_wizard_plan.py:1)
- Keep tests deterministic and offline by mocking OCI SDK clients as done in current tests. (tests/test_missing_type_enrichers.py:23; tests/test_genai_chat_runner.py:49)

### Contract changes and backward compatibility
- Changes to JSONL/CSV/Parquet formats, diff hashing, or report outputs should be treated as breaking and require explicit documentation updates. (README.md:223; src/oci_inventory/diff/hash.py:9; src/oci_inventory/report.py:28)

## 3.9 Suggested Technical Roadmap (High Level, Repo-Specific)
1) Consolidate and clean up GenAI chat handling to remove duplicate code paths and make behavior consistent. (src/oci_inventory/cli.py:55)
2) Improve memory scalability by streaming discovery/enrichment outputs to exports instead of accumulating full lists in memory. (src/oci_inventory/cli.py:243)
3) Expand enrichment coverage for missing resource types (example: MediaAsset noted in docs) and add targeted tests for new enrichers. (README.md:211; src/oci_inventory/enrich/oci_metadata.py:318)
4) Add an end-to-end pipeline test for `cmd_run` and a focused discovery test with mocked Resource Search responses to validate the full flow. (src/oci_inventory/cli.py:232; src/oci_inventory/oci/discovery.py:48)
5) Enhance resiliency with explicit retry/backoff or rate-limit handling around discovery/enrichment beyond default SDK retry strategy. (src/oci_inventory/auth/providers.py:147; src/oci_inventory/oci/discovery.py:61)
6) Grow relationship enrichment so graph outputs carry meaningful cross-resource edges beyond IN_COMPARTMENT. (src/oci_inventory/cli.py:320; src/oci_inventory/enrich/oci_metadata.py:58)
7) Add richer run observability (per-step timings, per-region metrics) in report.md and/or run_summary.json. (src/oci_inventory/report.py:28; src/oci_inventory/cli.py:323)
