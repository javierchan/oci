"""Index captured product taxonomy and bounded SKU detail lookups.

Revision ID: 20260721_0048
Revises: 20260721_0047
Create Date: 2026-07-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260721_0048"
down_revision = "20260721_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_commercial_sku_product_name",
        "commercial_skus",
        [
            sa.text(
                "(COALESCE(NULLIF(metadata -> 'product_hierarchy' ->> -1, ''), display_name))"
            )
        ],
        unique=False,
    )
    op.create_index(
        "ix_commercial_sku_product_category",
        "commercial_skus",
        [
            sa.text(
                "(COALESCE(NULLIF(metadata -> 'product_hierarchy' ->> -2, ''), service_category))"
            )
        ],
        unique=False,
    )
    op.create_index(
        "ix_commercial_candidate_sku_created",
        "commercial_mapping_candidates",
        ["commercial_sku_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_sku_commercial_term_sku_created",
        "sku_commercial_terms",
        ["commercial_sku_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_service_product_sku_mapping_part",
        "service_product_sku_mappings",
        ["part_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_service_product_sku_mapping_part",
        table_name="service_product_sku_mappings",
    )
    op.drop_index(
        "ix_sku_commercial_term_sku_created",
        table_name="sku_commercial_terms",
    )
    op.drop_index(
        "ix_commercial_candidate_sku_created",
        table_name="commercial_mapping_candidates",
    )
    op.drop_index("ix_commercial_sku_product_category", table_name="commercial_skus")
    op.drop_index("ix_commercial_sku_product_name", table_name="commercial_skus")
