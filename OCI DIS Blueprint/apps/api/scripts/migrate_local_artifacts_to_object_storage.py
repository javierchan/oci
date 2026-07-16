"""One-time, idempotent migration from legacy local artifact directories to S3."""

from __future__ import annotations
# ruff: noqa: E402

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import cast

from sqlalchemy import select

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.db import AsyncSessionLocal
from app.models import ImportBatch, PriceCatalogSnapshot, SyntheticGenerationJob
from app.services import storage_service


def _upload_exports(root: Path) -> tuple[int, int]:
    files_root = root / "exports" / "files"
    jobs_root = root / "exports" / "jobs"
    file_count = 0
    job_count = 0
    for metadata_path in sorted(jobs_root.glob("*.json")):
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        legacy_path = Path(str(payload.get("file_path", "")))
        artifact_path = files_root / legacy_path.name
        if artifact_path.is_file():
            reference = storage_service.put_bytes(
                f"exports/files/{artifact_path.name}",
                artifact_path.read_bytes(),
                metadata={
                    "project-id": str(payload.get("project_id", "")),
                    "snapshot-id": str(payload.get("snapshot_id", "")),
                },
            )
            payload.pop("file_path", None)
            payload["file_reference"] = reference
            file_count += 1
        storage_service.put_json(f"exports/jobs/{metadata_path.name}", payload)
        job_count += 1
    return file_count, job_count


async def _migrate_database_references(root: Path, reports_root: Path | None) -> dict[str, int]:
    counters = {"imports": 0, "rate_cards": 0, "synthetic_reports": 0}
    async with AsyncSessionLocal() as db, db.begin():
        batches = (
            await db.scalars(select(ImportBatch).where(ImportBatch.storage_reference.is_(None)))
        ).all()
        root_files = [path for path in root.iterdir() if path.is_file()]
        for batch in batches:
            source = next(
                (
                    path
                    for path in root_files
                    if path.name == batch.filename or path.name.endswith(f"-{batch.filename}")
                ),
                None,
            )
            if source is None:
                continue
            batch.storage_reference = storage_service.put_bytes(
                f"imports/{batch.project_id}/{source.name}",
                source.read_bytes(),
                metadata={"project-id": batch.project_id, "import-batch-id": batch.id},
            )
            counters["imports"] += 1

        rate_root = root / "pricing" / "rate-cards"
        for source in rate_root.glob("*.csv"):
            snapshot = await db.get(PriceCatalogSnapshot, source.stem)
            if snapshot is None:
                continue
            reference = storage_service.put_bytes(
                f"pricing/rate-cards/{source.name}",
                source.read_bytes(),
                content_type="text/csv",
                metadata={"snapshot-id": snapshot.id, "currency": snapshot.currency},
            )
            snapshot_metadata = dict(snapshot.snapshot_metadata or {})
            snapshot_metadata.pop("stored_path", None)
            snapshot_metadata["storage_reference"] = reference
            snapshot.snapshot_metadata = snapshot_metadata
            counters["rate_cards"] += 1

        if reports_root and reports_root.is_dir():
            jobs = (await db.scalars(select(SyntheticGenerationJob))).all()
            report_references: dict[str, str] = {}
            for source in reports_root.iterdir():
                if not source.is_file():
                    continue
                report_references[source.name] = storage_service.put_bytes(
                    f"synthetic/reports/{source.name}",
                    source.read_bytes(),
                )
                counters["synthetic_reports"] += 1
            for job in jobs:
                manifest = dict(job.artifact_manifest or {})
                changed = False
                for field in ("report_json_path", "report_markdown_path"):
                    value = str(manifest.get(field, ""))
                    reference = report_references.get(Path(value).name)
                    if reference:
                        manifest[field] = reference
                        changed = True
                if changed:
                    job.artifact_manifest = cast(dict[str, object], manifest)
    return counters


async def _run(uploads_root: Path, reports_root: Path | None) -> None:
    storage_service.ensure_bucket()
    export_files, export_jobs = _upload_exports(uploads_root)
    counters = await _migrate_database_references(uploads_root, reports_root)
    print(json.dumps({**counters, "export_files": export_files, "export_jobs": export_jobs}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uploads-root", type=Path, required=True)
    parser.add_argument("--reports-root", type=Path)
    arguments = parser.parse_args()
    asyncio.run(_run(arguments.uploads_root, arguments.reports_root))


if __name__ == "__main__":
    main()
