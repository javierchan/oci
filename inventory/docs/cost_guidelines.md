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
- Carbon and clean-energy endpoints exist (`request_average_carbon_emission`, `request_clean_energy_usage`, `request_usage_carbon_emissions`) but are optional and must be explicitly requested.

### Subscription Usage (Optional)

- `oci.osub_usage.ComputedUsageClient` exposes subscription usage computations for OneSubscription data.

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

1. `# OCI Cost & Usage Assessment`
2. Intro paragraph stating scope, time range, currency, and that the report ends with Execution Metadata.
3. `## At a Glance` (total cost, currency, time range, count of services/compartments/regions covered).
4. `## Assessment Scope & Intent`
5. `## Assessment Lenses & Scoring`
6. `## Assessment Outcomes`
7. `## Assessment Focus Areas`
8. `## Time Range & Currency`
9. `## Cost Summary (Tenancy Total)`
10. `## Cost by Service`
11. `## Cost by Compartment`
12. `## Cost by Region`
13. `## Credits, Discounts & Promotions` (if present; otherwise "(none)").
14. `## Budgets & Alerts (Read-only)` (if visible; otherwise "(none)").
15. `## Risks & Gaps (Non-blocking)`
16. `### Coverage Notes`
17. `### Recommendations (Non-binding)`
18. `## Execution Metadata`
    - `### Steps Executed`
    - `### Run Configuration`
    - `### Query Inputs`
    - `### Assessment Inputs`
    - `### Results`
    - `### Findings`
    - `### Notes`
    - `### Alias Map`

## Data Requirements

- Time range MUST be explicit start/end in UTC (ISO 8601).
- Currency code MUST be explicit (ISO 4217) and consistent across tables.
- Use tenancy-wide scope; do not omit compartments without stating the gap.
- Grouping dimensions MUST be explicit in the report (service, compartment, region, SKU if used).
- Assessment target group, target scope, and target scores MUST be explicit.
- Lens weights MUST be listed if used.
- Each capability score MUST reference supporting evidence (table, metric, or external artifact).

## Formatting Rules

- Use Markdown headings exactly as listed above.
- Use Markdown tables for summaries and breakdowns.
- Monetary values MUST be numeric with fixed 2-decimal formatting.
- Truncation MUST be explicit (for example, "Top 10; remaining aggregated as Other").
- Assessment tables MUST list capabilities by domain, then capability name.
- Lens order MUST be: Knowledge, Process, Metrics, Adoption, Automation.

## Redaction Rules

- No raw OCIDs in the main body.
- Use compartment aliases in the main body.
- Raw OCIDs MAY appear only in Execution Metadata (Alias Map or Query Inputs).

## Determinism Rules

- Sort by cost descending, then by name (ASCII, case-insensitive).
- Apply fixed caps: top 10 services, top 20 compartments, top 20 regions, unless the report is smaller.
- Use stable rounding and document the rounding in Execution Metadata.
- For assessment tables, sort by domain then capability (ASCII, case-insensitive).

## Error Handling

- If Usage API queries fail or return partial data, state the gap in `Risks & Gaps` and include error details in `Execution Metadata`.
- If some regions/compartments are excluded, list them explicitly in `Execution Metadata`.
- If assessment inputs are missing, mark the affected sections "(not assessed)" and record the gap.

## Change Control

- If report structure or section names change, update:
  - `docs/cost_guidelines.md`
  - `docs/architecture.md` (Output Artifacts section)
  - `AGENTS.md`
