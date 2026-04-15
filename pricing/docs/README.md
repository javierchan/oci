# Docs Guide

## Purpose

This directory contains the operating documentation for the `pricing` codebase.

The goal of this guide is to keep the docs set easy to navigate, low on overlap, and clear about which file is the source of truth for each decision type.

## Recommended Reading Order

1. [Architecture](/Users/javierchan/Documents/GitHub/oci/pricing/docs/ARCHITECTURE.md)
2. [Execution Plan](/Users/javierchan/Documents/GitHub/oci/pricing/docs/EXECUTION_PLAN.md)
3. [Coverage Roadmap](/Users/javierchan/Documents/GitHub/oci/pricing/docs/COVERAGE_ROADMAP.md)
4. [Improvement Milestones](/Users/javierchan/Documents/GitHub/oci/pricing/docs/IMPROVEMENT_MILESTONES.md)
5. [Assistant Branch Inventory](/Users/javierchan/Documents/GitHub/oci/pricing/docs/ASSISTANT_BRANCH_INVENTORY.md)
6. [Sub-Agent Strategy](/Users/javierchan/Documents/GitHub/oci/pricing/docs/SUBAGENT_STRATEGY.md)
7. [Parallel Execution Lanes](/Users/javierchan/Documents/GitHub/oci/pricing/docs/PARALLEL_EXECUTION_LANES.md)
8. [Quality Regression](/Users/javierchan/Documents/GitHub/oci/pricing/docs/QUALITY_REGRESSION.md)

## Source Of Truth Matrix

| Question | Primary document | Notes |
| --- | --- | --- |
| What system are we building and what contracts must remain stable? | [Architecture](/Users/javierchan/Documents/GitHub/oci/pricing/docs/ARCHITECTURE.md) | Architecture owns design intent, stable contracts, and system boundaries. |
| What should we do next, in what order, and how do we define completion? | [Execution Plan](/Users/javierchan/Documents/GitHub/oci/pricing/docs/EXECUTION_PLAN.md) | This is the tactical sequencing document. |
| What is already covered, validated, or still missing in runtime coverage? | [Coverage Roadmap](/Users/javierchan/Documents/GitHub/oci/pricing/docs/COVERAGE_ROADMAP.md) | Coverage state and validated baselines belong here. |
| What architectural problems were identified and how should they be fixed? | [Improvement Milestones](/Users/javierchan/Documents/GitHub/oci/pricing/docs/IMPROVEMENT_MILESTONES.md) | Source of truth for remediation milestones, rationale, and exit criteria. |
| How should we reduce remaining assistant-owned policy safely? | [Assistant Branch Inventory](/Users/javierchan/Documents/GitHub/oci/pricing/docs/ASSISTANT_BRANCH_INVENTORY.md) | This is the tracking artifact for the boundary-hardening stream. |
| When should sub-agents be used at all? | [Sub-Agent Strategy](/Users/javierchan/Documents/GitHub/oci/pricing/docs/SUBAGENT_STRATEGY.md) | This defines delegation policy and boundaries. |
| If sub-agents are used, how should parallel work be partitioned? | [Parallel Execution Lanes](/Users/javierchan/Documents/GitHub/oci/pricing/docs/PARALLEL_EXECUTION_LANES.md) | This defines concurrency topology, not product priorities. |
| How do we run and interpret the live assistant quality check? | [Quality Regression](/Users/javierchan/Documents/GitHub/oci/pricing/docs/QUALITY_REGRESSION.md) | This owns the fixed semantic-quality baseline. |

## Document Boundaries

- `ARCHITECTURE.md`
  - should explain the system and its stable contracts
  - should not become a running task tracker
- `EXECUTION_PLAN.md`
  - should define sequence, milestones, and exit criteria
  - should not become the sole long-term changelog for every completed slice
- `COVERAGE_ROADMAP.md`
  - should summarize validated coverage and remaining gaps
  - should not duplicate execution sequencing
- `IMPROVEMENT_MILESTONES.md`
  - should own the full set of architectural remediation milestones and their exit criteria
  - should not track active functional coverage work (that belongs in Coverage Roadmap and Execution Plan)
- `ASSISTANT_BRANCH_INVENTORY.md`
  - should track assistant-boundary work only
  - should not become a general refactor backlog
- `SUBAGENT_STRATEGY.md`
  - should define when delegation is appropriate
  - should not define active work priorities
- `PARALLEL_EXECUTION_LANES.md`
  - should define safe ownership lanes and validation boundaries
  - should not replace the execution plan
- `QUALITY_REGRESSION.md`
  - should define the live semantic-quality regression and how to read it
  - should not duplicate parity or deterministic test coverage tracking

## Update Rules

- update docs only for work that has been validated or explicitly approved as strategy
- keep sequencing changes in [Execution Plan](/Users/javierchan/Documents/GitHub/oci/pricing/docs/EXECUTION_PLAN.md)
- keep validated runtime coverage changes in [Coverage Roadmap](/Users/javierchan/Documents/GitHub/oci/pricing/docs/COVERAGE_ROADMAP.md)
- keep architectural boundary changes in [Architecture](/Users/javierchan/Documents/GitHub/oci/pricing/docs/ARCHITECTURE.md)
- if a topic starts appearing in multiple files, prefer one owner file and convert the others into short references

## Quality Standard

This docs set should behave like senior engineering documentation:

- concise enough to navigate during execution
- detailed enough to make decisions without guesswork
- explicit about ownership and authority
- difficult to misread under delivery pressure
