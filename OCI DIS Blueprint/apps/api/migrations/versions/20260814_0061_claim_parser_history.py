"""Preserve service-limit claim history across parser versions.

Revision ID: 20260814_0061
Revises: 20260814_0060
Create Date: 2026-08-14
"""

from alembic import op


revision = "20260814_0061"
down_revision = "20260814_0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_service_limit_claim_source_hash",
        "service_limit_evidence_claims",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_service_limit_claim_source_hash_parser",
        "service_limit_evidence_claims",
        [
            "service_limit_id",
            "evidence_source_id",
            "source_content_hash",
            "parser_version",
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_service_limit_claim_source_hash_parser",
        "service_limit_evidence_claims",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_service_limit_claim_source_hash",
        "service_limit_evidence_claims",
        ["service_limit_id", "evidence_source_id", "source_content_hash"],
    )
