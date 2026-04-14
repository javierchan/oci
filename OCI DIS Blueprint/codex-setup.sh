#!/usr/bin/env bash
# =============================================================================
# OCI DIS Blueprint — Codex Pre-Task Setup Script
# Run automatically by Codex before the agent starts working.
# Target: macOS (Codex CLI runs locally on macOS, not in a Linux VM).
#
# Prerequisites already present on developer macOS:
#   - Homebrew
#   - python3.12   (brew install python@3.12)
#   - node / npm   (brew install node  OR  via nvm)
#   - git
#
# Python dependencies are installed inside a virtual environment at .venv/
# All python3 / pytest / ruff calls use .venv/bin/ explicitly.
# The app itself (api, web, db, redis, worker, minio) runs in Docker Desktop.
# This script only sets up the local toolchain Codex uses to verify its work.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

VENV=".venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"
PYTEST="$VENV/bin/pytest"
RUFF="$VENV/bin/ruff"

# ---------------------------------------------------------------------------
echo "=== [1/6] Verify Python 3.12 is available ==="
# asyncpg 0.29.0 and pydantic-core 2.18.2 do not support Python 3.13+
PYTHON312=""
for candidate in python3.12 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12; do
  if command -v "$candidate" &>/dev/null; then
    PYTHON312="$candidate"
    break
  fi
done

if [ -z "$PYTHON312" ]; then
  echo "ERROR: python3.12 not found. Install it with: brew install python@3.12"
  exit 1
fi

echo "✓ Using $PYTHON312 ($($PYTHON312 --version))"

# ---------------------------------------------------------------------------
echo "=== [2/6] Python virtual environment ==="
if [ ! -f "$VENV/bin/activate" ]; then
  "$PYTHON312" -m venv "$VENV"
  echo "✓ Created venv at $VENV"
else
  echo "✓ Venv already exists at $VENV"
fi

"$PIP" install --upgrade pip --quiet
"$PIP" install \
  fastapi==0.111.0 \
  "uvicorn[standard]==0.29.0" \
  sqlalchemy==2.0.30 \
  alembic==1.13.1 \
  asyncpg==0.29.0 \
  pydantic==2.7.1 \
  pydantic-settings==2.2.1 \
  python-multipart==0.0.9 \
  httpx==0.27.0 \
  openpyxl==3.1.2 \
  pandas==2.2.2 \
  celery==5.4.0 \
  redis==5.0.4 \
  "python-jose[cryptography]==3.3.0" \
  "passlib[bcrypt]==1.7.4" \
  structlog==24.1.0 \
  pytest==8.2.0 \
  pytest-asyncio==0.23.6 \
  coverage==7.5.1 \
  ruff==0.4.4 \
  --quiet
echo "✓ Virtualenv ready at $VENV"

# ---------------------------------------------------------------------------
echo "=== [3/6] Node — web app dependencies ==="
if [ -f "apps/web/package.json" ]; then
  cd apps/web
  npm install --silent
  cd "$REPO_ROOT"
  echo "✓ Node modules installed"
else
  echo "⚠ apps/web/package.json not found — skipping npm install"
fi

# ---------------------------------------------------------------------------
echo "=== [4/6] Python package __init__ files ==="
touch packages/calc-engine/src/__init__.py
touch packages/calc-engine/src/engine/__init__.py
touch packages/calc-engine/src/tests/__init__.py
touch packages/calc-engine/src/drivers/__init__.py
touch packages/calc-engine/src/scenarios/__init__.py
touch apps/api/app/__init__.py
touch apps/api/app/core/__init__.py
touch apps/api/app/models/__init__.py
touch apps/api/app/services/__init__.py
touch apps/api/app/workers/__init__.py
touch apps/api/app/schemas/__init__.py
touch apps/api/app/migrations/__init__.py
echo "✓ __init__.py files in place"

# ---------------------------------------------------------------------------
echo "=== [5/6] Verify parity tests pass (baseline must be green before you start) ==="
"$PYTEST" packages/calc-engine/src/tests/ -v --tb=short
echo "✓ All parity tests green — baseline confirmed"

# ---------------------------------------------------------------------------
echo "=== [6/6] TypeScript baseline check ==="
if [ -f "apps/web/package.json" ]; then
  cd apps/web
  npx tsc --noEmit --skipLibCheck 2>&1 | tail -5 || echo "(TSC errors expected before M3 — web scaffolding is in place)"
  cd "$REPO_ROOT"
fi

echo ""
echo "=== Environment ready ==="
echo "Repo root : $REPO_ROOT"
echo "Virtualenv: $REPO_ROOT/$VENV"
echo "Python    : $("$PYTHON" --version)"
echo "Node      : $(node --version)"
echo "Pytest    : $("$PYTEST" --version)"
echo ""
echo "IMPORTANT: All subsequent python/pytest/ruff calls must use .venv/bin/ — not the system python3."
echo "The Docker stack (api/web/db/redis/worker/minio) is in docker-compose.yml."
echo "Run 'docker compose up --build -d' after Codex completes M1-M4."
echo "Setup complete. Codex may now begin the task."
