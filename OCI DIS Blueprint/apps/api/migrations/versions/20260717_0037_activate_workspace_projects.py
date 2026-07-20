"""Normalize legacy workspace drafts to the editable project lifecycle."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260717_0037"
down_revision = "20260717_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Promote legacy drafts; project drafts were never a product-visible lifecycle."""

    op.execute(sa.text("UPDATE projects SET status = 'active' WHERE status = 'draft'"))


def downgrade() -> None:
    """Do not demote active projects: legacy draft provenance was not recorded."""
