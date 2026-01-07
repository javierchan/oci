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
# Optional Parquet export support:
pip install .[parquet]
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

Run a full discovery with the default query (MUST be "query all resources"):

```
oci-inv run --auth auto --profile DEFAULT --outdir out
```

Optional flags:

- Enable Parquet export (requires pyarrow):
  ```
  oci-inv run --parquet
  ```
- Use a custom search query:
  ```
  oci-inv run --query "query all resources where lifecycleState = 'ACTIVE'"
  ```
- Adjust concurrency:
  ```
  oci-inv run --workers-region 6 --workers-enrich 24
  ```

Output structure per run:

```
out/<timestamp>/
  inventory.jsonl
  inventory.csv
  inventory.parquet        # when --parquet and pyarrow installed
  relationships.jsonl      # when relationships are emitted
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
- OCI_INV_PARQUET
- OCI_INV_INCLUDE_TERMINATED
- OCI_INV_JSON_LOGS
- OCI_INV_LOG_LEVEL
- OCI_INV_WORKERS_REGION
- OCI_INV_WORKERS_ENRICH
- OCI_INV_AUTH
- OCI_INV_PROFILE
- OCI_TENANCY_OCID

## Troubleshooting

- Ensure your ~/.oci/config has the correct profile and keys if using config-file auth.
- Avoid printing secrets in logs or terminal history.
- For Parquet errors, install pyarrow: `pip install .[parquet]`.
- Increase log verbosity:
  ```
  OCI_INV_LOG_LEVEL=DEBUG oci-inv run ...
