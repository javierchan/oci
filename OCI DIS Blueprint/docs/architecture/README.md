# Architecture Documentation Portal

This directory is the governed entry point for understanding OCI DIS Blueprint.
It distinguishes executable behavior from approved plans so a reader does not
mistake a Docker-local capability for an OCI production capability.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| **Implemented** | Executable in the repository and covered by a relevant validation gate. |
| **Implemented locally** | Executable in the production-mode Docker Compose stack; not yet an OCI deployment claim. |
| **Planned** | Design is documented, but implementation or validation is still pending. |
| **Blocked** | A known prerequisite prevents a truthful production-readiness claim. |
| **Decision required** | Multiple valid options remain and an authorized owner must select one. |

## Recommended reading order

1. [Current-State Architecture](./current-state-architecture.md) — what the
   repository implements today, its runtime boundaries, data authority, trust
   model, and principal workflows.
2. [Design Decision Register](./design-decision-register.md) — why the major
   architectural choices were made and their consequences.
3. [OCI OKE Horizontal-Scale Deployment Plan](./oci-oke-horizontal-scale-deployment-plan.md)
   — the planned Queretaro topology, observability platform, prerequisites, and
   authorization gates.
4. [Current vs. Target Roadmap](./current-vs-target-roadmap.md) — the concise
   capability gap between the local runtime and the planned OCI platform.
5. [System Overview](./system-overview.md) — short operational summary and
   links into the specialized designs.

## Specialized designs

| Domain | Primary document | Status |
| --- | --- | --- |
| App knowledge and embeddings | [Governed App Knowledge Base](./app-knowledge-base.md) | Implemented locally; shared publication planned |
| Contextual assistant | [Contextual Support Assistant](./contextual-support-assistant.md) | Implemented locally |
| Governed agents | [OCI Agent Runtime](./oci-agent-runtime.md) | Implemented locally |
| OCI inference and Guardrails | [OCI Generative AI Integration](./oci-generative-ai.md) | Implemented; remote dependency |
| Import interpretation and correction | [Governed External Import Intake](./governed-external-import-intake.md) | Implemented locally |
| Technical demand propagation | [DIS Technical Demand Propagation](./dis-technical-demand-propagation.md) | Implemented locally |
| Pricing and BOM | [OCI Pricing and BOM Plan](./oci-pricing-bom-plan.md) | Implemented locally |
| Commercial governance | [Pricing Governance Workspace](./pricing-governance-workspace.md) | Implemented locally |
| Integration recommendation | [Integration Recommendation Workspace](./integration-recommendation-workspace.md) | Implemented locally |
| Offline capture | [Offline Capture Workbook v3](./offline-capture-workbook-v3.md) | Implemented locally |
| Pattern governance | [Pattern Certification Matrix](./pattern-certification-matrix.md) | Implemented locally |
| Synthetic reference data | [Admin Synthetic Lab](./admin-synthetic-lab.md) | Implemented locally |

## Architecture governance

- `AGENTS.md` is the implementation and milestone contract.
- `README.md` is the operator and contributor entry point.
- `docs/api/openapi.yaml` and `app/knowledge/derived_app_knowledge.json` are
  generated, drift-checked contracts.
- `docs/adr/` contains immutable decision records.
- `design-decision-register.md` exposes decisions that exist in code or plans
  but still need individual ADR coverage.
- Audit reports under `docs/reports/` are dated evidence, not evergreen
  architecture authority.

Historical milestone identifiers in `AGENTS.md` are immutable delivery records.
Some identifiers are duplicated or non-sequential. New work must not renumber
them silently; use a unique new identifier and reconcile the index in a
dedicated governance change.
