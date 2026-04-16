"""Executable entrypoint for deterministic synthetic enterprise project seeding."""

from __future__ import annotations
# ruff: noqa: E402

import asyncio
import json
from pathlib import Path
import sys

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.db import AsyncSessionLocal
from app.services.synthetic_service import (
    DEFAULT_SYNTHETIC_SPEC,
    create_synthetic_enterprise_project,
)


async def _run() -> None:
    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await create_synthetic_enterprise_project(db, DEFAULT_SYNTHETIC_SPEC)
        print(
            json.dumps(
                {
                    "project_id": result.project_id,
                    "project_name": result.project_name,
                    "catalog_count": result.catalog_count,
                    "distinct_systems": result.distinct_systems,
                    "covered_pattern_ids": result.covered_pattern_ids,
                    "import_batch_id": result.import_batch_id,
                    "imported_snapshot_id": result.imported_snapshot_id,
                    "final_snapshot_id": result.final_snapshot_id,
                    "report_json_path": result.artifacts.report_json_path,
                    "report_markdown_path": result.artifacts.report_markdown_path,
                },
                indent=2,
            )
        )


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
