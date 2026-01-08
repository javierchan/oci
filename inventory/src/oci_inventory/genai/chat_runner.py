from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..auth.providers import resolve_auth
from ..logging import get_logger
from .config import GenAIConfig, load_genai_config
from .redact import redact_text

LOG = get_logger(__name__)


def run_genai_chat(
    *,
    message: str,
    api_format: str = "GENERIC",
    system: Optional[str] = None,
    max_tokens: int = 300,
    temperature: Optional[float] = None,
    genai_cfg: Optional[GenAIConfig] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Run a single OCI GenAI Inference chat() call.

    Returns (redacted_text, hint_dict). This is best-effort and intentionally
    avoids returning raw payloads.
    """

    cfg = genai_cfg or load_genai_config()
    api_format_u = (api_format or "GENERIC").strip().upper()

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

    oci_cfg = dict(ctx.config_dict or {})

    client_kwargs: Dict[str, Any] = {
        "service_endpoint": cfg.endpoint,
        "retry_strategy": getattr(oci.retry, "DEFAULT_RETRY_STRATEGY", None),
        "timeout": (10, 60),
    }
    if ctx.signer is not None:
        client_kwargs["signer"] = ctx.signer

    client = GenerativeAiInferenceClient(oci_cfg, **client_kwargs)

    # Always redact inputs.
    system_red = redact_text(system or "").strip() if system else None
    message_red = redact_text(message or "").strip()

    if api_format_u == BaseChatRequest.API_FORMAT_COHERE:
        kwargs: Dict[str, Any] = {
            "api_format": BaseChatRequest.API_FORMAT_COHERE,
            "message": message_red,
            "is_stream": False,
            "max_tokens": max_tokens,
            "top_p": 0.9,
            "preamble_override": system_red or None,
        }
        if temperature is not None:
            kwargs["temperature"] = float(temperature)

        chat_req = CohereChatRequest(**kwargs)
    else:
        messages = []
        if system_red:
            messages.append(SystemMessage(content=[TextContent(text=system_red)]))
        messages.append(UserMessage(content=[TextContent(text=message_red)]))

        # Prefer maxCompletionTokens and fall back to maxTokens if required.
        kwargs2: Dict[str, Any] = {
            "api_format": BaseChatRequest.API_FORMAT_GENERIC,
            "messages": messages,
            "is_stream": False,
            "max_completion_tokens": max_tokens,
            "verbosity": "LOW",
        }
        if temperature is not None:
            kwargs2["temperature"] = float(temperature)

        chat_req = GenericChatRequest(**kwargs2)

    chat_details = ChatDetails(
        compartment_id=cfg.compartment_id,
        serving_mode=OnDemandServingMode(model_id=cfg.base_model_id),
        chat_request=chat_req,
    )

    hint: Dict[str, Any] = {"api_format": api_format_u}
    try:
        resp = client.chat(chat_details)
    except Exception as e:
        # Retry GENERIC only when maxCompletionTokens is rejected.
        if api_format_u == "GENERIC" and getattr(e, "status", None) == 400 and "maxcompletiontokens" in str(e).lower():
            from oci.generative_ai_inference.models import GenericChatRequest  # type: ignore

            chat_details = ChatDetails(
                compartment_id=cfg.compartment_id,
                serving_mode=OnDemandServingMode(model_id=cfg.base_model_id),
                chat_request=GenericChatRequest(
                    api_format=BaseChatRequest.API_FORMAT_GENERIC,
                    messages=messages,
                    is_stream=False,
                    max_tokens=max_tokens,
                    verbosity="LOW",
                ),
            )
            resp = client.chat(chat_details)
            hint["retry_max_tokens"] = True
        else:
            raise

    data = getattr(resp, "data", None)
    cr = getattr(data, "chat_response", None) if data is not None else None

    # Parse COHERE response
    if api_format_u == "COHERE":
        text = getattr(cr, "text", None)
        out = str(text or "").strip()
        hint["text_len"] = len(out)
        return redact_text(out).strip(), hint

    # Parse GENERIC response
    choices = getattr(cr, "choices", None) if cr is not None else None
    if not choices:
        hint["choices"] = 0
        return "", hint
    choice0 = choices[0]
    msg = getattr(choice0, "message", None)
    content = getattr(msg, "content", None) if msg is not None else None
    refusal = getattr(msg, "refusal", None) if msg is not None else None

    out = ""
    if isinstance(content, list) and content:
        out = str(getattr(content[0], "text", "") or "").strip()
    if not out and isinstance(refusal, str) and refusal.strip():
        out = refusal.strip()

    content_item_types = []
    content0_text_len = None
    if isinstance(content, list) and content:
        content_item_types = [type(x).__name__ for x in content[:3]]
        content0_text_len = len(str(getattr(content[0], "text", "") or ""))

    hint.update(
        {
            "choices": len(choices) if choices else 0,
            "message_type": type(msg).__name__ if msg is not None else "None",
            "content_type": type(content).__name__ if content is not None else "None",
            "content_len": len(content) if isinstance(content, list) else None,
            "content_item_types": "+".join(content_item_types) if content_item_types else "",
            "content0_text_len": content0_text_len,
            "out_len": len(out),
            "refusal_len": len(refusal.strip()) if isinstance(refusal, str) else 0,
        }
    )

    return redact_text(out).strip(), hint
