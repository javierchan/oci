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
- If a valid method already exists, reuse or adapt it before introducing a new approach.
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
- docs/cost_guidelines.md: cost report structure and FinOps assessment alignment
- docs/report_guidelines.md: report.md structure and content requirements
- docs/goals.md: detailed codebase report, risks, and maintainer guidance
- docs/planned.md: project planning notes

## Diagram Guidelines (Required)
For any diagram creation or diagram-related task, use:
`docs/diagram_guidelines.md`
- Treat it as the source of truth for layout, abstraction level, and component grouping.
- If there is any conflict between a request and the guidelines, follow the guidelines and call out the mismatch.

## Report Guidelines (Required)
For any report.md creation or report-related task, use:
`docs/report_guidelines.md`
- Treat it as the source of truth for structure, wording, and redaction rules.
- If there is any conflict between a request and the guidelines, follow the guidelines and call out the mismatch.

## Cost Guidelines (Required)
For any cost report creation or cost-related assessment task, use:
`docs/cost_guidelines.md`
- Treat it as the source of truth for structure, scoring, and redaction rules.
- If there is any conflict between a request and the guidelines, follow the guidelines and call out the mismatch.

---

# Diagram & Report Operating Contract (Required for Inventory Pipeline)

When working with report and diagram generation tasks, agents MUST follow this operating contract:

## Operating Modes

Agents operate in one or more of the following modes, depending on the prompt:

1. **Validate**
   - Compare current pipeline outputs (reports/diagrams) against `docs/diagram_guidelines.md` and `docs/report_guidelines.md`.
   - Detect violations of abstraction, data usage, readability, or formatting rules.
   - Surface violations clearly; do NOT silently ignore them.

2. **Render**
   - Generate reports and diagrams from inventory+graph sources.
   - Apply all abstraction rules and data-driven rendering rules.
   - Produce deterministic output (same input → same output).

3. **Refactor for Compliance**
   - When drift is detected, modify only the minimal code/templates necessary to restore compliance.
   - Do NOT change the guidelines unless explicitly requested.

4. **Request Guidelines Update**
   - If guidelines are incomplete or technically incompatible with reality, propose a change with evidence.
   - Wait for confirmation before updating `docs/diagram_guidelines.md` or `docs/report_guidelines.md`.

## Views / Artifacts (Minimum Set)

Inventory → Code → Report → Diagrams MUST support at least these views:

- **Tenancy View**: tenancy/region/compartment structure (no workloads)
- **Network View**: VCNs, subnets, gateways, DRG, edge services
- **Workload View(s)**: flows, relationships, assets, services
- **Consolidated View**: functional compartments + network + workloads

Failure to produce a required view is considered drift.

## Determinism Requirements

- Ordering MUST be deterministic:
  - Sort workloads alphabetically
  - Sort resources by type → name
  - Sort edges by source → target → type
- Rendering MUST NOT depend on:
  - Random values
  - Timestamps
  - Non-deterministic traversal order
  - Python `dict` iteration semantics

If ordering is ambiguous, agents MUST choose the lexicographically smallest option.

## Drift Detection Rules

The following conditions are considered drift and MUST trigger **Validate → Refactor**:

- Resources placed outside canonical OCI hierarchy
- In-VCN vs out-of-VCN violations
- Missing minimum labels (tenancy, compartments, VCNs, subnets, gateways)
- Missing required gateways when present in inventory
- Workloads without at least one meaningful flow
- Workloads present in inventory but missing in diagrams
- Diagram counts not matching report counts
- IAM/security constructs drawn as peer workloads
- Missing legend when overlays or icons exist
- Ignoring tags/metadata when relevant overlays are enabled

## Alignment Rules

- `docs/diagram_guidelines.md` defines **what** to draw and **how** to abstract.
- `docs/report_guidelines.md` defines **what** to write and **how** to structure.
- The **inventory model and graph** define **what exists in reality**.
- The report is authoritative for **workloads & counts**.
- The diagrams must visually reflect the report.

If conflicts appear:
1. Prefer **reality (inventory/graph)** over report/diagrams.
2. Prefer **report** over diagrams.
3. Prefer **guidelines** over aesthetics.

Agents MUST call out conflicts rather than silently deciding.

## No-Silence Rule

Agents MUST NOT silently:
- Omit workloads
- Drop relationships
- Collapse counts incorrectly
- Remove IAM/security overlays without justification
- Ignore anomalies in graph integrity

If information is missing or unclear, agents MUST surface the gap instead of guessing.

---

## Report Operating Contract (Required for Inventory Pipeline)

When generating or validating `report.md`, agents MUST apply the following rules:

### Required Structure
- Section ordering MUST match `docs/report_guidelines.md` exactly.
- All required sections MUST appear, even if empty or marked "(none)".
- `Execution Metadata` MUST appear at the end.

### Data Source Alignment
- Inventory/graph are authoritative for existence of regions, compartments, services, and workloads.
- Report is authoritative for workload identity, counts, and classifications.
- Diagrams MUST visually reflect the report; discrepancies are **drift**.

### Redaction Rules
- No raw OCIDs in the main body.
- Compartment aliases MUST be used in the body.
- Raw OCIDs MAY appear in `Execution Metadata` only.
- Agents MUST NOT bypass redaction.

### Determinism Requirements
- Tables and lists MUST be sorted deterministically (region → type → name → compartment).
- Caps (`top N`) MUST be applied consistently according to `report_guidelines.md`.
- Wording for missing data MUST be consistent.

### Drift Detection Rules (Report)
The following conditions are considered **report drift** and MUST trigger Validate → Refactor:

- Missing required sections or incorrect ordering.
- Missing Execution Metadata or alias map.
- Raw OCIDs present in main body.
- Workloads present in inventory but missing in report.
- Region/compartment mismatches between report and inventory.
- Counts in report not reconcilable with inventory.
- Determinism violations (non-sorted tables, inconsistent truncation).
- Graph artifacts exist but `Graph Artifacts (Summary)` section is missing.

### No-Silence Rule (Report)
Agents MUST NOT silently:
- Drop workloads,
- Remove sections,
- Hide missing data,
- Skip redaction,
- Omit Execution Metadata.

If information is incomplete or missing, agents MUST surface the gap in:
- `Risks & Gaps`,
AND include details in:
- `Execution Metadata`.

### Allowed Fallbacks
If GenAI summary fails:
- Insert a short deterministic fallback summary.
- Document the failure in `Execution Metadata`.

### Guidelines Update Path
If `report_guidelines.md` is incomplete or incompatible with reality, agents MUST:
1. Surface evidence of the issue,
2. Propose minimal guideline updates,
3. Wait for confirmation before modifying guidelines.

---

# End of AGENTS.md
