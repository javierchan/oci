#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${TMPDIR:-/tmp}/pricing-pdf-venv"
EXTRACT_DIR="$ROOT_DIR/data/price-list-extract"
OUT_FILE="$ROOT_DIR/data/rule-registry/rules.json"

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --quiet pypdf

python "$SCRIPT_DIR/build_rule_registry.py" \
  --extract-dir "$EXTRACT_DIR" \
  --out-file "$OUT_FILE"

echo "Rule registry written to $OUT_FILE"
