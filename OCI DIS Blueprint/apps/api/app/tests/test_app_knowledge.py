"""Deterministic coverage for the repository-derived App knowledge contract."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import cast

import pytest

from app.core.config import get_genai_settings_for_use_case, get_settings
from app.knowledge import builder as knowledge_builder
from app.knowledge.builder import (
    DERIVED_PATH,
    _discover_repo_root,
    build_derived_manifest,
    load_curated_knowledge,
    validate_knowledge_base,
)
from app.services import app_knowledge_service
from app.services.app_knowledge_service import (
    build_app_knowledge_evidence,
    knowledge_grounding_failure,
)
from app.services.genai_client import GenAiEmbeddingResult
from scripts.build_app_knowledge import (
    _discover_source_repo_root,
    _load_manifest_for_build,
    _preserve_matching_provider_embeddings,
    _provider_embedding_errors,
)


def test_repo_root_discovery_is_safe_in_the_shallow_production_layout(tmp_path) -> None:
    """Importing the packaged knowledge module must not require monorepo depth."""

    packaged_knowledge = tmp_path / "app" / "knowledge"
    packaged_knowledge.mkdir(parents=True)

    assert _discover_repo_root(packaged_knowledge) == tmp_path


def test_knowledge_build_script_uses_committed_manifest_in_shallow_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Provider enrichment must work without frontend sources in production."""

    api_root = tmp_path / "app-image"
    knowledge_dir = api_root / "app" / "knowledge"
    knowledge_dir.mkdir(parents=True)
    derived = knowledge_dir / "derived_app_knowledge.json"
    derived.write_text('{"schema_version":"2.0.0","retrieval_units":[]}', encoding="utf-8")
    monkeypatch.setattr("scripts.build_app_knowledge.API_ROOT", api_root)
    monkeypatch.setattr("scripts.build_app_knowledge.DERIVED_PATH", derived)

    assert _discover_source_repo_root(api_root) is None
    assert _load_manifest_for_build(provider_embeddings=True)["schema_version"] == "2.0.0"
    with pytest.raises(RuntimeError, match="requires a source checkout"):
        _load_manifest_for_build(provider_embeddings=False)


def test_committed_app_knowledge_matches_executable_contracts() -> None:
    """The committed manifest and curated references must match current code."""

    current = build_derived_manifest()
    assert DERIVED_PATH.is_file()
    assert validate_knowledge_base(load_curated_knowledge(), current) == []
    source_hash = current["source_hash"]
    assert isinstance(source_hash, str)
    assert source_hash in DERIVED_PATH.read_text(encoding="utf-8")


def test_knowledge_build_preserves_only_matching_provider_embeddings() -> None:
    """Deterministic regeneration must not erase or misapply cached OCI vectors."""

    current: dict[str, object] = {
        "embedding_spaces": {"local": {"model": "local"}},
        "retrieval_units": [
            {"id": "same", "text": "unchanged"},
            {"id": "changed", "text": "new evidence"},
            {"id": "new", "text": "new unit"},
        ],
    }
    committed: dict[str, object] = {
        "embedding_spaces": {
            "local": {"model": "local"},
            "provider": {"model": "oci-embed", "dimensions": 2},
        },
        "retrieval_units": [
            {
                "id": "same",
                "text": "unchanged",
                "provider_embedding": [0.1, 0.2],
            },
            {
                "id": "changed",
                "text": "old evidence",
                "provider_embedding": [0.3, 0.4],
            },
        ],
    }

    _preserve_matching_provider_embeddings(current, committed)

    units = current["retrieval_units"]
    assert isinstance(units, list)
    assert units[0]["provider_embedding"] == [0.1, 0.2]
    assert "provider_embedding" not in units[1]
    assert "provider_embedding" not in units[2]
    assert current["embedding_spaces"] == {
        "local": {"model": "local"},
        "provider": {"model": "oci-embed", "dimensions": 2},
    }


