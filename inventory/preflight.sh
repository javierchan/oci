#!/usr/bin/env bash
# Preflight setup for OCI Inventory project
# - Verifies prerequisites and installs missing OS-level tools (bootstrap)
# - Creates/uses .venv tied to the current Python major.minor
# - Installs project (editable) with all defined extras
# - Installs and verifies CLI tools (oci-inv, oci, mmdc)
# - Idempotent and CI-friendly
set -euo pipefail

# Logging helpers
info() { printf "[INFO] %s\n" "$*"; }
ok()   { printf "[OK]   %s\n" "$*"; }
warn() { printf "[WARN] %s\n" "$*"; }
err()  { printf "[ERROR] %s\n" "$*" >&2; }

MODE="${OCI_INV_MODE:-bootstrap}"
case "${MODE}" in
  bootstrap|check) ;;
  *)
    err "Invalid OCI_INV_MODE: ${MODE} (expected bootstrap or check)"
    exit 1
    ;;
esac

is_bootstrap() { [ "${MODE}" = "bootstrap" ]; }

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
REPO_ROOT="$(cd "${REPO_ROOT}" && pwd -P)"
cd "${REPO_ROOT}"

VENV_DIR="${REPO_ROOT}/.venv"
PY_VERSION_FILE="${VENV_DIR}/.python-version"

OS_NAME="$(uname -s 2>/dev/null || echo unknown)"
OS_ID=""
if [ "${OS_NAME}" = "Linux" ] && [ -f /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_ID="${ID:-}"
fi

APT_UPDATED=0

require_sudo() {
  if ! command -v sudo >/dev/null 2>&1; then
    err "sudo is required for package installation but was not found."
    exit 1
  fi
}

apt_install() {
  if ! is_bootstrap; then
    err "Missing required package(s): $* (OCI_INV_MODE=check)"
    exit 1
  fi
  case "${OS_ID}" in
    debian|ubuntu|linuxmint) ;;
    *)
      err "Automatic install not supported for this Linux distribution (ID=${OS_ID})."
      exit 1
      ;;
  esac
  require_sudo
  if [ "${APT_UPDATED}" -eq 0 ]; then
    info "Running apt-get update..."
    sudo apt-get update -y >/dev/null
    APT_UPDATED=1
  fi
  info "Installing packages via apt-get: $*"
  sudo apt-get install -y "$@" >/dev/null
}

brew_install() {
  if ! command -v brew >/dev/null 2>&1; then
    err "Homebrew is required but not found. Install it from https://brew.sh/ and retry."
    exit 1
  fi
  if ! is_bootstrap; then
    err "Missing required package(s): $* (OCI_INV_MODE=check)"
    exit 1
  fi
  info "Installing packages via Homebrew: $*"
  brew install "$@"
}

ensure_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    if ! is_bootstrap; then
      err "python3 is required but missing (OCI_INV_MODE=check)."
      exit 1
    fi
    if [ "${OS_NAME}" = "Darwin" ]; then
      brew_install python@3.12
    elif [ "${OS_NAME}" = "Linux" ]; then
      apt_install python3 python3-venv
    else
      err "Unsupported OS for automatic Python install: ${OS_NAME}"
      exit 1
    fi
  fi
  if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    err "Python 3.11+ required; detected: $(python3 --version 2>/dev/null || echo unknown)"
    exit 1
  fi
  if ! python3 -c 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("venv") else 1)'; then
    if ! is_bootstrap; then
      err "Python venv module missing (OCI_INV_MODE=check)."
      exit 1
    fi
    if [ "${OS_NAME}" = "Linux" ]; then
      apt_install python3-venv
    else
      err "Python venv module missing; reinstall Python 3.11+ with venv support."
      exit 1
    fi
  fi
  if ! python3 -c 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("ensurepip") else 1)'; then
    if ! is_bootstrap; then
      err "Python ensurepip module missing (OCI_INV_MODE=check)."
      exit 1
    fi
    if [ "${OS_NAME}" = "Linux" ]; then
      apt_install python3-venv
    else
      err "Python ensurepip module missing; reinstall Python 3.11+ with ensurepip support."
      exit 1
    fi
  fi
  ok "python3 detected: $(python3 --version 2>/dev/null | tr -d '\n')"
}

