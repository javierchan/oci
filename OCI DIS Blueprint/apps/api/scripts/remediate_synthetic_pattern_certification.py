"""Repair pattern certification gaps in one existing synthetic project."""

from __future__ import annotations
# ruff: noqa: E402

import argparse
import asyncio
import json
from pathlib import Path
import sys

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.db import AsyncSessionLocal
from app.services.synthetic_service import remediate_synthetic_pattern_certification


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply governed canvas certification repairs to a synthetic project."
    )
    parser.add_argument("--project-id", required=True)
    return parser.parse_args()


async def _run(project_id: str) -> None:
    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await remediate_synthetic_pattern_certification(project_id, db)
    print(json.dumps(result, indent=2, sort_keys=True))


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args.project_id))


if __name__ == "__main__":
    main()