def test_provider_embedding_gate_requires_complete_matching_vector_space() -> None:
    settings = get_genai_settings_for_use_case("support_assistant")
    complete: dict[str, object] = {
        "embedding_spaces": {
            "provider": {
                "model": settings.OCI_GENAI_EMBEDDING_MODEL_NAME,
                "dimensions": 2,
            }
        },
        "retrieval_units": [
            {"id": "one", "provider_embedding": [0.1, 0.2]},
            {"id": "two", "provider_embedding": [0.3, 0.4]},
        ],
    }
    assert _provider_embedding_errors(complete) == []

    incomplete = deepcopy(complete)
    incomplete_units = cast(list[dict[str, object]], incomplete["retrieval_units"])
    incomplete_units[1].pop("provider_embedding")
    errors = _provider_embedding_errors(incomplete)
    assert any("lack provider embeddings" in error for error in errors)

    drifted = deepcopy(complete)
    embedding_spaces = cast(
        dict[str, dict[str, object]],
        drifted["embedding_spaces"],
    )
    embedding_spaces["provider"]["model"] = "stale-model"
    errors = _provider_embedding_errors(drifted)
    assert any("Provider embedding model drift" in error for error in errors)


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


@pytest.mark.asyncio
async def test_unknown_capability_returns_not_documented_and_rejects_invented_route() -> None:
    """Feature claims fail closed when no matching App knowledge exists."""

    evidence = await build_app_knowledge_evidence(
        "Can the App automatically provision the OCI resources in a BOM?",
        "/projects",
        language="en",
        project_id=None,
        integration_id=None,
    )

    assessment = evidence["capability_assessment"]
    assert isinstance(assessment, dict)
    assert assessment["status"] == "not_documented"
    assert "is not documented" in str(evidence["fallback_answer"])
    assert knowledge_grounding_failure(
        "The App can deploy it from [Launch](/admin/mars-deployments).",
        {"app_knowledge": evidence},
    ) == "unsupported_app_route"


@pytest.mark.asyncio
async def test_functional_questions_do_not_expose_raw_api_contracts_to_the_model() -> None:
    functional = await build_app_knowledge_evidence(
        "¿Cómo importo un archivo y reviso sus columnas?",
        "/projects",
        language="es",
        project_id=None,
        integration_id=None,
    )
    functional_entries = cast(list[object], functional["entries"])
    functional_matches = cast(list[object], functional["matches"])
    functional_top_match = cast(dict[str, object], functional["top_match"])
    assert all(
        "endpoints" not in entry
        for entry in functional_entries
        if isinstance(entry, dict)
    )
    assert all(
        "provider_embedding" not in match and "local_embedding" not in match
        for match in functional_matches
        if isinstance(match, dict)
    )
    assert "provider_embedding" not in functional_top_match
    assert "local_embedding" not in functional_top_match

    technical = await build_app_knowledge_evidence(
        "¿Qué endpoint REST uso para importar un archivo?",
        "/projects",
        language="es",
        project_id=None,
        integration_id=None,
    )
    technical_entries = cast(list[object], technical["entries"])
    assert any(
        isinstance(entry, dict) and entry.get("endpoints")
        for entry in technical_entries
    )


@pytest.mark.asyncio
async def test_capability_matching_uses_semantic_units_and_fails_closed() -> None:
    """Semantic retrieval resolves explicit capabilities and fails closed for unknowns."""

    documented = await build_app_knowledge_evidence(
        "Can I export a BOM as XLSX?",
        "/projects",
        language="en",
        project_id=None,
        integration_id=None,
    )
    assessment = documented["capability_assessment"]
    assert isinstance(assessment, dict)
    assert assessment["status"] == "documented"
    assert "export XLSX" in str(assessment["matched_actions"])
    assert knowledge_grounding_failure(
        str(documented["fallback_answer"]),
        {"app_knowledge": documented},
    ) is None

    unknown = await build_app_knowledge_evidence(
        "Can project users chat with each other inside the App?",
        "/projects",
        language="en",
        project_id=None,
        integration_id=None,
    )
    unknown_assessment = unknown["capability_assessment"]
    assert isinstance(unknown_assessment, dict)
    assert unknown_assessment["status"] == "not_documented"
    assert knowledge_grounding_failure(
        str(unknown["fallback_answer"]), {"app_knowledge": unknown}
    ) is None


