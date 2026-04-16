"""Focused QA-engine tests for workbook trigger semantics and activation rules."""

from ..engine.qa import evaluate_qa, normalize_trigger_type


def test_active_row_without_formal_id_still_gets_qa_evaluation() -> None:
    result = evaluate_qa(
        interface_id=None,
        trigger_type="REST Trigger",
        selected_pattern="#02",
        pattern_rationale="Valid architecture rationale.",
        core_tools="OIC Gen3, OCI Queue",
        payload_per_execution_kb=None,
        is_fan_out=False,
        fan_out_targets=None,
        uncertainty="TBD",
        is_active_row=True,
    )

    assert result.status == "REVISAR"
    assert "MISSING_ID_FORMAL" not in result.reasons
    assert "MISSING_PAYLOAD" in result.reasons
    assert "TBD_UNCERTAINTY" in result.reasons


def test_inactive_row_stays_outside_qa() -> None:
    result = evaluate_qa(
        interface_id=None,
        trigger_type=None,
        selected_pattern=None,
        pattern_rationale=None,
        core_tools=None,
        payload_per_execution_kb=None,
        is_fan_out=None,
        fan_out_targets=None,
        uncertainty=None,
        is_active_row=False,
    )

    assert result.status == "PENDING"
    assert result.reasons == []


def test_workbook_trigger_vocabulary_is_accepted() -> None:
    for trigger in ["REST Trigger", "SOAP Trigger", "Event Trigger", "Scheduled"]:
        result = evaluate_qa(
            interface_id="INT-001",
            trigger_type=trigger,
            selected_pattern="#02",
            pattern_rationale="Sufficient workbook-aligned rationale.",
            core_tools="OIC Gen3",
            payload_per_execution_kb=100.0,
            is_fan_out=False,
            fan_out_targets=None,
            uncertainty=None,
        )
        assert "INVALID_TRIGGER_TYPE" not in result.reasons


def test_unknown_trigger_text_remains_invalid() -> None:
    assert normalize_trigger_type("Something Else") is None
