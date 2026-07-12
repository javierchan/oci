"""Persist governed prices and BOM amounts with exact decimal precision.

Revision ID: 20260712_0020
Revises: 20260712_0019
Create Date: 2026-07-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260712_0020"
down_revision = "20260712_0019"
branch_labels = None
depends_on = None


def _to_numeric(table: str, column: str, precision: int, scale: int) -> None:
    op.alter_column(
        table,
        column,
        existing_type=sa.Float(),
        type_=sa.Numeric(precision, scale),
        postgresql_using=f"{column}::numeric({precision},{scale})",
        existing_nullable=False,
    )


def upgrade() -> None:
    """Replace binary floating-point storage at pricing output boundaries."""

    _to_numeric("price_items", "value", 24, 10)
    op.alter_column(
        "price_items",
        "range_min",
        existing_type=sa.Float(),
        type_=sa.Numeric(24, 8),
        postgresql_using="range_min::numeric(24,8)",
        existing_nullable=True,
    )
    op.alter_column(
        "price_items",
        "range_max",
        existing_type=sa.Float(),
        type_=sa.Numeric(24, 8),
        postgresql_using="range_max::numeric(24,8)",
        existing_nullable=True,
    )
    for column in ("monthly_total", "annual_total", "contract_total"):
        _to_numeric("bom_snapshots", column, 24, 2)
    _to_numeric("bom_line_items", "quantity", 28, 8)
    _to_numeric("bom_line_items", "unit_price", 24, 10)
    for column in ("monthly_amount", "annual_amount", "contract_amount"):
        _to_numeric("bom_line_items", column, 24, 2)


def downgrade() -> None:
    """Restore binary floating point only for a deliberate rollback."""

    for table, columns in (
        ("bom_line_items", ("contract_amount", "annual_amount", "monthly_amount", "unit_price", "quantity")),
        ("bom_snapshots", ("contract_total", "annual_total", "monthly_total")),
        ("price_items", ("range_max", "range_min", "value")),
    ):
        for column in columns:
            op.alter_column(
                table,
                column,
                type_=sa.Float(),
                postgresql_using=f"{column}::double precision",
                existing_nullable=column in {"range_min", "range_max"},
            )
