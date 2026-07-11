"""Replace the retired OIC message-pack evidence URL with its canonical location."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260710_0015"
down_revision = "20260710_0014"
branch_labels = None
depends_on = None


OLD_URL = (
    "https://docs.oracle.com/en/cloud/paas/application-integration/"
    "oracle-integration-oci/message-pack-usage-and-synchronous-requests.html"
)
NEW_URL = (
    "https://docs.oracle.com/en/cloud/paas/application-integration/"
    "oracle-integration-oci/message-pack-usage-synchronous-requests.html"
)


def _evidence_sources() -> sa.TableClause:
    return sa.table(
        "service_evidence_sources",
        sa.column("url", sa.Text()),
        sa.column("last_checked_at", sa.DateTime(timezone=True)),
        sa.column("last_changed_at", sa.DateTime(timezone=True)),
        sa.column("content_hash", sa.String()),
        sa.column("status", sa.String()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )


def _replace_url(source_url: str, target_url: str) -> None:
    evidence_sources = _evidence_sources()
    op.get_bind().execute(
        evidence_sources.update()
        .where(evidence_sources.c.url == source_url)
        .values(
            url=target_url,
            last_checked_at=None,
            last_changed_at=None,
            content_hash=None,
            status="pending_verification",
            updated_at=sa.func.now(),
        )
    )


def upgrade() -> None:
    _replace_url(OLD_URL, NEW_URL)


def downgrade() -> None:
    _replace_url(NEW_URL, OLD_URL)
