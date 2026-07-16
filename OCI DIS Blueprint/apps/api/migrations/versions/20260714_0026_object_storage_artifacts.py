"""Persist authoritative Object Storage references for imported workbooks."""

from alembic import op
import sqlalchemy as sa


revision = "20260714_0026"
down_revision = "20260714_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column("storage_reference", sa.String(length=2048)),
    )


def downgrade() -> None:
    op.drop_column("import_batches", "storage_reference")
