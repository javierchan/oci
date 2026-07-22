#!/usr/bin/env python3
"""Generate or verify the deterministic App knowledge manifest."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.knowledge.builder import (  # noqa: E402
    CURATED_PATH,
    DERIVED_PATH,
    _load_curated,
    build_derived_manifest,
    validate_knowledge_base,
)
from app.core.config import get_genai_settings_for_use_case  # noqa: E402
from app.services.genai_client import generate_embeddings  # noqa: E402
from app.services.genai_telemetry import close_genai_telemetry_clients  # noqa: E402


def _discover_source_repo_root(start: Path) -> Path | None:
    """Return the monorepo root, or None in the intentionally shallow image."""

    for candidate in (start, *start.parents):
        if (candidate / "apps" / "api" / "app").is_dir() and (
            candidate / "apps" / "web" / "app"
        ).is_dir():
            return candidate
    return None


def _load_manifest_for_build(*, provider_embeddings: bool) -> dict[str, object]:
    repo_root = _discover_source_repo_root(API_ROOT)
    if repo_root is not None:
        return build_derived_manifest(repo_root)
    if provider_embeddings and DERIVED_PATH.is_file():
        # Production images contain the validated generated artifact, not the
        # frontend source tree. Provider enrichment must preserve that artifact
        # rather than trying to derive repository contracts inside the image.
        loaded = json.loads(DERIVED_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            return loaded
    raise RuntimeError(
        "App knowledge derivation requires a source checkout; "
        "the production image only supports --provider-embeddings."
    )


async def _add_provider_embeddings(manifest: dict[str, object]) -> None:
    units = manifest.get("retrieval_units")
    if not isinstance(units, list):
        raise RuntimeError("Generated knowledge manifest has no retrieval units")
    texts = [str(unit.get("text") or "") for unit in units if isinstance(unit, dict)]
    result = await generate_embeddings(
        texts,
        get_genai_settings_for_use_case("support_assistant"),
        input_type="SEARCH_DOCUMENT",
    )
    if result.status != "completed" or len(result.embeddings) != len(texts):
        raise RuntimeError(f"OCI knowledge embedding generation failed: {result.status}")
    for unit, vector in zip(units, result.embeddings, strict=True):
        if isinstance(unit, dict):
            unit["provider_embedding"] = vector
    spaces = manifest.setdefault("embedding_spaces", {})
    if isinstance(spaces, dict):
        spaces["provider"] = {
            "model": result.model,
            "dimensions": len(result.embeddings[0]) if result.embeddings else 0,
        }


async def _enrich_with_provider_embeddings(manifest: dict[str, object]) -> None:
    """Enrich the manifest and close telemetry resources on process exit."""

    try:
        await _add_provider_embeddings(manifest)
    finally:
        await close_genai_telemetry_clients()


def _deterministic_projection(manifest: dict[str, object]) -> dict[str, object]:
    """Ignore provider vectors when checking deterministic repository drift."""

    projected = json.loads(json.dumps(manifest))
    spaces = projected.get("embedding_spaces")
    if isinstance(spaces, dict):
        spaces.pop("provider", None)
    units = projected.get("retrieval_units")
    if isinstance(units, list):
        for unit in units:
            if isinstance(unit, dict):
                unit.pop("provider_embedding", None)
    return projected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail when generated facts or curated links drift")
    parser.add_argument(
        "--provider-embeddings",
        action="store_true",
        help="Embed KB units with OCI and cache the vectors in the derived artifact",
    )
    args = parser.parse_args()
    current = _load_manifest_for_build(provider_embeddings=args.provider_embeddings)
    if args.provider_embeddings:
        asyncio.run(_enrich_with_provider_embeddings(current))
    errors = validate_knowledge_base(_load_curated(CURATED_PATH), current)
    if args.check:
        if not DERIVED_PATH.exists():
            errors.append(f"Missing generated manifest: {DERIVED_PATH}")
        else:
            committed = json.loads(DERIVED_PATH.read_text(encoding="utf-8"))
            if _deterministic_projection(committed) != _deterministic_projection(current):
                errors.append("derived_app_knowledge.json is stale; regenerate it")
    else:
        DERIVED_PATH.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"App knowledge is consistent ({str(current.get('source_hash') or '')[:12]}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
