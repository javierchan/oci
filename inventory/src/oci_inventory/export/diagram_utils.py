"""Pure utility functions for Mermaid diagram generation.

This module contains stateless helper functions extracted from diagram_projections.py.
None of these functions depend on module-level rendering context (_RENDER_THEME,
_RENDER_LABEL_TAG_KEYS) — they accept all parameters explicitly.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .graph import Edge, Node


# ---------------------------------------------------------------------------
# String / OCID helpers
# ---------------------------------------------------------------------------

def _slugify(value: str, *, max_len: int = 48) -> str:
    v = (value or "").strip().lower()
    v = re.sub(r"[^a-z0-9]+", "_", v)
    v = re.sub(r"_+", "_", v).strip("_")
    if not v:
        return "unknown"
    return v[:max_len]


def _short_ocid(ocid: str) -> str:
    o = (ocid or "").strip()
    if o.startswith("ocid1") and len(o) > 18:
        return o[-8:]
    return o


def _redact_ocids_for_label(value: str, *, replacement: str = "Redacted") -> str:
    return re.sub(r"ocid1[0-9a-zA-Z._-]*", replacement, str(value or ""))


def _redact_ocids_for_id(value: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        digest = hashlib.sha1(match.group(0).encode("utf-8", errors="ignore")).hexdigest()[:8]
        return f"ocid_{digest}"
    return re.sub(r"ocid1[0-9a-zA-Z._-]*", _repl, str(value or ""))


def _semantic_id_key(value: str) -> str:
    return str(value or "")


# ---------------------------------------------------------------------------
# Node metadata helpers
# ---------------------------------------------------------------------------

def _get_meta(metadata: Mapping[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in metadata:
            return metadata[k]
        # Accept camelCase vs snake_case interchangeably.
        camel = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), k)
        snake = re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), k)
        if camel in metadata:
            return metadata[camel]
        if snake in metadata:
            return metadata[snake]
    return None


def _node_metadata(node: Node) -> Mapping[str, Any]:
    meta = node.get("metadata")
    return meta if isinstance(meta, Mapping) else {}


def _is_node_type(node: Node, *suffixes: str) -> bool:
    t = str(node.get("nodeType") or "")
    for s in suffixes:
        if t == s or t.endswith("." + s) or t.endswith(s):
            return True
    return False


# ---------------------------------------------------------------------------
# Mermaid ID generation
# ---------------------------------------------------------------------------

def _mermaid_id(key: str) -> str:
    # Semantic, deterministic Mermaid node IDs (no hashed/hex IDs).
    clean = _redact_ocids_for_id(_semantic_id_key(key))
    full = _slugify(clean, max_len=512)
    max_len = 160
    slug = full[:max_len]
    if len(full) > max_len:
        suffix = full[-8:] or "suffix"
        head_len = max_len - (len(suffix) + 1)
        slug = f"{full[:head_len]}_{suffix}"
    if not slug:
        slug = "node"
    if not slug[0].isalpha():
        slug = f"n_{slug}"
    return slug


def _unique_mermaid_id_factory(reserved: Optional[Iterable[str]] = None) -> Callable[[str], str]:
    used: Set[str] = set(reserved or [])
    counts: Dict[str, int] = {}

    def _make(key: str) -> str:
        base = _mermaid_id(key)
        if base in used:
            count = counts.get(base, 1) + 1
            candidate = f"{base}_{count}"
            while candidate in used:
                count += 1
                candidate = f"{base}_{count}"
            counts[base] = count
            base = candidate
        else:
            counts[base] = 1
        used.add(base)
        return base

    return _make


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------

def _friendly_type(node_type: str) -> str:
    t = (node_type or "").strip()
    if "." in t:
        return t.split(".")[-1]
    return t or "Resource"


def _compact_label(value: str, *, max_len: int = 40) -> str:
    safe = _redact_ocids_for_label(str(value or "").replace('"', "'").strip())
    if len(safe) <= max_len:
        return safe
    return f"{safe[: max_len - 3].rstrip()}..."


def _node_tag_label_suffix(node: Node, tag_keys: Tuple[str, ...]) -> str:
    """Return a compact tag summary line for the node label (e.g., 'env:prod, team:payments')."""
    meta = _node_metadata(node)
    freeform = _get_meta(meta, "freeformTags", "freeform_tags") or {}
    defined_raw = _get_meta(meta, "definedTags", "defined_tags") or {}

    # Also check top-level tags dict (some records nest tags differently)
    top_tags = node.get("tags")
    if isinstance(top_tags, dict):
        if not freeform:
            freeform = top_tags.get("freeformTags") or top_tags.get("freeform_tags") or {}
        if not defined_raw:
            defined_raw = top_tags.get("definedTags") or top_tags.get("defined_tags") or {}

    # Flatten defined tag namespaces into key→value
    flat: Dict[str, str] = {}
    if isinstance(freeform, dict):
        for k, v in freeform.items():
            flat[str(k).lower()] = str(v)
    if isinstance(defined_raw, dict):
        for ns_val in defined_raw.values():
            if isinstance(ns_val, dict):
                for k, v in ns_val.items():
                    flat.setdefault(str(k).lower(), str(v))

    parts: List[str] = []
    for key in tag_keys:
        val = flat.get(key.lower())
        if val:
            safe_val = _compact_label(val, max_len=20)
            parts.append(f"{key}:{safe_val}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Edge helpers
# ---------------------------------------------------------------------------

def _sanitize_edge_label(label: str) -> str:
    # Keep edge labels conservative to avoid Mermaid parse edge-cases.
    safe = str(label).replace('"', "'")
    for ch in ("|", "\n", "\r", "\t"):
        safe = safe.replace(ch, " ")
    for ch in ("<", ">", "{", "}", "[", "]", "(", ")"):
        safe = safe.replace(ch, "")
    return " ".join(safe.split())


def _mermaid_text_size(lines: Sequence[str]) -> int:
    return sum(len(line) + 1 for line in lines)


def _edge_sort_key(edge: Edge) -> Tuple[str, str, str]:
    return (
        str(edge.get("relation_type") or ""),
        str(edge.get("source_ocid") or ""),
        str(edge.get("target_ocid") or ""),
    )


def _edge_single_target_map(edges: Sequence[Edge], relation_type: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for edge in sorted(edges, key=_edge_sort_key):
        if str(edge.get("relation_type") or "") != relation_type:
            continue
        src = str(edge.get("source_ocid") or "")
        dst = str(edge.get("target_ocid") or "")
        if not src or not dst:
            continue
        out.setdefault(src, dst)
    return out
