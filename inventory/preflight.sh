#!/usr/bin/env bash
# Preflight setup for OCI Inventory project
# - Verifies prerequisites
# - Creates/uses .venv
# - Installs project (editable) with optional extras via INVENTORY_EXTRAS
# - Idempotent and CI-friendly
set -euo pipefail

# Logging helpers
info() { printf "[INFO] %s\n" "$*"; }
ok()   { printf "[OK]   %s\n" "$*"; }
warn() { printf "[WARN] %s\n" "$*"; }
err()  { printf "[ERROR] %s\n" "$*" >&2; }

# Resolve repo root (directory of this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# 1) Prerequisite checks
info "Checking prerequisites..."

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Required command not found: $1"
    return 1
  fi
  return 0
}

# python3
need_cmd python3 || { err "python3 is required (>= 3.11)"; exit 1; }
PY_OK=0
if ! python3 - <<'PY'
import sys
ok = (sys.version_info.major > 3) or (sys.version_info.major == 3 and sys.version_info.minor >= 11)
sys.exit(0 if ok else 1)
PY
then
  PY_OK=1
fi
if [ "${PY_OK}" -ne 0 ]; then
  err "Python 3.11+ required; detected: $(python3 --version 2>/dev/null || echo 'unknown')"
  exit 1
fi
ok "python3 detected: $(python3 --version 2>/dev/null | tr -d '\n')"

# pip (module for current python)
if ! python3 -m pip --version >/dev/null 2>&1; then
  err "pip is required (for python3). Try: python3 -m ensurepip --upgrade or install pip for Python 3."
  exit 1
fi
ok "pip detected: $(python3 -m pip --version | tr -d '\n')"

# git
need_cmd git || { err "git is required"; exit 1; }
ok "git detected: $(git --version | tr -d '\n')"

# oci CLI (optional)
if command -v oci >/dev/null 2>&1; then
  ok "oci CLI detected: $(oci --version 2>/dev/null | tr -d '\n')"
else
  warn "oci CLI not found. Optional but recommended for local workflows (https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm)."
fi

# 2) Python virtual environment
VENV_DIR=".venv"
if [ -d "${VENV_DIR}" ]; then
  info "Using existing virtual environment: ${VENV_DIR}"
else
  info "Creating virtual environment: ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
  ok "Virtual environment created"
fi

# shellcheck source=/dev/null
# Activate venv for this script process
. "${VENV_DIR}/bin/activate"
ok "Activated virtual environment: ${VENV_DIR}"

# 3) Upgrade pip/setuptools/wheel inside venv
info "Upgrading pip, setuptools, wheel..."
python -m pip install --upgrade pip setuptools wheel >/dev/null
ok "Tooling upgraded: $(pip --version | tr -d '\n')"

# 4) Install project (editable), supporting optional extras via INVENTORY_EXTRAS
EXTRAS_SPEC=""
if [ "${INVENTORY_EXTRAS:-}" != "" ]; then
  # Sanitize spaces
  EXTRAS_SANITIZED="$(printf "%s" "${INVENTORY_EXTRAS}" | tr -d ' ')"
  EXTRAS_SPEC=".[${EXTRAS_SANITIZED}]"
  info "Installing with extras: ${EXTRAS_SANITIZED}"
else
  info "Installing without extras"
fi

# Respect pyproject.toml as source of truth; do not generate lock files here
SETUP_TARGET="."
if ! python -m pip install -e "${SETUP_TARGET}${EXTRAS_SPEC}"; then
  err "pip install failed. Check network, index access, or extras name (INVENTORY_EXTRAS=${INVENTORY_EXTRAS:-<unset>})."
  exit 1
fi
ok "Project installed (editable) ${EXTRAS_SPEC}"

# 5) Final summary and next steps
cat <<'OUT'
[OK] Preflight complete.

Next steps:
  - Activate your virtual environment in new shells:
      . .venv/bin/activate
    (or run this script again to ensure activation in this shell)
  - Show CLI help:
      oci-inv --help

Optional:
  - Install with Parquet support:
      INVENTORY_EXTRAS=parquet ./preflight.sh
  - Install dev extras (if defined later):
      INVENTORY_EXTRAS=dev ./preflight.sh

Common issues:
  - Python version < 3.11 -> Install Python 3.11+ and re-run
  - Missing pip for python3 -> python3 -m ensurepip --upgrade
  - Missing git -> Install git for your OS
  - Missing oci CLI -> Optional; install if needed for manual CLI workflows
OUT