ensure_git() {
  if command -v git >/dev/null 2>&1; then
    ok "git detected: $(git --version | tr -d '\n')"
    return 0
  fi
  if [ "${OS_NAME}" = "Darwin" ]; then
    err "git is required. Install Command Line Tools: xcode-select --install"
    exit 1
  elif [ "${OS_NAME}" = "Linux" ]; then
    apt_install git
    ok "git installed: $(git --version | tr -d '\n')"
  else
    err "Unsupported OS for automatic git install: ${OS_NAME}"
    exit 1
  fi
}

ensure_nodejs() {
  if command -v npm >/dev/null 2>&1; then
    ok "npm detected: $(npm --version 2>/dev/null | tr -d '\n')"
    return 0
  fi
  if [ "${OS_NAME}" = "Darwin" ]; then
    brew_install node
  elif [ "${OS_NAME}" = "Linux" ]; then
    apt_install nodejs npm
  else
    err "Unsupported OS for automatic Node.js/npm install: ${OS_NAME}"
    exit 1
  fi
  if ! command -v npm >/dev/null 2>&1; then
    err "npm installation completed but npm not found on PATH."
    exit 1
  fi
  ok "npm installed: $(npm --version 2>/dev/null | tr -d '\n')"
}

ensure_mmdc() {
  if command -v mmdc >/dev/null 2>&1; then
    ok "mmdc detected: $(mmdc --version 2>/dev/null | tr -d '\n')"
    return 0
  fi
  if ! is_bootstrap; then
    err "mmdc is required but missing (OCI_INV_MODE=check)."
    exit 1
  fi
  info "Installing Mermaid CLI (@mermaid-js/mermaid-cli)..."
  if npm install -g @mermaid-js/mermaid-cli; then
    :
  elif command -v sudo >/dev/null 2>&1; then
    info "Retrying Mermaid CLI install with sudo..."
    if ! sudo npm install -g @mermaid-js/mermaid-cli; then
      info "Falling back to user prefix for Mermaid CLI..."
      npm install -g --prefix "${HOME}/.local" @mermaid-js/mermaid-cli
      export PATH="${HOME}/.local/bin:${PATH}"
    fi
  else
    info "Falling back to user prefix for Mermaid CLI..."
    npm install -g --prefix "${HOME}/.local" @mermaid-js/mermaid-cli
    export PATH="${HOME}/.local/bin:${PATH}"
  fi
  NPM_GLOBAL_BIN="$(npm bin -g 2>/dev/null || true)"
  if [ -n "${NPM_GLOBAL_BIN}" ]; then
    export PATH="${NPM_GLOBAL_BIN}:${PATH}"
  fi
  if ! command -v mmdc >/dev/null 2>&1; then
    err "mmdc installation completed but command not found on PATH."
    exit 1
  fi
  ok "mmdc installed: $(mmdc --version 2>/dev/null | tr -d '\n')"
}

ensure_venv() {
  local current_py_version=""
  current_py_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  local recreate=0
  if [ ! -d "${VENV_DIR}" ] || [ ! -f "${VENV_DIR}/bin/activate" ]; then
    recreate=1
  elif [ -f "${PY_VERSION_FILE}" ]; then
    if [ "$(cat "${PY_VERSION_FILE}")" != "${current_py_version}" ]; then
      recreate=1
    fi
  fi

  if [ "${recreate}" -eq 1 ]; then
    if ! is_bootstrap; then
      err "Virtualenv missing or incompatible (OCI_INV_MODE=check)."
      exit 1
    fi
    info "Creating virtual environment: ${VENV_DIR}"
    rm -rf "${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
  else
    info "Using existing virtual environment: ${VENV_DIR}"
  fi

  if [ ! -f "${VENV_DIR}/bin/activate" ]; then
    err "Virtual environment activation script not found: ${VENV_DIR}/bin/activate"
    exit 1
  fi

  # shellcheck source=/dev/null
  . "${VENV_DIR}/bin/activate"
  printf "%s\n" "${current_py_version}" > "${PY_VERSION_FILE}"
  ok "Activated virtual environment: ${VENV_DIR}"
}

ensure_pip() {
  if ! python -m pip --version >/dev/null 2>&1; then
    if ! is_bootstrap; then
      err "pip missing in virtualenv (OCI_INV_MODE=check)."
      exit 1
    fi
    info "Bootstrapping pip inside virtual environment..."
    if ! python -m ensurepip --upgrade >/dev/null 2>&1; then
      if [ "${OCI_INV_ALLOW_GET_PIP:-}" = "1" ]; then
        if ! command -v curl >/dev/null 2>&1; then
          err "curl is required for get-pip.py but was not found."
          exit 1
        fi
        info "ensurepip failed; using get-pip.py (OCI_INV_ALLOW_GET_PIP=1)..."
        curl -sSfL https://bootstrap.pypa.io/get-pip.py | python - >/dev/null 2>&1
      else
        err "ensurepip failed and OCI_INV_ALLOW_GET_PIP is not set."
        exit 1
      fi
    fi
  fi
  info "Upgrading pip, setuptools, wheel..."
  python -m pip install --upgrade pip setuptools wheel >/dev/null
  ok "Tooling upgraded: $(python -m pip --version | tr -d '\n')"
}

