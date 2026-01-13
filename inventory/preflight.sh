#!/usr/bin/env bash
# Preflight setup for OCI Inventory project
# - Verifies prerequisites
# - Creates/uses .venv
# - Installs project (editable) with all defined extras (mandatory)
# - Idempotent and CI-friendly
set -euo pipefail

# Logging helpers
info() { printf "[INFO] %s\n" "$*"; }
ok()   { printf "[OK]   %s\n" "$*"; }
warn() { printf "[WARN] %s\n" "$*"; }
err()  { printf "[ERROR] %s\n" "$*" >&2; }

# Resolve repo root (directory containing pyproject.toml)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"
if [ ! -f "${REPO_ROOT}/pyproject.toml" ]; then
  if [ -f "${REPO_ROOT}/inventory/pyproject.toml" ]; then
    REPO_ROOT="${REPO_ROOT}/inventory"
  else
    err "pyproject.toml not found under ${SCRIPT_DIR}; run this script from the inventory repo."
    exit 1
  fi
fi
cd "${REPO_ROOT}"

is_offline() {
  case "${OCI_INV_OFFLINE:-}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

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

ensure_nodejs() {
  if command -v npm >/dev/null 2>&1; then
    ok "npm detected: $(npm --version 2>/dev/null | tr -d '\n')"
    return 0
  fi
  if is_offline; then
    err "npm is required but missing, and offline mode is enabled."
    err "Install Node.js/npm and retry."
    exit 1
  fi
  local os_id=""
  if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    os_id="${ID:-}"
  fi
  case "${os_id}" in
    debian|ubuntu|linuxmint)
      if ! command -v apt-get >/dev/null 2>&1; then
        err "npm is required but apt-get was not found."
        err "Install Node.js/npm for your OS and retry."
        exit 1
      fi
      if [ "$(id -u)" -ne 0 ]; then
        if ! command -v sudo >/dev/null 2>&1; then
          err "npm is required but sudo is not available."
          err "Install Node.js/npm and retry:"
          err "  sudo apt-get update"
          err "  sudo apt-get install -y nodejs npm"
          exit 1
        fi
        if [ ! -t 0 ]; then
          err "npm is required but missing, and no TTY is available for sudo."
          err "Install Node.js/npm and retry:"
          err "  sudo apt-get update"
          err "  sudo apt-get install -y nodejs npm"
          exit 1
        fi
        info "Node.js/npm required. Allow sudo install? [y/N]"
        read -r install_node
        case "${install_node}" in
          y|Y|yes|YES)
            info "Requesting sudo authentication (input will be hidden)..."
            if ! sudo -v; then
              err "sudo authentication failed."
              exit 1
            fi
            info "Installing Node.js and npm via sudo apt-get..."
            if ! sudo apt-get update >/dev/null 2>&1; then
              err "apt-get update failed."
              exit 1
            fi
            if ! sudo apt-get install -y nodejs npm >/dev/null 2>&1; then
              err "apt-get install nodejs npm failed."
              exit 1
            fi
            ;;
          *)
            err "npm is required; install Node.js/npm and retry."
            exit 1
            ;;
        esac
      else
        info "Installing Node.js and npm via apt-get..."
        if ! apt-get update >/dev/null 2>&1; then
          err "apt-get update failed."
          exit 1
        fi
        if ! apt-get install -y nodejs npm >/dev/null 2>&1; then
          err "apt-get install nodejs npm failed."
          exit 1
        fi
      fi
      if command -v npm >/dev/null 2>&1; then
        ok "npm installed: $(npm --version 2>/dev/null | tr -d '\n')"
      else
        err "npm installation completed but npm not found on PATH."
        exit 1
      fi
      ;;
    *)
      err "npm is required but missing."
      err "Install Node.js/npm for your OS and retry."
      exit 1
      ;;
  esac
}

