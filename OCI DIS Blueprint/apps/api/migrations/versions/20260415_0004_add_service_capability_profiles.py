"""Add service_capability_profiles table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260415_0004"
down_revision = "20260414_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_capability_profiles",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("service_id", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("sla_uptime_pct", sa.Float(), nullable=True),
        sa.Column("pricing_model", sa.String(200), nullable=True),
        sa.Column(
            "limits",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("architectural_fit", sa.Text(), nullable=True),
        sa.Column("anti_patterns", sa.Text(), nullable=True),
        sa.Column("interoperability_notes", sa.Text(), nullable=True),
        sa.Column("oracle_docs_urls", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_id"),
    )
    op.create_index(
        "ix_service_capability_profiles_service_id",
        "service_capability_profiles",
        ["service_id"],
    )
    op.create_index(
        "ix_service_capability_profiles_category",
        "service_capability_profiles",
        ["category"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_service_capability_profiles_category",
        table_name="service_capability_profiles",
    )
    op.drop_index(
        "ix_service_capability_profiles_service_id",
        table_name="service_capability_profiles",
    )
    op.drop_table("service_capability_profiles")
