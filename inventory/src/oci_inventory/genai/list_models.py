from __future__ import annotations

import csv
import re
from typing import Any, Dict, Iterable, List, Optional, TextIO

from ..auth.providers import resolve_auth
from ..logging import get_logger
from .config import GenAIConfig

LOG = get_logger(__name__)


_REGION_FROM_ENDPOINT_RE = re.compile(r"inference\.generativeai\.(?P<region>[a-z0-9-]+)\.")


def _endpoint_region(endpoint: str) -> Optional[str]:
    m = _REGION_FROM_ENDPOINT_RE.search(endpoint or "")
    if not m:
        return None
    return m.group("region")


def list_genai_models(*, genai_cfg: GenAIConfig) -> List[Dict[str, Any]]:
    """List available OCI GenAI models and their capabilities.

    This uses the OCI Generative AI control-plane client (oci.generative_ai),
    not the inference client.
    """

    # Use config auth profile from genai.yaml for consistency.
    ctx = resolve_auth("config", genai_cfg.oci_profile, None)

    import oci  # type: ignore
    from oci.generative_ai import GenerativeAiClient  # type: ignore

    inferred_region = _endpoint_region(genai_cfg.endpoint)
    oci_cfg = dict(ctx.config_dict or {})
    # The Generative AI control-plane client is region-scoped. We must query the
    # region where the service endpoint is hosted; profile region may differ.
    if inferred_region:
        oci_cfg["region"] = inferred_region
    elif not oci_cfg.get("region"):
        oci_cfg["region"] = "us-chicago-1"

    client_kwargs: Dict[str, Any] = {
        "retry_strategy": getattr(oci.retry, "DEFAULT_RETRY_STRATEGY", None),
        "timeout": (10, 60),
    }
    if ctx.signer is not None:
        client_kwargs["signer"] = ctx.signer

    client = GenerativeAiClient(oci_cfg, **client_kwargs)
    resp = client.list_models(compartment_id=genai_cfg.compartment_id)
    data = getattr(resp, "data", None)
    if data is None:
        models = []
    else:
        items = getattr(data, "items", None)
        if isinstance(items, list):
            models = items
        elif isinstance(data, list):
            models = data
        else:
            raise TypeError(f"Unexpected list_models response data type: {type(data).__name__}")

    rows: List[Dict[str, Any]] = []
    for m in models:
        capabilities = getattr(m, "capabilities", None)
        if not isinstance(capabilities, list):
            capabilities = []

        rows.append(
            {
                "id": getattr(m, "id", ""),
                "display_name": getattr(m, "display_name", ""),
                "vendor": getattr(m, "vendor", ""),
                "version": getattr(m, "version", ""),
                "type": getattr(m, "type", ""),
                "lifecycle_state": getattr(m, "lifecycle_state", ""),
                "capabilities": sorted([str(x) for x in capabilities if str(x)]),
            }
        )

    # Stable ordering for diffs.
    rows.sort(key=lambda r: (str(r.get("display_name") or ""), str(r.get("id") or "")))
    LOG.info("Listed GenAI models", extra={"count": len(rows), "region": str(oci_cfg.get("region") or "")})
    return rows


def write_genai_models_csv(rows: Iterable[Dict[str, Any]], out: TextIO) -> None:
    writer = csv.writer(out)
    writer.writerow(["id", "display_name", "vendor", "version", "type", "lifecycle_state", "capabilities"])
    for r in rows:
        caps = r.get("capabilities") or []
        if isinstance(caps, list):
            caps_s = "|".join([str(x) for x in caps if str(x)])
        else:
            caps_s = str(caps)
        writer.writerow(
            [
                str(r.get("id") or ""),
                str(r.get("display_name") or ""),
                str(r.get("vendor") or ""),
                str(r.get("version") or ""),
                str(r.get("type") or ""),
                str(r.get("lifecycle_state") or ""),
                caps_s,
            ]
        )
