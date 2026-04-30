"""Focused coverage for synthetic worker auto-cleanup behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.workers import synthetic_worker


class _FakeBeginContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class _FakeSession:
    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def begin(self) -> _FakeBeginContext:
        return _FakeBeginContext()


class _FakeSessionFactory:
    def __call__(self) -> _FakeSession:
        return _FakeSession()


def _job_result(
    *,
    status: str,
    cleanup_policy: str,
    project_id: str | None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id="job-1",
        status=status,
        project_id=project_id,
        finished_at=datetime.now(UTC),
        normalized_payload={"cleanup_policy": cleanup_policy},
    )


def test_execute_synthetic_generation_job_task_auto_cleans_ephemeral_job(monkeypatch) -> None:
    """Verify the worker auto-cleans the ephemeral smoke preset after completion."""

    calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(synthetic_worker, "AsyncSessionLocal", _FakeSessionFactory())

    async def fake_mark_running(job_id: str, db: object) -> None:
        calls.append(("running", job_id, db is not None))

    async def fake_run(job_id: str, db: object) -> SimpleNamespace:
        calls.append(("run", job_id, db is not None))
        return _job_result(
            status="completed",
            cleanup_policy="ephemeral_auto_cleanup",
            project_id="project-1",
        )

    async def fake_cleanup(job_id: str, actor_id: str, db: object) -> SimpleNamespace:
        calls.append(("cleanup", job_id, actor_id, db is not None))
        return _job_result(
            status="cleaned_up",
            cleanup_policy="ephemeral_auto_cleanup",
            project_id=None,
        )

    monkeypatch.setattr(synthetic_worker.synthetic_service, "mark_synthetic_job_running", fake_mark_running)
    monkeypatch.setattr(synthetic_worker.synthetic_service, "run_synthetic_generation_job", fake_run)
    monkeypatch.setattr(synthetic_worker.synthetic_service, "cleanup_synthetic_job", fake_cleanup)

    result = synthetic_worker.execute_synthetic_generation_job_task("job-1")

    assert result["status"] == "cleaned_up"
    assert result["project_id"] is None
    assert ("cleanup", "job-1", synthetic_worker.synthetic_service.SYNTHETIC_ACTOR_ID, True) in calls


def test_execute_synthetic_generation_job_task_keeps_manual_job_until_explicit_cleanup(monkeypatch) -> None:
    """Verify the worker does not auto-clean enterprise jobs with manual retention."""

    calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(synthetic_worker, "AsyncSessionLocal", _FakeSessionFactory())

    async def fake_mark_running(job_id: str, db: object) -> None:
        calls.append(("running", job_id, db is not None))

    async def fake_run(job_id: str, db: object) -> SimpleNamespace:
        calls.append(("run", job_id, db is not None))
        return _job_result(
            status="completed",
            cleanup_policy="manual",
            project_id="project-1",
        )

    async def fake_cleanup(job_id: str, actor_id: str, db: object) -> SimpleNamespace:
        raise AssertionError("Manual jobs must not auto-clean.")

    monkeypatch.setattr(synthetic_worker.synthetic_service, "mark_synthetic_job_running", fake_mark_running)
    monkeypatch.setattr(synthetic_worker.synthetic_service, "run_synthetic_generation_job", fake_run)
    monkeypatch.setattr(synthetic_worker.synthetic_service, "cleanup_synthetic_job", fake_cleanup)

    result = synthetic_worker.execute_synthetic_generation_job_task("job-1")

    assert result["status"] == "completed"
    assert result["project_id"] == "project-1"
