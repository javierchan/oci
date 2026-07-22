"""Derive, validate, and retrieve the in-App product knowledge base.

The generated manifest is facts from code.  The YAML file is deliberately small
and human-owned: it explains why a surface exists and how a user operates it.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


KNOWLEDGE_DIR = Path(__file__).resolve().parent


def _discover_repo_root(start: Path) -> Path:
    """Find a source checkout without making runtime imports depend on its depth.

    Production images intentionally contain only ``/app/app`` plus the generated
    knowledge manifest, while repository checks run from the full monorepo.  A
    fixed ``parents[n]`` lookup therefore makes importing the runtime package
    fail inside Docker before the committed manifest can be read.
    """

    for candidate in (start, *start.parents):
        if (candidate / "apps" / "api" / "app").is_dir() and (
            candidate / "apps" / "web" / "app"
        ).is_dir():
            return candidate
    # The production image does not derive contracts at runtime.  This fallback
    # keeps module import portable; generation scripts always pass the repo root.
    return start.parent.parent


REPO_ROOT = _discover_repo_root(KNOWLEDGE_DIR)
CURATED_PATH = KNOWLEDGE_DIR / "app_knowledge.yaml"
DERIVED_PATH = KNOWLEDGE_DIR / "derived_app_knowledge.json"
ROUTE_PARAMETER_PATTERN = re.compile(r"\[[^/]+\]|\{[^/]+\}")
TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9&+-]*", re.IGNORECASE)
STOPWORDS = frozenset(
    {
        "a", "an", "and", "app", "can", "de", "del", "el", "en", "es", "esta", "for",
        "i", "la", "las", "los", "of", "or", "para", "por", "que", "the", "to", "un",
        "una", "use", "with", "y",
    }
)
ROUTE_CONTEXT_QUESTION_PATTERN = re.compile(
    r"\b(?:what can i do|how (?:do|can) i|this (?:page|view)|here|"
    r"qu[eé] puedo hacer|c[oó]mo (?:uso|puedo)|esta (?:p[aá]gina|vista)|aqu[ií])\b",
    re.IGNORECASE,
)
TOKEN_ALIASES = {
    "archivo": "workbook",
    "archivos": "workbook",
    "byol": "licensing",
    "escenario": "scenario",
    "escenarios": "scenario",
    "filas": "rows",
    "importacion": "import",
    "importar": "import",
    "importo": "import",
    "licencia": "licensing",
    "licencias": "licensing",
}


class KnowledgeValidationError(ValueError):
    """Raised when code-derived facts and curated knowledge disagree."""


def _as_list(value: object) -> list[object]:
    """Narrow untyped JSON/YAML collections before iteration."""

    return value if isinstance(value, list) else []


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _next_route(page: Path, app_root: Path) -> str:
    parts = list(page.relative_to(app_root).parts[:-1])
    visible = [part for part in parts if not (part.startswith("(") and part.endswith(")"))]
    return "/" + "/".join(visible) if visible else "/"


def _derive_routes(repo_root: Path) -> list[dict[str, str]]:
    app_root = repo_root / "apps" / "web" / "app"
    routes: list[dict[str, str]] = []
    for page in sorted(app_root.rglob("page.tsx")):
        routes.append(
            {
                "route": _next_route(page, app_root),
                "source": str(page.relative_to(repo_root)),
            }
        )
    return routes


def _load_openapi(repo_root: Path) -> dict[str, Any]:
    raw = yaml.safe_load((repo_root / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _derive_endpoints(repo_root: Path) -> list[dict[str, object]]:
    document = _load_openapi(repo_root)
    source_media = _derive_source_media_types(repo_root)
    rows: list[dict[str, object]] = []
    for path, path_item in sorted((document.get("paths") or {}).items()):
        if not isinstance(path_item, dict):
            continue
        for method, operation in sorted(path_item.items()):
            if method.lower() not in {"get", "post", "put", "patch", "delete"} or not isinstance(operation, dict):
                continue
            media_types: set[str] = set()
            for response in (operation.get("responses") or {}).values():
                if not isinstance(response, dict):
                    continue
                content = response.get("content")
                if isinstance(content, dict):
                    media_types.update(str(item) for item in content)
            key = (method.upper(), str(path))
            media_types.update(source_media.get(key, set()))
            rows.append(
                {
                    "method": method.upper(),
                    "path": str(path),
                    "summary": str(operation.get("summary") or ""),
                    "media_types": sorted(media_types),
                }
            )
    return rows


def _literal_string(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _derive_source_media_types(repo_root: Path) -> dict[tuple[str, str], set[str]]:
    """Read response media types from router source, where OpenAPI cannot infer them."""

    result: dict[tuple[str, str], set[str]] = {}
    router_root = repo_root / "apps" / "api" / "app" / "routers"
    for source in sorted(router_root.glob("*.py")):
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        prefix = ""
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not any(
                isinstance(target, ast.Name) and target.id == "router" for target in node.targets
            ):
                continue
            if isinstance(node.value, ast.Call):
                for keyword in node.value.keywords:
                    if keyword.arg == "prefix":
                        prefix = _literal_string(keyword.value) or ""
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            method = None
            local_path = None
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id != "router":
                    continue
                candidate_method = decorator.func.attr.upper()
                if candidate_method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                    continue
                method = candidate_method
                local_path = _literal_string(decorator.args[0]) if decorator.args else ""
            if method is None or local_path is None:
                continue
            media_types: set[str] = set()
            local_mappings: dict[str, set[str]] = {}
            for child in ast.walk(node):
                if isinstance(child, ast.Assign) and len(child.targets) == 1 and isinstance(child.targets[0], ast.Name):
                    if isinstance(child.value, ast.Dict):
                        values = {
                            value
                            for item in child.value.values
                            if (value := _literal_string(item)) is not None
                        }
                        local_mappings[child.targets[0].id] = values
                if isinstance(child, ast.keyword) and child.arg == "media_type":
                    literal = _literal_string(child.value)
                    if literal:
                        media_types.add(literal)
                    elif isinstance(child.value, ast.Call) and isinstance(child.value.func, ast.Attribute):
                        owner = child.value.func.value
                        if isinstance(owner, ast.Name):
                            media_types.update(local_mappings.get(owner.id, set()))
            if media_types:
                full_path = f"/api/v1{prefix}{local_path}" or "/api/v1"
                result[(method, full_path)] = media_types
    return result


def _class_names(path: Path) -> set[str]:
    names: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return names
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
    return names


def _derive_entities(repo_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for kind, root in (
        ("model", repo_root / "apps" / "api" / "app" / "models"),
        ("schema", repo_root / "apps" / "api" / "app" / "schemas"),
    ):
        for source in sorted(root.rglob("*.py")):
            for name in sorted(_class_names(source)):
                rows.append({"name": name, "kind": kind, "source": str(source.relative_to(repo_root))})
    return rows


def build_derived_manifest(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    """Build a deterministic manifest from executable repository contracts."""

    routes = _derive_routes(repo_root)
    endpoints = _derive_endpoints(repo_root)
    entities = _derive_entities(repo_root)
    exports = [
        endpoint
        for endpoint in endpoints
        if "/exports/" in str(endpoint["path"])
        or str(endpoint["path"]).endswith("/export")
        or str(endpoint["path"]).endswith("/xlsx")
        or str(endpoint["path"]).endswith("/brief")
    ]
    facts = {
        "routes": routes,
        "endpoints": endpoints,
        "entities": entities,
        "exports": exports,
    }
    return {"schema_version": "1.0.0", "source_hash": _stable_hash(facts), **facts}


def _load_curated(curated_path: Path = CURATED_PATH) -> dict[str, object]:
    document = yaml.safe_load(curated_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("sections"), list):
        raise KnowledgeValidationError("app_knowledge.yaml must contain a sections list")
    return document


def load_curated_knowledge(curated_path: Path = CURATED_PATH) -> dict[str, object]:
    """Load the human-owned knowledge contract without exposing mutation helpers."""

    return _load_curated(curated_path)


def load_derived_manifest(derived_path: Path = DERIVED_PATH) -> dict[str, object]:
    """Load the immutable code-derived contract packaged with the application."""

    document = json.loads(derived_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise KnowledgeValidationError("derived_app_knowledge.json must contain an object")
    return document


def _normalized_route(route: str) -> str:
    return ROUTE_PARAMETER_PATTERN.sub("{}", route.rstrip("/") or "/")


def _route_matches(left: str, right: str) -> bool:
    return _normalized_route(left) == _normalized_route(right)


def validate_knowledge_base(
    curated: dict[str, object],
    derived: dict[str, object],
) -> list[str]:
    """Return every deterministic drift error; an empty list means CI-safe."""

    errors: list[str] = []
    sections = curated.get("sections")
    if not isinstance(sections, list):
        return ["Curated knowledge has no sections list"]
    route_rows = _as_list(derived.get("routes"))
    derived_routes = [str(item.get("route")) for item in route_rows if isinstance(item, dict)]
    endpoint_rows = _as_list(derived.get("endpoints"))
    endpoints = {
        (str(item.get("method") or "").upper(), str(item.get("path") or "")): item
        for item in endpoint_rows
        if isinstance(item, dict)
    }
    entity_rows = _as_list(derived.get("entities"))
    entities = {str(item.get("name")) for item in entity_rows if isinstance(item, dict)}
    covered_routes: set[str] = set()
    section_ids: set[str] = set()
    for raw_section in sections:
        if not isinstance(raw_section, dict):
            errors.append("Each curated section must be an object")
            continue
        section_id = str(raw_section.get("id") or "")
        if not section_id or section_id in section_ids:
            errors.append(f"Section id is missing or duplicated: {section_id or '<empty>'}")
        section_ids.add(section_id)
        for field in ("name", "purpose", "when_to_use", "steps"):
            if not raw_section.get(field):
                errors.append(f"Section {section_id} is missing {field}")
        for route in _as_list(raw_section.get("routes")):
            route_value = str(route)
            match = next((candidate for candidate in derived_routes if _route_matches(route_value, candidate)), None)
            if match is None:
                errors.append(f"Section {section_id} references missing Next route {route_value}")
            else:
                covered_routes.add(match)
        for endpoint in _as_list(raw_section.get("endpoints")):
            if not isinstance(endpoint, dict):
                errors.append(f"Section {section_id} has an invalid endpoint reference")
                continue
            key = (str(endpoint.get("method") or "").upper(), str(endpoint.get("path") or ""))
            if key not in endpoints:
                errors.append(f"Section {section_id} references missing endpoint {key[0]} {key[1]}")
        for export in _as_list(raw_section.get("exports")):
            if not isinstance(export, dict):
                errors.append(f"Section {section_id} has an invalid export reference")
                continue
            key = (str(export.get("method") or "GET").upper(), str(export.get("path") or ""))
            actual = endpoints.get(key)
            if actual is None:
                errors.append(f"Section {section_id} references missing export {key[0]} {key[1]}")
                continue
            actual_media = set(actual.get("media_types") or []) if isinstance(actual, dict) else set()
            for media_type in _as_list(export.get("media_types")):
                if media_type not in actual_media:
                    errors.append(
                        f"Section {section_id} export {key[1]} does not expose media type {media_type}"
                    )
        for entity in _as_list(raw_section.get("entities")):
            if str(entity) not in entities:
                errors.append(f"Section {section_id} references missing entity {entity}")
    for route in derived_routes:
        if route not in covered_routes:
            errors.append(f"Next route has no curated knowledge owner: {route}")
    return errors


def write_derived_manifest(repo_root: Path = REPO_ROOT, output_path: Path = DERIVED_PATH) -> dict[str, object]:
    manifest = build_derived_manifest(repo_root)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


@lru_cache(maxsize=1)
def load_knowledge_base() -> dict[str, object]:
    curated = _load_curated()
    derived = load_derived_manifest()
    errors = validate_knowledge_base(curated, derived)
    if errors:
        raise KnowledgeValidationError("; ".join(errors))
    return {
        "schema_version": str(curated.get("version") or "1.0.0"),
        "source_hash": str(derived.get("source_hash") or ""),
        "sections": curated["sections"],
        "derived": derived,
    }


def _tokens(value: object) -> set[str]:
    tokens: set[str] = set()
    for item in TOKEN_PATTERN.findall(str(value)):
        normalized = item.casefold()
        normalized = (
            normalized.replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
        )
        normalized = TOKEN_ALIASES.get(normalized, normalized)
        if len(normalized) > 1 and normalized not in STOPWORDS:
            tokens.add(normalized)
    return tokens


def retrieve_knowledge(question: str, current_route: str, *, limit: int = 3) -> dict[str, object]:
    """Select bounded entries using route affinity plus deterministic term overlap."""

    knowledge = load_knowledge_base()
    question_tokens = _tokens(question)
    scored: list[tuple[int, int, dict[str, object]]] = []
    for raw in _as_list(knowledge.get("sections")):
        if not isinstance(raw, dict):
            continue
        section = dict(raw)
        searchable = " ".join(
            str(section.get(key) or "")
            for key in ("name", "purpose", "when_to_use", "keywords", "supported_actions")
        )
        lexical_score = len(question_tokens & _tokens(searchable)) * 4
        score = lexical_score
        if any(_route_matches(current_route, str(route)) for route in _as_list(section.get("routes"))):
            # The current view is useful context, but an explicit question such
            # as "how do I import?" must outrank the generic Projects route.
            # Route affinity becomes authoritative only for contextual prompts
            # such as "what can I do here?".
            score += 7 if ROUTE_CONTEXT_QUESTION_PATTERN.search(question) else 1
        if score:
            scored.append((score, lexical_score, section))
    scored.sort(key=lambda item: (-item[0], str(item[2].get("name") or "")))
    entries = [item for _, _, item in scored[:limit]]
    if not entries:
        entries = [
            dict(item)
            for item in _as_list(knowledge.get("sections"))
            if isinstance(item, dict) and item.get("id") == "projects"
        ][:1]
    documented = any(lexical_score > 0 for _, lexical_score, _ in scored) or bool(
        ROUTE_CONTEXT_QUESTION_PATTERN.search(question)
    )
    allowed_routes = sorted({str(route) for item in entries for route in _as_list(item.get("routes"))})
    export_formats = sorted(
        {
            str(media_type)
            for item in entries
            for export in _as_list(item.get("exports"))
            if isinstance(export, dict)
            for media_type in _as_list(export.get("media_types"))
        }
    )
    return {
        "documented": documented,
        "entries": entries,
        "allowed_routes": allowed_routes,
        "allowed_export_media_types": export_formats,
        "source_hash": knowledge["source_hash"],
    }
