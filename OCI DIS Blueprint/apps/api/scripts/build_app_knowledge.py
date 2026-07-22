#!/usr/bin/env python3
"""Generate or verify the deterministic App knowledge manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from app.knowledge.builder import (  # noqa: E402
    CURATED_PATH,
    DERIVED_PATH,
    _load_curated,
    build_derived_manifest,
    validate_knowledge_base,
    write_derived_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail when generated facts or curated links drift")
    args = parser.parse_args()
    current = build_derived_manifest(REPO_ROOT)
    errors = validate_knowledge_base(_load_curated(CURATED_PATH), current)
    if args.check:
        if not DERIVED_PATH.exists():
            errors.append(f"Missing generated manifest: {DERIVED_PATH}")
        else:
            committed = json.loads(DERIVED_PATH.read_text(encoding="utf-8"))
            if committed != current:
                errors.append("derived_app_knowledge.json is stale; regenerate it")
    else:
        write_derived_manifest(REPO_ROOT, DERIVED_PATH)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"App knowledge is consistent ({current['source_hash'][:12]}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
