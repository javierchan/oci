# Codex Skill — Project Audit Report

## Purpose

Produce a structured audit of this codebase: what is complete, what is deviating
from spec, what is pending, and what is blocking forward progress.

**Do not modify any source file. Do not implement anything. Read, run, and report only.**

This skill is self-configuring: it discovers milestones, tech stack, and verification
commands from the repository itself. It works at any stage of development.

---

## Phase 1 — Context Discovery

Read the following files in order. Extract the information noted for each.

**Step 1.1 — Milestone registry**

Look for these files and read the first one found:
- `AGENTS.md`
- `README.md`
- `docs/progress.md`

From whichever files exist, extract:
- List of milestones (M1, M2 … or equivalent phases/epics)
- Definition of done per milestone (checklist items, acceptance criteria)
- Current documented status per milestone (if any)

If none of these files exist, infer milestones from the git log:
```bash
git log --oneline --no-walk --tags 2>/dev/null | head -20
git log --oneline -40 2>/dev/null
```

**Step 1.2 — Tech stack detection**

Run the following and note what exists:
```bash
# Python
ls pyproject.toml setup.py requirements*.txt apps/api/requirements*.txt 2>/dev/null

# Node / TypeScript
ls package.json apps/web/package.json tsconfig.json 2>/dev/null

# Docker
ls docker-compose.yml docker-compose.yaml Dockerfile 2>/dev/null

# Database migrations
ls -d apps/api/migrations apps/api/alembic.ini alembic.ini 2>/dev/null

# Test frameworks
ls -d packages/*/src/tests tests/ __tests__/ cypress/ playwright/ 2>/dev/null

# CI/CD
ls .github/workflows/*.yml .gitlab-ci.yml Jenkinsfile 2>/dev/null
```

**Step 1.3 — Repository summary**
```bash
# Project age and activity
git log --format="%ad" --date=short | tail -1   # first commit date
git log --format="%ad" --date=short | head -1   # latest commit date
git log --oneline | wc -l                        # total commits
git shortlog -sn --no-merges | head -5           # top contributors

# Current branch and uncommitted changes
git status --short
git stash list 2>/dev/null | head -5

# File count by type
find . -not -path '*/node_modules/*' -not -path '*/.venv/*' \
       -not -path '*/.git/*' -not -path '*/dist/*' \
       \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' \) | wc -l

# Lines of code (if cloc is available; skip if not)
cloc . --exclude-dir=node_modules,.venv,.git,dist,__pycache__ \
       --quiet --sum-one 2>/dev/null | tail -3
```

---

## Phase 2 — Verification Commands

Run every applicable command for the detected stack. Capture full output verbatim.
If a command fails, note the failure and continue — do not abort.

**2A — Python / Backend**
```bash
# Tests
./.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -40

# Lint
./.venv/bin/python -m ruff check . 2>&1 | tail -20

# Type check (if mypy present)
./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary 2>&1 | tail -10
```

**2B — TypeScript / Frontend**
```bash
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -30; cd ../..

# ESLint (if configured)
cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0 2>&1 | tail -20; cd ../..
```

**2C — Docker stack**
```bash
docker compose ps 2>&1
docker compose ps --format json 2>/dev/null | python3 -c "
import json, sys
try:
    containers = json.load(sys.stdin)
    if isinstance(containers, list):
        total = len(containers)
        healthy = sum(1 for c in containers if 'running' in c.get('Status','').lower() or 'Up' in c.get('Status',''))
        print(f'Containers: {healthy}/{total} running')
        for c in containers:
            print(f'  {c.get(\"Service\",\"?\"): <20} {c.get(\"Status\",\"?\")}')
except:
    pass
" 2>/dev/null
```

**2D — Live API probe (if containers are running)**
```bash
# Health
curl -sf http://localhost:8000/health 2>/dev/null && echo "API: UP" || echo "API: DOWN"

# Count registered endpoints
curl -sf http://localhost:8000/openapi.json 2>/dev/null | python3 -c "
import json, sys
try:
    spec = json.load(sys.stdin)
    paths = spec.get('paths', {})
    total_ops = sum(len([m for m in v if m in ('get','post','put','patch','delete')]) for v in paths.values())
    print(f'Registered endpoints: {len(paths)} paths, {total_ops} operations')
except:
    print('Could not parse OpenAPI spec')
" 2>/dev/null
```