ensure_mmdc() {
  if command -v mmdc >/dev/null 2>&1; then
    ok "mmdc detected: $(mmdc --version 2>/dev/null | tr -d '\n')"
    return 0
  fi
  if is_offline; then
    err "mmdc is required but missing, and offline mode is enabled."
    err "Install Mermaid CLI and retry: npm install -g @mermaid-js/mermaid-cli"
    exit 1
  fi
  local npm_global_bin=""
  local npm_can_write=0
  npm_global_bin="$(npm bin -g 2>/dev/null || true)"
  if [ -n "${npm_global_bin}" ] && [ -w "${npm_global_bin}" ]; then
    npm_can_write=1
  fi
  if [ "${npm_can_write}" -eq 1 ]; then
    info "Installing Mermaid CLI (@mermaid-js/mermaid-cli) globally..."
    if ! npm install -g @mermaid-js/mermaid-cli; then
      err "Failed to install Mermaid CLI via npm."
      exit 1
    fi
    if [ -n "${npm_global_bin}" ]; then
      export PATH="${npm_global_bin}:${PATH}"
    fi
  else
    local use_sudo=""
    if command -v sudo >/dev/null 2>&1 && [ -t 0 ]; then
      info "Global npm prefix is not writable. Use sudo for global install? [y/N]"
      read -r use_sudo
    fi
    case "${use_sudo}" in
      y|Y|yes|YES)
        info "Requesting sudo authentication (input will be hidden)..."
        if ! sudo -v; then
          err "sudo authentication failed."
          exit 1
        fi
        info "Installing Mermaid CLI via sudo npm..."
        if ! sudo npm install -g @mermaid-js/mermaid-cli; then
          err "Failed to install Mermaid CLI via sudo npm."
          exit 1
        fi
        npm_global_bin="$(npm bin -g 2>/dev/null || true)"
        if [ -n "${npm_global_bin}" ]; then
          export PATH="${npm_global_bin}:${PATH}"
        fi
        ;;
      *)
        local user_prefix="${HOME}/.local"
        info "Installing Mermaid CLI to user prefix: ${user_prefix}"
        if ! npm install -g --prefix "${user_prefix}" @mermaid-js/mermaid-cli; then
          err "Failed to install Mermaid CLI via npm (user prefix)."
          exit 1
        fi
        export PATH="${user_prefix}/bin:${PATH}"
        ;;
    esac
  fi
  if command -v mmdc >/dev/null 2>&1; then
    ok "mmdc installed: $(mmdc --version 2>/dev/null | tr -d '\n')"
  else
    err "mmdc installation completed but command not found on PATH."
    err "Check npm global bin path and your PATH."
    exit 1
  fi
}

ensure_nodejs
ensure_mmdc

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

ensure_oci_cli() {
  local venv_bin=""
  venv_bin="$(python -c 'import sys, pathlib; print(pathlib.Path(sys.executable).parent)' 2>/dev/null || true)"
  if [ -z "${venv_bin}" ]; then
    err "Unable to determine virtual environment bin directory."
    exit 1
  fi
  if [ -x "${venv_bin}/oci" ]; then
    ok "oci CLI detected in venv: $("${venv_bin}/oci" --version 2>/dev/null | tr -d '\n')"
    return 0
  fi
  if is_offline; then
    err "oci CLI is required but missing, and offline mode is enabled."
    err "Install oci-cli in the venv when network access is available."
    exit 1
  fi
  info "Installing OCI CLI inside virtual environment..."
  if python -m pip install oci-cli; then
    if [ -x "${venv_bin}/oci" ]; then
      ok "oci CLI installed: $("${venv_bin}/oci" --version 2>/dev/null | tr -d '\n')"
    else
      err "oci CLI installation completed but command not found in venv."
      exit 1
    fi
  else
    err "Failed to install oci CLI via pip."
    exit 1
  fi
}

ensure_oci_cli

# 4) Install project (editable) with all defined extras (mandatory)
EXTRAS_SPEC=""
ALL_EXTRAS=""
if ! ALL_EXTRAS="$(python -c 'import tomllib, pathlib; data=tomllib.loads(pathlib.Path("pyproject.toml").read_text()); extras=sorted((data.get("project") or {}).get("optional-dependencies") or {}); print(",".join(extras))' 2>/dev/null)"; then
  err "Failed to read optional dependencies from pyproject.toml."
  exit 1
fi
if [ -n "${INVENTORY_EXTRAS:-}" ]; then
  warn "INVENTORY_EXTRAS is set but all extras are mandatory; ignoring override."
fi
if [ -n "${ALL_EXTRAS}" ]; then
  EXTRAS_SPEC=".[${ALL_EXTRAS}]"
  info "Installing with all extras: ${ALL_EXTRAS}"
else
  info "Installing without extras (none defined)"
fi

# Respect pyproject.toml as source of truth; do not generate lock files here
SETUP_TARGET="."
if ! python -m pip install -e "${SETUP_TARGET}${EXTRAS_SPEC}"; then
  err "pip install failed. Check network or index access."
  exit 1
fi
ok "Project installed (editable) ${EXTRAS_SPEC}"

# 5) Sanity checks for extras/config
if printf "%s" "${EXTRAS_SPEC}" | grep -q "parquet"; then
  if python -c 'import pyarrow' >/dev/null 2>&1; then
    ok "pyarrow import check passed"
  else
    err "pyarrow not importable; Parquet export will fail."
    exit 1
  fi
fi
if printf "%s" "${EXTRAS_SPEC}" | grep -q "wizard"; then
  if python -c 'import rich' >/dev/null 2>&1; then
    ok "rich import check passed"
  else
    err "rich not importable; wizard CLI will fail."
    exit 1
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
  if [ -f "${REPO_ROOT}/.local/genai.yaml" ]; then
    printf "%s" "${REPO_ROOT}/.local/genai.yaml"
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

Notes:
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
  - Missing npm/Node.js -> Install Node.js (npm is required for Mermaid CLI)
  - Offline mode with missing deps -> Disable offline mode or preinstall dependencies
OUT
