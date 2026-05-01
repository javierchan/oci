"""Clean canvas dictionary governance records.

Revision ID: 20260501_0009
Revises: 20260501_0008
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260501_0009"
down_revision = "20260501_0008"
branch_labels = None
depends_on = None


DESCRIPTION_UPDATES = {
    "FQ01": "Type: Scheduled. Use for: explicit high frequency. Status: Valid.",
    "FQ02": "Type: Scheduled. Use for: explicit high frequency. Status: Valid.",
    "FQ03": "Type: Scheduled. Use for: explicit high frequency. Status: Valid.",
    "FQ04": "Type: Scheduled. Use for: explicit high frequency. Status: Valid.",
    "FQ05": "Type: Scheduled. Use for: standard frequency. Status: Valid.",
    "FQ06": "Type: Scheduled. Use for: standard frequency. Status: Valid.",
    "FQ07": "Type: Scheduled. Use for: standard frequency. Status: Valid.",
    "FQ08": "Type: Scheduled. Use for: standard frequency. Status: Valid.",
    "FQ09": "Type: Scheduled. Use for: standard frequency. Status: Valid.",
    "FQ10": "Type: Scheduled. Use for: standard frequency. Status: Valid.",
    "FQ11": "Type: Scheduled. Use for: standard frequency. Status: Valid.",
    "FQ12": "Type: Scheduled. Use for: low frequency. Status: Valid.",
    "FQ13": "Type: Scheduled. Use for: low frequency. Status: Valid.",
    "FQ14": "Type: Scheduled. Use for: low frequency. Status: Valid.",
    "FQ15": "Type: Event / continuous. Use for: equivalent batch proxy; validate final design. Status: Valid with caution.",
    "FQ16": "Type: Occasional. Use for: initial proxy; confirm later. Status: Valid with caution.",
    "T01": "Type: Core. Volumetry: direct. Metric/proxy: messages/month, packs/hour, peak/hour.",
    "T02": "Type: Core. Volumetry: direct. Metric/proxy: GB/month, partitions.",
    "T03": "Type: Add-on core service. Volumetry: direct. Metric/proxy: requests/month.",
    "T04": "Type: Add-on core service. Volumetry: direct. Metric/proxy: invocations and GB-seconds.",
    "T05": "Type: Core. Volumetry: direct. Metric/proxy: processed GB and pipeline runs.",
    "T06": "Type: Core / traditional. Volumetry: proxy. Metric/proxy: jobs/month (proxy).",
    "T07": "Type: Core / CDC. Volumetry: proxy. Metric/proxy: changes/month (proxy).",
    "AO01": "Type: Architectural overlay / proxy. Volumetry: proxy. Typical use: protected API ingress or egress. Capture rule: use one value; separate multiple values with commas.",
    "AO02": "Type: Architectural overlay / proxy. Volumetry: proxy. Typical use: stateful process or saga orchestration. Capture rule: use one value; separate multiple values with commas.",
    "AO03": "Type: Architectural overlay / proxy. Volumetry: proxy. Typical use: managed event routing. Capture rule: use one value; separate multiple values with commas.",
}

INVALID_CORE_TOOL_VALUES = (
    "OCI API Gateway",
    "Oracle Functions",
    "Oracle ORDS",
    "ATP",
    "Oracle DB",
    "SFTP",
    "OCI Object Storage",
    "OCI APM",
)


def upgrade() -> None:
    bind = op.get_bind()

    for code, description in DESCRIPTION_UPDATES.items():
        bind.execute(
            sa.text(
                """
                UPDATE dictionary_options
                   SET description = :description,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE code = :code
                """
            ),
            {"code": code, "description": description},
        )

    bind.execute(
        sa.text(
            """
            UPDATE dictionary_options
               SET is_active = FALSE,
                   updated_at = CURRENT_TIMESTAMP
             WHERE category = 'TOOLS'
               AND is_active = TRUE
               AND (
                 code IS NULL
                 OR code = ''
                 OR description IS NULL
                 OR description = ''
                 OR value IN :invalid_values
               )
            """
        ).bindparams(sa.bindparam("invalid_values", expanding=True)),
        {"invalid_values": INVALID_CORE_TOOL_VALUES},
    )

    bind.execute(
        sa.text(
            """
            UPDATE catalog_integrations
               SET core_tools = REPLACE(core_tools, 'Oracle Functions', 'OCI Functions'),
                   additional_tools_overlays = REPLACE(additional_tools_overlays, 'Oracle Functions', 'OCI Functions'),
                   updated_at = CURRENT_TIMESTAMP
             WHERE core_tools LIKE '%Oracle Functions%'
                OR additional_tools_overlays LIKE '%Oracle Functions%'
            """
        )
    )


def downgrade() -> None:
    """Data cleanup is intentionally not reversed."""
