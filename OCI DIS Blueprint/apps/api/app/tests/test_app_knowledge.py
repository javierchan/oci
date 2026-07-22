"""Deterministic coverage for the repository-derived App knowledge contract."""

from __future__ import annotations

from copy import deepcopy

from app.core.config import get_genai_settings_for_use_case, get_settings
from app.knowledge.builder import (
    DERIVED_PATH,
    _discover_repo_root,
    build_derived_manifest,
    load_curated_knowledge,
    validate_knowledge_base,
)
from app.services.app_knowledge_service import (
    build_app_knowledge_evidence,
    knowledge_grounding_failure,
)


def test_repo_root_discovery_is_safe_in_the_shallow_production_layout(tmp_path) -> None:
    """Importing the packaged knowledge module must not require monorepo depth."""

    packaged_knowledge = tmp_path / "app" / "knowledge"
    packaged_knowledge.mkdir(parents=True)

    assert _discover_repo_root(packaged_knowledge) == tmp_path


def test_committed_app_knowledge_matches_executable_contracts() -> None:
    """The committed manifest and curated references must match current code."""

    current = build_derived_manifest()
    assert DERIVED_PATH.is_file()
    assert validate_knowledge_base(load_curated_knowledge(), current) == []
    source_hash = current["source_hash"]
    assert isinstance(source_hash, str)
    assert source_hash in DERIVED_PATH.read_text(encoding="utf-8")


def test_app_knowledge_check_rejects_uncovered_route_and_stale_export() -> None:
    """A new route or inaccurate export claim must fail loudly in CI."""

    derived = build_derived_manifest()
    routes = derived["routes"]
    assert isinstance(routes, list)
    derived["routes"] = [
        *routes,
        {"route": "/new-unowned-surface", "source": "apps/web/app/new-unowned-surface/page.tsx"},
    ]
    curated = deepcopy(load_curated_knowledge())
    sections = curated["sections"]
    assert isinstance(sections, list)
    bom = next(item for item in sections if isinstance(item, dict) and item.get("id") == "bom")
    exports = bom["exports"]
    assert isinstance(exports, list) and isinstance(exports[0], dict)
    exports[0]["media_types"] = ["text/csv"]

    errors = validate_knowledge_base(curated, derived)

    assert "Next route has no curated knowledge owner: /new-unowned-surface" in errors
    assert any("does not expose media type text/csv" in error for error in errors)


def test_unknown_capability_returns_not_documented_and_rejects_invented_route() -> None:
    """Feature claims fail closed when no matching App knowledge exists."""

    evidence = build_app_knowledge_evidence(
        "Can the App deploy a Kubernetes cluster to Mars?",
        "/projects",
        language="en",
        project_id=None,
        integration_id=None,
    )

    assert evidence["documented"] is False
    assert "don't have that capability documented" in str(evidence["fallback_answer"])
    assert knowledge_grounding_failure(
        "The App can deploy it from [Launch](/admin/mars-deployments).",
        {"app_knowledge": evidence},
    ) == "unsupported_app_route"


def test_genai_model_overrides_are_isolated_by_use_case(monkeypatch) -> None:
    """Only support and knowledge maintenance use the larger model."""

    monkeypatch.setenv("OCI_GENAI_MODEL_ID", "openai.gpt-oss-20b")
    monkeypatch.setenv("OCI_GENAI_MODEL_NAME", "OpenAI gpt-oss-20b")
    monkeypatch.setenv("OCI_GENAI_SUPPORT_MODEL_ID", "openai.gpt-oss-120b")
    monkeypatch.setenv("OCI_GENAI_SUPPORT_MODEL_NAME", "OpenAI gpt-oss-120b")
    monkeypatch.setenv("OCI_GENAI_KNOWLEDGE_MODEL_ID", "openai.gpt-oss-120b")
    monkeypatch.setenv("OCI_GENAI_KNOWLEDGE_MODEL_NAME", "OpenAI gpt-oss-120b")
    get_settings.cache_clear()
    try:
        assert get_genai_settings_for_use_case("support_assistant").OCI_GENAI_MODEL_ID == "openai.gpt-oss-120b"
        assert get_genai_settings_for_use_case("knowledge_maintenance").OCI_GENAI_MODEL_ID == "openai.gpt-oss-120b"
        assert get_genai_settings_for_use_case("architecture_review").OCI_GENAI_MODEL_ID == "openai.gpt-oss-20b"
    finally:
        get_settings.cache_clear()
