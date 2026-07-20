"""Allow the approval-gated external intake status on legacy import batches.

Revision ID: 20260717_0039
Revises: 20260717_0038
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260717_0039"
down_revision = "20260717_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "import_batches",
        "status",
        existing_type=sa.String(length=10),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "import_batches",
        "status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
