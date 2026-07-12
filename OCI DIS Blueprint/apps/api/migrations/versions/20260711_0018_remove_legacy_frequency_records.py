"""Remove superseded frequency dictionary rows after FQNN standardization."""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20260711_0018"
down_revision = "20260711_0017"
branch_labels = None
depends_on = None


LEGACY_ROWS = (
    ("a01571ac-fb2c-497d-a9cf-9bd1dc68e095", "FREQ-02", "2 veces al día", 2.0, 2),
    ("f9e7d3ca-0777-4649-90f1-6c8e113d859b", "FREQ-03", "4 veces al día", 4.0, 3),
    ("f5e89552-24b0-4f8a-8cf8-ed08eb745e38", "FREQ-04", "Cada hora", 24.0, 4),
    ("81cac22b-110a-48a4-840b-60a28ce3d224", "FREQ-08", "Cada minuto", 1440.0, 8),
    ("1f3f6e49-2f14-4030-b94a-e3cf1319e1dc", "FREQ-09", "Tiempo real", 1440.0, 9),
    ("f1d57a03-f66e-4737-8ad4-c2460a40894e", "FREQ-13", "TBD", None, 13),
)


def _dictionary_options() -> sa.TableClause:
    return sa.table(
        "dictionary_options",
        sa.column("id", sa.String()),
        sa.column("category", sa.String()),
        sa.column("code", sa.String()),
        sa.column("value", sa.String()),
        sa.column("description", sa.String()),
        sa.column("executions_per_day", sa.Float()),
        sa.column("is_volumetric", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
        sa.column("version", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )


def upgrade() -> None:
    dictionary_options = _dictionary_options()
    legacy_codes = tuple(row[1] for row in LEGACY_ROWS)
    op.get_bind().execute(
        dictionary_options.delete().where(
            dictionary_options.c.category == "FREQUENCY",
            dictionary_options.c.code.in_(legacy_codes),
            dictionary_options.c.is_active.is_(False),
        )
    )


def downgrade() -> None:
    dictionary_options = _dictionary_options()
    now = datetime.now(UTC)
    op.bulk_insert(
        dictionary_options,
        [
            {
                "id": row_id,
                "category": "FREQUENCY",
                "code": code,
                "value": value,
                "description": None,
                "executions_per_day": executions_per_day,
                "is_volumetric": None,
                "sort_order": sort_order,
                "is_active": False,
                "version": "1.0.0",
                "created_at": now,
                "updated_at": now,
            }
            for row_id, code, value, executions_per_day, sort_order in LEGACY_ROWS
        ],
    )
