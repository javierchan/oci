"""Export or verify the committed OpenAPI artifact for the API application."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = REPO_ROOT / "docs" / "api" / "openapi.yaml"


def build_openapi_text() -> str:
    """Return the runtime OpenAPI document serialized as YAML-compatible JSON text."""

    if str(API_ROOT) not in sys.path:
        sys.path.insert(0, str(API_ROOT))

    from app.main import app

    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    """Write or verify the committed OpenAPI artifact."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that the committed OpenAPI artifact matches the runtime spec.",
    )
    args = parser.parse_args()

    rendered = build_openapi_text()
    if args.check:
        if not OUTPUT_PATH.exists():
            print(f"Missing OpenAPI artifact: {OUTPUT_PATH}")
            return 1
        if OUTPUT_PATH.read_text(encoding="utf-8") != rendered:
            print(f"OpenAPI artifact is out of date: {OUTPUT_PATH}")
            return 1
        print(f"OpenAPI artifact is up to date: {OUTPUT_PATH}")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote OpenAPI artifact: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
