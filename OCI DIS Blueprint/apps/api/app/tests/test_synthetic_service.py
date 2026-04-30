"""Focused coverage for deterministic synthetic dataset generation."""

from __future__ import annotations

import json

from app.services import synthetic_service


def test_generated_synthetic_dataset_meets_scale_and_coverage_targets() -> None:
    dataset = synthetic_service.generate_synthetic_dataset(synthetic_service.DEFAULT_SYNTHETIC_SPEC)
    validation = synthetic_service.validate_synthetic_dataset(dataset)

    assert len(dataset.import_rows) == 420
    assert len(dataset.manual_rows) == 60
    assert len(dataset.excluded_rows) == 36
    assert validation.catalog_count == 480
    assert validation.distinct_systems >= 70
    assert len(validation.covered_pattern_ids) == 17
    assert validation.max_canvas_state_length < 1000


def test_generated_smoke_dataset_meets_smoke_targets_and_full_pattern_coverage() -> None:
    dataset = synthetic_service.generate_synthetic_dataset(synthetic_service.SMOKE_SYNTHETIC_SPEC)
    validation = synthetic_service.validate_synthetic_dataset(dataset)

    assert len(dataset.import_rows) == 12
    assert len(dataset.manual_rows) == 6
    assert len(dataset.excluded_rows) == 2
    assert validation.catalog_count == 18
    assert validation.distinct_systems >= 12
    assert len(validation.covered_pattern_ids) == synthetic_service.SUPPORTED_PATTERN_COUNT
    assert validation.max_canvas_state_length < 1000


def test_canvas_state_is_compact_and_parseable_shape() -> None:
    payload = synthetic_service.build_canvas_state(
        ("OIC Gen3", "OCI Queue", "OCI Functions"),
        ("OCI API Gateway",),
        2048.0,
    )

    assert "\"v\":3" in payload
    assert "\"coreToolKeys\"" in payload
    assert "\"overlayKeys\"" in payload
    assert len(payload) < 1000


def test_canvas_state_uses_non_overlapping_route_positions() -> None:
    payload = synthetic_service.build_canvas_state(
        ("OCI Streaming", "OIC Gen3"),
        ("OCI Events",),
        54.0,
    )
    parsed = json.loads(payload)
    nodes = parsed["nodes"]

    assert [node["x"] for node in nodes] == sorted(node["x"] for node in nodes)
    assert {node["y"] for node in nodes} == {220}
    for left, right in zip(nodes, nodes[1:]):
        assert right["x"] - left["x"] >= 260
