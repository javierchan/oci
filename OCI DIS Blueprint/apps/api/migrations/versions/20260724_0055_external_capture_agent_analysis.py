"""Link grounded row-level agent analysis to external capture drafts."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260724_0055"
down_revision = "20260723_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_capture_drafts",
        sa.Column("agent_analysis_run_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "external_capture_drafts",
        sa.Column(
            "agent_analysis_evidence_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "external_capture_drafts",
        sa.Column("agent_analysis_payload", sa.JSON(), nullable=True),
    )
    op.add_column(
        "external_capture_drafts",
        sa.Column(
            "agent_analyzed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_external_capture_drafts_agent_analysis_run_id",
        "external_capture_drafts",
        "agent_runs",
        ["agent_analysis_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_external_capture_drafts_agent_analysis_run_id",
        "external_capture_drafts",
        ["agent_analysis_run_id"],
        unique=False,
    )
    # Existing Capture Review evidence may contain workbook formulas. Preserve
    # only their header/classification as exclusion evidence; formula text must
    # never remain in the App's persisted operational row document.
    op.execute(
        sa.text(
            """
            WITH cleaned AS (
                SELECT
                    draft.id,
                    COALESCE(
                        jsonb_object_agg(source.key, source.value)
                            FILTER (
                                WHERE jsonb_typeof(source.value) <> 'string'
                                   OR left(ltrim(source.value #>> '{}'), 1) <> '='
                            ),
                        '{}'::jsonb
                    ) AS source_record,
                    COALESCE(
                        jsonb_agg(
                            jsonb_build_object(
                                'source_header', source.key,
                                'classification',
                                    CASE
                                        WHEN lower(source.key) ~ '(cost|costo|price|precio|usd)'
                                            THEN 'commercial_formula'
                                        ELSE 'formula'
                                    END,
                                'reason',
                                    CASE
                                        WHEN lower(source.key) ~ '(cost|costo|price|precio|usd)'
                                            THEN 'Commercial formula excluded from the App record; it is never evaluated or promoted.'
                                        ELSE 'Formula excluded from the App record; only source inputs may populate governed fields.'
                                    END,
                                'value_kind', 'formula'
                            )
                        ) FILTER (
                            WHERE jsonb_typeof(source.value) = 'string'
                              AND left(ltrim(source.value #>> '{}'), 1) = '='
                        ),
                        '[]'::jsonb
                    ) AS formula_exclusions
                FROM external_capture_drafts AS draft
                CROSS JOIN LATERAL jsonb_each(draft.source_record::jsonb) AS source
                GROUP BY draft.id
            )
            UPDATE external_capture_drafts AS draft
            SET
                source_record = cleaned.source_record::json,
                validation_evidence = (
                    COALESCE(draft.validation_evidence::jsonb, '{}'::jsonb)
                    || jsonb_build_object(
                        'excluded_source_fields',
                        COALESCE(
                            draft.validation_evidence::jsonb -> 'excluded_source_fields',
                            '[]'::jsonb
                        ) || cleaned.formula_exclusions
                    )
                )::json
            FROM cleaned
            WHERE draft.id = cleaned.id
              AND jsonb_array_length(cleaned.formula_exclusions) > 0
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_capture_drafts_agent_analysis_run_id",
        table_name="external_capture_drafts",
    )
    op.drop_constraint(
        "fk_external_capture_drafts_agent_analysis_run_id",
        "external_capture_drafts",
        type_="foreignkey",
    )
    op.drop_column("external_capture_drafts", "agent_analyzed_at")
    op.drop_column("external_capture_drafts", "agent_analysis_payload")
    op.drop_column("external_capture_drafts", "agent_analysis_evidence_hash")
    op.drop_column("external_capture_drafts", "agent_analysis_run_id")
