# Dependency Maintenance Plan — 2026-04-28 13:15:17

## Scope

This report captures the remaining non-functional maintenance backlog after the
Admin Synthetic Lab productization slice was completed. It does not propose a
blind upgrade wave. The goal is to separate safe patch work from high-risk
framework migrations.

## Commands Run

- `NPM_CONFIG_CACHE=/tmp/codex-npm-cache npm outdated --json` in `apps/web/`
- `./.venv/bin/python -m pip list --outdated --format=json` in `apps/api/`

## Environment Note

- `npm outdated` failed with the default `~/.npm` cache because the cache
  contains root-owned files. Using `NPM_CONFIG_CACHE=/tmp/codex-npm-cache`
  worked around the issue safely for inspection.
- Before a routine dependency-refresh cycle, fix local npm cache ownership or
  keep using an isolated cache path in maintenance scripts.

## Web Findings

### Safe patch/minor candidates

- `@tanstack/react-query`: `5.99.0` -> `5.100.6`
- `axios`: `1.15.0` -> `1.15.2`
- `postcss`: `8.5.9` -> `8.5.12`

### Hold for dedicated compatibility branch

- `next`: `14.2.3` -> `16.2.4`
- `react` / `react-dom`: `18.3.1` -> `19.2.5`
- `tailwindcss`: `3.4.19` -> `4.2.4`
- `eslint-config-next`: `14.2.3` -> `16.2.4`
- `lucide-react`: `0.383.0` -> `1.12.0`
- `recharts`: `2.15.4` -> `3.8.1`
- `typescript`: `5.9.3` -> `6.0.3`
- `zod`: `3.25.76` -> `4.3.6`
- `zustand`: `4.5.7` -> `5.0.12`

These are major ecosystem moves with real breakage risk across App Router,
React semantics, Tailwind config, chart rendering, and generated types.

## API Findings

### Safe patch/minor candidates

- `aiosqlite`: `0.20.0` -> `0.22.1`
- `openpyxl`: `3.1.2` -> `3.1.5`
- `psycopg2-binary`: `2.9.9` -> `2.9.12`
- `click`: `8.3.2` -> `8.3.3`
- `certifi`: `2026.2.25` -> `2026.4.22`
- `mypy`: `1.20.1` -> `1.20.2`

### Medium-risk minor upgrades that need focused validation

- `SQLAlchemy`: `2.0.30` -> `2.0.49`
- `alembic`: `1.13.1` -> `1.18.4`
- `httpx`: `0.27.0` -> `0.28.1`
- `fastapi`: `0.111.0` -> `0.136.1`
- `pydantic`: `2.7.1` -> `2.13.3`
- `pydantic-settings`: `2.2.1` -> `2.14.0`
- `celery`: `5.4.0` -> `5.6.3`
- `redis`: `5.0.4` -> `7.4.0`
- `python-multipart`: `0.0.9` -> `0.0.27`

### Hold for dedicated migration work

- `pandas`: `2.2.2` -> `3.0.2`
- `pytest`: `8.2.0` -> `9.0.3`
- `pytest-asyncio`: `0.23.6` -> `1.3.0`
- `uvicorn`: `0.29.0` -> `0.46.0`
- `opentelemetry-sdk`: `1.24.0` -> `1.41.1`
- `structlog`: `24.1.0` -> `25.5.0`

These affect runtime behavior, async test semantics, or observability surfaces
and should not be mixed into a safe housekeeping PR.

## Recommended Execution Plan

### Wave 1 — Low-risk housekeeping

- Web: upgrade `react-query`, `axios`, `postcss`
- API: upgrade `aiosqlite`, `openpyxl`, `psycopg2-binary`, `click`, `certifi`, `mypy`
- Re-run:
  - `apps/web`: `tsc`, `eslint`, `vitest`
  - `apps/api`: `pytest`, `ruff`

### Wave 2 — Medium-risk platform refresh

- API: `SQLAlchemy`, `Alembic`, `FastAPI`, `Pydantic`, `httpx`, `Celery`, `redis`
- Validate router serialization, migrations, worker dispatch, and request-model
  compatibility with focused smoke tests against the live stack.

### Wave 3 — Framework migration program

- Web: `Next 14 -> 16`, `React 18 -> 19`, `Tailwind 3 -> 4`
- API: `pandas 3`, `pytest 9`, `pytest-asyncio 1.x`, newer telemetry stack
- Execute on a dedicated branch with explicit regression budget and UI/runtime
  verification.

## Current Recommendation

No dependency upgrade is blocking core OCI DIS Blueprint functionality right
now. The highest-value next move is a small Wave 1 maintenance PR, followed by
targeted validation, instead of mixing framework migrations into the current
feature branch.
