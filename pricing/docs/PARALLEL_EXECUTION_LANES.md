# Parallel Execution Lanes

## Purpose

Define a safe parallel execution model for the current `pricing` stage.

This document is deliberately conservative.

Its job is not to maximize raw throughput.
Its job is to let us move faster without degrading:

- deterministic pricing correctness
- assistant response consistency
- regression signal quality
- integration safety

## Current Recommendation

Use `3 execution lanes` with up to `4 sub-agents` plus one primary integrator as the operating model for the current stage.

That does not mean arbitrary writers on any file.
It means a small number of bounded lanes with explicit ownership, collision control, and centralized integration.

Current hard limits:

- only `1` writer may own [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js) at a time
- only `1` writer may own [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js) at a time
- only `1` writer may own shared plan and registry-alignment docs at a time

## Why This Is The Right Number Now

The codebase is healthier than before, but it still has a few shared-pressure points:

- [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js) is still the orchestration hotspot
- [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js) remains the center of declarative family policy
- assistant regression coverage now spans multiple focused suites, so the old monolithic sink has been retired
- [EXECUTION_PLAN.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/EXECUTION_PLAN.md) and [COVERAGE_ROADMAP.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/COVERAGE_ROADMAP.md) are live shared docs
- generated registry artifacts converge through [build_coverage_artifacts.js](/Users/javierchan/Documents/GitHub/oci/pricing/tools/build_coverage_artifacts.js)

Because of that, `10` concurrent writers would create more merge friction than real velocity, while fully serial execution leaves throughput on the table.

## Lane Model

### Lane 1. Follow-Up And Regression Slices

Goal:

- land bounded follow-up and regression slices with the fastest safe validation loop

Primary ownership:

- focused assistant and follow-up regression suites under [pricing/server/test/](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/)
- [assistant-test-helpers.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-test-helpers.js)
- workbook and RVTools-oriented follow-up slices that do not require orchestration redesign

Allowed scope:

- mirror regressions
- small bundle-expansion regressions
- workbook and RVTools persistence slices
- test-only closures for already-understood behavior

Should avoid:

- inventing new runtime policy
- simultaneous edits in other hotspot lanes

Minimum validation:

- relevant focused suite files
- `node --test pricing/server/test/assistant-followup-*.test.js`

### Lane 2. Metadata, Parity, And Registry Alignment

Goal:

- harden declarative behavior and deterministic coverage without competing with the regression hotspot

Primary ownership:

- [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js)
- [service-families.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/service-families.test.js)
- [rule-registry.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/rule-registry.test.js)
- [calculator-parity.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/calculator-parity.test.js)
- [build_coverage_artifacts.js](/Users/javierchan/Documents/GitHub/oci/pricing/tools/build_coverage_artifacts.js)

Allowed scope:

- family capability extensions
- parity additions
- registry artifact generation
- metadata-driven hardening for already-understood runtime behavior

Should avoid:

- broad `assistant.js` orchestration work
- docs narration not tied to validated behavior

Minimum validation:

- `node --test pricing/server/test/service-families.test.js`
- `node --test pricing/server/test/rule-registry.test.js`
- `node --test pricing/server/test/calculator-parity.test.js`

### Lane 3. Docs, Exploration, And Next-Slice Prep

Goal:

- keep project truth aligned while preparing the next low-risk slice in parallel

Primary ownership:

- [EXECUTION_PLAN.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/EXECUTION_PLAN.md)
- [COVERAGE_ROADMAP.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/COVERAGE_ROADMAP.md)
- [SUBAGENT_STRATEGY.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/SUBAGENT_STRATEGY.md)
- [PARALLEL_EXECUTION_LANES.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/PARALLEL_EXECUTION_LANES.md)

Allowed scope:

- gap discovery
- bounded codebase exploration
- roadmap updates after validated work
- operational-strategy documentation
- next-slice candidate preparation

Should avoid:

- editing production modules
- documenting unvalidated behavior as complete

Minimum validation:

- verify referenced files, commands, and artifacts exist

## Hotspot Rules

The following files are single-owner hotspots for now:

- [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js)
- [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js)
- [EXECUTION_PLAN.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/EXECUTION_PLAN.md)
- [COVERAGE_ROADMAP.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/COVERAGE_ROADMAP.md)

If a slice needs one of those files, it must declare ownership before work begins.

## Practical Assignment Pattern

Recommended distribution for a normal execution wave:

1. Primary owner: architecture, integration, hotspot ownership, final validation
2. Regression worker: targeted follow-up or workbook/RVTools slice
3. Metadata/parity worker: family metadata, parity, or registry slice
4. Explorer worker: bounded gap discovery and next-slice preparation
5. Docs worker: plan, roadmap, and operating-strategy alignment after validation

This keeps the highest-risk files under explicit control while still giving us real concurrency, but without pretending every worker needs to be active on every wave.

## When Not To Parallelize

Do not parallelize a slice when:

- the behavior is still being designed
- the slice depends immediately on a result from another lane
- more than one worker would need to edit the same hotspot file
- the validation surface is too cross-cutting to isolate cleanly

In those cases, the main owner should execute locally and keep the critical path short.

## Readiness For Higher Parallelism

We should not move to `10` concurrent writers yet.

Prerequisites for that step:

- keep new regression additions routed into the existing focused suites instead of rebuilding a monolithic assistant test file
- reduce remaining policy concentration in [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js)
- reduce metadata convergence pressure in [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js)
- separate shared docs ownership from registry-generation ownership
- prove that the `3-lane` model with up to `4` sub-agents increases throughput without increasing regression churn

## Success Signal

This model is working if:

- slices land faster with fewer merge conflicts
- targeted tests become easier to run and interpret
- `assistant.js` continues shrinking safely
- declarative metadata grows without destabilizing runtime behavior
- docs remain aligned without becoming a bottleneck
