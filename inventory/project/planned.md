Analizar los inventarios y crear diagramas de arquitectura

Analizar los inventarios y comparar vs la best practices de OCI (CAF?)
Posible integracion en el mismo codebase para correr los scripts de CIS, reusando el codigo existente, solo encadenando y usando las credenciales y targets definidos por oci-inv

Mejorar los enrichments, firewall por ejemplo y su asociacion con VMs (o servicios), Security Groups and Control Access Lists.
---

AGENTS.md - modelos alternativos,

Opción A: 1 solo archivo → AGENTS.md completo.

Opción B: 3 archivos → AGENTS.md (overview) + POLICIES.md (reglas duras) + INTERACTION.md (loop/flujo).

# AGENTS.md

High-level expectations for AI Agents working in this repository.

- Operate only inside `inventory/`.
- Preserve existing behavior unless instructed otherwise.
- Produce deterministic, reproducible, human-readable code.
- Follow project conventions in naming, structure, and patterns.
- All outputs must be English (US).
- If ambiguous, ask for clarification first.
- If blocked, document attempts and what is missing.

See `POLICIES.md` for constraints and rules.
See `INTERACTION.md` for execution workflow.

# End of AGENTS.md

---

# POLICIES.md

## Boundaries
- Do not touch files outside `inventory/`.
- New files only when explicitly requested and within `inventory/`.

## Read-Only OCI Policy
Allowed:
- list, search, get

Forbidden:
- create, update, delete, patch, move,
- enable/disable, attach/detach,
- or any mutating OCI action.

## Safety & Security
- Do not log secrets or credentials.
- Do not modify auth, keys, or tokens.
- Do not expose sensitive data.

## Quality & Determinism
- Maintain clear module boundaries.
- Consistent naming (snake_case for Python).
- Stable ordering for hashing, diffs, exports.
- No non-deterministic behavior unless requested.

## Dependencies & Tooling
- No new dependencies without approval.
- Never reformat entire files without instruction.
- Use existing tooling and conventions.

## Testing Requirements
- Tests must be offline, deterministic, fast.
- Add tests for any behavior change or fix.

## Research & Enhancement Policy
- Use official / reputable sources when stuck.
- Synthesize insights, do not paste verbatim.
- Document source type and adaptation.
- If still blocked, mark as BLOCKED and explain.

# End of POLICIES.md

---

# INTERACTION.md

## Agent Interaction Loop (Required)

1. Restate task with assumptions.
2. Plan minimal steps (1–4).
3. Ask for clarification if unsafe or ambiguous.
4. Execute changes.
5. Verify with evidence:
   - tests
   - inspection
   - file paths & line numbers
6. Report results including:
   - changed files
   - observations
   - evidence
   - remaining uncertainties

## Failure & Blocking

If unable to proceed:
- State what was attempted,
- Why it failed,
- What is missing,
- Mark as `BLOCKED`.

## Language Rule
- All outputs in English (US).

# End of INTERACTION.md

---
