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


def test_scatter_gather_exceeds_parallel_limit() -> None:
    result = evaluate_qa(
        interface_id="TEST-001",
        trigger_type="REST",
        selected_pattern="#07",
        pattern_rationale="Parallel price aggregation across 8 suppliers with governed fallback handling.",
        core_tools="OIC Gen3",
        payload_per_execution_kb=50.0,
        is_fan_out=True,
        fan_out_targets=8,
        uncertainty=None,
    )

    assert "SCATTER_GATHER_EXCEEDS_OIC_PARALLEL_LIMIT" in result.reasons
    assert result.status == "REVISAR"


def test_streaming_payload_exceeds_1mb() -> None:
    result = evaluate_qa(
        interface_id="TEST-002",
        trigger_type="Event",
        selected_pattern="#02",
        pattern_rationale="Event-driven pub-sub for order events with replay support.",
        core_tools="OCI Streaming, OIC Gen3",
        payload_per_execution_kb=2048.0,
        is_fan_out=False,
        fan_out_targets=None,
        uncertainty=None,
    )

    assert "STREAMING_PAYLOAD_EXCEEDS_1MB_LIMIT" in result.reasons


def test_functions_payload_exceeds_6mb() -> None:
    result = evaluate_qa(
        interface_id="TEST-003",
        trigger_type="REST",
        selected_pattern="#03",
        pattern_rationale="API facade for document processing with partner-specific response shaping.",
        core_tools="Oracle Functions, OCI API Gateway",
        payload_per_execution_kb=8192.0,
        is_fan_out=False,
        fan_out_targets=None,
        uncertainty=None,
    )

    assert "FUNCTIONS_PAYLOAD_EXCEEDS_6MB_LIMIT" in result.reasons


def test_certified_data_mesh_requires_governed_evidence_and_overlays() -> None:
    result = evaluate_qa(
        interface_id="TEST-004",
        trigger_type="REST",
        selected_pattern="#12",
        pattern_rationale="TBD",
        core_tools="OCI Data Integration",
        payload_per_execution_kb=100.0,
        is_fan_out=False,
        fan_out_targets=None,
        uncertainty=None,
    )

    assert "BUSINESS_CRITICALITY_REQUIRED" in result.reasons
    assert "RETENTION_POLICY_REQUIRED" in result.reasons
    assert "DATA_CLASSIFICATION_REQUIRED" in result.reasons
    assert "PATTERN_OVERLAYS_NOT_CERTIFIED" in result.reasons


def test_claim_check_requires_retention_and_classification() -> None:
    result = evaluate_qa(
        interface_id="TEST-020",
        trigger_type="Event",
        selected_pattern="#20",
        pattern_rationale="Externalize large attachments and send only a governed object reference.",
        core_tools="OCI Object Storage, OCI Queue, OIC Gen3",
        payload_per_execution_kb=8192.0,
        is_fan_out=False,
        fan_out_targets=None,
        uncertainty=None,
    )

    assert "INVALID_PATTERN" not in result.reasons
    assert "RETENTION_POLICY_REQUIRED" in result.reasons
    assert "DATA_CLASSIFICATION_REQUIRED" in result.reasons


def test_dlq_pattern_is_ok_with_retry_and_idempotency_evidence() -> None:
    result = evaluate_qa(
        interface_id="TEST-021",
        trigger_type="Event",
        selected_pattern="#21",
        pattern_rationale="Bounded delivery retries isolate terminal failures for governed replay.",
        core_tools="OCI Queue, OIC Gen3",
        payload_per_execution_kb=100.0,
        is_fan_out=False,
        fan_out_targets=None,
        uncertainty=None,
        retry_policy="3 attempts; exponential backoff; DLQ",
        idempotency="Deduplicate by eventId for 7 days",
        additional_tools_overlays="OCI Observability",
    )

    assert result.status == "OK"
