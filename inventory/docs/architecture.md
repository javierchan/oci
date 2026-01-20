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
   - Known gaps (SDK 2.164.2 lacks `get_*` APIs): LimitsIncreaseRequest, ProcessAutomationInstance, QueryServiceProject.
   - The top-level `searchSummary` field is removed from the final record before export.
   - When present, `searchSummary` is preserved under `details` for auditability and backfills.
6. Exports:
   - JSONL: canonicalized, stable key order, sorted by `(ocid, resourceType)`.
   - CSV: report fields only.
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
9. Cost reporting (optional):
   - Usage API summaries in the tenancy home region with deterministic aggregation.
   - Writes `cost/cost_report.md` and cost usage exports when enabled.

## Output Artifacts (out/<timestamp>/)

Each `run` writes a deterministic set of artifacts. Fields below are the stable schema contract consumed by reports and diagrams.
Canonical field requirements and definitions live in `src/oci_inventory/normalize/schema.py`.

- `inventory/inventory.jsonl`
  - One JSON object per resource record.
  - Required fields: `ocid`, `resourceType`, `region`, `collectedAt`, `enrichStatus`, `details`, `relationships`.
  - Common fields: `displayName`, `compartmentId`, `lifecycleState`, `timeCreated`, `definedTags`, `freeformTags`, `enrichError`.
  - `relationships` is a list of `{source_ocid, relation_type, target_ocid}` sorted by `(source_ocid, relation_type, target_ocid)`.
  - `collectedAt` is a run-level UTC timestamp applied consistently to all records.

- `inventory/inventory.csv`
  - Report fields only (see `CSV_REPORT_FIELDS` in `src/oci_inventory/normalize/schema.py`).

- `cost/cost_report.md`
  - Optional cost and usage assessment report when cost reporting is enabled.
  - Must follow `docs/cost_guidelines.md`.
- `cost/cost_usage_items.csv`
  - Optional Usage API rows with full fields for validation/export (group_by, time window, service/region/compartment).
- `cost/cost_usage_items.jsonl`
  - Optional full Usage API items for auditability.
- `cost/cost_usage_items_grouped.csv`
  - Optional combined group_by export when `--cost-group-by` is set.
- `cost/cost_usage_service.csv`, `cost/cost_usage_region.csv`, `cost/cost_usage_compartment.csv`
  - Optional per-view exports derived from Usage API groupings for stable FinOps reporting.

- `inventory/relationships.jsonl`
  - Derived + enricher relationships (graph edges), one per line.
  - Required fields: `source_ocid`, `relation_type`, `target_ocid`.

- `run_summary.json`
  - Coverage metrics for the run.
  - Required fields: `schema_version`, `total_discovered`, `enriched_ok`, `not_implemented`, `errors`,
    `counts_by_resource_type`, `counts_by_enrich_status`, `counts_by_resource_type_and_status`.

- `graph/graph_nodes.jsonl` (optional; generated when diagrams are enabled)
  - Node projection of inventory records.
  - Required fields: `nodeId`, `nodeType`, `nodeCategory`, `name`, `region`, `compartmentId`,
    `metadata`, `tags`, `enrichStatus`, `enrichError`.

- `graph/graph_edges.jsonl` (optional; generated when diagrams are enabled)
  - Graph edges (relationships) with node typing hints.
  - Required fields: `source_ocid`, `target_ocid`, `relation_type`, `source_type`, `target_type`, `region`.

  - Raw Mermaid graph export (full graph, intended for debugging).

- `diagrams/tenancy/diagram.tenancy.mmd`, `diagrams/network/diagram.network.*.mmd`, `diagrams/workload/diagram.workload.*.mmd`, `diagrams/workload/diagram.workload.*.partNN.mmd`, `diagrams/consolidated/diagram.consolidated.architecture.mmd`, `diagrams/consolidated/diagram.consolidated.flowchart.mmd`, `diagrams/consolidated/diagram.consolidated.*.{region|compartment}.*.mmd` (optional; generated when diagrams are enabled)
  - Mermaid projections derived from `graph_nodes.jsonl` and `graph_edges.jsonl`.
  - `diagrams/consolidated/diagram.consolidated.architecture.mmd` uses Mermaid `architecture-beta` syntax for the high-level architecture view.
- Consolidated diagrams honor `--diagram-depth` (1=global regions only, 2=regional abstraction with aggregated network-attached workloads, 3=full workloads + edges).
  - Consolidated diagrams auto-reduce depth when Mermaid limits are exceeded; if still oversized at depth 1, they are split by region (preferred) or top-level compartment and the base diagram becomes a stub that references the split outputs.
  - Workload diagrams are full-detail for the workload scope; oversized diagrams are split into deterministic overflow parts, and single-node slices that still exceed Mermaid limits are skipped and summarized in the report.
  - Per-VCN diagrams remain full-detail; oversized per-VCN diagrams are skipped and summarized in the report.

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
- Cost Usage API queries can run in parallel when `--workers-cost` is set (opt-in).
- Cost export writes can run in parallel when `--workers-export` is set (opt-in).
- Enrichment results are chunked to disk before final exports to reduce peak memory usage.
- OCI SDK default retry strategy is enabled for clients.
- Local helpers provide safe concurrency patterns.

## Extensibility (Future Phases)

- Additional service-specific enrichers:
  - Register new enrichers with `register_enricher(resourceType, factory)`.
  - Enrichers return `details` and `relationships` (graph edges).
- Filtering and include/exclude semantics can be added at discovery time.
- Additional exports (e.g., graph formats) can be layered atop `relationships`.
- Expanded coverage metrics and run metadata provenance.

## Diagram Reference Guidelines

The repository includes reference architecture diagrams and a distilled set of layout guidelines in
`docs/diagram_guidelines.md`.
- This is the required source of truth for any diagram creation or diagram-related task.
- If a request conflicts with these guidelines, follow the guidelines and call out the mismatch.
