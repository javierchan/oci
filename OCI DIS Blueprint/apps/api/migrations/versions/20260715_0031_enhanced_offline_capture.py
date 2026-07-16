"""Adopt enhanced offline-capture fields and patterns 18 through 21."""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20260715_0031"
down_revision = "20260715_0030"
branch_labels = None
depends_on = None


PATTERNS = [
    ("#18", "Scheduled Batch / File Transfer", "BATCH / DATA", "Move governed datasets or files on a schedule with explicit processing windows and reprocessing controls.", "OIC Gen3 scheduled orchestration | OCI Data Integration | OCI Object Storage | SFTP endpoints"),
    ("#19", "Async Request-Reply (Correlation)", "ASYNCHRONOUS", "Accept a request immediately, process it asynchronously, and correlate a later callback or response.", "OCI Queue | OIC Gen3 | OCI Functions | callback or webhook endpoint"),
    ("#20", "Claim Check", "DELIVERY / PERFORMANCE", "Store a large payload securely and move a governed reference through the integration path.", "OCI Object Storage | OCI Streaming or OCI Queue | OIC Gen3"),
    ("#21", "DLQ / Retry with Backoff", "RESILIENCE / DELIVERY GUARANTEES", "Retry transient failures with bounded backoff, then isolate terminal failures in a governed dead-letter queue.", "OCI Queue | OIC Gen3 error handling | OCI Notifications | OCI Monitoring"),
]


def upgrade() -> None:
    for column_name, length in (
        ("business_criticality", 100),
        ("target_latency_sla", 255),
        ("data_security_classification", 255),
        ("retention_processing_window", 500),
        ("idempotency", 500),
    ):
        op.add_column("catalog_integrations", sa.Column(column_name, sa.String(length), nullable=True))

    bind = op.get_bind()
    table = sa.table(
        "pattern_definitions",
        sa.column("id", sa.String()),
        sa.column("pattern_id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("category", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("oci_components", sa.Text()),
        sa.column("when_to_use", sa.Text()),
        sa.column("when_not_to_use", sa.Text()),
        sa.column("technical_flow", sa.Text()),
        sa.column("business_value", sa.Text()),
        sa.column("applicability_examples", sa.JSON()),
        sa.column("selection_questions", sa.JSON()),
        sa.column("required_inputs", sa.JSON()),
        sa.column("is_system", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
        sa.column("version", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    for index, (pattern_id, name, category, description, components) in enumerate(PATTERNS, start=18):
        existing_id = bind.scalar(sa.text("SELECT id FROM pattern_definitions WHERE pattern_id = :pattern_id"), {"pattern_id": pattern_id})
        if existing_id is not None:
            bind.execute(
                sa.text(
                    "UPDATE pattern_definitions SET name=:name, category=:category, description=:description, "
                    "oci_components=:components, is_system=true, is_active=true, version='3.0.0', updated_at=:now "
                    "WHERE pattern_id=:pattern_id"
                ),
                {"pattern_id": pattern_id, "name": name, "category": category, "description": description, "components": components, "now": now},
            )
            continue
        bind.execute(table.insert().values(
            id=f"03100000-0000-4000-8000-{index:012d}",
            pattern_id=pattern_id,
            name=name,
            category=category,
            description=description,
            oci_components=components,
            when_to_use="See governed v3 offline workbook and Pattern Library guidance.",
            when_not_to_use="Do not approve without the required operational evidence and Service Product compatibility review.",
            technical_flow="Review the governed Pattern Library flow before implementation.",
            business_value="Adds an explicit, reviewable architecture choice for a common enterprise integration concern.",
            applicability_examples=[],
            selection_questions=[],
            required_inputs=[],
            is_system=True,
            is_active=True,
            version="3.0.0",
            created_at=now,
            updated_at=now,
        ))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM pattern_definitions WHERE pattern_id IN ('#18', '#19', '#20', '#21')"))
    for column_name in (
        "idempotency",
        "retention_processing_window",
        "data_security_classification",
        "target_latency_sla",
        "business_criticality",
    ):
        op.drop_column("catalog_integrations", column_name)
