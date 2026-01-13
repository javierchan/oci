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
# System pip is not strictly required; we will ensure pip inside the virtualenv.
if ! python3 -m pip --version >/dev/null 2>&1; then
  warn "System pip for python3 not found; will bootstrap pip inside the virtual environment."
else
  ok "pip detected: $(python3 -m pip --version | tr -d '\n')"
fi

# git
need_cmd git || { err "git is required"; exit 1; }
ok "git detected: $(git --version | tr -d '\n')"

# Mermaid CLI (optional; used for --validate-diagrams)
if command -v mmdc >/dev/null 2>&1; then
  ok "mmdc detected: $(mmdc --version 2>/dev/null | tr -d '\n')"
else
  warn "mmdc not found; Mermaid diagram syntax validation will be skipped."
  warn "(When mmdc is installed, oci-inv will validate all diagram*.mmd outputs automatically.)"
  warn "Install (macOS): npm install -g @mermaid-js/mermaid-cli"
fi


should_install_oci_cli() {
  case "${OCI_INV_INSTALL_OCI_CLI:-}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

is_offline() {
  case "${OCI_INV_OFFLINE:-}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

print_python_venv_help() {
  local os_name=""
  os_name="$(uname -s 2>/dev/null || echo unknown)"
  case "${os_name}" in
    Darwin)
      warn "macOS: ensure python3 includes venv/ensurepip (python.org installer or Homebrew)."
      warn "Homebrew: brew install python@3.12"
      ;;
    Linux)
      if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        case "${ID:-}" in
          debian|ubuntu|linuxmint)
            warn "Debian/Ubuntu: sudo apt-get install -y python3-venv or python3.<minor>-venv"
            ;;
          *)
            warn "Linux: install your distro's python3 venv/ensurepip package (often named python3-venv)."
            ;;
        esac
      else
        warn "Linux: install your distro's python3 venv/ensurepip package (often named python3-venv)."
      fi
      ;;
    *)
      warn "Install the Python venv/ensurepip components for your OS."
      ;;
  esac
}

VENV_WITHOUT_PIP=0
VENV_PIP_FLAG=""
PY_MISSING_MODULES="$(
  python3 -c 'import importlib.util; missing=[m for m in ("venv","ensurepip") if importlib.util.find_spec(m) is None]; print(",".join(missing))' 2>/dev/null || true
)"
if printf "%s" "${PY_MISSING_MODULES}" | grep -q "venv"; then
  err "Python venv module is missing; cannot create a virtual environment."
  print_python_venv_help
  exit 1
fi
if printf "%s" "${PY_MISSING_MODULES}" | grep -q "ensurepip"; then
  warn "Python ensurepip module is missing; venv will be created without pip."
  VENV_WITHOUT_PIP=1
  VENV_PIP_FLAG="--without-pip"
  if is_offline; then
    err "Offline mode enabled and ensurepip is unavailable; cannot bootstrap pip in venv."
    print_python_venv_help
    exit 1
  fi
  if ! command -v curl >/dev/null 2>&1; then
    err "curl is required to bootstrap pip when ensurepip is unavailable."
    print_python_venv_help
    exit 1
  fi
fi

if is_offline; then
  export PIP_NO_INDEX=1
  export PIP_DISABLE_PIP_VERSION_CHECK=1
  info "Offline mode enabled; network operations will be skipped when possible."
fi

# oci CLI (opt-in install; avoids changes outside .venv by default)
if command -v oci >/dev/null 2>&1; then
  ok "oci CLI detected: $(oci --version 2>/dev/null | tr -d '\n')"
else
  if should_install_oci_cli; then
    if is_offline; then
      warn "Offline mode enabled; skipping OCI CLI install."
    else
      info "oci CLI not found; installing non-interactively (no sudo)..."
      # Accept defaults (installs under $HOME and updates PATH in rc files). Avoid prompts.
      if bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)" -- --accept-all-defaults >/dev/null 2>&1; then
        export PATH="$HOME/bin:$PATH"
        ok "oci CLI installed: $(oci --version 2>/dev/null | tr -d '\n')"
      else
        err "oci CLI installation failed. Please install manually if needed:"
        err '  bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)" -- --accept-all-defaults'
        exit 1
      fi
    fi
  else
    warn "oci CLI not found; skipping install (set OCI_INV_INSTALL_OCI_CLI=1 to install)"
  fi
fi

# 2) Python virtual environment
VENV_DIR=".venv"
VENV_ACTIVATE=""
RECREATE_VENV=0
if [ -e "${VENV_DIR}" ] && [ ! -d "${VENV_DIR}" ]; then
  err "${VENV_DIR} exists but is not a directory; remove or rename it and retry."
  exit 1
fi
if [ -d "${VENV_DIR}" ]; then
  if [ -f "${VENV_DIR}/bin/activate" ]; then
    VENV_ACTIVATE="${VENV_DIR}/bin/activate"
    info "Using existing virtual environment: ${VENV_DIR}"
  elif [ -f "${VENV_DIR}/Scripts/activate" ]; then
    VENV_ACTIVATE="${VENV_DIR}/Scripts/activate"
    info "Using existing virtual environment: ${VENV_DIR}"
  else
    warn "Existing ${VENV_DIR} is missing activation scripts; recreating."
    RECREATE_VENV=1
  fi
