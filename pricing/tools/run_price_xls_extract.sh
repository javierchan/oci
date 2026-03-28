#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SOURCE_DOCS_DIR="$ROOT_DIR/data/source-docs/current"
XLS_FILE="${1:-$SOURCE_DOCS_DIR/localizable_price_list.xls}"
OUT_DIR="$ROOT_DIR/data/xls-extract"

TMPDIR_EXTRACT="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_EXTRACT"' EXIT

python3 -m venv "$TMPDIR_EXTRACT/venv"
source "$TMPDIR_EXTRACT/venv/bin/activate"
python -m pip install -q xlrd

if [[ ! -f "$XLS_FILE" && -f "$SOURCE_DOCS_DIR/ORACLE+PAAS+AND+IAAS+PUBLIC+CLOUD+LOCALIZABLE+PRICE+LIST.xls" ]]; then
  XLS_FILE="$SOURCE_DOCS_DIR/ORACLE+PAAS+AND+IAAS+PUBLIC+CLOUD+LOCALIZABLE+PRICE+LIST.xls"
fi

if [[ ! -f "$XLS_FILE" ]]; then
  echo "Missing source workbook: $XLS_FILE" >&2
  exit 1
fi

python "$SCRIPT_DIR/extract_price_list_xls.py" \
  --xls-file "$XLS_FILE" \
  --out-dir "$OUT_DIR"

echo "XLS extraction written to $OUT_DIR"
