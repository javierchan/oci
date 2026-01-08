from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass(frozen=True)
class GenAIConfig:
    oci_profile: str
    compartment_id: str
    endpoint: str
    base_model_id: str
    vision_model_id: Optional[str] = None


def default_genai_config_path() -> Path:
    # Intentionally outside the repo so this stays safe for public repos.
    return Path.home() / ".config" / "oci-inv" / "genai.yaml"


def _require_str(data: Dict[str, Any], key: str) -> str:
    v = data.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"GenAI config field '{key}' is required and must be a non-empty string")
    return v.strip()


def load_genai_config(path: Optional[Path] = None) -> GenAIConfig:
    p = path or default_genai_config_path()
    if not p.exists():
        raise FileNotFoundError(
            f"GenAI config file not found: {p}. Create it first (see inventory/README.md)."
        )

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("GenAI config must be a YAML mapping/object")

    cfg = GenAIConfig(
        oci_profile=_require_str(raw, "oci_profile"),
        compartment_id=_require_str(raw, "compartment_id"),
        endpoint=_require_str(raw, "endpoint"),
        base_model_id=_require_str(raw, "base_model_id"),
        vision_model_id=(str(raw.get("vision_model_id")).strip() if raw.get("vision_model_id") else None),
    )
    return cfg
