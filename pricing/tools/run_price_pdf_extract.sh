#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${TMPDIR:-/tmp}/pricing-pdf-venv"
OUT_DIR="$ROOT_DIR/data/price-list-extract"
SOURCE_DOCS_DIR="$ROOT_DIR/data/source-docs/current"
PRICE_LIST_PDF="${1:-$SOURCE_DOCS_DIR/global_price_list.pdf}"
SUPPLEMENT_PDF="${2:-$SOURCE_DOCS_DIR/global_price_list_supplement.pdf}"

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --quiet pypdf

if [[ ! -f "$PRICE_LIST_PDF" && -f "$SOURCE_DOCS_DIR/ORACLE+PAAS+AND+IAAS+PUBLIC+CLOUD+GLOBAL+PRICE+LIST.pdf" ]]; then
  PRICE_LIST_PDF="$SOURCE_DOCS_DIR/ORACLE+PAAS+AND+IAAS+PUBLIC+CLOUD+GLOBAL+PRICE+LIST.pdf"
fi

if [[ ! -f "$SUPPLEMENT_PDF" && -f "$SOURCE_DOCS_DIR/ORACLE+PAAS+AND+IAAS+PUBLIC+CLOUD+GLOBAL+PRICE+LIST+SUPPLEMENT.pdf" ]]; then
  SUPPLEMENT_PDF="$SOURCE_DOCS_DIR/ORACLE+PAAS+AND+IAAS+PUBLIC+CLOUD+GLOBAL+PRICE+LIST+SUPPLEMENT.pdf"
fi

if [[ ! -f "$PRICE_LIST_PDF" ]]; then
  echo "Missing price list PDF: $PRICE_LIST_PDF" >&2
  exit 1
fi

if [[ ! -f "$SUPPLEMENT_PDF" ]]; then
  echo "Missing supplement PDF: $SUPPLEMENT_PDF" >&2
  exit 1
fi

python "$SCRIPT_DIR/extract_price_list_rules.py" \
  --price-list "$PRICE_LIST_PDF" \
  --supplement "$SUPPLEMENT_PDF" \
  --out-dir "$OUT_DIR"

echo "Artifacts written to $OUT_DIR"
