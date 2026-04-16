# Pricing Docs

## Purpose

This directory is the operating documentation set for the `pricing` codebase.

It is organized by decision type, not by creation date. The goal is to make it obvious:

- where architecture lives
- where active execution state lives
- where validation evidence lives
- where agent/collaboration guidance lives
- where API contracts and audit artifacts live

This structure is intentionally optimized for repository navigation and agent execution:

- the top-level `README.md` is the entrypoint
- subdirectories group related documents by ownership
- each major document names its source-of-truth role
- collaboration guidance is consolidated instead of split across overlapping files

## Directory Layout

| Path | Purpose | Primary audience |
| --- | --- | --- |
| [`core/`](./core) | Stable system design, contracts, and boundaries | Engineers, reviewers, agents |
| [`planning/`](./planning) | Active sequence, milestones, and validated coverage state | Engineers, delivery owners, agents |
| [`operations/`](./operations) | Operational validation and regression runbooks | Engineers, operators |
| [`collaboration/`](./collaboration) | Agent execution policy, hotspot ownership, and assistant-boundary inventory | Agents, maintainers |
| [`contracts/`](./contracts) | Machine-readable API contract artifacts | Server engineers, integrators |
| [`prompts/`](./prompts) | Reusable prompt/operator instructions | Agents, maintainers |
| [`reports/`](./reports) | Generated audit and assessment outputs | Reviewers, maintainers |

## Recommended Reading Paths

### For system understanding

1. [Architecture](./core/ARCHITECTURE.md)
2. [Execution Plan](./planning/EXECUTION_PLAN.md)
3. [Coverage Roadmap](./planning/COVERAGE_ROADMAP.md)
4. [Improvement Milestones](./planning/IMPROVEMENT_MILESTONES.md)

### For active implementation work

1. [Execution Plan](./planning/EXECUTION_PLAN.md)
2. [Improvement Milestones](./planning/IMPROVEMENT_MILESTONES.md)
3. [Coverage Roadmap](./planning/COVERAGE_ROADMAP.md)
4. [Assistant Branch Inventory](./collaboration/ASSISTANT_BRANCH_INVENTORY.md) when the slice touches `assistant.js`

### For operational validation

1. [Quality Regression](./operations/QUALITY_REGRESSION.md)
2. [OpenAPI Contract](./contracts/openapi.yaml)
3. [reports/](./reports)

### For agent execution and ownership boundaries

1. [Collaboration Guide](./collaboration/COLLABORATION_GUIDE.md)
2. [Assistant Branch Inventory](./collaboration/ASSISTANT_BRANCH_INVENTORY.md)
3. [Execution Plan](./planning/EXECUTION_PLAN.md)

## Source Of Truth Matrix

| Question | Primary document | Notes |
| --- | --- | --- |
| What system are we building and what contracts must remain stable? | [Architecture](./core/ARCHITECTURE.md) | Owns design intent, stable contracts, and system boundaries. |
| What should we do next, in what order, and how do we define completion? | [Execution Plan](./planning/EXECUTION_PLAN.md) | Tactical sequencing document. |
| What architectural gaps exist and what does done mean for each one? | [Improvement Milestones](./planning/IMPROVEMENT_MILESTONES.md) | Remediation milestones and exit criteria. |
| What is already covered, validated, or still missing in runtime coverage? | [Coverage Roadmap](./planning/COVERAGE_ROADMAP.md) | Validation state and runtime coverage baseline. |
| How do we run and interpret the live semantic-quality check? | [Quality Regression](./operations/QUALITY_REGRESSION.md) | Quality baseline and interpretation guide. |
| How should agents collaborate, delegate, and avoid hotspot collisions? | [Collaboration Guide](./collaboration/COLLABORATION_GUIDE.md) | Consolidated delegation and parallel work policy. |
| How should we reduce remaining assistant-owned policy safely? | [Assistant Branch Inventory](./collaboration/ASSISTANT_BRANCH_INVENTORY.md) | Boundary-hardening tracking artifact for `assistant.js`. |
| What is the machine-readable server contract? | [OpenAPI Contract](./contracts/openapi.yaml) | Canonical API artifact. |
| Where do generated audits and point-in-time assessments live? | [reports/](./reports) | Generated artifacts, not living strategy docs. |

## Ownership Rules

- `core/` should explain stable behavior, not act as a changelog.
- `planning/` should capture sequence, scope, milestones, and validated coverage state.
- `operations/` should capture how to run checks and how to interpret results.
- `collaboration/` should capture agent policy, hotspot ownership, and bounded inventory artifacts.
- `contracts/` should hold machine-readable interfaces, not prose duplicates of those interfaces.
- `reports/` should contain dated outputs and should not silently override source-of-truth docs.

## Update Rules

- Update docs only for work that has been validated or explicitly approved as strategy.
- Keep architecture changes in [Architecture](./core/ARCHITECTURE.md).
- Keep execution state and sequencing changes in [Execution Plan](./planning/EXECUTION_PLAN.md).
- Keep remediation scope and exit criteria in [Improvement Milestones](./planning/IMPROVEMENT_MILESTONES.md).
- Keep runtime coverage evidence in [Coverage Roadmap](./planning/COVERAGE_ROADMAP.md).
- Keep operational runbooks in [operations/](./operations).
- Keep agent policy in [Collaboration Guide](./collaboration/COLLABORATION_GUIDE.md), not spread across multiple parallel docs.

## Quality Standard

This docs set should remain:

- easy to scan under delivery pressure
- explicit about ownership and authority
- low on overlap
- high on navigability
- safe for both humans and repository-aware coding agents
