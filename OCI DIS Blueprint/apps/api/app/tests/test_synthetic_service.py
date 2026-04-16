"""Focused coverage for deterministic synthetic dataset generation."""

from __future__ import annotations

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
