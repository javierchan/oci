# OCI Inventory Planned Work

## Executive Summary (Planned)
- Expand inventory analysis to include OCI best practices (CAF) and CIS health checks.
- Improve enrichment coverage with relationships for network security controls and workloads.
- Extend `report/report.md` with As-Is/To-Be and design-decision sections aligned to diagram/report guidelines.
- Add skills artifacts (pptx) and OCI SDK usage guidance.

## Planned Workstreams (Future Functionality)

### Inventory analysis vs OCI best practices (CAF)
- Goal: compare inventory outputs against OCI CAF or documented best practices.
- Inputs: inventory JSONL, graph artifacts, and report data.
- Outputs: report section with findings, gaps, and prioritized recommendations.
- Constraints: read-only, deterministic, offline tests.
- Owner: TBD.
- Milestones: M1 define CAF criteria mapping; M2 implement evaluation logic; M3 add report output and tests.
- Acceptance criteria: report section is present and deterministic; findings trace to inventory/graph evidence; no OCI mutations.

### CIS health check integration
- Goal: integrate CIS health check scripts using existing auth context and targets from `oci-inv`.
- Inputs: run config (tenancy, regions, compartments) and resolved auth context.
- Outputs: stored CIS artifacts plus a report summary of pass/fail results.
- Constraints: reuse the existing `.venv`; avoid new dependencies unless approved; enforce read-only access.
- Reference: https://github.com/oracle-devrel/technology-engineering/blob/main/security/security-design/shared-assets/oci-security-health-check-standard/files/oci-security-health-check-standard/README.md
- Owner: TBD.
- Milestones: M1 define wrapper interface and artifact locations; M2 integrate execution with `oci-inv` config; M3 add report summary and tests.
- Acceptance criteria: CIS outputs are captured and summarized deterministically; integration uses existing auth/targets; offline tests validate parsing.