read_all_extras() {
  local tmp=""
  tmp="$(mktemp)"
  printf "%s\n" \
    "import tomllib" \
    "from pathlib import Path" \
    "data = tomllib.loads(Path(\"pyproject.toml\").read_text(encoding=\"utf-8\"))" \
    "extras = (data.get(\"project\") or {}).get(\"optional-dependencies\") or {}" \
    "print(\",\".join(sorted(extras)))" > "${tmp}"
  python "${tmp}"
  rm -f "${tmp}"
}

install_project() {
  local all_extras=""
  all_extras="$(read_all_extras)"
  if is_bootstrap; then
    if [ -n "${all_extras}" ]; then
      info "Installing project with all extras: ${all_extras}"
      python -m pip install -e "${REPO_ROOT}[${all_extras}]"
    else
      info "No extras defined; installing project only"
      python -m pip install -e "${REPO_ROOT}"
    fi
    ok "Project installed (editable)"
  else
    info "OCI_INV_MODE=check: skipping project installation."
  fi

  if printf ",%s," "${all_extras}" | grep -q ",parquet,"; then
    if python -c 'import pyarrow' >/dev/null 2>&1; then
      ok "pyarrow import check passed"
    else
      err "pyarrow not importable; Parquet support will fail."
      exit 1
    fi
  fi
  if printf ",%s," "${all_extras}" | grep -q ",wizard,"; then
    if python -c 'import rich' >/dev/null 2>&1; then
      ok "rich import check passed"
    else
      err "rich not importable; wizard CLI will fail."
      exit 1
    fi
  fi
}

ensure_oci_cli() {
  if is_bootstrap; then
    info "Installing OCI CLI inside virtual environment..."
    python -m pip install -U oci-cli >/dev/null
  fi
  if [ ! -x "${VENV_DIR}/bin/oci" ]; then
    err "OCI CLI binary not found in venv: ${VENV_DIR}/bin/oci"
    exit 1
  fi
  OCI_PATH="$(command -v oci || true)"
  case "${OCI_PATH}" in
    "${VENV_DIR}/bin/"*)
      ok "oci CLI detected in venv: $("${VENV_DIR}/bin/oci" --version 2>/dev/null | tr -d '\n')"
      ;;
    *)
      err "oci CLI on PATH is not from the virtual environment: ${OCI_PATH}"
      exit 1
      ;;
  esac
}

ensure_project_cli() {
  if ! command -v oci-inv >/dev/null 2>&1; then
    err "Project CLI 'oci-inv' not found on PATH after install."
    exit 1
  fi
  if ! oci-inv --help >/dev/null 2>&1; then
    err "oci-inv --help failed; installation may be broken."
    exit 1
  fi
  ok "oci-inv CLI available"
}

create_env_template() {
  local template="${REPO_ROOT}/inventory.env.example"
  if [ -f "${template}" ] || ! is_bootstrap; then
    return 0
  fi
  printf "%s\n" \
    "# Example config for OCI Inventory" \
    "" \
    "# Enable diagram generation (default: 1)" \
    "OCI_INV_DIAGRAMS=1" \
    "" \
    "# OneSubscription subscription ID for cost reports" \
    "OCI_INV_OSUB_SUBSCRIPTION_ID=<subscription_id>" \
    "" \
    "# Offline mode (no network at runtime)" \
    "OCI_INV_OFFLINE=0" \
    "" > "${template}"
  ok "Wrote configuration template: ${template}"
}

info "Checking prerequisites..."
ensure_python
ensure_git
ensure_nodejs
ensure_mmdc
ensure_venv
ensure_pip
ensure_oci_cli
install_project
ensure_project_cli

info "Skipping validation of OCI config (~/.oci/config) and GenAI YAML config."
create_env_template

printf "%s\n" \
  "[OK] Preflight complete." \
  "" \
  "Next steps:" \
  "  - Activate your virtual environment in new shells:" \
  "      . .venv/bin/activate" \
  "  - Show CLI help:" \
  "      oci-inv --help"
