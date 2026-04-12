# Sub-Agent Strategy

## Purpose

Define how to use sub-agents in the `pricing` codebase to improve delivery speed without sacrificing deterministic behavior, regression safety, architectural consistency, or assistant response quality.

This document is intentionally operational. It is not a research note. Its goal is to help us decide:

- when sub-agents are useful
- when they are not appropriate
- what ownership boundaries they should have
- how their work should be integrated safely

## Recommendation

Use sub-agents selectively.

They are recommended for bounded, parallelizable work with clear ownership and low coupling. They are not recommended as the primary owner of core assistant behavior, routing policy, or cross-cutting architectural decisions.

For this codebase, the best model at the current stage is:

- one primary agent owns architecture, integration, and final verification
- up to `4` sub-agents handle bounded side work in parallel
- work is grouped into `3` execution lanes with explicit ownership
- the primary agent remains responsible for:
  - changes to core request flow
  - integration across helpers
  - regression selection
  - final acceptance criteria

## Why This Fits `pricing`

The `pricing` project is not just a CRUD or UI codebase. Quality depends on:

- deterministic pricing correctness
- consistency of quote routing
- guardrails for unsupported scenarios
- stable follow-up behavior across active quotes
- disciplined reduction of hardcoded logic in `assistant.js`

That means naive parallelism can create hidden damage:

- duplicated heuristics
- rule drift between helpers
- accidental changes to quote behavior
- regressions that only appear in mixed bundle scenarios

Sub-agents help only when we preserve strong boundaries.

## Good Uses For Sub-Agents

Sub-agents are recommended for:

- targeted helper extraction with a clearly assigned write scope
- focused test creation for a helper or family behavior already designed
- exploration of isolated code paths or coverage gaps
- documentation updates that reflect already-implemented behavior
- regression expansion for one bounded service area
- metadata or context-pack extensions with clear ownership

Examples that fit this project well:

- add regression coverage for one family or one bundle category
- extract a small helper from `assistant.js` after the integration design is already chosen
- update `EXECUTION_PLAN.md` and `COVERAGE_ROADMAP.md` after validated work
- expand family metadata in `service-families.js` for one isolated service cluster

## Bad Uses For Sub-Agents

Sub-agents should not own:

- end-to-end redesign of assistant routing
- simultaneous edits across multiple tightly coupled core modules without clear boundaries
- final arbitration of conflicting intent, quote, and discovery behavior
- policy decisions about deterministic versus GenAI responsibilities
- broad refactors where the integration plan is still evolving

For this codebase, the following should stay primarily with the main agent:

- `pricing/server/assistant.js` orchestration decisions
- `quotePlan` contract evolution
- follow-up routing semantics
- unsupported-service and unsupported-variant guardrails
- final integration of extracted helpers

## Operating Model

### Primary Agent Responsibilities

The primary agent remains the senior owner of the codebase slice in progress.

It is responsible for:

- selecting the next implementation slice
- defining the intended behavior before delegation
- assigning clear write ownership
- integrating sub-agent output
- running the final relevant validations
- updating project-level docs

### Sub-Agent Responsibilities

A sub-agent should receive a bounded task with:

- a clear objective
- explicit files it may change
- explicit files it should avoid
- expected validations
- a requirement to preserve existing behavior unless the task explicitly changes it

A sub-agent should not improvise architecture.

## Recommended Initial Sub-Agent Roles

These are the first roles that make sense for `pricing`.

### 1. `regression-worker`

Purpose:

- add or extend focused tests for a bounded behavior slice

Good ownership:

- `pricing/server/test/*.test.js`

Allowed supporting reads:

- helper module under test
- relevant pieces of `assistant.js`
- existing regression fixtures

Should avoid:

- broad behavior changes in production modules unless explicitly assigned

Example tasks:

- add tests for one new helper extracted from `assistant.js`
- expand coverage for one family follow-up behavior
- add parity cases for one mixed-service bundle category

### 2. `docs-roadmap-worker`

Purpose:

- keep execution and coverage documentation aligned with validated implementation

Good ownership:

- `pricing/docs/EXECUTION_PLAN.md`
- `pricing/docs/COVERAGE_ROADMAP.md`
- new docs under `pricing/docs/`

Should avoid:

- changing runtime code
- documenting unvalidated behavior as complete

Example tasks:

- record completed refactor slices
- document coverage additions and remaining gaps
- summarize scoring or validation criteria after tests land

### 3. `assistant-refactor-worker`

Purpose:

- extract one bounded helper from `assistant.js` after the integration design is already chosen

Good ownership:

- one new helper module
- one focused production file slice
- its dedicated test file

Should avoid:

- changing unrelated core orchestration paths
- redesigning route semantics on its own

Example tasks:

- extract one request-shaping helper
- extract one clarification helper
- extract one deterministic reply-shaping helper

### 4. `family-metadata-worker`

Purpose:

- move isolated family-specific behavior out of `assistant.js` and into declarative metadata

Good ownership:

- `pricing/server/service-families.js`
- family-specific tests
- possibly `context-packs.js` when explicitly assigned

Should avoid:

- changing generic quote orchestration
- changing unrelated families in the same pass

## Delegation Rules

Before using a sub-agent, the primary agent should decide:

1. Is the task parallelizable?
2. Does it have a bounded write scope?
3. Can it be validated independently?
4. Will the next main-agent step be blocked on it?

If the answer to 1 through 3 is yes, and 4 is no, delegation is usually beneficial.

If the next critical step depends on the result immediately, the main agent should usually keep the work local.

## Quality Guardrails

Any sub-agent work should follow these rules:

- no silent architectural changes
- no broad refactors outside the assigned slice
- no reverting unrelated user or agent work
- no merging without validation
- no documentation of behavior that has not been tested or verified

For runtime changes, the integration owner should require at least one of:

- helper unit tests
- focused assistant regressions
- parity coverage when quote behavior changes materially

## Integration Workflow

Recommended workflow for this project:

1. Primary agent selects a bounded slice.
2. Primary agent decides whether the slice is safe for delegation.
3. If yes, delegate the isolated portion only.
4. While the sub-agent works, the primary agent continues with non-overlapping work.
5. Primary agent reviews the returned changes.
6. Primary agent runs relevant validations.
7. Primary agent updates `EXECUTION_PLAN.md` and `COVERAGE_ROADMAP.md`.

## Practical Starting Policy

For the current `pricing` roadmap, we should use this policy:

- use sub-agents for tests, docs, and isolated helper extraction
- do not use sub-agents as the owner of full `assistant.js` orchestration refactors
- keep final behavior decisions centralized
- keep hotspot files under single-writer protection
- scale usage only after we see that velocity improves without regression churn

## Current Operating Envelope

For the current stage, the recommended operating mode is:

- one primary integrator plus up to `4` sub-agents
- organized into `3` execution lanes
- with explicit lane ownership
- with single-writer protection on the main hotspots

The intended `3-lane` shape is:

- `Lane A`: bounded follow-up and regression slices
- `Lane B`: metadata, parity, and registry-alignment slices
- `Lane C`: docs, gap exploration, and next-slice preparation

The operational lane map lives in:

- [PARALLEL_EXECUTION_LANES.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/PARALLEL_EXECUTION_LANES.md)

That document should be treated as the practical execution companion to this strategy note.

## Success Criteria

Sub-agent usage is working well if:

- validated slices land faster
- regression quality improves
- `assistant.js` keeps shrinking safely
- documentation stays current with less overhead
- we do not see more behavioral drift or integration rework

If sub-agent usage increases churn, conflicting edits, or regression noise, we should reduce delegation scope immediately.
