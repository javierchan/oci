# OCI Inventory
Production-ready Python CLI to inventory Oracle Cloud Infrastructure (OCI) resources using Resource Search, with an enrichment framework, deterministic exports, and diffs.

Phase 1 implements:
- Tenancy-wide discovery using Resource Search (Structured Search) with default query: "query all resources"
- Enricher registry + DefaultEnricher with per-service metadata enrichers for supported resource types
- Exports: JSONL (default) and CSV
- Graph + diagram projections (Mermaid flowchart + consolidated architecture-beta + consolidated flowchart; disable with --no-diagrams)
- Cost snapshot reporting via Usage API with optional OneSubscription usage (opt-in)
- Optional GenAI narratives for report.md and cost_report.md
- Diffs and stable hashing (excluding collectedAt)
- Coverage metrics and schema validation
- Tests, docs, CI (ruff + pytest)

Repository scope for this package is strictly local under this directory.

## How it works (pipeline)
The CLI runs a deterministic, read-only pipeline and writes a timestamped output folder.

```mermaid
flowchart LR
  A[Auth resolved] --> B[Discover subscribed regions]
  B --> C[Structured Search per region]
  C --> D[Normalize records]
  D --> E[Enrich records + relationships]
  E --> F[Derive metadata relationships]
  F --> G[Write inventory.jsonl inventory.csv]
  G --> H[Write run_summary.json]
  H --> I[Build graph nodes and edges optional]
  I --> J[Write diagram projections optional]
  J --> K[Validate out timestamp schema]
  K --> L[Validate diagrams if enabled]
  L --> M[Optional diff if prev]
  M --> N[Write report.md always]
```

Key guarantees:
- Read-only OCI calls only (list/search/get).
- Stable ordering and hashing for reproducible diffs.
- Report is always written, even if the run fails.
- Schema validation runs in auto mode by default; use `--validate-schema` to force full/sampled/off (errors fail when enabled).

## Install
- Python 3.11+
- Git
- Node.js + npm (required for Mermaid CLI)
- Use a `.venv` for all Python dependencies (required)

Recommended: `./preflight.sh` (installs all required components).

Manual install (inside `.venv`):
```
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install .[wizard]
pip install oci-cli
npm install -g @mermaid-js/mermaid-cli
```

## Preflight setup
Use the preflight script to prepare a local or CI environment (macOS/Linux; may require sudo on Debian/Ubuntu and Homebrew on macOS for Node.js/npm or Mermaid CLI). It:
- Verifies prerequisites (python3 ≥ 3.11, git, npm) and installs Mermaid CLI (mmdc) if missing
- Creates or reuses a .venv virtual environment and upgrades pip/setuptools/wheel
- Installs the project in editable mode, respecting pyproject.toml
- Installs all extras defined in pyproject.toml (wizard)
- Installs OCI CLI inside the virtual environment
- Uses network access for pip/npm installs and dependency upgrades

Run:
```
./preflight.sh
```

Offline mode (skip network actions; requires deps already available):
```
OCI_INV_OFFLINE=1 ./preflight.sh
```

Next steps after running:
- Activate: `. .venv/bin/activate`
- Show CLI help: `oci-inv --help`

