#!/usr/bin/env bash
# =============================================================================
# OCI DIS Blueprint — Codex Pre-Task Setup Script
# Run automatically by Codex before the agent starts working.
# Target: Ubuntu (Codex sandbox). All commands idempotent.
# =============================================================================
set -euo pipefail

echo "=== [1/7] System packages ==="
apt-get update -qq
apt-get install -y --no-install-recommends \
  curl git build-essential libpq-dev \
  python3 python3-pip python3-venv \
  nodejs npm \
  postgresql-client

echo "=== [2/7] Python — calc engine + API dependencies ==="
python3 -m pip install --upgrade pip --quiet
python3 -m pip install \
  fastapi==0.111.0 \
  uvicorn[standard]==0.29.0 \
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
  python-jose[cryptography]==3.3.0 \
  passlib[bcrypt]==1.7.4 \
  structlog==24.1.0 \
  pytest==8.2.0 \
  pytest-asyncio==0.23.6 \
  coverage==7.5.1 \
  ruff==0.4.4 \
  --quiet

echo "=== [3/7] Node — web app dependencies ==="
cd apps/web
npm install --silent
cd ../..

echo "=== [4/7] Python package __init__ files ==="
touch packages/calc-engine/src/__init__.py
touch packages/calc-engine/src/engine/__init__.py
touch packages/calc-engine/src/tests/__init__.py
touch packages/calc-engine/src/drivers/__init__.py
touch packages/calc-engine/src/scenarios/__init__.py
touch apps/api/app/__init__.py
touch apps/api/app/core/__init__.py
touch apps/api/app/models/__init__.py
touch apps/api/app/routers/__init__already.py 2>/dev/null || true
touch apps/api/app/services/__init__.py
touch apps/api/app/workers/__init__.py
touch apps/api/app/schemas/__init__.py
touch apps/api/app/migrations/__init__.py

echo "=== [5/7] Verify parity tests pass (baseline must be green before you start) ==="
python3 -m pytest packages/calc-engine/src/tests/ -v --tb=short
echo "✓ All parity tests green — baseline confirmed"

echo "=== [6/7] TypeScript baseline check ==="
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -5 || echo "(TSC errors expected before M3 — web scaffolding is in place)"
cd ../..

echo "=== [7/7] Environment ready ==="
echo "Repo root: $(pwd)"
echo "Python: $(python3 --version)"
echo "Node: $(node --version)"
echo "Pytest: $(python3 -m pytest --version)"
echo ""
echo "Setup complete. Codex may now begin the task."
