```md
# AGENTS.md

Senior-level guidance for AI Agents working in this repository. This file defines
best practices, safety boundaries, and execution discipline. Task-specific solution
instructions must live in the agent prompt.

---

# Scope & Boundaries

- Operate only inside `inventory/`.
- Do not read, modify, or reference files outside this directory.
- New files MAY be created only when:
  - The prompt explicitly requests it, AND
  - The file resides under `inventory/`, AND
  - It follows naming conventions (snake_case for Python), AND
  - It is referenced by existing modules or tests.

---

# Session Language Rule

- User instructions: **Spanish (Mexico)**.
- All agent outputs, actions, code, and documentation: **English (US)**.

---

# Senior Engineering Practices

- Favor minimal, well-scoped changes that solve the prompt directly.
- Preserve existing behavior unless explicitly instructed otherwise.
- Keep changes deterministic and reproducible.
- Be explicit about assumptions and unknowns.
- Avoid speculative changes; anchor decisions in evidence.
- Follow established patterns in `src/oci_inventory/**` where applicable.
- Respect module boundaries and avoid leaking responsibilities across layers.
- Minimize mutation; prefer pure/immutable transformations where reasonable.

---

# Safety & Security

- Never log or introduce secrets or credentials.
- Do not add or modify files that could expose sensitive data.
- If a command requires network access, request explicit approval.
- Do not generate content that manipulates private keys, tokens, or auth configs.

---

# OCI Safety Guardrails

This codebase is for **inventory/discovery only**.

Allowed (read-only):
- `list`, `search`, `get` operations via SDK/CLI/API.

Forbidden (mutating):
- `create`, `update`, `delete`, `patch`, `move`,
- `enable/disable`, `attach/detach`,
- or any action that changes OCI resource state or policies.

**Rationale:** Inventory is read-only by design.

---

# Quality Standards

- Maintain clear module boundaries and cohesive responsibilities.
- Keep naming consistent with existing conventions (snake_case for Python modules).
- Add comments only when code is not self-explanatory.
- Prefer stable ordering for outputs, hashing, and diffs.
- Avoid unnecessary abstraction layers; keep architecture practical.

---

# Testing Discipline

- Add tests for any behavior change or bug fix.
- Keep tests offline, deterministic, and fast.
- Run the smallest relevant subset of tests; expand only if necessary.
- Avoid external dependencies in tests (network, OCI, real services).

---

# Evidence & Reporting

When asserting or justifying decisions:

- Cite file paths and line numbers.
- Document command outcomes and failures with exact error messages.
- If verification is not possible, mark as `NOT VERIFIED` and explain why.
- Prefer factual evidence over assumptions.

---

# Change Hygiene

- Avoid touching unrelated files.
- Do not refactor or reformat unrelated code.
- Keep diffs small, focused, and logically grouped.
- Separate refactors from functional changes.
- Always re-use the existing `.venv` located at:
  `/Users/javierchan/Documents/GitHub/oci/inventory/.venv`
  Update this only if actually required.

---

# Collaboration Expectations

- If the prompt is ambiguous, ask for clarification before proceeding.
- Summarize planned changes before executing them.
- Summarize final changes and next steps clearly and concisely.
- Avoid proposing future work unless explicitly requested.

---

# Interaction Loop (Required)

Agents must follow this loop for every task:

1. **Restate the task** in English (US) including assumptions.
2. **Plan** the minimal set of changes (1–4 steps).
3. **Ask clarifying questions** *only if the task cannot be executed safely*.
4. **Execute changes** according to plan.
5. **Verify** behavior via evidence (tests, file inspection, errors).
6. **Report results** with:
   - Changed files
   - Observations and evidence
   - Any remaining uncertainties

---

# Non-Goals / Failure Modes

Agents must NOT:

- Introduce architectural refactors unless explicitly requested.
- Convert frameworks/tools “just because”.
- Suggest future enhancements not requested.
- Create parallel utilities (e.g. `utils2.py`) unless justified.
- Expand scope beyond the user prompt.
- Produce non-deterministic output without strong reasoning.

---

# End of AGENTS.md
```
