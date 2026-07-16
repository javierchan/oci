"""Seed coverage for workbook-derived governed reference data."""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.migrations.reference_seed_data import CANVAS_COMBINATIONS, DICTIONARY_OPTIONS
from app.migrations.seed import ASSUMPTION_SET, seed_assumption_set, seed_dictionary_options, seed_patterns
from app.models import AssumptionSet, Base, DictionaryOption, PatternDefinition


def test_reference_seed_is_idempotent_and_workbook_complete() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        first_pattern_count = seed_patterns(session)
        first_dictionary_count = seed_dictionary_options(session)
        second_pattern_count = seed_patterns(session)
        second_dictionary_count = seed_dictionary_options(session)
        session.commit()

        assert first_pattern_count == 21
        assert second_pattern_count == 0
        assert first_dictionary_count == len(DICTIONARY_OPTIONS)
        assert second_dictionary_count == 0

        pattern = session.scalar(
            select(PatternDefinition).where(PatternDefinition.pattern_id == "#01")
        )
        assert pattern is not None
        assert pattern.description
        assert pattern.when_to_use
        assert pattern.when_not_to_use
        assert pattern.technical_flow
        assert pattern.business_value

        tiempo_real = session.scalar(
            select(DictionaryOption).where(
                DictionaryOption.category == "FREQUENCY",
                DictionaryOption.code == "FQ15",
            )
        )
        assert tiempo_real is not None
        assert tiempo_real.executions_per_day == 24.0

        overlay = session.scalar(
            select(DictionaryOption).where(
                DictionaryOption.category == "OVERLAYS",
                DictionaryOption.code == "AO01",
            )
        )
        assert overlay is not None
        assert overlay.is_volumetric is True
        spanish_metadata_terms = (
            "Msgs/mes",
            "particiones",
            "Complemento",
            "Invocaciones",
            "GB procesados",
            "Cambios/mes",
            "Usar valor individual",
        )
        for option in session.scalars(select(DictionaryOption)).all():
            description = option.description or ""
            assert not any(term in description for term in spanish_metadata_terms)
        assert len(CANVAS_COMBINATIONS) == 27
        assert CANVAS_COMBINATIONS[3]["code"] == "G04"
        assert CANVAS_COMBINATIONS[3]["recommended_overlays"] == []
        covered_pattern_ids = {
            pattern_id
            for combination in CANVAS_COMBINATIONS
            for pattern_id in combination["compatible_pattern_ids"]
        }
        assert covered_pattern_ids == {f"#{index:02d}" for index in range(1, 22)}
        governed_overlay_codes = {
            option.code
            for option in session.scalars(
                select(DictionaryOption).where(DictionaryOption.category == "OVERLAYS")
            ).all()
        }
        assert governed_overlay_codes == {f"AO{index:02d}" for index in range(1, 10)}

    Base.metadata.drop_all(engine)


def test_assumption_seed_is_idempotent_and_contains_only_client_inputs() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        first_insert = seed_assumption_set(session)
        second_insert = seed_assumption_set(session)
        session.commit()

        assert first_insert == 1
        assert second_insert == 0

        assumption_set = session.scalar(
            select(AssumptionSet).where(AssumptionSet.version == ASSUMPTION_SET["version"])
        )
        assert assumption_set is not None
        assert assumption_set.assumptions["month_days"] == 31
        assert assumption_set.assumptions["functions_default_duration_ms"] == 2000
        assert assumption_set.assumptions["business_metadata"]
        assert "oic_billing_threshold_kb" not in assumption_set.assumptions
        assert "queue_max_message_kb" not in assumption_set.assumptions

    Base.metadata.drop_all(engine)
