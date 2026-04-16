# Collaboration Guide

## Purpose

Define how work should be delegated, partitioned, validated, and integrated in the `pricing` codebase.

This document consolidates the previous split between delegation policy and parallel execution topology so there is one owner file for:

- when to use sub-agents
- when not to use them
- safe lane ownership
- hotspot collision control
- integration and validation rules

Document role:

- this file is the source of truth for collaboration policy
- it does not define product sequencing
- active work order lives in [Execution Plan](/Users/javierchan/Documents/GitHub/oci/pricing/docs/planning/EXECUTION_PLAN.md)
- assistant-boundary tracking lives in [Assistant Branch Inventory](/Users/javierchan/Documents/GitHub/oci/pricing/docs/collaboration/ASSISTANT_BRANCH_INVENTORY.md)
- the full docs map lives in [Pricing Docs](/Users/javierchan/Documents/GitHub/oci/pricing/docs/README.md)

## Operating Principle

Use agents selectively and with explicit ownership.

The `pricing` project depends on:

- deterministic pricing correctness
- stable routing and follow-up semantics
- consistent metadata ownership
- trustworthy regression signal

Because of that, collaboration should optimize for safe throughput, not for maximum concurrent writers.

## Recommended Model

Use:

- one primary integrator
- up to `4` sub-agents when the work is truly parallelizable
- `3 execution lanes`
- single-writer protection on hotspot files

The primary integrator remains responsible for:

- architecture and boundary decisions
- hotspot ownership
- final integration
- final validation
- source-of-truth doc updates

## Good Uses For Sub-Agents

Sub-agents are recommended for:

- bounded helper extraction with a clear write scope
- focused tests for an already-designed behavior slice
- isolated metadata extensions for one service cluster
- documentation updates that reflect validated behavior
- bounded codebase exploration or gap classification

## Bad Uses For Sub-Agents

Sub-agents should not own:

- end-to-end redesign of routing semantics
- broad refactors across tightly coupled hotspot files
- final arbitration of deterministic versus model behavior
- policy changes whose integration plan is still evolving
- undocumented architecture changes

For this repository, the following should stay with the main integrator by default:

- `pricing/server/assistant.js` orchestration decisions
- `quotePlan` contract evolution
- follow-up routing semantics
- unsupported-scenario guardrails
- final behavior integration across helpers

## Lane Model

### Lane 1. Regression And Follow-Up Slices

Primary ownership:

- focused assistant and follow-up regression suites under [pricing/server/test/](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/)
- [assistant-test-helpers.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-test-helpers.js)

Use this lane for:

- mirror regressions
- workbook or RVTools regression slices
- bounded test-only hardening

Avoid:

- inventing runtime policy
- concurrent edits in hotspot production files

Minimum validation:

- relevant focused suites

### Lane 2. Metadata, Parity, And Deterministic Hardening

Primary ownership:

- [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js)
- [dependency-resolver.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/dependency-resolver.js)
- metadata/parity-oriented tests

Use this lane for:

- family capability extensions
- parity additions
- metadata-driven hardening
- deterministic resolver cleanup

Avoid:

- broad `assistant.js` orchestration redesign
- docs narration that is not tied to validated behavior

Minimum validation:

- relevant metadata and parity suites

### Lane 3. Docs, Exploration, And Closeout

Primary ownership:

- [Execution Plan](/Users/javierchan/Documents/GitHub/oci/pricing/docs/planning/EXECUTION_PLAN.md)
- [Coverage Roadmap](/Users/javierchan/Documents/GitHub/oci/pricing/docs/planning/COVERAGE_ROADMAP.md)
- [Improvement Milestones](/Users/javierchan/Documents/GitHub/oci/pricing/docs/planning/IMPROVEMENT_MILESTONES.md)
- [reports/](/Users/javierchan/Documents/GitHub/oci/pricing/docs/reports)

Use this lane for:

- roadmap updates after validation
- bounded exploration
- milestone closeout
- audit and closeout documentation

Avoid:

- editing production modules as part of the same slice
- documenting unvalidated behavior as complete

Minimum validation:

- verify referenced files, commands, and artifacts exist

## Hotspot Rules

The following are single-writer hotspots unless a slice explicitly transfers ownership:

- [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js)
- [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js)
- [dependency-resolver.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/dependency-resolver.js)
- [Execution Plan](/Users/javierchan/Documents/GitHub/oci/pricing/docs/planning/EXECUTION_PLAN.md)
- [Coverage Roadmap](/Users/javierchan/Documents/GitHub/oci/pricing/docs/planning/COVERAGE_ROADMAP.md)

If a slice needs one of these files, ownership should be explicit before work begins.

## Integration Workflow

1. The primary integrator selects a bounded slice.
2. The integrator decides whether the slice is safe for delegation.
3. If yes, only the isolated portion is delegated.
4. The primary integrator continues with non-overlapping work.
5. Returned changes are reviewed before merge.
6. Relevant validations are run by the integrator.
7. Source-of-truth docs are updated only after validation.

## Quality Guardrails

Any delegated work should follow these rules:

- no silent architecture changes
- no broad refactors outside the assigned slice
- no reverting unrelated user or agent work
- no documentation of unvalidated behavior as complete
- no merge without validation

For runtime changes, require at least one of:

- helper unit coverage
- focused regression coverage
- parity coverage when deterministic quote behavior changes materially

## Success Signal

The collaboration model is working if:

- slices land faster with fewer merge conflicts
- regression signal remains easy to interpret
- `assistant.js` and resolver hotspots shrink safely over time
- docs stay aligned without becoming another hotspot
- throughput rises without increased behavioral drift

## Consolidation Note

This guide replaces the previous split between `SUBAGENT_STRATEGY.md` and `PARALLEL_EXECUTION_LANES.md`.
