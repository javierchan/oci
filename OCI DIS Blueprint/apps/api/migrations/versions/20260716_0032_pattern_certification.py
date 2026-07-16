"""Add governed overlays required by the pattern certification contracts."""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20260716_0032"
down_revision = "20260715_0031"
branch_labels = None
depends_on = None


OVERLAYS = (
    ("AO04", "OCI Object Storage", "Type: Architectural overlay. Typical use: payload staging, claim check, archival, or governed batch exchange.", True, 4),
    ("AO05", "OCI IAM and Security Services", "Type: Architectural overlay. Typical use: identity boundary, least privilege, secrets, and zero-trust policy.", False, 5),
    ("AO06", "OCI Observability", "Type: Architectural overlay. Typical use: metrics, logs, alarms, tracing, dead-letter monitoring, and operational evidence.", False, 6),
    ("AO07", "OCI Data Catalog", "Type: Architectural overlay. Typical use: data-product ownership, lineage, discovery, and event-contract governance.", False, 7),
    ("AO08", "OCI AI Services", "Type: External-capacity overlay. Typical use: governed inference or model-assisted enrichment; size the selected AI service separately.", False, 8),
    ("AO09", "OKE / Service Mesh", "Type: External-capacity overlay. Typical use: mTLS, mesh traffic policy, and platform-owned service routing; size OKE separately.", False, 9),
)


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    for index, (code, value, description, is_volumetric, sort_order) in enumerate(
        OVERLAYS, start=4
    ):
        existing_id = bind.scalar(
            sa.text(
                "SELECT id FROM dictionary_options WHERE category='OVERLAYS' AND value=:value"
            ),
            {"value": value},
        )
        values = {
            "code": code,
            "value": value,
            "description": description,
            "is_volumetric": is_volumetric,
            "sort_order": sort_order,
            "now": now,
        }
        if existing_id is not None:
            bind.execute(
                sa.text(
                    "UPDATE dictionary_options SET code=:code, description=:description, "
                    "is_volumetric=:is_volumetric, sort_order=:sort_order, is_active=true, "
                    "version='1.0.0', updated_at=:now WHERE id=:id"
                ),
                {**values, "id": existing_id},
            )
            continue
        bind.execute(
            sa.text(
                "INSERT INTO dictionary_options "
                "(id, category, code, value, description, executions_per_day, is_volumetric, "
                "sort_order, is_active, version, created_at, updated_at) VALUES "
                "(:id, 'OVERLAYS', :code, :value, :description, NULL, :is_volumetric, "
                ":sort_order, true, '1.0.0', :now, :now)"
            ),
            {**values, "id": f"03200000-0000-4000-8000-{index:012d}"},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM dictionary_options WHERE category='OVERLAYS' "
            "AND code IN ('AO04', 'AO05', 'AO06', 'AO07', 'AO08', 'AO09')"
        )
    )
