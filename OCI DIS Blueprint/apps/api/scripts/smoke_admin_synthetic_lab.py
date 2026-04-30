"""Run a bounded live smoke check for the Admin Synthetic Lab."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TERMINAL_JOB_STATUSES = {"completed", "failed", "cleaned_up"}


@dataclass(frozen=True)
class SmokeConfig:
    """Operator-configurable inputs for the admin synthetic smoke run."""

    base_url: str
    actor_id: str
    actor_role: str
    preset_code: str
    timeout_seconds: int
    poll_interval_seconds: float
    expected_catalog_count: int
    expected_import_count: int
    expected_manual_count: int
    expected_excluded_count: int
    expected_cleanup_policy: str | None
    min_distinct_systems: int


class SmokeCheckError(RuntimeError):
    """Raised when the bounded smoke contract fails."""


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def _decode_json(payload: bytes, context: str) -> dict[str, Any]:
    text = payload.decode("utf-8")
    if not text:
        return {}
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive failure path
        raise SmokeCheckError(f"{context} returned non-JSON payload: {text}") from exc
    if not isinstance(decoded, dict):
        raise SmokeCheckError(f"{context} returned unexpected JSON shape: {decoded!r}")
    return decoded


def _request_json(
    config: SmokeConfig,
    method: str,
    path: str,
    body: dict[str, object] | None = None,
    include_admin_headers: bool = True,
) -> dict[str, Any]:
    headers: dict[str, str] = {"Accept": "application/json"}
    if include_admin_headers:
        headers["X-Actor-Id"] = config.actor_id
        headers["X-Actor-Role"] = config.actor_role

    data: bytes | None = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    request = Request(f"{config.base_url}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            return _decode_json(response.read(), f"{method} {path}")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise SmokeCheckError(f"{method} {path} failed with HTTP {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise SmokeCheckError(f"{method} {path} could not reach the local stack: {exc}") from exc


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeCheckError(message)


def _healthcheck(config: SmokeConfig) -> dict[str, Any]:
    health = _request_json(config, "GET", "/health", include_admin_headers=False)
    _expect(str(health.get("status", "")).lower() == "ok", f"Unexpected health payload: {health}")
    return health


def _validate_presets(config: SmokeConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _request_json(config, "GET", "/api/v1/admin/synthetic/presets")
    presets = payload.get("presets")
    _expect(isinstance(presets, list), f"Preset response missing presets list: {payload}")
    matched_preset = next(
        (preset for preset in presets if isinstance(preset, dict) and preset.get("code") == config.preset_code),
        None,
    )
    _expect(matched_preset is not None, f"Preset catalog does not include {config.preset_code!r}.")
    if config.expected_cleanup_policy is not None:
        _expect(
            matched_preset.get("cleanup_policy") == config.expected_cleanup_policy,
            f"Preset {config.preset_code!r} cleanup policy mismatch: {matched_preset}",
        )
    _expect(
        int(matched_preset.get("target_catalog_size", -1)) == config.expected_catalog_count,
        f"Preset {config.preset_code!r} target mismatch: {matched_preset}",
    )
    return payload, matched_preset


def _list_jobs(config: SmokeConfig, limit: int = 20) -> dict[str, Any]:
    payload = _request_json(config, "GET", f"/api/v1/admin/synthetic/jobs?limit={limit}")
    jobs = payload.get("jobs")
    _expect(isinstance(jobs, list), f"Jobs response missing jobs list: {payload}")
    return payload


def _create_smoke_job(config: SmokeConfig) -> dict[str, Any]:
    payload = _request_json(
        config,
        "POST",
        "/api/v1/admin/synthetic/jobs",
        body={"preset_code": config.preset_code},
    )
    _expect(payload.get("preset_code") == config.preset_code, f"Unexpected create response: {payload}")
    job_id = payload.get("id")
    _expect(isinstance(job_id, str) and job_id, f"Create response missing job id: {payload}")
    return payload


def _wait_for_terminal_job(config: SmokeConfig, job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + config.timeout_seconds
    last_payload: dict[str, Any] | None = None

    while time.monotonic() < deadline:
        payload = _request_json(config, "GET", f"/api/v1/admin/synthetic/jobs/{job_id}")
        last_payload = payload
        if str(payload.get("status")) in TERMINAL_JOB_STATUSES:
            return payload
        time.sleep(config.poll_interval_seconds)

    raise SmokeCheckError(
        f"Timed out waiting for job {job_id} to settle. Last payload: {json.dumps(last_payload, indent=2)}"
    )


def _validate_job_counts(config: SmokeConfig, payload: dict[str, Any]) -> None:
    validation_results = payload.get("validation_results")
    _expect(isinstance(validation_results, dict), f"Job missing validation results: {payload}")
    _expect(
        int(validation_results.get("catalog_count", -1)) == config.expected_catalog_count,
        f"Catalog count mismatch: {validation_results}",
    )
    _expect(
        int(validation_results.get("import_included_count", -1)) == config.expected_import_count,
        f"Import count mismatch: {validation_results}",
    )
    _expect(
        int(validation_results.get("manual_count", -1)) == config.expected_manual_count,
        f"Manual count mismatch: {validation_results}",
    )
    _expect(
        int(validation_results.get("excluded_import_count", -1)) == config.expected_excluded_count,
        f"Excluded import count mismatch: {validation_results}",
    )
    _expect(
        int(validation_results.get("distinct_systems", -1)) >= config.min_distinct_systems,
        f"Distinct system coverage mismatch: {validation_results}",
    )
    _expect(
        bool(validation_results.get("meets_catalog_target")) is True,
        f"Job did not satisfy catalog target: {validation_results}",
    )
    _expect(
        bool(validation_results.get("meets_distinct_system_target")) is True,
        f"Job did not satisfy distinct-system target: {validation_results}",
    )

    pattern_ids = validation_results.get("covered_pattern_ids")
    _expect(
        isinstance(pattern_ids, list) and len(pattern_ids) == 17,
        f"Expected full pattern coverage, got: {validation_results}",
    )


def _validate_completed_manual_job(
    config: SmokeConfig,
    payload: dict[str, Any],
    cleanup_policy: str,
) -> dict[str, Any]:
    status = str(payload.get("status"))
    if status == "failed":
        raise SmokeCheckError(
            "Synthetic smoke job failed. "
            f"error_details={json.dumps(payload.get('error_details'), indent=2)}"
        )
    _expect(status == "completed", f"Expected completed terminal state before explicit cleanup, got {status!r}.")
    project_id = payload.get("project_id")
    _expect(isinstance(project_id, str) and project_id, f"Expected retained project_id before cleanup: {payload}")

    normalized_payload = payload.get("normalized_payload")
    _expect(isinstance(normalized_payload, dict), f"Job missing normalized payload: {payload}")
    _expect(
        normalized_payload.get("cleanup_policy") == cleanup_policy,
        f"Cleanup policy mismatch: {normalized_payload}",
    )

    _validate_job_counts(config, payload)
    return payload


def _validate_cleaned_up_job(
    config: SmokeConfig,
    payload: dict[str, Any],
    cleanup_policy: str,
) -> dict[str, Any]:
    status = str(payload.get("status"))
    if status == "failed":
        raise SmokeCheckError(
            "Synthetic smoke job failed. "
            f"error_details={json.dumps(payload.get('error_details'), indent=2)}"
        )
    _expect(status == "cleaned_up", f"Expected cleaned_up terminal state, got {status!r}.")
    _expect(payload.get("project_id") is None, f"Expected project_id to be null after cleanup: {payload}")

    normalized_payload = payload.get("normalized_payload")
    _expect(isinstance(normalized_payload, dict), f"Job missing normalized payload: {payload}")
    _expect(
        normalized_payload.get("cleanup_policy") == cleanup_policy,
        f"Cleanup policy mismatch: {normalized_payload}",
    )

    result_summary = payload.get("result_summary")
    _expect(isinstance(result_summary, dict), f"Job missing result summary: {payload}")
    removed_paths = result_summary.get("cleanup_removed_paths")
    _expect(
        isinstance(removed_paths, list) and len(removed_paths) > 0,
        f"Cleanup did not report removed artifact paths: {result_summary}",
    )

    _validate_job_counts(config, payload)
    return payload


def _cleanup_job(config: SmokeConfig, job_id: str) -> dict[str, Any]:
    payload = _request_json(config, "POST", f"/api/v1/admin/synthetic/jobs/{job_id}/cleanup")
    _expect(str(payload.get("status")) == "cleaned_up", f"Cleanup response did not clean the job: {payload}")
    return payload


def _validate_recent_jobs_contains(job_id: str, jobs_payload: dict[str, Any]) -> None:
    jobs = jobs_payload.get("jobs")
    _expect(isinstance(jobs, list), f"Jobs response missing list: {jobs_payload}")
    found = any(isinstance(job, dict) and job.get("id") == job_id for job in jobs)
    _expect(found, f"Recent jobs list does not include job {job_id!r}.")


def run_smoke(config: SmokeConfig) -> dict[str, Any]:
    """Execute the bounded admin synthetic smoke contract."""

    health = _healthcheck(config)
    preset_payload, matched_preset = _validate_presets(config)
    cleanup_policy = str(
        matched_preset.get("cleanup_policy", config.expected_cleanup_policy or "ephemeral_auto_cleanup")
    )
    _list_jobs(config)
    created_job = _create_smoke_job(config)
    job_id = str(created_job["id"])
    settled_job = _wait_for_terminal_job(config, job_id)
    final_job: dict[str, Any]
    cleanup_mode: str
    initial_terminal_status = str(settled_job.get("status"))
    if cleanup_policy == "manual":
        _validate_completed_manual_job(config, settled_job, cleanup_policy)
        final_job = _validate_cleaned_up_job(
            config,
            _cleanup_job(config, job_id),
            cleanup_policy,
        )
        cleanup_mode = "explicit"
    else:
        final_job = _validate_cleaned_up_job(config, settled_job, cleanup_policy)
        cleanup_mode = "automatic"
    recent_jobs = _list_jobs(config)
    _validate_recent_jobs_contains(job_id, recent_jobs)

    return {
        "ok": True,
        "job_id": job_id,
        "initial_terminal_status": initial_terminal_status,
        "status": final_job["status"],
        "cleanup_mode": cleanup_mode,
        "cleanup_policy": cleanup_policy,
        "health": health,
        "preset_count": len(preset_payload["presets"]),
        "cleanup_removed_paths": final_job["result_summary"]["cleanup_removed_paths"],
        "validation_results": final_job["validation_results"],
    }


def _parse_args(argv: list[str]) -> SmokeConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--actor-id", default="web-admin")
    parser.add_argument("--actor-role", default="Admin")
    parser.add_argument("--preset-code", default="ephemeral-smoke")
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument("--expected-catalog-count", type=int, default=18)
    parser.add_argument("--expected-import-count", type=int, default=12)
    parser.add_argument("--expected-manual-count", type=int, default=6)
    parser.add_argument("--expected-excluded-count", type=int, default=2)
    parser.add_argument("--expected-cleanup-policy")
    parser.add_argument("--min-distinct-systems", type=int, default=12)
    args = parser.parse_args(argv)

    return SmokeConfig(
        base_url=_normalize_base_url(args.base_url),
        actor_id=args.actor_id,
        actor_role=args.actor_role,
        preset_code=args.preset_code,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        expected_catalog_count=args.expected_catalog_count,
        expected_import_count=args.expected_import_count,
        expected_manual_count=args.expected_manual_count,
        expected_excluded_count=args.expected_excluded_count,
        expected_cleanup_policy=args.expected_cleanup_policy,
        min_distinct_systems=args.min_distinct_systems,
    )


def main(argv: list[str] | None = None) -> int:
    config = _parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        result = run_smoke(config)
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
