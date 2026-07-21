"""Apply the bounded Agent Operations execution-history retention policy."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.db import AsyncSessionLocal
from app.services.agent_service import AGENT_RUN_HISTORY_LIMIT, prune_agent_run_history


async def prune_history() -> int | None:
    """Delete terminal agent runs when the governed schema is available.

    Fresh production deployments start the image before Alembic is invoked by
    the deployment orchestrator. Retention is maintenance, so it must not make
    an otherwise valid empty-database bootstrap impossible.
    """

    async with AsyncSessionLocal() as db:
        async with db.begin():
            agent_runs_table = await db.scalar(text("SELECT to_regclass('public.agent_runs')"))
            if agent_runs_table is None:
                return None
            return await prune_agent_run_history(db)


def main() -> None:
    """Run retention before the API accepts traffic."""

    deleted = asyncio.run(prune_history())
    if deleted is None:
        print("Agent execution retention deferred: the governed schema is not installed yet.")
    else:
        print(
            f"Agent execution retention ready: latest {AGENT_RUN_HISTORY_LIMIT} terminal runs retained; "
            f"{deleted} expired run(s) removed."
        )


if __name__ == "__main__":
    main()
