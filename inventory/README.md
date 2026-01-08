# OCI Inventory (Phase 1)
Production-ready Python CLI to inventory Oracle Cloud Infrastructure (OCI) resources using Resource Search, with an enrichment framework, deterministic exports, and diffs.

Phase 1 implements:
- Tenancy-wide discovery using Resource Search (Structured Search) with default query: "query all resources"
- Enricher registry + DefaultEnricher with per-service metadata enrichers for selected resource types
- Exports: JSONL (default) and CSV; Parquet optional via pyarrow
- Diffs and stable hashing (excluding collectedAt)
- Coverage metrics
- Tests, docs, CI (ruff + pytest)

Repository scope for this package is strictly local under this directory.

## Install
- Python 3.11+
- Recommended in a virtualenv

```
pip install -U pip
pip install .
# Optional Parquet support
pip install .[parquet]
```

## Preflight setup
Use the preflight script to prepare a local or CI environment (macOS/Linux, no sudo required). It:
- Verifies prerequisites (python3 ≥ 3.11, pip, git; oci CLI is optional and opt-in)
- Creates or reuses a .venv virtual environment and upgrades pip/setuptools/wheel
- Installs the project in editable mode, respecting pyproject.toml
- Supports optional extras via INVENTORY_EXTRAS (e.g., parquet)
- Uses network access for pip upgrades and dependency installs (and OCI CLI if enabled)

Run:
```
./preflight.sh
```

With extras:
```
INVENTORY_EXTRAS=parquet ./preflight.sh
INVENTORY_EXTRAS=parquet,dev ./preflight.sh
```

Install OCI CLI (opt-in):
```
OCI_INV_INSTALL_OCI_CLI=1 ./preflight.sh
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

## CLI
Entrypoint: `oci-inv`

Commands:
- Run inventory:
  ```
  oci-inv run --outdir out --auth auto --profile DEFAULT --parquet --prev out/20240101T000000Z/inventory.jsonl \
              --workers-region 6 --workers-enrich 24 --include-terminated \
              --query "query all resources"
  ```
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

JSONL + CSV are always written. Parquet is optional and recommended for analytics.

```
oci-inv run --auth auto --profile DEFAULT --outdir out --parquet --query "query all resources"
```

### Notes

- `--regions` limits execution to a comma-separated list (e.g., `--regions mx-queretaro-1,us-phoenix-1`).
- For consistent diffs, compare `inventory.jsonl` files. The stable hash excludes `collectedAt` by design.
- Queries are OCI Resource Search Structured Search strings. Keep the default query exactly `query all resources` unless you intentionally scope it.

Flags and config precedence: defaults < config file < environment < CLI  
- Default search query: "query all resources" (MUST)
- Workers defaults: regions=6, enrich=24
- Output: creates a timestamped directory under `--outdir` (default `out/TS`) for run
- Boolean flags accept `--no-<flag>` to override config/env (e.g., `--no-parquet`, `--no-json-logs`)
- Limit discovery regions with `--regions` (comma-separated) or `OCI_INV_REGIONS`

## Output Contract
Each run writes to: `out/<timestamp>/`
- report.md (execution steps, exclusions, and findings)
- inventory.jsonl (canonicalized, stable JSON lines)
- inventory.csv (report fields)
- inventory.parquet (optional; pyarrow required)
- relationships.jsonl (optional; when relationships exist)
- graph_nodes.jsonl (diagram-ready nodes)
- graph_edges.jsonl (diagram-ready edges)
- diagram.mmd (Mermaid diagram)
- diff.json + diff_summary.json (when --prev provided)
- run_summary.json (coverage metrics)

JSONL stability notes:
- Keys sorted; deterministic line ordering by ocid then resourceType
- Hash excludes `collectedAt` to enable meaningful diffs

## Enrichment
Enrichers use **read-only** OCI SDK calls to fetch full metadata for supported resource types.
Metadata is stored under `details.metadata` as the SDK `to_dict()` output, with sensitive fields
redacted by key substring (e.g., private_key, passphrase, password, secret, token, ssh, content).
For resource types without a registered enricher, DefaultEnricher returns `NOT_IMPLEMENTED` and
stores the raw search summary under `details.searchSummary`.

Supported resource types (initial set):
- Compute: Instance, Image, BootVolume, BlockVolume, InstanceConfiguration, InstancePool
- Networking: Vcn, Subnet, Vnic, NetworkSecurityGroup, SecurityList, RouteTable, InternetGateway, NatGateway, ServiceGateway, DhcpOptions
- Security: Bastion, Vault, Secret, CloudGuardTarget

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

## Environment Variables
- OCI_INV_QUERY
- OCI_INV_OUTDIR
- OCI_INV_PREV
- OCI_INV_CURR
- OCI_INV_PARQUET
- OCI_INV_INCLUDE_TERMINATED
- OCI_INV_JSON_LOGS
- OCI_INV_LOG_LEVEL (INFO, DEBUG, ...)
- OCI_INV_WORKERS_REGION
- OCI_INV_WORKERS_ENRICH
- OCI_INV_REGIONS
- OCI_INV_AUTH
- OCI_INV_PROFILE
- OCI_TENANCY_OCID

## Logging
- Std logging, INFO by default
- Structured JSON logs toggled with `--json-logs` or `OCI_INV_JSON_LOGS=1`

## Development
- Linting: ruff
- Tests: pytest
- Build backend: hatchling

Run locally:
```
pip install -e .[parquet]
pip install ruff pytest
ruff check .
pytest
```

## Interactive Wizard (Optional)

If you prefer a guided, copy/paste-friendly UX (with command previews and safer defaults), install the optional wizard extra and run:

```
pip install .[wizard]
oci-inv-wizard
```

The wizard does not replace `oci-inv`; it generates and executes the same underlying commands and writes the same outputs.

## GenAI Configuration (Future)

This repository is public. Do not commit tenant-specific configuration, OCIDs, or any credentials.

For local development, keep real GenAI values in a user-owned config file outside the repo, for example:

```
~/.config/oci-inv/genai.yaml
```

This repo provides a git-ignored local file under `inventory/.local/genai.yaml` that you can copy to your home directory:

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
log_level: INFO
json_logs: false
outdir: out
regions: [mx-queretaro-1]
query: "query all resources"
parquet: false
workers_region: 6
workers_enrich: 24
YAML

oci-inv-wizard --from wizard-run.yaml --dry-run
oci-inv-wizard --from wizard-run.yaml --yes
```

## Docs
- docs/quickstart.md: minimal getting started
- docs/architecture.md: layout and design
- docs/auth.md: authentication options and safety

## License
Apache-2.0 (see LICENSE)
