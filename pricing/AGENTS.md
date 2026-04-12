# AGENTS.md

## Scope

These instructions apply only to the `pricing` codebase at `/Users/javierchan/Documents/GitHub/oci/pricing`.

## Operating Mode

Work in this codebase in continuous autonomous mode.

Execute the plan sequentially, end-to-end, with senior developer judgment, prioritizing stability, coverage, declarative refactoring, and operational success of the project.

## Working Rules

- Do not stop to ask for user interaction unless it is strictly necessary.
- Continue from one logical step to the next without pausing when the next step can be resolved safely from local context.
- After each meaningful change:
  1. analyze the relevant context,
  2. implement,
  3. validate with tests,
  4. fix issues if something fails,
  5. update documentation or execution tracking if needed,
  6. continue with the next useful step.
- If a non-critical blocker appears, document it and continue with the next productive front.
- If validation fails because of sandbox, loopback, network, or environment restrictions, report it as an environment blocker and keep progressing where meaningful work is still possible.
- Do not stop at planning if implementation is possible.
- Make design and strategy decisions with senior-level ownership unless a decision is materially risky or irreversible.

## Continuous Execution Rule

- Do not stop after reporting progress if there is still a clear next implementation step available.
- After completing one validated work block, immediately begin the next logical block in the plan unless:
  1. user interaction is strictly required,
  2. permissions are required,
  3. there is a destructive-risk decision,
  4. or there is a materially ambiguous architecture choice.
- Status updates are progress checkpoints, not stopping points.

## Default Behavior

- Assume that `continue` remains in effect across the session.
- Do not wait for renewed user confirmation between consecutive implementation blocks.

## Priority Order

1. Maintain and expand deterministic coverage.
2. Reduce hardcoded logic in `pricing/server/assistant.js`.
3. Move behavior into metadata, `service-families`, and `context-packs`.
4. Strengthen reusable follow-up behavior by family.
5. Expand calculator parity and workbook/RVTools coverage.
6. Improve operational hardening without slowing functional delivery.

## Stop And Ask Only If

- There is risk of data loss or destructive impact.
- Credentials, approvals, or out-of-sandbox permissions are required.
- A product or architecture decision has strong tradeoffs and is not easily reversible.
- There is real ambiguity with multiple valid paths that have materially different consequences.

## Project-Specific Expectations

- Keep `pricing/docs/EXECUTION_PLAN.md` aligned with the real implementation state.
- Use `pricing/docs/COVERAGE_ROADMAP.md` as the primary roadmap reference.
- Use `pricing/docs/SUBAGENT_STRATEGY.md` when deciding whether work should stay with the main agent or be delegated into bounded parallel slices.
- Do not revert user changes that were not made by the agent.
- Prefer declarative and reusable solutions over prompt-specific patches.
- Treat deterministic behavior, regression safety, and parity confidence as first-class concerns.
- Report progress briefly and concretely, focused on outcomes and blockers.

## Sub-Agent Delegation Policy

- Use sub-agents only when the task has a bounded write scope, independent validation, and low architectural coupling.
- Keep architecture, orchestration, and final integration ownership with the primary agent.
- Prefer sub-agents for:
  1. focused tests,
  2. docs alignment,
  3. isolated helper extraction,
  4. family metadata extensions with clear ownership.
- Avoid delegating broad `assistant.js` behavior redesign unless the write scope and intended behavior are already fully defined.
- Always validate delegated work before considering the slice complete.

## Validation Notes

- Prefer targeted tests while iterating, then run broader validation before closing a work block.
- Known sandbox-only failures such as loopback-restricted endpoint tests should be reported clearly as environmental, not as functional regressions.
