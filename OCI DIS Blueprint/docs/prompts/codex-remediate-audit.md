# Codex Task — Audit Remediation

## Situation

The automated audit (`docs/audit-report.md`, generated 2026-04-14) identified repository
hygiene and quality-gate issues that prevent M8-M10 from being reproducible from committed
history, even though the application is running correctly at runtime.

This task fixes those issues. **No new features. No dependency upgrades.**

Read `docs/audit-report.md` before doing anything else so you have the full context.

---

## Task 1 — Fix Git State (CRITICAL)

The worktree is on a detached HEAD with 17 modified files and 4 untracked files that belong
to committed milestones.

### 1A — Move off detached HEAD

```bash
# Check current state
git status
git rev-parse --abbrev-ref HEAD

# Create and switch to a named branch from current commit
git checkout -b main 2>/dev/null || git checkout main
# If main already exists and HEAD is ahead of it:
# git branch -f main HEAD && git checkout main
```

### 1B — Stage and commit the milestone backend files

These files exist in the worktree but are either modified or untracked.
They belong to milestones already marked complete. Commit them now.

Stage in logical groups and commit each group separately:

**Commit 1 — M8 governance migration and models:**
```bash
git add \
  apps/api/migrations/versions/20260414_0003_add_is_system_to_pattern_definitions.py \
  apps/api/app/models/governance.py \
  apps/api/app/routers/patterns.py \
  apps/api/app/services/reference_service.py \
  apps/api/app/schemas/reference.py \
  apps/api/app/migrations/seed.py
git commit -m "feat(M8): commit is_system migration, governance model updates, and seed"
```

**Commit 2 — M9 capture backend:**
```bash
git add \
  apps/api/app/routers/catalog.py \
  apps/api/app/services/catalog_service.py \
  apps/api/app/routers/imports.py \
  apps/api/app/services/import_service.py \
  apps/api/app/schemas/imports.py \
  apps/api/app/routers/projects.py \
  apps/api/app/services/project_service.py \
  apps/api/app/schemas/project.py \
  apps/api/app/routers/justifications.py \
  apps/api/app/services/justification_service.py \
  apps/api/app/schemas/justification.py \
  apps/api/app/core/calc_engine.py
git commit -m "feat(M9): commit capture and import backend changes"
```

**Commit 3 — M10 graph backend:**
```bash
git add \
  apps/api/app/services/graph_service.py \
  apps/api/app/schemas/graph.py
git commit -m "feat(M10): commit graph service and schema (were untracked)"
```

**Commit 4 — misc untracked docs:**
```bash
git add docs/status-report.md package-lock.json 2>/dev/null
git diff --cached --name-only | grep -q . && \
  git commit -m "chore: add status-report and sync package-lock" || \
  echo "Nothing additional to commit"
```

After all four commits, verify the worktree is clean:
```bash
git status
# Expected: "nothing to commit, working tree clean"
```

---

## Task 2 — Fix Ruff Lint Errors (3 unused imports)

The audit found:

```
packages/calc-engine/src/engine/importer.py:14:8: F401 `re` imported but unused
packages/calc-engine/src/tests/test_importer.py:9:8: F401 `pytest` imported but unused
packages/calc-engine/src/tests/test_volumetry.py:9:8: F401 `math` imported but unused
```

Fix all three with the auto-fix flag:

```bash
./.venv/bin/python -m ruff check packages/calc-engine/ --fix
```

Verify clean:
```bash
./.venv/bin/python -m ruff check . 2>&1
# Expected: "All checks passed!"
```

Commit:
```bash
git add packages/calc-engine/src/engine/importer.py \
        packages/calc-engine/src/tests/test_importer.py \
        packages/calc-engine/src/tests/test_volumetry.py
git commit -m "fix: remove unused imports in calc-engine (ruff F401)"
```

---

## Task 3 — Add ESLint Config

The audit found ESLint 8.57.1 installed but no config file, causing the quality gate to fail:

```
ESLint couldn't find a configuration file.
```

Create `apps/web/.eslintrc.json`:

```json
{
  "extends": ["next/core-web-vitals"],
  "rules": {
    "@typescript-eslint/no-unused-vars": ["warn", { "argsIgnorePattern": "^_" }],
    "@typescript-eslint/no-explicit-any": "warn",
    "react-hooks/exhaustive-deps": "warn"
  }
}
```

Verify it runs without crashing:
```bash
cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 50 2>&1 | tail -10; cd ../..
```

The goal is a running lint gate, not zero warnings on first run — suppress that with `--max-warnings 50`
for now; tighten to `0` once existing warnings are triaged.

Commit:
```bash
git add apps/web/.eslintrc.json
git commit -m "chore: add ESLint config for Next.js project"
```

---

## Task 4 — Install mypy in .venv

The audit found `mypy` missing from the local `.venv`. Add it so the type-check audit
command can run:

```bash
./.venv/bin/pip install mypy 2>&1 | tail -5
```

Run a quick check to confirm it works:
```bash
./.venv/bin/python -m mypy apps/api/app \
  --ignore-missing-imports --no-error-summary 2>&1 | tail -10
```

Do not fix any mypy errors found — just confirm the tool runs. Add `mypy` to
`apps/api/requirements.txt` if it is not already there.

Commit if requirements.txt was changed:
```bash
grep -q mypy apps/api/requirements.txt || echo "mypy>=1.10" >> apps/api/requirements.txt
git add apps/api/requirements.txt
git diff --cached --name-only | grep -q . && \
  git commit -m "chore: add mypy to API requirements" || echo "Already present"
```

