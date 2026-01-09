# AGENTS.md

Senior-level guidance for AI Agents working in this repository. This file defines
best practices, safety boundaries, execution discipline, research practices, and
operational policies. Task-specific solution instructions must live in the agent prompt.

---

# Scope & Boundaries

- Operate only inside `inventory/`.
- Do not read, modify, or reference files outside this directory.
- New files MAY be created only when:
  - The prompt explicitly requests it, AND
  - The file resides under `inventory/`, AND
  - It follows naming conventions (snake_case for Python), AND
  - It is referenced by existing modules or tests.
- Do not modify build, CI/CD, infrastructure, or external repository areas unless asked.

---

# Session Language Rule

- User instructions: **Spanish (Mexico)**.
- All agent outputs, actions, code, docs: **English (US)**.

---

# Senior Engineering Practices

- Favor minimal, well-scoped changes that solve the prompt directly.
- Preserve existing behavior unless explicitly instructed otherwise.
- Keep changes deterministic and reproducible.
- Be explicit about assumptions and unknowns.
- Avoid speculative changes; anchor decisions in evidence.
- Follow established patterns in `src/oci_inventory/**` where applicable.
- Respect module boundaries and avoid cross-layer leaks.
- Prefer pure/immutable transformations when feasible.
- Produce code and docs that humans can read without AI assistance.
- Explicitly avoid “clever” solutions; clarity first.

---

# Safety & Security

- Never log or introduce credentials or secrets.
- Do not add or modify files that expose sensitive data.
- If a command requires network access, request explicit approval.
- Do not manipulate private keys, tokens, or auth configs.
- Avoid writing logs containing OCIDs, user info, or tenancy details unless redacted.

---

# OCI Safety Guardrails

This codebase is for **inventory/discovery only**.

Allowed (read-only):
- `list`, `search`, `get` SDK/CLI/API calls.

Forbidden (mutating):
- `create`, `update`, `delete`, `patch`, `move`,
- `enable/disable`, `attach/detach`,
- or any action that changes OCI resource state or policies.

**Rationale:** Inventory is read-only by design.

---

# Quality Standards

- Maintain clear module boundaries and cohesive responsibilities.
- Keep naming consistent with snake_case for Python modules.
- Add comments only where code is not self-explanatory.
- Prefer stable ordering for outputs, hashing, and diffs.
- Avoid unnecessary abstraction layers.
- Use existing project patterns for graph, export, enrichment, diff logic.

---

# Testing Discipline

- Add tests for any behavior change or bug fix.
- Tests must be offline, deterministic, and fast.
- Avoid network calls, real OCI access, or external dependencies.
- Run smallest relevant subset of tests; expand only if needed.

---

# Evidence & Reporting

When making claims or decisions:

- Cite file paths and line numbers.
- Document command outcomes and errors verbatim.
- If verification is not possible, mark `NOT VERIFIED` and explain.
- Use factual observations over assumptions.

---

# Change Hygiene

- Avoid touching unrelated files.
- Do not reformat or refactor unrelated areas.
- Keep diffs small, focused, logically grouped.
- Separate refactors from functional changes.
- Always re-use the existing `.venv` located at:
  `/Users/javierchan/Documents/GitHub/oci/inventory/.venv`
- Only update the venv if strictly necessary.

---

# Dependencies & Tooling Discipline

- Do not introduce new dependencies unless explicitly requested.
- Justify any required dependency (purpose, maturity, footprint).
- Prefer Python standard library and existing deps first.
- Follow existing lint/format/type tooling without modification.
- Do not reformat entire files unless requested.
- Maintain existing import ordering and spacing.

---

# Version Awareness & Compatibility

- Acknowledge OCI SDK, Python, and dependency versions.
- If decisions depend on versions, mention them.
- Do not upgrade dependencies unless asked.
- Do not change Python version unless asked.

---

# Determinism & Reproducibility

