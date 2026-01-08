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

Flags and config precedence: defaults < config file < environment < CLI  
- Default search query: "query all resources" (MUST)
- Workers defaults: regions=6, enrich=24
- Output: creates a timestamped directory under `--outdir` (default `out/TS`) for run
- Boolean flags accept `--no-<flag>` to override config/env (e.g., `--no-parquet`, `--no-json-logs`)
- Limit discovery regions with `--regions` (comma-separated) or `OCI_INV_REGIONS`

## Output Contract
Each run writes to: `out/<timestamp>/`
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

## Docs
- docs/quickstart.md: minimal getting started
- docs/architecture.md: layout and design
- docs/auth.md: authentication options and safety

## License
Apache-2.0 (see LICENSE)
