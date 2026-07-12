"""Deactivate legacy frequency records and enforce governed FQNN codes."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260711_0017"
down_revision = "20260710_0016"
branch_labels = None
depends_on = None


LEGACY_CODES = ("FREQ-02", "FREQ-03", "FREQ-04", "FREQ-08", "FREQ-09", "FREQ-13")


def upgrade() -> None:
    dictionary_options = sa.table(
        "dictionary_options",
        sa.column("category", sa.String()),
        sa.column("code", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.get_bind().execute(
        dictionary_options.update()
        .where(
            dictionary_options.c.category == "FREQUENCY",
            dictionary_options.c.code.in_(LEGACY_CODES),
        )
        .values(is_active=False, updated_at=sa.func.now())
    )
    op.create_check_constraint(
        "ck_dictionary_frequency_active_code",
        "dictionary_options",
        "category <> 'FREQUENCY' OR is_active = false OR code ~ '^FQ[0-9]{2}$'",
    )
    op.create_index(
        "uq_dictionary_frequency_active_code",
        "dictionary_options",
        ["code"],
        unique=True,
        postgresql_where=sa.text("category = 'FREQUENCY' AND is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_dictionary_frequency_active_code", table_name="dictionary_options")
    op.drop_constraint("ck_dictionary_frequency_active_code", "dictionary_options", type_="check")
    dictionary_options = sa.table(
        "dictionary_options",
        sa.column("category", sa.String()),
        sa.column("code", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.get_bind().execute(
        dictionary_options.update()
        .where(
            dictionary_options.c.category == "FREQUENCY",
            dictionary_options.c.code.in_(LEGACY_CODES),
        )
        .values(is_active=True, updated_at=sa.func.now())
    )
