# Cost Guidelines (Required)

This document defines how OCI account cost and usage data must be collected and reported for inventory runs, aligned to the FinOps Assessment Guide.

## Scope

- Applies to cost/usage reporting artifacts produced by the inventory pipeline (for example, `out/<timestamp>/cost_report.md`).
- Read-only by design; no OCI resource state changes.
- Deterministic, reproducible output.
- FinOps assessment alignment applies when reports claim maturity or capability scoring.

## Core Principles

- Evidence-only: rely on SDK responses; no estimates or speculation.
- Read-only: use list/get/request endpoints only.
- Redaction: no raw OCIDs in the main body.
- Determinism: stable sorting, fixed caps, explicit time ranges.
- Assessment alignment: scope, lenses, and scores must be explicit and evidence-backed.

## Evidence Sources

- FinOps Assessment Guide: https://www.finops.org/wg/finops-assessment/
- OCI Python SDK API Reference (oci 2.164.2): https://docs.oracle.com/en-us/iaas/tools/python/latest/api/landing.html
- Usage API module: https://docs.oracle.com/en-us/iaas/tools/python/latest/api/usage_api.html
- UsageapiClient methods: https://docs.oracle.com/en-us/iaas/tools/python/latest/api/usage_api/client/oci.usage_api.UsageapiClient.html
- Osub Usage module: https://docs.oracle.com/en-us/iaas/tools/python/latest/api/osub_usage.html
- Budget module: https://docs.oracle.com/en-us/iaas/tools/python/latest/api/budget.html
- BudgetClient methods: https://docs.oracle.com/en-us/iaas/tools/python/latest/api/budget/client/oci.budget.BudgetClient.html
- Usage module: https://docs.oracle.com/en-us/iaas/tools/python/latest/api/usage.html

## FinOps Assessment Alignment (Required)

### Intent and Scope

- The assessment is a continuous practice, not a one-time grade.
- Define a target group (team, business unit, or org) and target scope (domains and capabilities).
- Keep scope intentionally narrow so results are repeatable and actionable.

### Lenses and Scoring

Assess each selected capability using five lenses:

- Knowledge: awareness and understanding of the capability across the target group.
- Process: documented and repeatable workflows that deliver the capability.
- Metrics: measurable outcomes and KPIs with defined cadence.
- Adoption: how widely the capability is used in BAU behavior.
- Automation: degree to which repeatable tasks are automated.

Scoring expectations:

- Use a 0-4 scale per lens (0 = none, 4 = fully established).
- Optional lens weighting is allowed; document the weights explicitly.
- The maximum unweighted capability score is 20 (five lenses x four points).
- Target scores are required for each assessed capability and must be stated.

### Assessment Stages (Required)

1. Introduction: define target group, target scope, lens weighting, and target scores.
2. Measure: gather evidence (including cost data) and discovery inputs for each lens.
3. Outcome: report scores and summarize maturity per capability.
4. Focus: highlight the most impactful gaps and next actions.

### Capability Targeting Guidance

When cost reporting is the primary focus, commonly assessed capabilities include:

- Allocation
- Reporting and Analytics
- Data Ingestion
- Rate Optimization
- Workload Optimization
- FinOps Education and Enablement
- Forecasting
- Budgeting
- Invoicing and Chargeback
- Unit Economics

If a capability is not assessed, mark it as "(not assessed)" and explain why.

## SDK Capabilities (Cost-Related)

### Usage API (Primary Cost Source)

- `oci.usage_api.UsageapiClient` supports usage and cost queries via `request_summarized_usages` and configuration discovery via `request_summarized_configurations`.
- `request_summarized_usages` supports grouping by dimensions; use it to build totals by service, compartment, region, and SKU when needed.
- Usage API queries MUST run in the tenancy home region (no fallback to non-home regions).
- Carbon and clean-energy endpoints exist (`request_average_carbon_emission`, `request_clean_energy_usage`, `request_usage_carbon_emissions`) but are optional and must be explicitly requested.

### Subscription Usage (Optional)

