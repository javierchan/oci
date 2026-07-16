"""Apply the bounded Agent Operations execution-history retention policy."""

from __future__ import annotations

import asyncio

from app.core.db import AsyncSessionLocal
from app.services.agent_service import AGENT_RUN_HISTORY_LIMIT, prune_agent_run_history


async def prune_history() -> int:
    """Delete terminal agent runs outside the governed history window."""

    async with AsyncSessionLocal() as db:
        async with db.begin():
            return await prune_agent_run_history(db)


def main() -> None:
    """Run retention before the API accepts traffic."""

    deleted = asyncio.run(prune_history())
    print(
        f"Agent execution retention ready: latest {AGENT_RUN_HISTORY_LIMIT} terminal runs retained; "
        f"{deleted} expired run(s) removed."
    )


if __name__ == "__main__":
    main()
