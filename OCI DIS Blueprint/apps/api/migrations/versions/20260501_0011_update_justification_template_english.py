"""Update deterministic justification template text to English US."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260501_0011"
down_revision = "20260501_0010"
branch_labels = None
depends_on = None


ENGLISH_TEMPLATE: dict[str, object] = {
    "summary": (
        "The integration {interface_name} connects {source_system} to {destination_system} "
        "and currently has QA status {qa_status}."
    ),
    "blocks": [
        {
            "title": "Context",
            "body": (
                "Interface {interface_id} supports brand {brand} within business process {business_process}. "
                "It runs at frequency {frequency} with {payload_text}."
            ),
        },
        {
            "title": "Pattern",
            "body": "Documented pattern: {pattern_label}. Rationale: {pattern_rationale}.",
        },
        {
            "title": "Implementation",
            "body": (
                "Type {type}, trigger {trigger_type}, and core tools {core_tools}. "
                "Retry policy: {retry_policy}."
            ),
        },
        {
            "title": "QA Governance",
            "body": "QA status {qa_status}. Observations: {qa_reasons}.",
        },
    ],
}

def _prompt_templates() -> sa.Table:
    return sa.table(
        "prompt_template_versions",
        sa.column("version", sa.String()),
        sa.column("template_config", sa.JSON()),
    )


def upgrade() -> None:
    prompt_templates = _prompt_templates()
    op.execute(
        prompt_templates.update()
        .where(prompt_templates.c.version == "1.0.0")
        .values(template_config=ENGLISH_TEMPLATE)
    )


def downgrade() -> None:
    # Keep deterministic narratives in English US even when rolling back this data patch.
    pass