@pytest.mark.asyncio
async def test_undocumented_cost_alert_uses_bom_as_the_closest_governed_workflow() -> None:
    """A missing alert feature must not drift into pricing or unrelated assumptions."""

    evidence = await build_app_knowledge_evidence(
        "Can I set up automated email alerts when cost exceeds a threshold?",
        "/projects",
        language="en",
        project_id=None,
        integration_id=None,
    )

    assessment = evidence["capability_assessment"]
    assert isinstance(assessment, dict)
    assert assessment["status"] == "not_documented"
    closest = assessment["closest_entry"]
    assert isinstance(closest, dict)
    assert closest["name"] == "BOM & Cost"
    assert "BOM & Cost" in str(evidence["fallback_answer"])
    wrapped: dict[str, object] = {"app_knowledge": evidence}
    assert knowledge_grounding_failure(
        "This feature is absent from the documented App capabilities.\n\n"
        "**Next action:** [Open BOM & Cost](/projects)",
        wrapped,
    ) is None
    assert knowledge_grounding_failure(
        "**Yes.** The App supports cost threshold alerts.\n\n"
        "**Next action:** [Open BOM & Cost](/projects)",
        wrapped,
    ) == "unsupported_app_capability"


@pytest.mark.asyncio
async def test_spanish_capture_and_agent_questions_keep_their_natural_intent() -> None:
    capture = await build_app_knowledge_evidence(
        "¿Cuándo debo usar Capture en vez de Import?",
        "/projects",
        language="es",
        project_id=None,
        integration_id=None,
    )
    assert capture["intent"] == "workflow_guidance"
    assert isinstance(capture["top_match"], dict)
    assert capture["top_match"]["section_id"] == "capture"

    agents = await build_app_knowledge_evidence(
        "¿Qué hacen los agentes de OCI DIS y qué no pueden cambiar?",
        "/admin/agents",
        language="es",
        project_id=None,
        integration_id=None,
    )
    assert agents["intent"] == "concept_explanation"
    assert isinstance(agents["top_match"], dict)
    assert agents["top_match"]["section_id"] == "agents"


@pytest.mark.asyncio
async def test_support_grounding_requires_one_real_next_action() -> None:
    """Provider prose cannot omit or duplicate the executable handoff."""

    evidence = await build_app_knowledge_evidence(
        "Can I create a new project?",
        "/projects",
        language="en",
        project_id=None,
        integration_id=None,
    )
    wrapped: dict[str, object] = {"app_knowledge": evidence}

    assert knowledge_grounding_failure(
        "Yes, the App supports project creation.",
        wrapped,
    ) == "invalid_next_action_count"
    assert knowledge_grounding_failure(
        "**Yes.** The App documents project creation.\n\n"
        "**Next action:** [Open Projects](/projects)\n\n"
        "**Next action:** [Open Projects](/projects)",
        wrapped,
    ) == "invalid_next_action_count"
    assert knowledge_grounding_failure(
        str(evidence["fallback_answer"]),
        wrapped,
    ) is None


