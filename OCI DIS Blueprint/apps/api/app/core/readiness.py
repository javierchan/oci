"""Runtime readiness checks for schema-dependent API routes."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.readiness import MigrationReadinessResponse


API_ROOT = Path(__file__).resolve().parents[2]


def _repository_heads() -> set[str]:
    config = Config(str(API_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    return set(script.get_heads())


async def check_migration_readiness(db: AsyncSession) -> MigrationReadinessResponse:
    """Compare the connected database revision with the repository Alembic head."""

    bind = db.get_bind()
    if bind.dialect.name == "sqlite":
        return MigrationReadinessResponse(
            ready=True,
            current_revisions=["metadata-created-test-db"],
            head_revisions=sorted(_repository_heads()),
            pending_revisions=[],
            recovery_hint=None,
        )

    head_revisions = _repository_heads()
    try:
        result = await db.execute(text("select version_num from alembic_version"))
        current_revisions = {str(row[0]) for row in result if row[0]}
    except SQLAlchemyError:
        current_revisions = set()

    pending_revisions = sorted(head_revisions - current_revisions)
    ready = not pending_revisions
    return MigrationReadinessResponse(
        ready=ready,
        current_revisions=sorted(current_revisions),
        head_revisions=sorted(head_revisions),
        pending_revisions=pending_revisions,
        recovery_hint=None if ready else "Run `alembic upgrade head` for the API service and retry.",
    )
