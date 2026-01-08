from __future__ import annotations

from dataclasses import dataclass
import os
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


def local_genai_config_path() -> Path:
    # Repo-local dev convenience (ignored by git).
    # This is intentionally a fallback behind the user-scoped config.
    inventory_root = Path(__file__).resolve().parents[3]
    return inventory_root / ".local" / "genai.yaml"


def default_genai_config_path() -> Path:
    # Intentionally outside the repo so this stays safe for public repos.
    return Path.home() / ".config" / "oci-inv" / "genai.yaml"


def resolve_genai_config_path(explicit_path: Optional[Path] = None) -> Path:
    if explicit_path is not None:
        return explicit_path

    env_path = os.environ.get("OCI_INV_GENAI_CONFIG")
    if env_path:
        return Path(env_path).expanduser()

    default_path = default_genai_config_path()
    if default_path.exists():
        return default_path

    return local_genai_config_path()


def _require_str(data: Dict[str, Any], key: str) -> str:
    v = data.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"GenAI config field '{key}' is required and must be a non-empty string")
    return v.strip()


def load_genai_config(path: Optional[Path] = None) -> GenAIConfig:
    p = resolve_genai_config_path(path)
    if not p.exists():
        searched = [
            f"explicit={path}" if path is not None else None,
            (
                f"OCI_INV_GENAI_CONFIG={os.environ.get('OCI_INV_GENAI_CONFIG')}"
                if os.environ.get("OCI_INV_GENAI_CONFIG")
                else None
            ),
            str(default_genai_config_path()),
            str(local_genai_config_path()),
        ]
        searched_s = "\n".join([f"- {s}" for s in searched if s])
        raise FileNotFoundError(
            "GenAI config file not found. Searched:\n"
            f"{searched_s}\n\n"
            "Create one (see inventory/README.md), or set OCI_INV_GENAI_CONFIG to point to a YAML file."
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
