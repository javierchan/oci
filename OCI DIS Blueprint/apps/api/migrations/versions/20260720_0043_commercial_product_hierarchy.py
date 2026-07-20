"""Version commercial document identity by parser revision.

Revision ID: 20260720_0043
Revises: 20260719_0042
"""

from alembic import op


revision = "20260720_0043"
down_revision = "20260719_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_commercial_document_kind_hash",
        "commercial_document_snapshots",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_commercial_document_kind_hash_parser",
        "commercial_document_snapshots",
        ["document_kind", "content_hash", "parser_version"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_commercial_document_kind_hash_parser",
        "commercial_document_snapshots",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_commercial_document_kind_hash",
        "commercial_document_snapshots",
        ["document_kind", "content_hash"],
    )
