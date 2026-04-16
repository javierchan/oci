# Codex Task — M23 Completion: Pattern Coverage 03–17

## Situation

The workbook documents 17 patterns, but the gap analysis confirms that end-to-end
behavior is still functionally partial. Some patterns exist today more as reference
records than as fully operationalized application behavior. That is acceptable only
if the support boundary is made explicit. It is not acceptable for the UI to imply
full support while the sizing logic, QA hints, narratives, and exports still behave
generically.

This milestone closes that ambiguity. Either:
- fully support patterns `#03`–`#17` end to end for phase parity, or
- explicitly classify some of them as library-only / unsupported in parity mode

The decision must be documented in code, UI, and project documentation.

No vague middle state. Unsupported patterns must not look production-ready if they are not.

**Read before writing any code:**
1. `AGENTS.md` — milestone and parity contract
2. `docs/reports/workbook-gap-analysis-adn-20260415.md`
3. `apps/api/app/migrations/seed.py` — seeded pattern catalog
4. `packages/calc-engine/src/engine/volumetry.py`
5. `packages/calc-engine/src/engine/qa.py`
6. `apps/api/app/services/dashboard_service.py`
7. `apps/api/app/services/export_service.py`
8. `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx`
9. `apps/web/components/integration-canvas.tsx`
10. `apps/web/components/justification-*` or narrative assembly files if present

Do not claim parity by documentation alone. Supported patterns must have real behavior.

---

## Task 1 — Decide and document the support boundary

### What to do first

Create an explicit support matrix for patterns `#01`–`#17`:
- fully supported
- partially supported
- reference-only / unsupported in phase parity

The matrix must be derived from actual code behavior, not aspiration.

At minimum, evaluate each pattern against these dimensions:
- capture and selection support
- QA hints and validation
- volumetry inputs and formulas
- dashboard grouping
- justification narrative branches
- export behavior

Document the decision in:
- `docs/progress.md` when completed
- README or milestone notes if the project already tracks support level there
- user-facing UI where unsupported patterns can currently be selected

---

## Task 2 — Fully support every pattern chosen as “supported”

### What to change

For each pattern marked supported:
- ensure the required inputs are captured or derivable
- ensure volumetry formulas branch correctly where the workbook defines pattern-specific behavior
- ensure QA hints are pattern-aware
- ensure dashboard grouping treats the pattern correctly
- ensure exports include the right pattern semantics
- ensure deterministic narratives reference the pattern accurately

Do not leave a supported pattern on generic fallback logic if the workbook defines
specific guidance or anti-pattern behavior.

### Verification

Add focused tests for each newly supported pattern path. Prefer table-driven tests
so the support matrix is explicit and maintainable.

---

## Task 3 — Make unsupported patterns explicit and safe

### What to change

For any pattern not fully operationalized:
- mark it clearly in the admin and user UI
- prevent misleading confidence or sizing output
- show a clear hint that the pattern exists in the library but is not yet fully supported

Possible UX:
- badge: `Reference only`
- disabled advanced estimate sections
- explanatory hint on selection

The key rule:
- unsupported patterns must not behave like generic placeholders with green status

### Verification

Selecting an unsupported pattern should never result in:
- false precision
- misleading QA completeness
- silent fallback to a generic supported path without disclosure

---

## Task 4 — Use workbook anti-pattern guidance in QA and pattern support

### What to change

The workbook pattern sheet contains anti-pattern guidance. Use it to improve:
- pattern selection hints
- QA reason messaging
- support warnings when a chosen tool stack conflicts with the selected pattern

This can be implemented progressively, but the milestone must at least connect the
anti-pattern metadata to one operational surface:
- QA hints
- canvas suggestion mismatches
- pattern detail guidance

### Verification

If a user chooses a pattern whose anti-pattern conditions clearly match the designed flow,
the system should surface a meaningful warning rather than remaining silent.

---

## Task 5 — Keep documentation and exports honest

### What to change

Update the project documentation and export behavior so external artifacts reflect
the actual support state.

Examples:
- exports may include a support note for unsupported patterns
- milestone documentation should record whether parity includes all 17 patterns or not
- admin/reference views should distinguish “defined in workbook” from “fully operationalized”

Do not hide the limitation in internal-only docs if the UI still exposes the pattern.

---

## Task 6 — Tests and milestone evidence

### Required validation

Add or update tests that prove:
- the support matrix is enforced
- supported patterns have explicit behavior
- unsupported patterns are surfaced as such

Create a concise written diff or milestone note that lists:
- which patterns are fully supported
- which remain reference-only, if any
- which code paths were extended to support the chosen scope

---

## Final Verification

Run all of the following:

```bash
./.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -10
./.venv/bin/python -m ruff check . 2>&1 | tail -10
./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary 2>&1 | tail -10
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -10; cd ../..
cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0 2>&1 | tail -10; cd ../..
```

Manual verification:
- inspect pattern selection and detail UX
- confirm supported patterns have differentiated behavior
- confirm unsupported patterns are clearly labeled and do not produce misleading confidence

---

## Definition of Done

M23 is complete only when all of the following are true:

- The support boundary for patterns `#03`–`#17` is explicit and documented
- Every supported pattern has end-to-end operational behavior
- Unsupported patterns are clearly surfaced as reference-only or unsupported
- Workbook anti-pattern guidance is used in at least one operational surface
- All five quality gates remain green

