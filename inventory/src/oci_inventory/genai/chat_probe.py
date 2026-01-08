from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..auth.providers import resolve_auth
from ..logging import get_logger
from .config import GenAIConfig, load_genai_config
from .redact import redact_text

LOG = get_logger(__name__)


@dataclass(frozen=True)
class ChatProbeResult:
    text: str
    hint: str


def _status_code(exc: BaseException) -> Optional[int]:
    v = getattr(exc, "status", None)
    try:
        return int(v)
    except Exception:
        return None


def chat_probe(
    *,
    message: str,
    api_format: str = "AUTO",  # AUTO|GENERIC|COHERE
    max_tokens: int = 256,
    temperature: float = 0.2,
    genai_cfg: Optional[GenAIConfig] = None,
) -> ChatProbeResult:
    """Execute a single GenAI chat request for debugging.

    This is best-effort: it never returns unredacted output.
    """

    cfg = genai_cfg or load_genai_config()
    ctx = resolve_auth("config", cfg.oci_profile, None)

    import oci  # type: ignore
    from oci.generative_ai_inference import GenerativeAiInferenceClient  # type: ignore
    from oci.generative_ai_inference.models import (  # type: ignore
        BaseChatRequest,
        ChatDetails,
        CohereChatRequest,
        GenericChatRequest,
        OnDemandServingMode,
        SystemMessage,
        TextContent,
        UserMessage,
    )

    # Always redact before sending.
    safe_message = redact_text(message)

    oci_cfg = dict(ctx.config_dict or {})
    # Keep SDK "region" consistent with the inference endpoint region.
    # The endpoint is authoritative for routing; region here is mainly for signing.
    # If region is already present in config, keep it.
    if not oci_cfg.get("region"):
        # best-effort extraction
        try:
            region = cfg.endpoint.split(".")[2]
            oci_cfg["region"] = region
        except Exception:
            pass

    client_kwargs: Dict[str, Any] = {
        "service_endpoint": cfg.endpoint,
        "retry_strategy": getattr(oci.retry, "DEFAULT_RETRY_STRATEGY", None),
        "timeout": (10, 60),
    }
    if ctx.signer is not None:
        client_kwargs["signer"] = ctx.signer

    client = GenerativeAiInferenceClient(oci_cfg, **client_kwargs)

    def _do_generic() -> Any:
        system = SystemMessage(
            content=[
                TextContent(
                    text=(
                        "You are a helpful assistant. "
                        "Reply with Markdown text only. "
                        "Do not include secrets, OCIDs, or URLs."
                    )
                )
            ]
        )
        user = UserMessage(content=[TextContent(text=safe_message)])
        req = GenericChatRequest(
            api_format=BaseChatRequest.API_FORMAT_GENERIC,
            messages=[system, user],
            is_stream=False,
            max_completion_tokens=max_tokens,
            verbosity="LOW",
        )
        return client.chat(
            ChatDetails(
                compartment_id=cfg.compartment_id,
                serving_mode=OnDemandServingMode(model_id=cfg.base_model_id),
                chat_request=req,
            )
        )

    def _do_cohere() -> Any:
        req = CohereChatRequest(
            api_format=BaseChatRequest.API_FORMAT_COHERE,
            message=safe_message,
            is_stream=False,
            max_tokens=max_tokens,
            temperature=float(temperature),
            top_p=0.9,
        )
        return client.chat(
            ChatDetails(
                compartment_id=cfg.compartment_id,
                serving_mode=OnDemandServingMode(model_id=cfg.base_model_id),
                chat_request=req,
            )
        )

    def _extract_text(resp: Any) -> str:
        data = getattr(resp, "data", None)
        cr = getattr(data, "chat_response", None) if data is not None else None

        # Cohere response path
        cr_text = getattr(cr, "text", None) if cr is not None else None
        if isinstance(cr_text, str) and cr_text.strip():
            return cr_text.strip()

        choices = getattr(cr, "choices", None) if cr is not None else None
        if not choices:
            choices = getattr(data, "choices", None) if data is not None else None
        if not choices:
            return ""

        msg = getattr(choices[0], "message", None)
        content = getattr(msg, "content", None) if msg is not None else None
        if isinstance(content, list) and content:
            t = getattr(content[0], "text", None)
            if isinstance(t, str):
                return t.strip()

        refusal = getattr(msg, "refusal", None) if msg is not None else None
        if isinstance(refusal, str) and refusal.strip():
            return refusal.strip()

        return ""

    tried = []
    last_err: Optional[str] = None
    for fmt in ([api_format] if api_format in {"GENERIC", "COHERE"} else ["GENERIC", "COHERE"]):
        try:
            tried.append(fmt)
            resp = _do_generic() if fmt == "GENERIC" else _do_cohere()
            text = _extract_text(resp)
            text = redact_text(text).strip()
            hint = f"tried={'+'.join(tried)}, text_len={len(text)}"
            return ChatProbeResult(text=text, hint=hint)
        except Exception as e:
            sc = _status_code(e)
            last_err = f"{type(e).__name__}:{sc}" if sc is not None else type(e).__name__
            LOG.debug("GenAI chat probe failed", extra={"format": fmt, "error": str(e)})

    return ChatProbeResult(text="", hint=f"tried={'+'.join(tried)}, error={last_err or 'error'}")
