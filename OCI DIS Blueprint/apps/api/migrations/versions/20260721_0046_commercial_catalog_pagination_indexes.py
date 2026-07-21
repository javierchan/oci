"""Add indexes for bounded commercial-catalog review queries.

Revision ID: 20260721_0046
Revises: 20260720_0045
Create Date: 2026-07-21
"""

from alembic import op


revision = "20260721_0046"
down_revision = "20260720_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_commercial_candidate_document_part",
        "commercial_mapping_candidates",
        ["document_snapshot_id", "part_number"],
        unique=False,
    )
    op.create_index(
        "ix_commercial_candidate_document_status",
        "commercial_mapping_candidates",
        ["document_snapshot_id", "status"],
        unique=False,
    )
    # Deliberately no pg_trgm index: enabling a PostgreSQL extension is outside
    # this migration's compatibility scope. Equality/order pagination remains indexed.


def downgrade() -> None:
    op.drop_index("ix_commercial_candidate_document_status", table_name="commercial_mapping_candidates")
    op.drop_index("ix_commercial_candidate_document_part", table_name="commercial_mapping_candidates")