**2E — Database state (if Postgres is accessible)**
```bash
docker compose exec -T db psql -U postgres -d dis_blueprint -c "
SELECT schemaname, tablename, n_live_tup AS rows
FROM pg_stat_user_tables ORDER BY tablename;
" 2>/dev/null | head -30
```

**2F — Dependency drift**
```bash
# Check for outdated Python packages
./.venv/bin/pip list --outdated 2>/dev/null | head -20

# Check for outdated npm packages (top-level only)
cd apps/web && npm outdated --depth=0 2>/dev/null | head -20; cd ../..
```

---

## Phase 3 — Milestone Assessment

For each milestone discovered in Phase 1, assess its status using a consistent rubric:

```
✅ Complete    — All definition-of-done items verified; evidence present
⚠  Partial     — Some items done; specific gaps identified
❌ Not Started — No evidence of implementation
🔄 In Progress — Evidence of partial work; known to be actively in development
```

For each milestone, produce:

1. **Status badge** (one of the four above)
2. **Evidence list** — what was found that confirms implementation (file paths, endpoint names, test names)
3. **Gap list** — what is missing or broken compared to the definition of done
4. **Deviation flag** — if actual implementation diverges from spec in a meaningful way

To find evidence, use:
```bash
# File existence checks — adapt paths to what was found in Phase 1
# Example pattern:
python3 -c "
import os, json

# Build your checklist from AGENTS.md or README.md content here
# Then for each item:
checks = []  # populate from discovered milestone definitions

for path, label in checks:
    exists = os.path.exists(path)
    size = os.path.getsize(path) if exists else 0
    print(f'{'OK  ' if exists else 'MISS'}  {size:>8}  {label}  ({path})')
"
```

---

## Phase 4 — Compute Progress Metrics

After assessing all milestones, compute:

```
Total milestones:          N
Complete (✅):             X  →  X/N = {pct}%
Partial (⚠):              Y
Not started (❌):          Z
In progress (🔄):          W

Definition-of-done items total:   T
Items verified:                    V  →  V/T = {pct}%
Items with gaps:                   G
```

Also compute:
- **Velocity proxy:** commits in last 7 days vs 7 days before that
- **Debt surface:** count of TODO/FIXME/HACK/PLACEHOLDER comments

```bash
# Velocity
git log --oneline --since="14 days ago" --until="7 days ago" | wc -l
git log --oneline --since="7 days ago" | wc -l

# Debt markers
grep -r "TODO\|FIXME\|HACK\|PLACEHOLDER\|XXX\|NOCOMMIT" \
     --include="*.py" --include="*.ts" --include="*.tsx" \
     --exclude-dir=node_modules --exclude-dir=.venv \
     -n . 2>/dev/null | grep -v "test_\|spec\." | head -30
```

---

## Phase 5 — Pending Task Classification

Classify every gap and deviation found into one of three buckets:

**CRITICAL** — blocks a demo, a deployment, or another milestone from starting.
Criteria: missing required file, failing test, broken endpoint, migration not applied.

**INCOMPLETE** — feature exists but is a stub, placeholder, or partially implemented.
Criteria: endpoint returns 501, synchronous where async was required, hardcoded values,
missing validation, UI page exists but data is mocked.

**DEFERRED** — intentionally not implemented yet; not a regression.
Criteria: appears in "Future" or "Optional" sections of AGENTS.md or the spec,
or was explicitly scoped out in the milestone definition.

For each pending task, include:
- File path or endpoint name (no vague descriptions)
- Which milestone it belongs to
- Why it is in this bucket (one sentence)

---

## Phase 6 — Write Report

Write the complete report to `docs/audit-report.md`.
If `docs/` does not exist, create it.
If `docs/audit-report.md` already exists, overwrite it (this report is always current state).