---

## Task 5 — Update README.md Milestone Status

The audit found `README.md` still marks M9 and M10 as `⚠ Partial` even though their
implementation is present and runtime-verified.

Open `README.md`, find the milestone table, and update these rows:

| Milestone | Old status | New status | Completed |
|-----------|-----------|-----------|-----------|
| M8 | ⚠ Partial | ✅ Complete | 2026-04-14 |
| M9 | ⚠ Partial | ✅ Complete | 2026-04-14 |
| M10 | ⚠ Partial | ✅ Complete | 2026-04-14 |

After editing, commit:
```bash
git add README.md
git commit -m "docs: mark M8-M10 complete in milestone table"
```

---

## Task 6 — Seed Benchmark Project (restore parity)

The audit found the live database has only `catalog_total=13` integrations in the first
project. The benchmark target is 144 loaded rows (157 TBQ=Y − 13 Duplicado 2 excluded).

The benchmark import uses the real workbook `Catalogo_Integracion.xlsx`.
If that file is not present in the repo (it is gitignored), use the synthetic fixture path
described in `AGENTS.md` or `codex-validate.md`.

**Option A — Real workbook available:**
```bash
curl -sf -X POST http://localhost:8000/api/v1/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Benchmark Validation Project","description":"M2 parity check"}' \
  | python3 -c "import json,sys; p=json.load(sys.stdin); print(p['id'])"
# Note the project ID, then import the workbook via the /imports/{pid} endpoint
```

**Option B — Synthetic XLSX (no real file):**

Run the synthetic parity test that already exists in the calc-engine test suite:
```bash
./.venv/bin/python -m pytest packages/calc-engine/src/tests/ -v --tb=short 2>&1
```

Expected: `26 passed` — this confirms the calculation logic is correct at engine level
even without a live DB import.

Also probe the existing project catalog to confirm the API is healthy:
```bash
PID=$(curl -sf http://localhost:8000/api/v1/projects/ | python3 -c \
  "import json,sys; projects=json.load(sys.stdin).get('projects',[]); print(projects[0]['id'] if projects else 'NONE')")
echo "First project ID: $PID"
curl -sf "http://localhost:8000/api/v1/catalog/$PID" | python3 -c \
  "import json,sys; data=json.load(sys.stdin); print(f\"Catalog rows: {data.get('total',0)}\")"
```

If `catalog_total` is still 13 (i.e. the existing project is the demo project, not the
benchmark), do not force-import — note it in the progress log and defer a fresh benchmark
import to a dedicated data-seeding session.

---

## Task 7 — Final Verification Pass

Run all quality gates and confirm results:

```bash
# 1. Tests
./.venv/bin/python -m pytest packages/calc-engine/src/tests/ -v --tb=short 2>&1 | tail -5

# 2. Ruff
./.venv/bin/python -m ruff check . 2>&1

# 3. TypeScript
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -5; cd ../..

# 4. ESLint
cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 50 2>&1 | tail -5; cd ../..

# 5. Docker
docker compose ps 2>&1

# 6. API health
curl -sf http://localhost:8000/health 2>&1

# 7. Git state
git status
git log --oneline -8
```

All must pass before the documentation update below.

---

## Task 8 — Update Progress Documentation

After all tasks above are verified:

**Append to `docs/progress.md`:**

```markdown
## Remediation — Audit Cleanup

**Completed:** {today's date}
**Status:** ✅ Complete

### What was fixed

- Committed 17 modified + 4 untracked milestone files for M8, M9, M10
- Moved worktree off detached HEAD onto `main` branch
- Removed 3 unused imports in `packages/calc-engine/` (ruff F401)
- Added `apps/web/.eslintrc.json` — ESLint quality gate now runs
- Installed `mypy` in `.venv` and added to `apps/api/requirements.txt`
- Updated `README.md`: M8, M9, M10 marked ✅ Complete

### Verification results

```text
pytest:  26 passed
ruff:    All checks passed!
tsc:     0 errors
ESLint:  running (<=50 warnings)
Docker:  6/6 containers Up
git:     working tree clean
```

### Gaps / known limitations

- ESLint warnings may remain (review and tighten `--max-warnings` in a follow-up)
- Benchmark DB parity (144 rows) not yet demonstrated in live DB if real workbook was unavailable
- mypy type errors not yet triaged — tool confirmed running only

---
```

**Update `README.md`** milestone table (already done in Task 5).

Commit documentation:
```bash
git add docs/progress.md README.md
git commit -m "docs: audit remediation complete — progress log and milestone table updated"
```

---

## Definition of Done

- [ ] `git status` → "nothing to commit, working tree clean"
- [ ] `git rev-parse --abbrev-ref HEAD` → `main` (not `HEAD`)
- [ ] `git log --oneline -5` shows the four milestone commits + the remediation commit
- [ ] `./.venv/bin/python -m ruff check .` → "All checks passed!"
- [ ] `cd apps/web && npx tsc --noEmit --skipLibCheck` → no output (0 errors)
- [ ] `cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 50` → exit code 0
- [ ] `./.venv/bin/python -m pytest packages/calc-engine/src/tests/ -q` → "26 passed"
- [ ] `docker compose ps` → 6/6 containers Up
- [ ] `README.md` shows M8, M9, M10 as ✅ Complete
- [ ] `docs/progress.md` contains a Remediation entry with today's date

## Language

All code comments, commit messages, and documentation entries must be in English (US).
