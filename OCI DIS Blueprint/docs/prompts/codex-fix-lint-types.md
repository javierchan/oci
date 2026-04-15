# Codex Task — Fix ESLint Gate + mypy Type Errors

## Situation

The latest audit (2026-04-14) shows the codebase is functionally complete (14/15
milestones ✅) but two quality gates are failing that block a clean release posture:

1. **Frontend ESLint** — `npx eslint . --ext .ts,.tsx --max-warnings 0` exits with
   3 errors and 17 warnings. The Browser QA milestone cannot be marked ✅ until this
   gate is green.
2. **Backend mypy** — `mypy apps/api/app` reports 10 type errors across 3 service
   files.

This task fixes both gates. No feature changes. No schema changes. No new packages.

---

## Pre-flight reads

Before writing any code read the following files to understand existing patterns:

1. `apps/web/lib/use-theme.ts`
2. `apps/web/components/graph-controls.tsx`
3. `apps/web/components/integration-graph.tsx`
4. `apps/web/components/system-autocomplete.tsx`
5. `apps/api/app/services/recalc_service.py`
6. `apps/api/app/services/import_service.py`
7. `apps/api/app/services/export_service.py`

---

## TASK 1 — Fix frontend ESLint (3 errors + 17 warnings)

### 1a. Unescaped entities in `system-autocomplete.tsx` (2 errors)

File: `apps/web/components/system-autocomplete.tsx`, line ~98

The hint text rendered when no suggestions match contains raw `"` characters inside
JSX which triggers `react/no-unescaped-entities`.

Find the JSX node that displays the empty-state hint (added in the Browser QA fix)
and replace every bare `"` with `&quot;`. Example:

```tsx
// before
<span>Try typing "OIC" or "SAP"</span>

// after
<span>Try typing &quot;OIC&quot; or &quot;SAP&quot;</span>
```

Inspect the actual text and escape all unescaped `"` and `'` characters in that
element.

### 1b. Unused parameter warnings — prefix with `_`

The ESLint rule `no-unused-vars` allows unused args only when they match `/^_/u`.
Rename every flagged parameter by prepending `_`. Do not remove the parameter
(it may be required by the interface/callback signature). Changes needed:

**`apps/web/lib/use-theme.ts`**
- Parameter named `theme` in a callback or function signature — rename to `_theme`

**`apps/web/components/graph-controls.tsx`**
- Parameter named `value` — rename to `_value`
- Two parameters named `mode` — rename both to `_mode`

**`apps/web/components/integration-graph.tsx`**
- Parameter named `node` — rename to `_node`
- Parameter named `edge` — rename to `_edge`
- Parameter named `updater` — rename to `_updater`
- Parameter named `current` — rename to `_current`

**`apps/web/components/system-autocomplete.tsx`**
- Parameter named `value` (separate from the JSX issue above) — rename to `_value`

After each rename verify that the parameter is not referenced anywhere in the
function body. If it is referenced, do NOT rename it — instead investigate why
ESLint is flagging it (likely a shadowing issue) and fix the shadowing instead.

### 1c. Verify gate after fix

```bash
cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0 2>&1 | tail -20
```

Expected: zero output (exit code 0). If any warnings remain, fix them before
proceeding to Task 2.

---

## TASK 2 — Fix backend mypy (10 type errors)

The root cause across all three files is the same pattern: ORM/dict operations
return `object` because the model or row type is not narrowed. Fix by casting to
`Any` at the narrowing boundary using `cast` from `typing`. Add
`from typing import Any, cast` at the top of each file if not already imported.

### 2a. `apps/api/app/services/recalc_service.py` — lines 126–129

Error: `Argument after ** must be a mapping, not "object"` (4 occurrences)

Pattern: code does `**some_orm_row_or_dict` where mypy infers the type as `object`.

Fix pattern:
```python
# before
result = SomeSchema(**row)

# after
from typing import Any, cast
result = SomeSchema(**cast(dict[str, Any], row))
```

Apply this cast to all four `**` expansion sites flagged at lines 126–129. Read
the surrounding context carefully — the cast target type should match what the
schema constructor expects.

### 2b. `apps/api/app/services/import_service.py` — lines 268, 269, 281, 305

**Lines 268–269**: `Value of type "object" is not indexable`

Pattern: subscript access `row["key"]` where `row` is typed as `object`.