Use exactly this structure:

```markdown
# Project Audit Report

**Generated:** {YYYY-MM-DD HH:MM}
**Repository:** {remote URL from `git remote get-url origin`}
**Branch:** {current branch}
**Commit:** {git log --oneline -1}
**Auditor:** Codex (automated)

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Milestones complete | X / N ({pct}%) |
| Definition-of-done items verified | V / T ({pct}%) |
| Test suite | X/Y passed |
| TypeScript errors | N |
| Lint errors | N |
| Docker containers running | N/6 |
| CRITICAL pending tasks | N |
| INCOMPLETE items | N |
| DEFERRED items | N |
| Debt markers (TODO/FIXME) | N |
| Commits last 7 days | N |

**Overall health:** ✅ On track / ⚠ At risk / ❌ Blocked

---

## Repository Profile

{git log summary, first/last commit dates, total commits, file counts, LoC}

---

## Milestone Status

| Milestone | Description | Status | Items Done | Gaps |
|-----------|-------------|--------|-----------|------|
| M1 | {name} | ✅ | X/Y | — |
| M2 | {name} | ⚠ | X/Y | N gaps |
...

### M1 — {Name}
**Status:** ✅ Complete

Evidence:
- [x] {item}: `{file path}` ({N} bytes)
- [x] {endpoint}: verified live → HTTP {status}

Gaps: None

---

### M2 — {Name}
**Status:** ⚠ Partial

Evidence:
- [x] {item}: `{file path}`

Gaps:
- [ ] {specific missing item} — `{expected file or endpoint}`

Deviation: {if the implementation differs from spec, describe here}

---

{... repeat for every milestone ...}

---

## Verification Results

### Test Suite
```text
{full pytest / jest output}
```
Result: X/Y passed

### Lint
```text
{ruff / eslint output}
```
Result: ✅ Clean / ❌ N errors

### TypeScript
```text
{tsc output}
```
Result: ✅ Clean / ❌ N errors

### Docker Stack
```text
{docker compose ps output}
```

### API Endpoint Count
```text
{openapi probe output}
```

### Database Tables
```text
{pg_stat_user_tables output}
```

---

## Pending Tasks

### 🔴 CRITICAL (blocks QA or demo)

| # | Task | File / Endpoint | Milestone | Reason |
|---|------|----------------|-----------|--------|
| 1 | {description} | `{path}` | M{N} | {one sentence} |

### 🟡 INCOMPLETE (partial implementation)

| # | Task | File / Endpoint | Milestone | Reason |
|---|------|----------------|-----------|--------|

### 🟢 DEFERRED (out of current scope)

| # | Task | File / Endpoint | Milestone | Reason |
|---|------|----------------|-----------|--------|

---

## Debt Markers

```text
{grep output for TODO/FIXME/HACK}
```

---

## Recommended Next Actions

Ordered by impact. Address CRITICAL items first.

1. **{Action}** — `{file}` — {one sentence rationale}
2. **{Action}** — `{file}` — {one sentence rationale}
3. **{Action}** — `{file}` — {one sentence rationale}
4. **{Action}** — `{file}` — {one sentence rationale}
5. **{Action}** — `{file}` — {one sentence rationale}

---

## Dependency Drift

### Python (outdated packages)
```text
{pip list --outdated output}
```

### npm (outdated packages)
```text
{npm outdated output}
```
```

After writing the report, print to stdout:

```
Audit complete.
docs/audit-report.md written ({N} lines).

Summary: {X}/{N} milestones complete — {pct}% — {CRITICAL} critical items blocking.
```

Then commit:
```bash
git add docs/audit-report.md
git commit -m "docs: automated audit report — $(date +%Y-%m-%d)"
```

---

## Constraints

- Read-only. Do not modify any source file, migration, seed, or configuration.
- Do not start, stop, or restart Docker containers.
- Do not install packages.
- If a verification command fails due to a missing tool, note the failure verbatim and continue.
- Report everything found, including gaps. Do not soften or omit findings.
- All report text must be in English (US).
- Use specific file paths and endpoint names — no vague statements.
