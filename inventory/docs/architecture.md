# Architecture

This document explains the Phase 1 architecture of the OCI Inventory CLI. The design is modular and extensible, with clear layers for discovery, enrichment, normalization, export, and diffing.

High-level goals:
- Tenancy-wide discovery via Resource Search (Structured Search).
- Enrichment layer that is pluggable per resource type and safe by default (DefaultEnricher).
- Deterministic, reproducible outputs (stable field ordering, stable hashing).
- Performance controls with parallelism and retries.
- Clean CLI with auth validation and helper commands.

## Package Layout

```
src/oci_inventory/
  auth/
    providers.py         # auth resolution (auto/config/instance/resource/security_token)
  oci/
    clients.py           # thin wrappers for OCI SDK clients + region subscriptions
    regions.py           # list subscribed regions
    compartments.py      # list compartments (root + subtree)
    discovery.py         # Structured Search per region with pagination
  enrich/
    base.py              # Enricher protocol and EnrichResult
    default.py           # DefaultEnricher: NOT_IMPLEMENTED, safe and non-throwing
    __init__.py          # global registry (resourceType -> Enricher factory)
  normalize/
    schema.py            # canonical types and CSV/report fields
    transform.py         # normalization from search summary + canonicalization helpers
  export/
    jsonl.py             # JSONL export with stable ordering
    csv.py               # CSV export for report fields
    parquet.py           # optional Parquet export via pyarrow
  diff/
    hash.py              # stable hashing (excluding collectedAt)
    diff.py              # basic diff computation and writers
  util/
    concurrency.py       # small helpers for parallel execution
    pagination.py        # generic page-token loop
    time.py              # UTC ISO helpers
    errors.py            # error taxonomy + exit codes
  config.py              # config model + CLI args/env/config merge
  logging.py             # std + optional JSON logs
  cli.py                 # entrypoint implementing commands
```

## Data Flow (run)

1. CLI parses config (defaults < config file < env < CLI).
2. Authentication is resolved:
   - auto: Resource Principals -> Instance Principals -> Config file.
   - explicit method supported via `--auth`.
3. Regions are discovered via Identity `list_region_subscriptions`.
4. Discovery per region (ThreadPool):
   - Structured Search default query: `query all resources`
   - Pagination via `opc-next-page`.
   - Each summary is normalized (canonical schema) and the region is injected.
   - The raw summary is stored transiently under `searchSummary` for enrichment.
5. Enrichment (ThreadPool):
   - Registry selects an enricher by `resourceType`.
   - DefaultEnricher returns:
     - enrichStatus: `NOT_IMPLEMENTED`
     - details: `{"searchSummary": ...}`
     - relationships: `[]`
     - never raises
   - The `searchSummary` field is removed from the final record before export.
6. Exports:
   - JSONL: canonicalized, stable key order, sorted by `(ocid, resourceType)`.
   - CSV: report fields only.
   - Parquet: optional (requires `pyarrow`) with canonical field order.
7. Coverage Metrics:
   - total_discovered
   - enriched_ok
   - not_implemented
   - errors
   - counts_by_resource_type
   - counts_by_enrich_status
   - Written to `run_summary.json`
8. Diff (optional):
   - If `--prev` is provided, compute a diff between previous JSONL and current JSONL.
   - Hash excludes `collectedAt`, enabling meaningful changes detection.
   - Writes `diff.json` and `diff_summary.json`.

## CLI Commands

- `run`: executes the pipeline, writes outputs under timestamped `out/TS/`.
- `diff`: compares two inventories (prev/curr) and writes diff artifacts in `--outdir`.
- `validate-auth`: resolves auth and attempts a regions listing (no secrets printed).
- `list-regions`: prints subscribed regions (one per line).
- `list-compartments`: prints `ocid,name` for root + subtree.

## Auth

The `auth.providers` module unifies SDK client creation:
- `resolve_auth`: computes an `AuthContext` (config dict or signer).
- `make_client`: creates clients with retry strategy and correct region settings.
- Supports:
  - Config-file auth with `--profile`.
  - Instance Principals.
  - Resource Principals.
  - Security token profile (treated as config-file auth).
- Tenancy OCID is inferred from config when possible or provided via `--tenancy`.

Secrets are never printed. The docs include operational guidance.

## Determinism and Stability

- JSONL lines are deterministic:
  - Stable key ordering (canonicalization).
  - Stable line ordering (sorted by `(ocid, resourceType)`).
- Hashing excludes `collectedAt` and uses sorted JSON for reproducibility.
- Regions and compartment lists are sorted.
- Pagination handled consistently.

## Concurrency and Reliability

- Region discovery and per-region search are parallelized with configurable workers.
- Enrichment runs with a separate worker pool (`--workers-enrich`).
- OCI SDK default retry strategy is enabled for clients.
- Local helpers provide safe concurrency patterns.

## Extensibility (Future Phases)

- Additional service-specific enrichers:
  - Register new enrichers with `register_enricher(resourceType, factory)`.
  - Enrichers return `details` and `relationships` (graph edges).
- Filtering and include/exclude semantics can be added at discovery time.
- Additional exports (e.g., graph formats) can be layered atop `relationships`.
- Expanded coverage metrics and run metadata provenance.