Fix:
```python
# before
value = row["column_name"]

# after
row_dict = cast(dict[str, Any], row)
value = row_dict["column_name"]
```

If both lines 268 and 269 access the same `row` variable, a single cast above both
is sufficient.

**Line 281**: `Argument "normalization_events" has incompatible type "list[object]"`

Fix: cast the list before passing:
```python
_build_catalog_integration(
    ...,
    normalization_events=cast(list[dict[str, Any]], normalization_events),
    ...
)
```

**Line 305**: `Incompatible types in assignment (expression has type "object", ...)`

Fix: annotate the variable explicitly:
```python
# before
result = some_expression

# after
result: dict[str, Any] | None = cast(dict[str, Any] | None, some_expression)
```

Read line 305 in context to confirm the correct target type.

### 2c. `apps/api/app/services/export_service.py` — line 185

Error: `Argument 1 to "ExportJobResponse" has incompatible type "**dict[str, object]"`

Pattern: `ExportJobResponse(**some_dict)` where the dict is typed as
`dict[str, object]`.

Fix:
```python
# before
return ExportJobResponse(**job_dict)

# after
return ExportJobResponse(**cast(dict[str, Any], job_dict))
```

### 2d. Verify gate after fix

```bash
./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary 2>&1 | tail -20
```

Expected: no `error:` lines. Warnings are acceptable. If new errors appear that
were previously hidden by the 10 errors, fix those too before proceeding.

---

## TASK 3 — Full verification pass

Run all gates in sequence and confirm each is green:

```bash
# Backend tests
./.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -5

# Ruff
./.venv/bin/python -m ruff check . 2>&1 | tail -5

# mypy
./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary 2>&1 | tail -10

# TypeScript
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -10

# ESLint
npx eslint . --ext .ts,.tsx --max-warnings 0 2>&1 | tail -10; cd ../..
```

All five commands must exit cleanly (no errors, no warnings for ESLint). If any
gate fails, fix it before proceeding to Task 4.

---

## TASK 4 — Commit in two logical units

### Commit A — Frontend ESLint fix

```
git add apps/web/lib/use-theme.ts \
        apps/web/components/graph-controls.tsx \
        apps/web/components/integration-graph.tsx \
        apps/web/components/system-autocomplete.tsx

git commit -m "fix(web): resolve ESLint gate — escape JSX entities, prefix unused params with _"
```

### Commit B — Backend mypy fix

```
git add apps/api/app/services/recalc_service.py \
        apps/api/app/services/import_service.py \
        apps/api/app/services/export_service.py

git commit -m "fix(api): resolve mypy gate — cast ORM object returns to concrete mapping types"
```

---

## TASK 5 — Update docs/progress.md

Append the following entry to `docs/progress.md`:

```markdown
## Quality Gates — ESLint + mypy Clean (2026-04-14)

**Status:** ✅ Complete

- Fixed `react/no-unescaped-entities` in `system-autocomplete.tsx`
- Prefixed unused callback params with `_` across `graph-controls.tsx`,
  `integration-graph.tsx`, `use-theme.ts`, `system-autocomplete.tsx`
- Fixed 10 mypy errors in `recalc_service.py`, `import_service.py`,
  `export_service.py` using `cast(dict[str, Any], ...)` at ORM return sites
- All five quality gates now green: pytest, ruff, mypy, tsc, eslint
```

Then commit:

```bash
git add docs/progress.md
git commit -m "docs: quality gates fully green — ESLint and mypy clean"
```

---

## Success criteria

- [ ] `npx eslint . --ext .ts,.tsx --max-warnings 0` exits 0 with no output
- [ ] `mypy apps/api/app` reports zero `error:` lines
- [ ] `pytest` still shows `26 passed`
- [ ] `ruff check .` still shows `All checks passed!`
- [ ] `tsc --noEmit` still produces no output
- [ ] Three commits pushed: ESLint fix, mypy fix, docs update
- [ ] `docs/progress.md` updated with Quality Gates entry

---

## Constraints

- All code comments, variable names, function names, and commit messages must be
  in English (US). User-facing Spanish strings (labels, tooltips, UI text) are
  exempt and must remain in Spanish.
- Do not upgrade any npm or pip package as part of this task.
- Do not change any API routes, DB schemas, or business logic.
- Do not add new React components or new API endpoints.
- Prefer `cast(...)` over `# type: ignore` for mypy fixes — the former is
  self-documenting and survives future type refinements.