@pytest.mark.asyncio
async def test_semantic_retrieval_embeds_once_and_never_needs_provider_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider-vector retrieval stays deterministic behind one mocked embedding call."""

    manifest = deepcopy(knowledge_builder.load_derived_manifest())
    retrieval_units = manifest["retrieval_units"]
    assert isinstance(retrieval_units, list)
    for unit in retrieval_units:
        assert isinstance(unit, dict)
        unit["provider_embedding"] = list(unit["local_embedding"])

    monkeypatch.setattr(app_knowledge_service, "load_derived_manifest", lambda: manifest)
    monkeypatch.setattr(knowledge_builder, "load_derived_manifest", lambda: manifest)
    knowledge_builder.clear_knowledge_base_cache()
    calls: list[list[str]] = []

    async def fake_generate_embeddings(
        texts: list[str],
        _settings: object,
        *,
        input_type: str,
    ) -> GenAiEmbeddingResult:
        assert input_type == "SEARCH_QUERY"
        calls.append(texts)
        return GenAiEmbeddingResult(
            status="completed",
            model="mock-provider-embedding",
            embeddings=[knowledge_builder.local_semantic_embedding(text) for text in texts],
        )

    monkeypatch.setattr(
        app_knowledge_service,
        "generate_embeddings",
        fake_generate_embeddings,
    )
    try:
        evidence = await build_app_knowledge_evidence(
            "How do I import a customer workbook?",
            "/projects/project-1/import",
            language="en",
            project_id="project-1",
            integration_id=None,
        )
    finally:
        knowledge_builder.clear_knowledge_base_cache()

    assert calls == [["How do I import a customer workbook?"]]
    assert evidence["embedding_space"] == "provider"
    assert evidence["intent"] == "workflow_guidance"
    assert evidence["mode"] == "knowledge"


def test_shared_runtime_knowledge_refreshes_when_object_version_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import storage_service

    object_key = "governance/app-knowledge/active/derived_app_knowledge.json"
    monkeypatch.setenv("APP_KNOWLEDGE_RUNTIME_OBJECT_KEY", object_key)
    first = deepcopy(knowledge_builder.load_packaged_derived_manifest())
    first["runtime_revision"] = "one"
    storage_service.put_json(object_key, first)
    knowledge_builder.clear_knowledge_base_cache()
    first_loaded = cast(dict[str, object], knowledge_builder.load_knowledge_base()["derived"])
    assert first_loaded["runtime_revision"] == "one"

    second = deepcopy(first)
    second["runtime_revision"] = "two"
    storage_service.put_json(object_key, second)
    second_loaded = cast(dict[str, object], knowledge_builder.load_knowledge_base()["derived"])
    assert second_loaded["runtime_revision"] == "two"
    knowledge_builder.clear_knowledge_base_cache()


@pytest.mark.asyncio
async def test_semantic_retrieval_fails_closed_when_configured_provider_embedding_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = deepcopy(knowledge_builder.load_derived_manifest())
    retrieval_units = cast(list[object], manifest["retrieval_units"])
    assert any(
        isinstance(unit, dict) and isinstance(unit.get("provider_embedding"), list)
        for unit in retrieval_units
    )

    async def failed_embeddings(
        texts: list[str],
        _settings: object,
        *,
        input_type: str,
    ) -> GenAiEmbeddingResult:
        assert texts == ["How do I import a workbook?"]
        assert input_type == "SEARCH_QUERY"
        return GenAiEmbeddingResult(
            status="failed",
            model="mock-provider-embedding",
            embeddings=[],
            error="embedding_transport_unavailable",
        )

    monkeypatch.setattr(app_knowledge_service, "load_derived_manifest", lambda: manifest)
    monkeypatch.setattr(
        app_knowledge_service,
        "get_genai_settings_for_use_case",
        lambda _: SimpleNamespace(OCI_GENAI_PROJECT_ID="configured-project"),
    )
    monkeypatch.setattr(app_knowledge_service, "generate_embeddings", failed_embeddings)

    with pytest.raises(RuntimeError, match="provider_query_embedding_failed"):
        await build_app_knowledge_evidence(
            "How do I import a workbook?",
            "/projects/project-1/import",
            language="en",
            project_id="project-1",
            integration_id=None,
        )


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
