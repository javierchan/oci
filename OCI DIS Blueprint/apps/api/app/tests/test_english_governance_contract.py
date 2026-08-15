"""Regression guards for the App-owned English governance contract."""

from app.migrations.reference_seed_data import DICTIONARY_OPTIONS
from app.models.project import IntegrationStatus, QAStatus
from app.core.calc_engine import evaluate_qa, normalize_controlled_value, normalize_frequency


def _values(category: str) -> list[str]:
    return [str(item["value"]) for item in DICTIONARY_OPTIONS if item["category"] == category]


def test_system_dictionaries_publish_only_canonical_english_values() -> None:
    assert _values("QA_STATUS") == ["OK", "REVIEW", "PENDING"]
    assert _values("COMPLEXITY") == ["Low", "Medium", "High"]
    assert _values("FREQUENCY") == [
        "Every 5 minutes",
        "Every 15 minutes",
        "Every 20 minutes",
        "Every 30 minutes",
        "Every hour",
        "Every 2 hours",
        "Every 4 hours",
        "Every 6 hours",
        "Every 8 hours",
        "Every 12 hours",
        "Once per day",
        "Weekly",
        "Biweekly",
        "Monthly",
        "Real Time",
        "On Demand",
    ]


def test_domain_enums_and_qa_engine_use_english_workflow_values() -> None:
    assert {item.value for item in QAStatus} == {"OK", "REVIEW", "PENDING"}
    assert {item.value for item in IntegrationStatus} == {
        "Already Exists",
        "Target State",
        "In Review",
        "In Progress",
        "TBD",
        "Duplicate 1",
    }
    result = evaluate_qa(
        interface_id=None,
        trigger_type=None,
        selected_pattern=None,
        pattern_rationale=None,
        core_tools=None,
        payload_per_execution_kb=None,
        is_fan_out=None,
        fan_out_targets=None,
    )
    assert result.status == "REVIEW"


def test_legacy_workbook_labels_are_input_aliases_not_output_values() -> None:
    frequency, frequency_event = normalize_frequency("Una vez al día")
    status, status_event = normalize_controlled_value("status", "En Revisión")

    assert frequency == "Once per day"
    assert status == "In Review"
    assert frequency_event is not None
    assert status_event is not None