- `oci.osub_usage.ComputedUsageClient` exposes subscription usage computations for OneSubscription data.
- Supply the subscription ID via CLI or config to enable OneSubscription usage collection; otherwise mark it as skipped.
- Use list/get methods only: `list_computed_usage_aggregateds`, `list_computed_usages`, or `get_computed_usage`.

### Budgets & Alerts (Read-only)

- `oci.budget.BudgetClient` supports budgets and alert rules.
- Allowed read-only calls: `list_budgets`, `get_budget`, `list_alert_rules`, `get_alert_rule`.

### Usage Limits / Rewards (Optional)

- `oci.usage.UsagelimitsClient` exposes usage limits and Oracle Support Rewards; do not treat this as cost data.

## Read-Only Guardrails (Mandatory)

- Forbidden operations include any `create_*`, `update_*`, `delete_*`, `patch_*`, or `move_*` calls in cost-related services.
- Specifically forbidden in Usage API: create/update/delete queries, schedules, custom tables, and email recipients groups.
- Specifically forbidden in Budget API: create/update/delete budgets or alert rules.
- If the SDK call mutates state, do not use it in this repository.

## Version Awareness & Compatibility

- This guidance aligns with the OCI Python SDK API Reference version 2.164.2.
- The repository requires `oci>=2.131.0`; validate method availability against the installed SDK version.

## Required Report Structure (Order)

1. `# OCI Cost Snapshot Report`
2. Intro paragraph stating this is a point-in-time snapshot focused on visibility/allocation and not a FinOps platform replacement.
3. `## Executive Summary`
4. `## Data Sources & Methodology`
5. `## Snapshot Overview` (table with Status/Total cost/Currency/Time range/Services/Compartments/Regions).
6. `## Cost Allocation Snapshots`
7. `### Cost by Service`
8. `### Cost by Compartment`
9. `### Cost by Region`
10. `## Consumption Insights (Descriptive Only)`
11. `## Coverage & Data Gaps`
12. `## Intended Audience & Usage Guidelines`
13. `## Suggested Next Steps (Optional)`

## Data Requirements

- Time range MUST be explicit start/end in UTC (ISO 8601).
- Currency code MUST be explicit (ISO 4217) and consistent across tables.
- If a requested currency differs from the Usage API currency, report the mismatch and keep amounts in the API currency unless a deterministic conversion is applied.
- Use tenancy-wide scope; do not omit compartments without stating the gap.
- Grouping dimensions MUST be explicit in the report (service, compartment, region, SKU if used).
- Narrative sections MUST be generated via OCI GenAI using structured context (time range, currency, totals, counts, and top contributors).
- Numeric values MUST be computed deterministically by the pipeline and never generated by GenAI.
- Snapshot Overview status MUST be one of `OK`, `WARNING`, or `ERROR`:
  - `OK` when all core cost/usage datasets are present.
  - `WARNING` when core cost data is present but optional datasets are missing.
  - `ERROR` when core cost/usage data is missing or unusable.

## Formatting Rules

- Use Markdown headings exactly as listed above.
- Use Markdown tables for summaries and breakdowns.
- Monetary values MUST be numeric with fixed 2-decimal formatting.
- Truncation MUST be explicit (for example, "Top 10; remaining aggregated as Other").
- Narrative content MUST be descriptive only (no optimization, forecasting, or recommendations beyond generic next steps).

## Redaction Rules

- No raw OCIDs in the main body.
- Use compartment aliases in the main body when grouping by compartment ID.

## Determinism Rules

- Sort by cost descending, then by name (ASCII, case-insensitive).
- Apply fixed caps: top 10 services, top 20 compartments, top 20 regions, unless the report is smaller.
- Use stable rounding and document the rounding in Execution Metadata.
- For assessment tables, sort by domain then capability (ASCII, case-insensitive).

## Error Handling

- If Usage API queries fail or return partial data, state the gap in `Coverage & Data Gaps`.
- If optional datasets (for example, OSUB usage or budgets) fail, record the omission in `Coverage & Data Gaps`.
- If assessment inputs are missing, mark the affected sections "(not assessed)" and record the gap.

## Change Control

- If report structure or section names change, update:
  - `docs/cost_guidelines.md`
  - `docs/architecture.md` (Output Artifacts section)
  - `AGENTS.md`