Common failure modes:
- Python version too low (< 3.11) — install Python 3.11+ and re-run
- Missing pip for python3 — try: `python3 -m ensurepip --upgrade`
- Missing git — install git for your OS
- Missing npm/Node.js — install Node.js (npm is required for Mermaid CLI)
- Missing Homebrew on macOS — install Homebrew (https://brew.sh/) and retry
- Offline mode with missing deps — disable offline mode or preinstall dependencies

## Dev Container (Docker Desktop)
For VS Code on macOS with Docker Desktop, use `.devcontainer/devcontainer.json`:
- It mounts `~/.oci` and `~/.config/oci-inv` into the container.
- It runs `./preflight.sh` on first create to install all prerequisites and extras.

Open the repo in VS Code and run: `Dev Containers: Reopen in Container`.

## CLI
Entrypoint: `oci-inv`

Quick help:
```
oci-inv --help
oci-inv <subcommand> --help
```

Commands:
- Run inventory:
  ```
  oci-inv run --outdir out --auth auto --profile DEFAULT --prev out/20240101T000000Z/inventory.jsonl \
              --workers-region 6 --workers-enrich 24 --workers-cost 2 --workers-export 2 \
              --query "query all resources"
  ```
  Opt-in worker overrides for cost collection/export are available via `--workers-cost` and `--workers-export` (defaults are 1 unless explicitly set).
- Diff two inventories:
  ```
  oci-inv diff --prev out/prev-run/inventory.jsonl --curr out/curr-run/inventory.jsonl --outdir out/diff
  ```
- Validate authentication:
  ```
  oci-inv validate-auth --auth auto --profile DEFAULT
  ```
- List subscribed regions:
  ```
  oci-inv list-regions --auth auto --profile DEFAULT
  ```
- List compartments:
  ```
  oci-inv list-compartments --auth auto --profile DEFAULT --tenancy ocid1.tenancy.oc1..xxxx
  ```
- List GenAI models:
  ```
  oci-inv list-genai-models
  ```

## IAM permissions (OCI)
This tool is read-only and relies on Resource Search plus per-service `get` calls for enrichment. The most reliable way to avoid permission errors is to grant explicit read/inspect access to the services present in scope.

Are these privileges appropriate? Yes, for a read-only inventory + cost snapshot. They do not grant write or modify actions. Use the least-privilege option when possible.

### Option A: Broad read-only (lowest friction)
```
allow group <group-name> to read all-resources in tenancy
allow group <group-name> to read usage-reports in tenancy
allow group <group-name> to read budgets in tenancy
```

### Option B: Least-privilege baseline (recommended if you manage IAM closely)
```
# Resource Search (discovery)
allow group <group-name> to inspect resources in tenancy

# Identity (users/groups/policies/compartments/tags)
allow group <group-name> to read users in tenancy
allow group <group-name> to read groups in tenancy
allow group <group-name> to read policies in tenancy
allow group <group-name> to read compartments in tenancy
allow group <group-name> to read tag-namespaces in tenancy
allow group <group-name> to read tag-defaults in tenancy

# Core workload/services (common enrichment targets)
allow group <group-name> to read virtual-network-family in tenancy
allow group <group-name> to read instance-family in tenancy
allow group <group-name> to read volume-family in tenancy
allow group <group-name> to read load-balancers in tenancy
allow group <group-name> to read objectstorage-family in tenancy
allow group <group-name> to read functions-family in tenancy
allow group <group-name> to read devops-family in tenancy
allow group <group-name> to read dns in tenancy
allow group <group-name> to read logging-family in tenancy
allow group <group-name> to read loganalytics-family in tenancy
allow group <group-name> to read cloud-guard-family in tenancy
allow group <group-name> to read vaults in tenancy
allow group <group-name> to read keys in tenancy
allow group <group-name> to read secret-family in tenancy
allow group <group-name> to read database-family in tenancy
allow group <group-name> to read osmh-family in tenancy
allow group <group-name> to read resource-manager-family in tenancy
allow group <group-name> to read service-connector-hub-family in tenancy
allow group <group-name> to read streams in tenancy
allow group <group-name> to read bastion in tenancy
allow group <group-name> to read waf-family in tenancy

# Cost + budgets
allow group <group-name> to read usage-reports in tenancy
allow group <group-name> to read budgets in tenancy
```

### Validate and refine
- If `report.md` shows `enrichStatus=ERROR` with NotAuthorized, expand read/inspect access for the affected services.
- If NotFound errors dominate, treat them as expected drift (resources deleted) and re-run to confirm.
- If Throttling errors appear, reduce `--workers-enrich` or increase `--client-connection-pool-size`.

## Performance tuning
- Worker overrides are opt-in: `--config config/workers.yaml` (region/enrich/cost/export workers).
- Schema validation modes: `--validate-schema auto|full|sampled|off` and `--validate-schema-sample N`.
- Consolidated diagram depth: `--diagram-depth 1|2|3` (1=tenancy/compartments+VCN/subnet/gateways, 2=add workloads, 3=add workload edges). Applies to `diagram.consolidated.architecture.mmd` and `diagram.consolidated.flowchart.mmd`.
- Consolidated diagrams auto-reduce depth when Mermaid text limits are exceeded; a NOTE comment is added to the output when this happens.
- Network/workload diagrams are skipped if a single diagram exceeds Mermaid text limits; the skip is logged for visibility.
- Use `--no-diagrams` when you only need inventory/cost outputs.
- OCI SDK clients are cached per service+region; set `OCI_INV_DISABLE_CLIENT_CACHE=1` to disable.
- Increase OCI SDK HTTP connection pool size with `--client-connection-pool-size N` or `OCI_INV_CLIENT_CONNECTION_POOL_SIZE` to reduce pool churn in high-concurrency runs.
- Sizing tip: set `--client-connection-pool-size` to at least `--workers-enrich` when you see connection pool warnings.
- The pool size applies to the OCI SDK vendored HTTP stack (`oci._vendor.requests`), so it targets the same connections that emit pool warnings.
- If warnings persist, increase `--client-connection-pool-size` or reduce `--workers-enrich`.
- Inventory exports are streamed/merged from chunk files for large runs to avoid extra in-memory sorting.

## Common Use Cases (Copy/Paste)

These examples focus on day-to-day workflows a cloud architect typically needs: tenancy-wide snapshots, scoped inventories (region/compartment/type), repeatable diffs, and auth validation.

### 1) Validate auth + discover subscribed regions

Use this first to confirm credentials and see what regions the tool will query by default.

```
oci-inv validate-auth --auth auto --profile DEFAULT
oci-inv list-regions --auth auto --profile DEFAULT
```

### 2) Tenancy-wide inventory (all subscribed regions)

This is the canonical baseline snapshot.

```
oci-inv run --auth auto --profile DEFAULT --outdir out --query "query all resources"
```

### 3) Inventory in a single region (limit blast radius)

Useful for troubleshooting, performance checks, and focused reviews.

```
oci-inv run --auth auto --profile DEFAULT --regions mx-queretaro-1 --outdir out --query "query all resources"
```

### 4) Inventory a specific compartment (by OCID)

OCI Resource Search filtering is OCID-based for compartments. First, list compartments to find the OCID for the target compartment name:

```
oci-inv list-compartments --auth auto --profile DEFAULT --tenancy ocid1.tenancy.oc1..xxxx
```

Then run a compartment-scoped search:

```
oci-inv run --auth auto --profile DEFAULT --regions mx-queretaro-1 --outdir out \
  --query "query all resources where compartmentId = 'ocid1.compartment.oc1..xxxx'"
```

### 5) Inventory a resource type (tenancy-wide or compartment-scoped)

Common examples: instances, VCNs, subnets, vaults, secrets.

Tenancy-wide (all subscribed regions):

```
oci-inv run --auth auto --profile DEFAULT --outdir out \
  --query "query all resources where resourceType = 'Instance'"
```

Compartment + type + region:

```
oci-inv run --auth auto --profile DEFAULT --regions mx-queretaro-1 --outdir out \
  --query "query all resources where compartmentId = 'ocid1.compartment.oc1..xxxx' and resourceType = 'Vcn'"
```

### 6) Produce a diff between two inventories

Option A: Run a new inventory and diff against a previous `inventory.jsonl` in one command:

```
oci-inv run --auth auto --profile DEFAULT --outdir out \
  --prev out/prev-run/inventory.jsonl \
  --query "query all resources"
```

Option B: Diff any two saved inventories:

```
oci-inv diff --prev out/prev-run/inventory.jsonl --curr out/curr-run/inventory.jsonl --outdir out/diff
```

### 7) Export formats used in reporting pipelines

JSONL + CSV are always written; diagram and cost artifacts are optional based on flags.

```
oci-inv run --auth auto --profile DEFAULT --outdir out --query "query all resources"
```

### Notes

- `--regions` limits execution to a comma-separated list (e.g., `--regions mx-queretaro-1,us-phoenix-1`).
- For consistent diffs, compare `inventory.jsonl` files. The stable hash excludes `collectedAt` by design.
- Queries are OCI Resource Search Structured Search strings. Keep the default query exactly `query all resources` unless you intentionally scope it.
- `--include-terminated` is reserved for future filters and currently has no effect.
- Cost reporting uses the tenancy home region for Usage API calls; if the home region cannot be resolved, Usage API cost collection is skipped and reported.
- `--cost-currency` does not convert amounts; if it differs from the Usage API currency, the report warns and keeps API currency amounts.
- OneSubscription usage requires `--osub-subscription-id` (or `OCI_INV_OSUB_SUBSCRIPTION_ID`); otherwise it is skipped.

Flags and config precedence: defaults < config file < environment < CLI  
- Default search query: "query all resources"
- Workers defaults: regions=6, enrich=24
- Output: creates a timestamped directory under `--outdir` (default `out/TS`) for run
- Boolean flags accept `--no-<flag>` to override config/env (e.g., `--no-json-logs`)
- Limit discovery regions with `--regions` (comma-separated) or `OCI_INV_REGIONS`
- Config files: `--config <path>` supports YAML/JSON and uses the same key names as CLI flags.

## Components and Usage
This section is a quick map of every user-facing component in the CLI, what it does, and a copy/paste example.

- **Inventory run** (core): discover + enrich, always writes JSONL/CSV and report.md.
  - Example: `oci-inv run --auth config --profile DEFAULT --regions mx-queretaro-1 --outdir out --query "query all resources where compartmentId = '<compartment_ocid>'" --genai-summary`
- **Diff**: compare two inventories; writes diff artifacts into an out directory.
  - Example: `oci-inv diff --prev out/old/inventory.jsonl --curr out/new/inventory.jsonl --outdir out/diff`
- **Auth validation and discovery helpers**: validate credentials and list tenancy-scoped data.
  - Examples: `oci-inv validate-auth --auth auto --profile DEFAULT`; `oci-inv list-regions --auth auto`; `oci-inv list-compartments --auth auto --tenancy <tenancy_ocid>`
- **GenAI model listing**: show OCI GenAI models and capabilities in CSV format.
  - Example: `oci-inv list-genai-models`
  - Config precedence: `OCI_INV_GENAI_CONFIG` env → `~/.config/oci-inv/genai.yaml` → `.local/genai.yaml`
- **GenAI report summary**: optional second pass during `run` that appends an executive summary into report.md using the run’s own findings as context.
  - Enable with `--genai-summary` on `run`. If GenAI fails, report.md is still written with an error note.
- **Cost report (optional)**: uses Usage API (home region) for totals and optional OneSubscription usage when `--osub-subscription-id` is provided; writes `cost_report.md`.
  - Enable with `--cost-report` on `run`.
  - Example (no diagrams): `oci-inv run --no-diagrams --cost-report --cost-start 2026-01-01T00:00:00Z --cost-end 2026-01-31T00:00:00Z --cost-currency USD`
  - Example (OneSubscription): `oci-inv run --cost-report --osub-subscription-id <subscription_id> --cost-start 2026-01-01T00:00:00Z --cost-end 2026-01-31T00:00:00Z --cost-currency USD`
  - Data model: Cost Management → Cost Analysis via `UsageapiClient.request_summarized_usages`. This reflects tenancy cost/usage and does not read Subscription Usage or Universal Credits usage.
  - Aggregation: `_extract_usage_amount` reads `computed_amount/cost/amount` from each Usage API item; `_request_summarized_usages` sums values per group (service, compartmentId, region, or total). `total_cost` is the sum across all buckets for the time range.
  - Default granularity is DAILY; time range inputs are normalized to 00:00:00 UTC before querying.
  - Default time range is month-to-date (first day of the current month at 00:00 UTC through now, normalized to 00:00 UTC).
  - Optional compartment grouping: `--cost-compartment-group-by [compartmentId|compartmentName|compartmentPath]` (defaults to compartmentId).
  - Optional multi-dimension group_by for a combined usage CSV: `--cost-group-by service,region,compartmentId`.
  - `cost_usage_items.csv` includes Usage API rows with full fields (group_by, time window, service/region/compartment where available).
  - `cost_usage_items_grouped.csv` is written when `--cost-group-by` is set and contains only those grouped rows.
  - `cost_usage_items.jsonl` includes full Usage API items for auditability.
  - Per-view exports: `cost_usage_service.csv`, `cost_usage_region.csv`, `cost_usage_compartment.csv`.
  - CSV exports replace missing/blank string or dimension values with `unknown`; numeric fields remain empty. JSONL retains nulls.
- **Enrichment coverage**: reports which resource types in an inventory lack enrichers.
  - Example: `oci-inv enrich-coverage --inventory out/<timestamp>/inventory.jsonl --top 10`
- **Interactive wizard**: guided, preview-first UX that builds/executes the same `oci-inv` commands; safe defaults and copy/pasteable outputs.
  - Run: `oci-inv-wizard`
  - Main modes: run, diff, troubleshooting
  - Troubleshooting includes: validate-auth, list-regions, list-compartments, enrich-coverage, list-genai-models
  - Advanced run options: diagram generation/validation, cost report inputs (including OneSubscription subscription ID), assessment metadata
  - Can save reusable wizard plan files (YAML/JSON) from the interactive flow
- **Outputs**: deterministic artifacts per run under `out/<timestamp>/` (JSONL, CSV, report.md, graph files, optional diff files when `--prev` is provided).
  - Hashing excludes `collectedAt` to keep diffs stable.

Notes for developers:
- The CLI is read-only; all SDK calls are list/get style. No mutations are performed.
- Region failures are tolerated and captured in report.md; GenAI is optional and isolated from the main run.
- Mermaid diagrams are generated as `.mmd` files unless `--no-diagrams` is set. Mermaid CLI (`mmdc`) is required and preflight installs it;
  validation runs automatically when diagrams are enabled.
  (During installation you may see npm warnings about Puppeteer deprecations; those are typically non-fatal.)
- Diagram and report rules are documented in `docs/diagram_guidelines.md` and `docs/report_guidelines.md`.

## Known Issues and Notes

- Zero-cost `cost_report.md` outputs can occur when the Usage API returns no data for the specified range. Use a full-day UTC range aligned to the Cost Analysis console, set `--cost-end` to the next day (end is effectively exclusive), and confirm the tenancy home region is correct.
- Large ranges can still time out; shorten the range or split it into smaller windows when validating data.

## Output flow (artifacts and consumers)
```mermaid
flowchart TB
subgraph out_ts[out timestamp]
    inv[inventory.jsonl]
    csv[inventory.csv]
    rel[relationships.jsonl]
    nodes[graph_nodes.jsonl optional]
    edges[graph_edges.jsonl optional]
    raw[diagram_raw.mmd optional]
    ten[diagram.tenancy.mmd optional]
    net[diagram.network.vcn.mmd optional]
    wl[diagram.workload.workload.mmd optional]
    cons[diagram.consolidated.architecture.mmd optional]
    cons_fc[diagram.consolidated.flowchart.mmd optional]
    rpt[report.md]
    sum[run_summary.json]
    diff[diff.json and diff_summary.json optional]
  end
  inv --> rpt
  sum --> rpt
  inv --> nodes
  rel --> edges
  nodes --> ten
  edges --> ten
  nodes --> net
  edges --> net
  nodes --> wl
  edges --> wl
  nodes --> cons
  edges --> cons
  nodes --> cons_fc
  edges --> cons_fc
  nodes --> raw
  edges --> raw
```

## Output Contract
Each run writes to: `out/<timestamp>/`
- report.md (execution steps, exclusions, findings, and optional GenAI summary)
- inventory.jsonl (canonicalized, stable JSON lines)
- inventory.csv (report fields; missing/blank values rendered as `unknown`)
- relationships.jsonl (always written; may be empty)
- graph_nodes.jsonl (diagram-ready nodes; optional)
- graph_edges.jsonl (diagram-ready edges; optional)
- diagram_raw.mmd (Mermaid diagram; raw graph; optional)
- diagram.tenancy.mmd (Mermaid diagram; tenancy/compartment view; optional)
- diagram.network.<vcn>.mmd (Mermaid diagram; per-VCN topology view; optional)
- diagram.workload.<workload>.mmd (Mermaid diagram; workload/application view; optional)
- diagram.consolidated.architecture.mmd (Mermaid architecture-beta diagram; all projections consolidated, edges are unlabelled by design; optional; respects `--diagram-depth`)
- diagram.consolidated.flowchart.mmd (Mermaid flowchart diagram; consolidated view with configurable depth; optional; respects `--diagram-depth`)
- diff.json + diff_summary.json (when --prev provided)
- run_summary.json (coverage metrics)

Quick reference (artifacts → purpose):
- report.md: human-readable run log + findings; holds GenAI summary when enabled.
- inventory.jsonl: canonical per-resource records for downstream processing/diffing.
- inventory.csv: tabular view aligned to report fields; missing values are rendered as `unknown`.
- relationships.jsonl: relationship edges from enrichers + derived metadata.
- graph_nodes.jsonl / graph_edges.jsonl / diagram_raw.mmd: raw topology outputs (optional).
- diagram.*.mmd: architecture-focused projected views (optional).
- diff.json / diff_summary.json: change set when `--prev` is used.
- run_summary.json: coverage/metrics snapshot for automation.

JSONL stability notes:
- Keys sorted; deterministic line ordering by ocid then resourceType
- Hash excludes `collectedAt` to enable meaningful diffs
- `collectedAt` is set per run (run start time) for consistency across records
- Large runs may create a temporary `.inventory_chunks` directory inside the outdir while streaming records; it is removed on successful completion.

Schema validation:
- Every run validates `inventory.jsonl`, `relationships.jsonl`, and `run_summary.json`.
- Graph artifacts (`graph_nodes.jsonl`, `graph_edges.jsonl`) are validated when diagrams are enabled.
- Validation warnings are logged; validation errors fail the run.

## Enrichment
Enrichers use **read-only** OCI SDK calls to fetch full metadata for supported resource types.
Metadata is stored under `details.metadata` as the SDK `to_dict()` output, with sensitive fields
redacted by key substring (e.g., private_key, passphrase, password, secret, token, ssh, content).
For resource types without a registered enricher, DefaultEnricher returns `NOT_IMPLEMENTED` and
stores the raw search summary under `details.searchSummary`.
When SDK metadata is missing network wiring fields, the pipeline backfills a small set of
network identifiers (VCN, subnet, DHCP options, route table, security lists, NSGs, DRG)
from `searchSummary` to keep diagrams and relationship edges consistent.

Supported resource types (current metadata enrichers):
- Access Governance: AgcsGovernanceInstance
- AI Services: AiDataPlatform, AiLanguageProject, AiVisionModel, AiVisionProject
- Analytics: AnalyticsInstance
- API Gateway: ApiDeployment, ApiGateway, ApiGatewayApi
- Budgets: Budget
- Certificates: Certificate, CertificateAuthority
- Cloud Guard: CloudGuardDetectorRecipe, CloudGuardManagedList, CloudGuardResponderRecipe, CloudGuardSavedQuery, CloudGuardTarget
- Compute: Instance, Image, BootVolume, BlockVolume, InstanceConfiguration, InstancePool, DedicatedVmHost
- Container: ClustersCluster, Container, ContainerImage, ContainerInstance, ContainerRepo
- Dashboards: ConsoleDashboard, ConsoleDashboardGroup
- Data Flow: DataFlowApplication, DataFlowRun
- Data Integration: DISWorkspace
- Data Labeling: DataLabelingDataset
- Data Safe: DataSafeAuditProfile, DataSafeReportDefinition, DataSafeSecurityAssessment, DataSafeUserAssessment
- Data Science: DataScienceJob, DataScienceJobRun, DataScienceModel, DataScienceModelDeployment, DataScienceModelVersionSet, DataScienceNotebookSession, DataScienceProject
- Database: AutonomousDatabase, DbNode, PluggableDatabase
- Database Tools: DatabaseToolsPrivateEndpoint
- DevOps: DevOpsBuildPipelineStage, DevOpsBuildRun, DevOpsDeployArtifact, DevOpsProject, DevOpsRepository
- DNS: DnsZone, CustomerDnsZone, DnsResolver, DnsView
- Email Delivery: EmailDkim, EmailDomain, EmailSender
- Events: EventRule
- File Storage: FileSystem
- Functions: FunctionsApplication, FunctionsFunction
- GenAI Agent: GenAiAgent, GenAiAgentDataIngestionJob, GenAiAgentDataSource, GenAiAgentEndpoint, GenAiAgentKnowledgeBase
- Identity: Policy, Compartment, DynamicResourceGroup, Group, IdentityProvider, User
- Identity Domains: App
- Integration: IntegrationInstance
- Key Management: Key, KmsHsmCluster, KmsHsmPartition, VaultSecret
- Logging: LogGroup, Log, LogSavedSearch, LogAnalyticsEntity
- Media Services: MediaWorkflow, MediaAsset, StreamCdnConfig, StreamDistributionChannel, StreamPackagingConfig
- MySQL: MysqlBackup, MysqlDbSystem
- Networking: Vcn, Subnet, Vnic, NetworkSecurityGroup, SecurityList, RouteTable, InternetGateway, NatGateway, ServiceGateway, Drg, DrgAttachment, IPSecConnection, IpSecConnection, VirtualCircuit, Cpe, LocalPeeringGateway, RemotePeeringConnection, CrossConnect, CrossConnectGroup, DhcpOptions, DHCPOptions, PrivateIp, DrgRouteDistribution, DrgRouteTable
- Notifications: OnsSubscription, OnsTopic
- ODA: OdaInstance
- Object Storage: Bucket
- OS Management Hub: OsmhLifecycleEnvironment, OsmhManagedInstanceGroup, OsmhProfile, OsmhScheduledJob, OsmhSoftwareSource
- Path Analyzer: PathAnalyzerTest
- PostgreSQL: PostgresqlConfiguration
- Recovery Service: ProtectedDatabase, RecoveryServiceSubnet
- Resource Manager: OrmConfigSourceProvider, OrmJob, OrmPrivateEndpoint, OrmStack, OrmTemplate
- Resource Scheduler: ResourceSchedule
- Security: Bastion, Vault, Secret, NetworkFirewall, NetworkFirewallPolicy, WebAppFirewall, WebAppFirewallPolicy, SecurityZonesSecurityRecipe, SecurityZonesSecurityZone, SecurityAttributeNamespace
- Service Connector: ServiceConnector
- Streaming: Stream, ConnectHarness
- Tags: TagDefault, TagNamespace
- Visual Builder: VisualBuilderInstance
- Volume Backups: BootVolumeBackup, VolumeBackup, VolumeBackupPolicy, VolumeGroup, VolumeGroupBackup
- Vulnerability Scanning: VssHostScanRecipe, VssHostScanTarget
- WAAS: HttpRedirect, WaasCertificate
- ZPR: ZprPolicy

Known missing enrichers (SDK 2.164.2 has no `get_*` API available yet):
- LimitsIncreaseRequest
- ProcessAutomationInstance
- QueryServiceProject

## Auth
Supported methods:
- auto (default): Resource Principals -> Instance Principals -> Config file
- config: `~/.oci/config` profile
- instance: Instance Principals
- resource: Resource Principals
- security_token: session profile via config

Do not print or commit secrets. See docs/auth.md for guidance.

Common flags:
- `--auth [auto|config|instance|resource|security_token]`
- `--profile PROFILE` (config-file auth)
- `--tenancy OCID` (some calls require explicit tenancy OCID when not available from config)
Signer-based auth also needs a region; set `OCI_REGION` (or `OCI_CLI_REGION`) when no region is provided.

## Environment Variables
- OCI_INV_QUERY
- OCI_INV_OUTDIR
- OCI_INV_PREV
- OCI_INV_CURR
- OCI_INV_INCLUDE_TERMINATED
- OCI_INV_JSON_LOGS
- OCI_INV_LOG_LEVEL (INFO, DEBUG, ...)
- OCI_INV_WORKERS_REGION
- OCI_INV_WORKERS_ENRICH
- OCI_INV_WORKERS_COST
- OCI_INV_WORKERS_EXPORT
- OCI_INV_CLIENT_CONNECTION_POOL_SIZE
- OCI_INV_REGIONS
- OCI_INV_GENAI_SUMMARY
- OCI_INV_VALIDATE_DIAGRAMS
- OCI_INV_DIAGRAMS
- OCI_INV_SCHEMA_VALIDATION
- OCI_INV_SCHEMA_SAMPLE_RECORDS
- OCI_INV_DIAGRAM_DEPTH
- OCI_INV_COST_REPORT
- OCI_INV_COST_START
- OCI_INV_COST_END
- OCI_INV_COST_CURRENCY
- OCI_INV_COST_COMPARTMENT_GROUP_BY
- OCI_INV_COST_GROUP_BY
- OCI_INV_OSUB_SUBSCRIPTION_ID
- OCI_INV_ASSESSMENT_TARGET_GROUP
- OCI_INV_ASSESSMENT_TARGET_SCOPE
- OCI_INV_ASSESSMENT_LENS_WEIGHTS
- OCI_INV_ASSESSMENT_CAPABILITIES
- OCI_INV_AUTH
- OCI_INV_PROFILE
- OCI_TENANCY_OCID
- OCI_INV_GENAI_CONFIG (GenAI config path)
- OCI_INV_DISABLE_CLIENT_CACHE (set to 1/true to disable client reuse)

## Logging
- Std logging, INFO by default
- Structured JSON logs toggled with `--json-logs` or `OCI_INV_JSON_LOGS=1`
- JSON logs include `event`, `step`, `phase`, and `duration_ms` when available; plain logs prefix `[step:phase]`.

## Development
- Linting: ruff
- Tests: pytest
- Build backend: hatchling

Run locally:
```
pip install -e .[wizard]
pip install ruff pytest
ruff check .
pytest
```

## Interactive Wizard

If you prefer a guided, preview-first UX with safer defaults, run:

```
oci-inv-wizard
```

What it does:
- Walks you through run/diff options, shows the exact `oci-inv` command before execution.
- Writes the same outputs as the CLI (`out/<timestamp>/`), so artifacts remain consistent.
- Supports plan files for non-interactive use (see below for an example).
- Covers all CLI modes, with advanced run options for diagram validation, schema validation, cost reporting, and assessments.
- Lets you save interactive runs as plan files for reproducible execution.
- Prompts for an optional config file path (default `config/workers.yaml`; enter `none` to skip).

## GenAI Configuration

GenAI features are available today for `list-genai-models` and `--genai-summary`. The tool redacts OCIDs/URLs in prompts and responses; if GenAI is misconfigured, main runs still complete and record the failure in report.md.

Config precedence (first found wins):
- `OCI_INV_GENAI_CONFIG` (env path)
- `~/.config/oci-inv/genai.yaml`
- `inventory/.local/genai.yaml` (gitignored; for local dev only)

Sample local setup (do not commit real values):

```
mkdir -p ~/.config/oci-inv
cp inventory/.local/genai.yaml ~/.config/oci-inv/genai.yaml
chmod 600 ~/.config/oci-inv/genai.yaml
```

Non-interactive usage (scriptable) is supported via a plan file:

```
cat > wizard-run.yaml <<'YAML'
mode: run
auth: config
profile: DEFAULT
config: config/workers.yaml
log_level: INFO
json_logs: false
outdir: out
regions: [mx-queretaro-1]
query: "query all resources"
workers_region: 6
workers_enrich: 24
workers_cost: 2
workers_export: 2
client_connection_pool_size: 16
cost_report: true
cost_group_by: [service, region, compartmentId]
YAML

oci-inv-wizard --from wizard-run.yaml --dry-run
oci-inv-wizard --from wizard-run.yaml --yes
```

Opt-in worker defaults are also provided in `config/workers.yaml` for reuse with `--config config/workers.yaml` (this file is not loaded automatically).

## Docs
- docs/quickstart.md: minimal getting started
- docs/architecture.md: layout and design
- docs/auth.md: authentication options and safety
- docs/cost_guidelines.md: cost reporting rules and constraints
- docs/diagram_guidelines.md: diagram rules and OCI-aligned abstraction
- docs/report_guidelines.md: report structure and content rules
- docs/planned.md: planned workstreams and roadmap
- docs/goals.md: project goals and scope guardrails

## License
Apache-2.0 (see LICENSE)
