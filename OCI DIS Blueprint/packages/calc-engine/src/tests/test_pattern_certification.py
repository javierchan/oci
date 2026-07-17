"""Pattern certification contracts must stay complete and deterministic."""

from ..engine.pattern_certification import (
    CERTIFICATION_VERSION,
    PATTERN_CERTIFICATIONS,
    composition_issues,
    get_pattern_certification,
)


def test_all_governed_patterns_have_complete_certification_profiles() -> None:
    assert set(PATTERN_CERTIFICATIONS) == {f"#{index:02d}" for index in range(1, 22)}
    for pattern_id, profile in PATTERN_CERTIFICATIONS.items():
        assert profile.pattern_id == pattern_id
        assert profile.certification_version == CERTIFICATION_VERSION
        assert profile.sizing_strategy
        assert profile.approved_core_tool_groups
        assert profile.commercial_service_ids
        assert profile.validation_controls
        assert profile.summary


def test_unknown_custom_pattern_is_not_certified() -> None:
    assert get_pattern_certification("#22") is None
    assert composition_issues("#22", "OIC Gen3", None) == ("PATTERN_NOT_CERTIFIED",)


def test_composition_requires_certified_tools_and_overlays() -> None:
    assert composition_issues("#13", "OIC Gen3", "OCI API Gateway") == (
        "PATTERN_OVERLAYS_NOT_CERTIFIED",
    )
    assert composition_issues(
        "#13",
        "OIC Gen3",
        "OCI API Gateway, OCI IAM and Security Services",
    ) == ()


def test_canvas_json_is_supported_by_certification_matching() -> None:
    canvas = (
        '{"nodes": ['
        '{"toolKey": "OCI API Gateway"}, '
        '{"toolKey": "OCI IAM and Security Services"}'
        "]}"
    )
    assert composition_issues("#13", "OIC Gen3", canvas) == ()


def test_saved_canvas_key_lists_are_supported_by_certification_matching() -> None:
    canvas = (
        '{"coreToolKeys": ["OIC Gen3"], '
        '"overlayKeys": ["OCI API Gateway", "OCI IAM and Security Services"]}'
    )
    assert composition_issues("#13", canvas, canvas) == ()


def test_cqrs_supports_the_governed_orchestration_projection_stack() -> None:
    assert composition_issues(
        "#10",
        "OCI Streaming, OIC Gen3, OCI Data Integration",
        None,
    ) == ()
