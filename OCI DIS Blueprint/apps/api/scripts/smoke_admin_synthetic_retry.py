"""Run a bounded live retry smoke check for the Admin Synthetic Lab."""

from __future__ import annotations
# ruff: noqa: E402

import asyncio
import json
from pathlib import Path
import sys
import time
from typing import Any

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from app.core.db import AsyncSessionLocal
from app.schemas.synthetic import SyntheticGenerationJobCreateRequest
from app.services import synthetic_service
from smoke_admin_synthetic_lab import (
    SmokeCheckError,
    SmokeConfig,
    _cleanup_job,
    _healthcheck,
    _list_jobs,
    _parse_args,
    _request_json,
    _validate_cleaned_up_job,
    _validate_completed_manual_job,
    _validate_job_counts,
    _validate_presets,
    _validate_recent_jobs_contains,
    _wait_for_terminal_job,
)


async def _seed_failed_job(config: SmokeConfig) -> dict[str, Any]:
    """Persist a controlled failed source job for retry runtime validation."""

    request = SyntheticGenerationJobCreateRequest(
        preset_code=config.preset_code,
        project_name=f"Admin Synthetic Retry Smoke {int(time.time())}",
    )
    async with AsyncSessionLocal() as db:
        async with db.begin():
            created = await synthetic_service.create_synthetic_job(request, config.actor_id, db)
        async with db.begin():
            failed = await synthetic_service.mark_synthetic_job_failed(
                created.id,
                {
                    "detail": "Seeded failed job for bounded retry smoke validation.",
                    "source": "apps/api/scripts/smoke_admin_synthetic_retry.py",
                },
                db,
            )
    return failed.model_dump(mode="json")


def _retry_job(config: SmokeConfig, source_job_id: str) -> dict[str, Any]:
    """Invoke the real retry API for a previously failed synthetic job."""

    payload = _request_json(
        config,
        "POST",
        f"/api/v1/admin/synthetic/jobs/{source_job_id}/retry",
    )
    if str(payload.get("id", "")) == source_job_id:
        raise SmokeCheckError("Retry returned the source job id instead of creating a new job.")
    if str(payload.get("status")) != "pending":
        raise SmokeCheckError(f"Retried job did not start in pending state: {payload}")
    return payload


def _validate_cleaned_up_failed_source_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Confirm a seeded failed source job was cleaned up without persisted artifacts."""

    if str(payload.get("status")) != "cleaned_up":
        raise SmokeCheckError(f"Expected cleaned_up source job after cleanup, got: {payload}")
    if payload.get("project_id") is not None:
        raise SmokeCheckError(f"Seeded failed source job unexpectedly retained a project_id: {payload}")
    result_summary = payload.get("result_summary")
    if not isinstance(result_summary, dict):
        raise SmokeCheckError(f"Seeded failed source job missing cleanup summary: {payload}")
    removed_paths = result_summary.get("cleanup_removed_paths")
    if removed_paths != []:
        raise SmokeCheckError(
            "Seeded failed source job should not report removed artifact paths: "
            f"{result_summary}"
        )
    return payload


def run_retry_smoke(config: SmokeConfig) -> dict[str, Any]:
    """Execute the bounded retry-runtime smoke contract against the live stack."""

    health = _healthcheck(config)
    preset_payload, matched_preset = _validate_presets(config)
    cleanup_policy = str(
        matched_preset.get("cleanup_policy", config.expected_cleanup_policy or "ephemeral_auto_cleanup")
    )
    _list_jobs(config)

    source_failed_job = asyncio.run(_seed_failed_job(config))
    source_job_id = str(source_failed_job["id"])
    if str(source_failed_job.get("status")) != "failed":
        raise SmokeCheckError(f"Seeded source job did not settle into failed status: {source_failed_job}")

    retried_job = _retry_job(config, source_job_id)
    retried_job_id = str(retried_job["id"])
    settled_retry_job = _wait_for_terminal_job(config, retried_job_id)

    if cleanup_policy == "manual":
        _validate_completed_manual_job(config, settled_retry_job, cleanup_policy)
        final_retry_job = _validate_cleaned_up_job(
            config,
            _cleanup_job(config, retried_job_id),
            cleanup_policy,
        )
        retry_cleanup_mode = "explicit"
    else:
        final_retry_job = _validate_cleaned_up_job(config, settled_retry_job, cleanup_policy)
        retry_cleanup_mode = "automatic"

    source_cleanup = _validate_cleaned_up_failed_source_job(_cleanup_job(config, source_job_id))
    _validate_job_counts(config, final_retry_job)

    recent_jobs = _list_jobs(config)
    _validate_recent_jobs_contains(source_job_id, recent_jobs)
    _validate_recent_jobs_contains(retried_job_id, recent_jobs)

    return {
        "ok": True,
        "source_job_id": source_job_id,
        "source_job_initial_status": "failed",
        "source_job_final_status": source_cleanup["status"],
        "retried_job_id": retried_job_id,
        "retried_job_status": final_retry_job["status"],
        "retry_cleanup_mode": retry_cleanup_mode,
        "cleanup_policy": cleanup_policy,
        "health": health,
        "preset_count": len(preset_payload["presets"]),
        "validation_results": final_retry_job["validation_results"],
    }


def main(argv: list[str] | None = None) -> int:
    config = _parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        result = run_retry_smoke(config)
    except SmokeCheckError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "base_url": config.base_url,
                    "preset_code": config.preset_code,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