fi
if [ "${RECREATE_VENV}" -eq 1 ]; then
  if python3 -m venv ${VENV_PIP_FLAG} --clear "${VENV_DIR}"; then
    ok "Virtual environment recreated"
  else
    err "Failed to recreate virtual environment."
    print_python_venv_help
    exit 1
  fi
  if [ -f "${VENV_DIR}/bin/activate" ]; then
    VENV_ACTIVATE="${VENV_DIR}/bin/activate"
  elif [ -f "${VENV_DIR}/Scripts/activate" ]; then
    VENV_ACTIVATE="${VENV_DIR}/Scripts/activate"
  else
    err "Virtual environment activation script not found after recreation."
    exit 1
  fi
fi
if [ -z "${VENV_ACTIVATE}" ]; then
  if [ "${VENV_WITHOUT_PIP}" -eq 1 ]; then
    info "Creating virtual environment without pip: ${VENV_DIR}"
  else
    info "Creating virtual environment: ${VENV_DIR}"
  fi
  if python3 -m venv ${VENV_PIP_FLAG} "${VENV_DIR}"; then
    ok "Virtual environment created"
  else
    err "Failed to create virtual environment."
    print_python_venv_help
    exit 1
  fi
  if [ -f "${VENV_DIR}/bin/activate" ]; then
    VENV_ACTIVATE="${VENV_DIR}/bin/activate"
  elif [ -f "${VENV_DIR}/Scripts/activate" ]; then
    VENV_ACTIVATE="${VENV_DIR}/Scripts/activate"
  else
    err "Virtual environment activation script not found after creation."
    exit 1
  fi
fi

# shellcheck source=/dev/null
# Activate venv for this script process
. "${VENV_ACTIVATE}"
ok "Activated virtual environment: ${VENV_DIR}"

# 3) Ensure/upgrade pip/setuptools/wheel inside venv
# Ensure pip present in venv
if ! command -v pip >/dev/null 2>&1; then
  info "Bootstrapping pip inside virtual environment..."
  if python -m ensurepip --upgrade >/dev/null 2>&1; then
    ok "ensurepip in venv succeeded"
  else
    if is_offline; then
      err "Offline mode enabled and ensurepip unavailable; cannot bootstrap pip in venv."
      exit 1
    else
      info "ensurepip unavailable; fetching get-pip.py to bootstrap pip in venv..."
      if curl -sSfL https://bootstrap.pypa.io/get-pip.py | python - >/dev/null 2>&1; then
        ok "get-pip.py succeeded"
      else
        err "Failed to bootstrap pip inside the virtual environment. Install python3-venv or python3-pip and retry."
        exit 1
      fi
    fi
  fi
fi
if is_offline; then
  warn "Offline mode enabled; skipping pip/setuptools/wheel upgrade."
else
  info "Upgrading pip, setuptools, wheel..."
  python -m pip install --upgrade pip setuptools wheel >/dev/null
  ok "Tooling upgraded: $(pip --version | tr -d '\n')"
fi

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

# 5) Optional sanity checks for extras/config
if printf "%s" "${EXTRAS_SPEC}" | grep -q "parquet"; then
  if ! python - <<'PY'
try:
    import pyarrow  # noqa: F401
except Exception as exc:
    raise SystemExit(1)
PY
  then
    warn "pyarrow not importable; Parquet export may fail. Install extras with INVENTORY_EXTRAS=parquet."
  else
    ok "pyarrow import check passed"
  fi
fi

find_genai_config() {
  if [ -n "${OCI_INV_GENAI_CONFIG:-}" ] && [ -f "${OCI_INV_GENAI_CONFIG}" ]; then
    printf "%s" "${OCI_INV_GENAI_CONFIG}"
    return 0
  fi
  if [ -f "$HOME/.config/oci-inv/genai.yaml" ]; then
    printf "%s" "$HOME/.config/oci-inv/genai.yaml"
    return 0
  fi
  if [ -f "${SCRIPT_DIR}/.local/genai.yaml" ]; then
    printf "%s" "${SCRIPT_DIR}/.local/genai.yaml"
    return 0
  fi
  return 1
}

if GENAI_PATH="$(find_genai_config)"; then
  ok "GenAI config detected: ${GENAI_PATH}"
else
  warn "GenAI config not found; GenAI features (genai-chat, --genai-summary) will be skipped. Set OCI_INV_GENAI_CONFIG or place ~/.config/oci-inv/genai.yaml."
fi

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
  - Install OCI CLI (opt-in):
      OCI_INV_INSTALL_OCI_CLI=1 ./preflight.sh
  - Offline mode (skip network actions):
      OCI_INV_OFFLINE=1 ./preflight.sh
  - Disable diagram generation (runtime):
      oci-inv run --no-diagrams
    Or set default via OCI_INV_DIAGRAMS=0
  - Provide OneSubscription subscription ID (runtime):
      oci-inv run --cost-report --osub-subscription-id <subscription_id>
    Or set default via OCI_INV_OSUB_SUBSCRIPTION_ID

Common issues:
  - Python version < 3.11 -> Install Python 3.11+ and re-run
  - Missing pip for python3 -> python3 -m ensurepip --upgrade
  - Missing git -> Install git for your OS
  - Missing oci CLI -> Optional; install if needed for manual CLI workflows
OUT
