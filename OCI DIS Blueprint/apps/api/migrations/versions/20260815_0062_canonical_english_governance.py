"""Canonicalize governed workflow values in English.

Revision ID: 20260815_0062
Revises: 20260814_0061
Create Date: 2026-08-15
"""

from alembic import op


revision = "20260815_0062"
down_revision = "20260814_0061"
branch_labels = None
depends_on = None


CATALOG_REPLACEMENTS = {
    "qa_status": {"REVISAR": "REVIEW"},
    "frequency": {
        "Cada 5 minutos": "Every 5 minutes",
        "Cada 15 minutos": "Every 15 minutes",
        "Cada 20 minutos": "Every 20 minutes",
        "Cada 30 minutos": "Every 30 minutes",
        "Cada 1 hora": "Every hour",
        "Cada 2 horas": "Every 2 hours",
        "Cada 4 horas": "Every 4 hours",
        "Cada 6 horas": "Every 6 hours",
        "Cada 8 horas": "Every 8 hours",
        "Cada 12 horas": "Every 12 hours",
        "Una vez al día": "Once per day",
        "Semanal": "Weekly",
        "Quincenal": "Biweekly",
        "Mensual": "Monthly",
        "Tiempo Real": "Real Time",
        "Bajo demanda": "On Demand",
    },
    "complexity": {"Bajo": "Low", "Medio": "Medium", "Alto": "High"},
    "initial_scope": {"Sí": "Yes", "Si": "Yes"},
    "status": {
        "Ya existe": "Already Exists",
        "Definitiva (End-State)": "Target State",
        "En Revisión": "In Review",
        "En Progreso": "In Progress",
        "Duplicado 1": "Duplicate 1",
    },
    "interface_status": {
        "Ya existe": "Already Exists",
        "Definitiva (End-State)": "Target State",
        "En Revisión": "In Review",
        "En Progreso": "In Progress",
        "Duplicado 1": "Duplicate 1",
    },
    "mapping_status": {
        "En análisis": "Under Analysis",
        "Mapeado": "Mapped",
        "Pendiente": "Pending",
    },
}

DICTIONARY_VALUES = {
    "FQ01": "Every 5 minutes", "FQ02": "Every 15 minutes",
    "FQ03": "Every 20 minutes", "FQ04": "Every 30 minutes",
    "FQ05": "Every hour", "FQ06": "Every 2 hours",
    "FQ07": "Every 4 hours", "FQ08": "Every 6 hours",
    "FQ09": "Every 8 hours", "FQ10": "Every 12 hours",
    "FQ11": "Once per day", "FQ12": "Weekly", "FQ13": "Biweekly",
    "FQ14": "Monthly", "FQ15": "Real Time", "FQ16": "On Demand",
    "CX01": "Low", "CX02": "Medium", "CX03": "High",
}


def _replace_json_tokens(table: str, column: str) -> None:
    replacements = {
        '"REVISAR"': '"REVIEW"',
        '"qa_revisar"': '"qa_review"',
        '"Sí"': '"Yes"',
        '"En Revisión"': '"In Review"',
        '"En Progreso"': '"In Progress"',
        '"En análisis"': '"Under Analysis"',
        '"Mapeado"': '"Mapped"',
        '"Pendiente"': '"Pending"',
    }
    expression = f"{column}::text"
    for old, new in replacements.items():
        old_sql = old.replace("'", "''")
        new_sql = new.replace("'", "''")
        expression = f"replace({expression}, '{old_sql}', '{new_sql}')"
    op.execute(
        f"UPDATE {table} SET {column} = ({expression})::json "
        f"WHERE {column} IS NOT NULL AND {column}::text <> ({expression})"
    )


def upgrade() -> None:
    for column, replacements in CATALOG_REPLACEMENTS.items():
        for old, new in replacements.items():
            old_sql = old.replace("'", "''")
            new_sql = new.replace("'", "''")
            op.execute(
                f"UPDATE catalog_integrations SET {column} = '{new_sql}' "
                f"WHERE {column} = '{old_sql}'"
            )

    # Derived workflow artifacts are mutable projections. Raw source rows and
    # audit history remain untouched for evidentiary traceability.
    for column in (
        "proposed_payload", "normalized_values", "pattern_assessment",
        "validation_evidence", "qa_preview", "agent_analysis_payload",
    ):
        _replace_json_tokens("external_capture_drafts", column)
    for table, column in (
        ("dashboard_snapshots", "charts"),
        ("dashboard_snapshots", "risks"),
        ("project_saved_views", "filters"),
        ("agent_runs", "context_payload"),
        ("agent_runs", "result_payload"),
        ("agent_artifacts", "payload"),
    ):
        _replace_json_tokens(table, column)

    # Keep one row per stable system code, preferring the already-canonical row.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY category, code
                       ORDER BY CASE WHEN value = 'REVIEW' THEN 0 ELSE 1 END,
                                created_at,
                                id
                   ) AS row_rank
            FROM dictionary_options
            WHERE code IS NOT NULL
        )
        DELETE FROM dictionary_options
        WHERE id IN (SELECT id FROM ranked WHERE row_rank > 1)
        """
    )
    op.execute(
        "UPDATE dictionary_options SET value = 'REVIEW', is_active = true "
        "WHERE category = 'QA_STATUS' AND code = 'QA02'"
    )
    for code, value in DICTIONARY_VALUES.items():
        category = "FREQUENCY" if code.startswith("FQ") else "COMPLEXITY"
        op.execute(
            f"UPDATE dictionary_options SET value = '{value}' "
            f"WHERE category = '{category}' AND code = '{code}'"
        )

    op.create_unique_constraint(
        "uq_dictionary_option_category_code",
        "dictionary_options",
        ["category", "code"],
    )


def downgrade() -> None:
    # English governed data remains valid on the previous application version;
    # only the schema guard must be reversed.
    op.drop_constraint(
        "uq_dictionary_option_category_code",
        "dictionary_options",
        type_="unique",
    )
