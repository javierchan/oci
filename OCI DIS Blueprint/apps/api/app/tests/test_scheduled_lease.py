from __future__ import annotations

from unittest.mock import Mock

from app.workers import scheduled_lease


def test_scheduled_task_lease_releases_only_owned_token(monkeypatch) -> None:
    client = Mock()
    client.set.return_value = True
    monkeypatch.setattr(scheduled_lease.redis, "from_url", Mock(return_value=client))

    with scheduled_lease.scheduled_task_lease("redis://test", "task-lock", 60) as acquired:
        assert acquired is True

    client.set.assert_called_once()
    client.eval.assert_called_once()
    assert client.eval.call_args.args[2] == "task-lock"
    client.close.assert_called_once()


def test_scheduled_task_lease_does_not_release_unowned_lock(monkeypatch) -> None:
    client = Mock()
    client.set.return_value = False
    monkeypatch.setattr(scheduled_lease.redis, "from_url", Mock(return_value=client))

    with scheduled_lease.scheduled_task_lease("redis://test", "task-lock", 60) as acquired:
        assert acquired is False

    client.eval.assert_not_called()
    client.close.assert_called_once()