- Avoid non-deterministic ordering, timestamps, random values.
- Avoid floating behavior from concurrency.
- Do not introduce non-deterministic tests.
- Use stable hashing and sorting for inventory/diff/export flows.

---

# Shell & Execution Safety

To avoid breaking the integrated terminal in VSCode or other execution environments, agents must follow these rules:

1. **Do Not Use Inline Here-Docs for Python or Shell Execution**
   - Forbidden patterns: `python - <<EOF`, `cat <<EOF`, or similar constructs.
   - These can break the terminal if the here-doc is not closed properly or if the shell does not support the syntax.

2. **Preferred Execution Methods**
   Agents must choose one of the following instead:
   - Create a temporary script file and execute it.
   - Create a script within `inventory/` when explicitly requested.
   - Use `python <file.py>` or `bash <file.sh>` directly.

3. **Command Construction Rules**
   - Do not chain multiple commands with `&&` if it risks leaving the terminal in an inconsistent state.
   - Avoid commands that alter the shell state or environment unintentionally (e.g., `source` without context).
   - When activation of a virtual environment is required, prefer:
     ```
     source /Users/javierchan/Documents/GitHub/oci/inventory/.venv/bin/activate
     ```
     and do not create new virtual environments.

4. **Terminal Stability**
   - Commands must not leave the terminal waiting for additional input.
   - Commands must not rely on multi-line paste behavior.
   - Commands must not change the user's shell or configuration.

5. **If Execution Is Uncertain**
   - Do not execute.
   - Ask for clarification or output the script to be reviewed manually.

---

# State & Context Management

- Carry forward relevant decisions and assumptions within a task.
- Reconstruct context from:
  - Current prompt
  - Codebase
  - Tests
  - Documentation
  - Provided history (if any)
- Do not assume historical memory if not present.

---

# External Research & Strategy Enhancement

If the problem cannot be solved with local context:

1. **Consult Reputable Sources**
   - OCI official docs, Python docs, SDK docs, RFCs, durable OSS docs.

2. **Synthesize, Don’t Copy**
   - Do not paste verbatim.
   - Extract insight and rewrite in project’s style.

3. **Align With This Codebase**
   - Validate that solutions:
     - Fit architecture,
     - Respect read-only OCI model,
     - Match conventions and tooling,
     - Do not add unnecessary frameworks.

4. **Document the Enhancement**
   Include:
   - Insight gained,
   - Source type (e.g. “OCI official docs”),
   - How it was adapted safely.

5. **Handle Unsolvable Cases**
   - Mark as `BLOCKED`,
   - List attempts,
   - State what is missing,
   - Suggest next steps if useful.

---

# Collaboration Expectations

- Ask for clarification when risky, ambiguous, or incomplete.
- Summarize planned changes before executing.
- Summarize final changes and next steps clearly.

---

# Interaction Loop (Required)

1. Restate the task with assumptions.
2. Plan minimal change steps (1–4 steps).
3. Ask clarifying questions if unsafe or under-specified.
4. Execute changes.
5. Verify with evidence (tests, inspection).
6. Report results with:
   - Changed files
   - Evidence
   - Remaining uncertainties

---

# Non-Goals / Failure Modes

Agents MUST NOT:

- Introduce architectural refactors unless requested.
- Suggest future improvements unless prompted.
- Change frameworks/tools without instruction.
- Create parallel utilities (e.g. `utils2.py`) without justification.
- Expand scope beyond the prompt.
- Produce non-deterministic output without justification.

---

## Docs
- docs/quickstart.md: minimal getting started
- docs/architecture.md: layout and design
- docs/auth.md: authentication options and safety
  +
+## Diagram Guidelines (Required)
  +For any diagram creation or diagram-related task, use:
  +`inventory/project/architecture_references/diagram_guidelines.md`
  +- Treat it as the source of truth for layout, abstraction level, and component grouping.
  +- If there is any conflict between a request and the guidelines, follow the guidelines and call out the
  mismatch.

---

# End of AGENTS.md
