"""Run resumable, single-row OCI QA for a governed external-capture session."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TERMINAL_RUN_STATES = {"completed", "failed", "cancelled"}
ANALYSIS_STATES = {"required", "current", "stale", "degraded"}


@dataclass(frozen=True)
class QaTarget:
    """One external-capture row that may require provider analysis."""

    draft_id: str
    source_row_number: int
    analysis_status: str


class ApiClient:
    """Small public-API client used by the resumable QA operator."""

    def __init__(self, base_url: str, *, actor_id: str, actor_role: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Actor-Id": actor_id,
            "X-Actor-Role": actor_role,
        }

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, object] | None = None,
        timeout: float = 30,
    ) -> dict[str, Any]:
        payload = json.dumps(body).encode() if body is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=payload,
            headers=self.headers,
            method=method,
        )
        with urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read())
        if not isinstance(value, dict):
            raise TypeError(f"Expected an object from {path}.")
        return value


def load_targets(
    client: ApiClient,
    *,
    project_id: str,
    session_id: str,
) -> list[QaTarget]:
    """Read every review row through the paginated public API."""

    targets: list[QaTarget] = []
    page = 1
    while True:
        query = urlencode({"page": page, "page_size": 100})
        payload = client.request(
            f"/projects/{project_id}/external-capture/sessions/{session_id}/drafts?{query}"
        )
        drafts = payload.get("drafts")
        if not isinstance(drafts, list):
            raise TypeError("External-capture draft page is missing drafts.")
        for draft in drafts:
            if not isinstance(draft, dict):
                continue
            analysis = draft.get("agent_analysis")
            if not isinstance(analysis, dict):
                continue
            status = str(analysis.get("status") or "")
            if status not in ANALYSIS_STATES:
                raise ValueError(f"Unsupported analysis status: {status}")
            targets.append(
                QaTarget(
                    draft_id=str(draft["id"]),
                    source_row_number=int(draft["source_row_number"]),
                    analysis_status=status,
                )
            )
        if len(targets) >= int(payload.get("total") or 0):
            break
        page += 1
    return targets


def run_target(
    client: ApiClient,
    *,
    project_id: str,
    session_id: str,
    target: QaTarget,
    poll_seconds: float,
    timeout_seconds: float,
) -> str:
    """Start and await one strictly focused Import Correction Agent run."""

    run = client.request(
        "/agents/runs",
        method="POST",
        body={
            "agent_type": "import_quality",
            "project_id": project_id,
            "context": {
                "external_capture_session_id": session_id,
                "external_capture_draft_id": target.draft_id,
            },
            "message": (
                f"Explain why source row {target.source_row_number} needs review. "
                "Use only this row's governed evidence, propose only supported "
                "formula-free corrections, and identify every human decision."
            ),
            "include_provider": True,
        },
    )
    run_id = str(run["id"])
    deadline = time.monotonic() + timeout_seconds
    status = str(run.get("status") or "")
    while status not in TERMINAL_RUN_STATES:
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"AgentRun {run_id} for source row {target.source_row_number} timed out."
            )
        time.sleep(poll_seconds)
        run = client.request(f"/agents/runs/{run_id}")
        status = str(run.get("status") or "")
    return status


def status_counts(targets: list[QaTarget]) -> dict[str, int]:
    """Return stable per-status counts for reconciliation."""

    return {
        status: sum(target.analysis_status == status for target in targets)
        for status in sorted(ANALYSIS_STATES)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--api-url", default="http://localhost:8000/api/v1")
    parser.add_argument("--actor-id", default="external-capture-provider-qa")
    parser.add_argument("--actor-role", default="Admin")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-degraded-retries", type=int, default=2)
    parser.add_argument("--max-runs", type=int)
    parser.add_argument("--report")
    args = parser.parse_args()

    client = ApiClient(
        args.api_url,
        actor_id=args.actor_id,
        actor_role=args.actor_role,
    )
    attempted: list[dict[str, object]] = []
    degraded_attempts: dict[str, int] = {}
    run_limit = args.max_runs if args.max_runs is not None else 10**9

    while len(attempted) < run_limit:
        targets = load_targets(
            client,
            project_id=args.project_id,
            session_id=args.session_id,
        )
        pending = [
            target
            for target in targets
            if target.analysis_status in {"required", "stale"}
            or (
                target.analysis_status == "degraded"
                and degraded_attempts.get(target.draft_id, 0)
                < args.max_degraded_retries
            )
        ]
        if not pending:
            break
        target = pending[0]
        if target.analysis_status == "degraded":
            degraded_attempts[target.draft_id] = (
                degraded_attempts.get(target.draft_id, 0) + 1
            )
        try:
            run_status = run_target(
                client,
                project_id=args.project_id,
                session_id=args.session_id,
                target=target,
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout_seconds,
            )
            outcome = {
                "draft_id": target.draft_id,
                "source_row_number": target.source_row_number,
                "previous_analysis_status": target.analysis_status,
                "run_status": run_status,
            }
        except (OSError, TimeoutError, TypeError, ValueError) as exc:
            outcome = {
                "draft_id": target.draft_id,
                "source_row_number": target.source_row_number,
                "previous_analysis_status": target.analysis_status,
                "run_status": "operator_error",
                "error": str(exc),
            }
        attempted.append(outcome)
        print(
            json.dumps(
                {
                    "attempt": len(attempted),
                    **outcome,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    final_targets = load_targets(
        client,
        project_id=args.project_id,
        session_id=args.session_id,
    )
    counts = status_counts(final_targets)
    report = {
        "project_id": args.project_id,
        "session_id": args.session_id,
        "total": len(final_targets),
        "attempted": len(attempted),
        "analysis_status_counts": counts,
        "operator_errors": sum(
            item.get("run_status") == "operator_error" for item in attempted
        ),
        "failed_runs": sum(item.get("run_status") == "failed" for item in attempted),
        "attempts": attempted,
    }
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if counts["required"] == 0 and counts["stale"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
