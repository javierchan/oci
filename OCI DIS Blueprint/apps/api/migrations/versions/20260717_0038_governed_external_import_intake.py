"""Stage external workbooks behind an approved mapping contract.

Revision ID: 20260717_0038
Revises: 20260717_0037
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260717_0038"
down_revision = "20260717_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("import_batches", sa.Column("candidate_count", sa.Integer(), nullable=True))
    op.add_column("import_batches", sa.Column("intake_mode", sa.String(length=32), nullable=False, server_default="official_template"))
    op.add_column("import_batches", sa.Column("mapping_contract", sa.JSON(), nullable=True))
    op.add_column("import_batches", sa.Column("mapping_profile_id", sa.String(length=36), nullable=True))
    op.add_column("import_batches", sa.Column("mapping_reviewed_by", sa.String(length=36), nullable=True))
    op.add_column("import_batches", sa.Column("mapping_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "import_mapping_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("header_fingerprint", sa.String(length=64), nullable=False, index=True),
        sa.Column("contract", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_import_mapping_profiles_project_fingerprint", "import_mapping_profiles", ["project_id", "header_fingerprint"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_import_mapping_profiles_project_fingerprint", table_name="import_mapping_profiles")
    op.drop_table("import_mapping_profiles")
    op.drop_column("import_batches", "mapping_reviewed_at")
    op.drop_column("import_batches", "mapping_reviewed_by")
    op.drop_column("import_batches", "mapping_profile_id")
    op.drop_column("import_batches", "mapping_contract")
    op.drop_column("import_batches", "intake_mode")
    op.drop_column("import_batches", "candidate_count")
