# OCI Inventory Planned Work

## 4.1 Executive Summary (Planned)
- Expand inventory analysis to include OCI best practices (CAF) and CIS health checks.
- Improve enrichment coverage with relationships for network security controls and workloads.
- Extend `report.md` with As-Is/To-Be and design-decision sections aligned to diagram/report guidelines.
- Add skills artifacts (pptx) and OCI SDK usage guidance.

## 4.2 Planned Workstreams (Future Functionality)

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

### Enrichment expansion for firewall and network controls
- Goal: enrich firewall, NSG, security list, and ACL data with explicit relationships to workloads.
- Inputs: SDK get/list per resource type and normalized inventory records.
- Outputs: `details.metadata` and relationship edges for graph/reporting.
- Constraints: deterministic ordering; no mutations; follow existing enrichment patterns.
- Owner: TBD.
- Milestones: M1 identify resource types and relationship rules; M2 implement enrichers and relationships; M3 add tests and coverage updates.
- Acceptance criteria: relationships are emitted and deterministically ordered; graph/report reflect associations; enrichers remain read-only.

### As-Is and To-Be section leveraging diagrams
- Goal: add an As-Is/To-Be section in `report.md` that uses diagram outputs to explain current and proposed architecture.
- Phase 1: text-only As-Is and To-Be summary.
- Phase 2: diagram proposals using GenAI and validated architectures guided by `at_guidelines.md` (future).
- Constraints: follow `docs/diagram_guidelines.md` and `docs/report_guidelines.md`; redact sensitive data.
- Owner: TBD.
- Milestones: M1 define section schema and wording rules; M2 render text-only output; M3 design diagram proposal inputs.
- Acceptance criteria: report includes As-Is/To-Be sections in required order; content is deterministic and redacted; phase 1 stays text-only.

### Design-decision inputs
- Goal: incorporate meeting inputs that justify architectural choices.
- Inputs: structured decision data (format TBD).
- Outputs: `report.md` section summarizing decisions and rationale linked to workloads/diagrams.
- Constraints: deterministic ordering; avoid sensitive identifiers in the body.
- Owner: TBD.
- Milestones: M1 define input schema and storage location; M2 implement parsing and report section; M3 add tests and redaction checks.
- Acceptance criteria: report includes decisions sorted deterministically; missing inputs are surfaced in Risks & Gaps; no sensitive identifiers appear in body.

### Skills in repo (pptx)
- Goal: add skills artifacts (pptx) to support presentations and enablement.
- Constraints: add files only when referenced by existing modules or tests; keep naming consistent.
- Owner: TBD.
- Milestones: M1 define artifact locations and naming; M2 add referenced pptx files; M3 document usage.
- Acceptance criteria: pptx files are referenced by docs/tests; no new dependencies introduced; repository rules are followed.

### OCI SDK usage documentation
- Goal: document OCI Python SDK usage patterns relevant to discovery/enrichment.
- Constraints: align with current dependency versions; no upgrades unless requested.
- Reference: https://docs.oracle.com/en-us/iaas/tools/python/latest/api/landing.html
- Owner: TBD.
- Milestones: M1 capture current SDK usage patterns; M2 draft documentation; M3 review for version alignment.
- Acceptance criteria: documentation reflects current SDK usage and versions; no dependency changes required.

## 4.3 Dependencies and Constraints (Global)
- Read-only OCI posture; no create/update/delete/attach/detach actions.
- Deterministic outputs and ordering; offline, fast tests.
- Redaction requirements for reports and GenAI outputs.
- No new dependencies without explicit approval; reuse the existing `.venv`.

## 4.4 Risks and Open Questions
- Definition and scope of "OCI best practices/CAF" and its data sources.
- Mapping rules for firewall/NSG/ACL associations to workloads.
- Input format and storage for design-decision data.
- CIS scripts may assume live access; testing must remain offline and deterministic.

## 4.5 Suggested Sequencing (High Level)
1) Expand enrichment types and relationships for network controls and workloads.
2) Define best-practices criteria and CIS integration outputs.
3) Add `report.md` sections for As-Is/To-Be and design decisions.
4) Document SDK usage and add skills artifacts once referenced.

---

register a OCI Icons to use in diagrams located on: /Users/javierchan/Documents/GitHub/oci/inventory/resources/icons or https://static.oracle.com/cdn/fnd/gallery/2604.0.2/images/preview/index.html using the mermaid methodology: https://mermaid.js.org/config/icons.html or as suggested by mermaid: https://icones.js.org/

MLX Support Addition to use LLM's in macOS to use when GenAI is not available, maybe ollama can be used to support multiplatform (tener un config file para esto).

Queue Manager, que pasa si hay varias sesiones consumiendo este codebase, mnecesitamos tener un queue manager que ejecute los jobs de manera efectiva

 