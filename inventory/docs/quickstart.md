# Quickstart

This guide shows how to install and run the OCI Inventory CLI locally.

Prerequisites:
- Python 3.11+
- OCI Python SDK credentials available through one of:
  - Config file: ~/.oci/config with a profile (e.g., DEFAULT)
  - Instance Principals (when running on OCI compute)
  - Resource Principals (Functions, OKE)
  - Security token session profile

Do not hardcode or commit secrets.

## Install

Create a fresh virtual environment and install the package:

```
python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install .
```

Verify installation:

```
oci-inv --help
```

## Validate authentication

Test that the CLI can authenticate and access tenancy metadata:

```
# Config file auth:
oci-inv validate-auth --auth config --profile DEFAULT

# Auto mode (tries Resource Principals, then Instance Principals, then Config):
oci-inv validate-auth --auth auto --profile DEFAULT
```

Expected output:

```
OK: authentication validated; subscribed regions: <region1>, <region2>, ...
```

## Run an inventory collection

Run a full discovery with the default query ("query all resources"):

```
oci-inv run --auth auto --profile DEFAULT --outdir out
```

Optional flags:

- Use a custom search query:
  ```
  oci-inv run --query "query all resources where lifecycleState = 'ACTIVE'"
  ```
- Adjust concurrency:
  ```
  oci-inv run --workers-region 6 --workers-enrich 24
  ```
  Opt-in cost/export workers:
  ```
  oci-inv run --workers-cost 2 --workers-export 2
  ```
  You can also reuse `config/workers.yaml` with `--config config/workers.yaml`.
- Increase the OCI SDK HTTP connection pool size (reduces pool churn at higher concurrency):
  ```
  oci-inv run --client-connection-pool-size 25
  ```
- Disable diagram generation:
  ```
  oci-inv run --no-diagrams
  ```
- Limit diagram volume (large tenancies):
  ```
  oci-inv run --diagram-depth 2
  ```
  Per-VCN and workload diagrams are skipped automatically if they exceed Mermaid text limits (the skip is logged).
- Tune schema validation for large outputs:
  ```
  oci-inv run --validate-schema sampled --validate-schema-sample 2000
  ```
- Enable cost reporting (home region; read-only):
  ```
  oci-inv run --cost-report --cost-start 2026-01-01T00:00:00Z --cost-end 2026-01-31T00:00:00Z --cost-currency USD
  ```
  Default time range (if omitted) is month-to-date, normalized to 00:00:00 UTC.
- Cost report without diagrams:
  ```
  oci-inv run --no-diagrams --cost-report --cost-start 2026-01-01T00:00:00Z --cost-end 2026-01-31T00:00:00Z --cost-currency USD
  ```
- Cost report with OneSubscription usage:
  ```
  oci-inv run --cost-report --osub-subscription-id <subscription_id> --cost-start 2026-01-01T00:00:00Z --cost-end 2026-01-31T00:00:00Z --cost-currency USD
  ```
- Cost report grouped by compartment name or path:
  ```
  oci-inv run --cost-report --cost-compartment-group-by compartmentName --cost-start 2026-01-01T00:00:00Z --cost-end 2026-01-31T00:00:00Z --cost-currency USD
  ```
- Cost report with multi-dimension group_by for combined usage items:
  ```
  oci-inv run --cost-report --cost-group-by service,region,compartmentId --cost-start 2026-01-01T00:00:00Z --cost-end 2026-01-31T00:00:00Z --cost-currency USD
  ```

Output structure per run:

```
out/<timestamp>/
  inventory.jsonl
  inventory.csv
  cost_report.md           # when --cost-report
  cost_usage_items.csv     # when --cost-report; full Usage API rows
  cost_usage_items_grouped.csv # when --cost-group-by; grouped multi-dim rows
  cost_usage_items.jsonl   # when --cost-report; full Usage API items
  cost_usage_service.csv   # when --cost-report; service view
  cost_usage_region.csv    # when --cost-report; region view
  cost_usage_compartment.csv # when --cost-report; compartment view
  relationships.jsonl      # always written (may be empty)
  graph_nodes.jsonl        # diagram-ready nodes (optional)
  graph_edges.jsonl        # diagram-ready edges (optional)
  diagram_raw.mmd          # Mermaid diagram (raw graph; optional)
  diagram.tenancy.mmd      # Mermaid diagram (tenancy/compartment view; optional)
  diagram.network.<vcn>.mmd # Mermaid diagram (per-VCN topology view; optional)
  diagram.workload.<workload>.mmd # Mermaid diagram (workload/application view; optional)
  diagram.consolidated.architecture.mmd # Mermaid diagram (all projections consolidated; optional)
  diagram.consolidated.flowchart.mmd # Mermaid diagram (consolidated flowchart; optional)
  diff.json                # when --prev provided
  diff_summary.json        # when --prev provided
  run_summary.json         # coverage metrics
```

Notes:
- JSONL lines are stable and canonicalized (sorted keys).
- Hashes used for diff exclude `collectedAt` to minimize noise.

## Diff two inventories

Given two inventory JSONL files (prev and curr), produce a diff:

```
oci-inv diff --prev out/20240101T000000Z/inventory.jsonl \
             --curr out/20240102T000000Z/inventory.jsonl \
             --outdir out/diff_20240102
```

This writes diff.json and diff_summary.json under the specified outdir.

## Environment variables

Common environment variables that influence behavior:

- OCI_INV_QUERY
- OCI_INV_OUTDIR
- OCI_INV_PREV
- OCI_INV_CURR
- OCI_INV_INCLUDE_TERMINATED
- OCI_INV_JSON_LOGS
- OCI_INV_LOG_LEVEL
- OCI_INV_WORKERS_REGION
- OCI_INV_WORKERS_ENRICH
- OCI_INV_WORKERS_COST
- OCI_INV_WORKERS_EXPORT
- OCI_INV_CLIENT_CONNECTION_POOL_SIZE
- OCI_INV_REGIONS
- OCI_INV_AUTH
- OCI_INV_PROFILE
- OCI_TENANCY_OCID
- OCI_INV_GENAI_CONFIG
- OCI_INV_DIAGRAMS
- OCI_INV_VALIDATE_DIAGRAMS
- OCI_INV_SCHEMA_VALIDATION
- OCI_INV_SCHEMA_SAMPLE_RECORDS
- OCI_INV_DIAGRAM_DEPTH
- OCI_INV_GENAI_SUMMARY
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
- OCI_INV_DISABLE_CLIENT_CACHE

## Troubleshooting

- Ensure your ~/.oci/config has the correct profile and keys if using config-file auth.
- Avoid printing secrets in logs or terminal history.
- Increase log verbosity:
  ```
  OCI_INV_LOG_LEVEL=DEBUG oci-inv run ...
