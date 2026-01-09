# Report Guidelines (Required)

This document defines how `report.md` must be structured and written for OCI inventory runs.

## Scope

- Applies to `out/<timestamp>/report.md`.
- Output must be deterministic, readable, and evidence-based.

## Core Principles

- Architecture-first summary: focus on tenancy structure, network, workloads, data, and governance.
- Evidence-only: avoid speculation; use observed inventory signals.
- Redaction: avoid raw OCIDs in the main report body; use aliases.
- Deterministic ordering: stable sorting and consistent truncation.
- Fast scan: short paragraphs and concise tables.

## Required Sections (Order)

1. `# OCI Inventory Architectural Assessment`
2. Intro paragraph explaining scope and that the report ends with Execution Metadata.
3. `## At a Glance` (key metrics and counts).
4. `## Graph Artifacts (Summary)` (only when graph artifacts exist).
5. `## Executive Summary` (GenAI summary if available; otherwise a concise fallback).
6. `## Tenancy & Compartment Overview`
7. `## Network Architecture`
8. `## Workloads & Services`
9. `## Data & Storage`
10. `## IAM / Policies (Visible)`
11. `## Observability / Logging`
12. `## Risks & Gaps (Non-blocking)`
13. `### Coverage Notes` (inside Risks & Gaps).
14. `### Recommendations (Non-binding)` (inside Risks & Gaps).
15. `## Inventory Listing (Complete)`
16. `## Execution Metadata`
    - `### Steps Executed`
    - `### Run Configuration`
    - `### Regions`
    - `### Results`
    - `### Findings`
    - `### Notes`

## Formatting Rules

- Use Markdown headings exactly as listed above.
- Use Markdown tables for summaries and listings.
- Use short, consistent labels (do not exceed 1 line per label when possible).
- Truncate long lists and note truncation explicitly.

## Redaction Rules

- Do not print raw OCIDs in the main body.
- Use compartment aliases in the main body and include the alias map under Execution Metadata.
- OCIDs can appear in Execution Metadata when required (for example, tenancy OCID).

## Determinism Rules

- Sort tables and lists deterministically (by region, name, type, and compartment).
- Keep caps stable (for example: top 10 workloads, top 20 subnets, top 40 data/observability rows).
- Use consistent wording for missing data (for example: "(unknown)" or "(none)").

## Error Handling

- If GenAI summary fails, note it briefly and keep the details in Execution Metadata.
- If regions are excluded, state partial results in Risks & Gaps and list details in Execution Metadata.
- Report export warnings (parquet/diff) in Execution Metadata.

## Maintainer Notes

- The report title and section ordering must match this guidance exactly.
- The main body must avoid raw OCIDs; use compartment aliases and short IDs.
- Execution Metadata is the only place where raw OCIDs may appear when required.
- Tables and lists must be deterministic and capped to keep the report readable.
- GenAI summaries are optional and must be redacted; failures should not break report generation.

## Change Control

- If you change report structure or section names, update:
  - `docs/report_guidelines.md`
  - `docs/architecture.md` (Output Artifacts section)
