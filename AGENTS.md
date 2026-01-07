# AGENTS.md

Senior-level guidance for AI Agents working in this repo. This file contains
best practices and operating standards only. Task-specific solution instructions
must live in the agent prompt.

## Scope
- Operate only inside `inventory/`.
- Do not read, modify, or reference files outside this directory.

## Session Language Rule
- User instructions are in Spanish (Mexico).
- All agent outputs, actions, code, and documentation must be in English (US).

## Senior Engineering Practices
- Favor minimal, well-scoped changes that solve the problem directly.
- Preserve existing behavior unless the prompt explicitly requires a change.
- Keep changes deterministic and reproducible.
- Be explicit about assumptions and unknowns.
- Avoid speculative changes; anchor decisions in evidence.

## Safety and Security
- Never log or introduce secrets or credentials.
- Do not add or modify files that could expose sensitive data.
- If a command requires network access, request explicit approval.

## Quality Standards
- Maintain clear module boundaries and cohesive responsibilities.
- Keep naming consistent and aligned with existing conventions.
- Add comments only where the code is not self-explanatory.
- Prefer stable ordering when output, hashing, or diffs depend on it.

## Testing Discipline
- Add tests for any behavior change or bug fix.
- Keep tests offline, deterministic, and fast.
- Run the smallest relevant test set; expand only as needed.

## Evidence and Reporting
- Cite file paths and line numbers for all claims.
- Document command outcomes and failures with exact error messages.
- If verification is not possible, mark as NOT VERIFIED and explain why.

## Change Hygiene
- Avoid touching unrelated files.
- Do not revert or reformat unrelated changes.
- Keep diffs small and focused; separate refactors from functional changes.

## Collaboration
- If the prompt is ambiguous, ask for clarification before proceeding.
- Summarize changes and next steps clearly and concisely.
