from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..auth.providers import resolve_auth
from ..logging import get_logger
from .config import GenAIConfig, load_genai_config
from .redact import redact_text

LOG = get_logger(__name__)


_REGION_FROM_ENDPOINT_RE = re.compile(r"inference\.generativeai\.(?P<region>[a-z0-9-]+)\.")


def _endpoint_region(endpoint: str) -> Optional[str]:
    m = _REGION_FROM_ENDPOINT_RE.search(endpoint or "")
    if not m:
        return None
    return m.group("region")


def _build_prompt(
    *,
    run_facts: Dict[str, Any],
    architecture_facts: Optional[Dict[str, Any]] = None,
    report_md: Optional[str] = None,
) -> str:
    # Keep it short and structured; the model should output Markdown text only.
    # Note: run_facts and architecture_facts are already redacted.
    lines: List[str] = []
    lines.append("You are a Cloud Architect and SRE.")
    lines.append("Write an Executive Summary for an OCI inventory report.")
    lines.append("Constraints:")
    lines.append("- Output Markdown text ONLY (no code fences).")
    lines.append("- 1-2 short sentences, then 4-8 bullet points max.")
    lines.append("- Describe tenancy structure, network layout, workload/service groupings, and data/stores when possible.")
    lines.append("- Include run coverage notes (scope, exclusions, enrichment gaps) as non-blocking observations.")
    lines.append("- No speculation; phrase as observations (e.g., 'appears to', 'suggests') and only when supported by facts.")
    lines.append("- Do not include secrets, OCIDs, URLs, or raw error dumps.")
    lines.append("")
    if report_md:
        # Provide the report as the primary context.
        # Keep it bounded to avoid huge prompts.
        txt = (report_md or "").strip()
        if len(txt) > 12000:
            txt = txt[:12000] + "\n... (truncated) ..."
        lines.append("Context (report.md):")
        lines.append("```")
        lines.append(txt)
        lines.append("```")
    else:
        lines.append("Facts:")
        for k in sorted(run_facts.keys()):
            lines.append(f"- {k}: {run_facts[k]}")
        if architecture_facts:
            lines.append("")
            lines.append("Architecture Facts:")
            for k in sorted(architecture_facts.keys()):
                lines.append(f"- {k}: {architecture_facts[k]}")
    lines.append("")
    lines.append("Now write the Executive Summary.")
    return "\n".join(lines)


def run_genai_best_effort_prompt(
    *,
    prompt: str,
    genai_cfg: Optional[GenAIConfig] = None,
    prefer_chat: bool = False,
    api_format: Optional[str] = None,
    max_tokens: int = 300,
    temperature: Optional[float] = None,
) -> tuple[str, str]:
    """Run a best-effort GenAI prompt with generate_text + chat fallback."""

    cfg = genai_cfg or load_genai_config()

    # Resolve auth for GenAI specifically (config profile from genai.yaml).
    ctx = resolve_auth("config", cfg.oci_profile, None)

    # Lazy import so tests can mock this function without importing OCI SDK models.
    import oci  # type: ignore

    from oci.generative_ai_inference import GenerativeAiInferenceClient  # type: ignore
    from oci.generative_ai_inference.models import (  # type: ignore
        CohereLlmInferenceRequest,
        BaseChatRequest,
        ChatDetails,
        GenerateTextDetails,
        OnDemandServingMode,
        LlamaLlmInferenceRequest,
        GenericChatRequest,
        SystemMessage,
        UserMessage,
        TextContent,
    )

    region = _endpoint_region(cfg.endpoint) or "us-chicago-1"
    oci_cfg = dict(ctx.config_dict or {})
    oci_cfg["region"] = oci_cfg.get("region") or region

    # IMPORTANT: Do not pass signer=None. The OCI SDK interprets the presence of a
    # signer kwarg as authoritative and will skip building a signer from config.
    client_kwargs: Dict[str, Any] = {
        "service_endpoint": cfg.endpoint,
        "retry_strategy": getattr(oci.retry, "DEFAULT_RETRY_STRATEGY", None),
        "timeout": (10, 60),
    }
    if ctx.signer is not None:
        client_kwargs["signer"] = ctx.signer

    client = GenerativeAiInferenceClient(oci_cfg, **client_kwargs)

    prompt_red = redact_text(prompt).strip()
    api_format_u = (api_format or "AUTO").strip().upper()
    temp_val = float(temperature) if temperature is not None else 0.2
    max_tokens = int(max_tokens)

    def _extract_text(value: Any, *, max_depth: int = 2, _seen: Optional[set[int]] = None) -> str:
        """Best-effort extraction of human-readable text."""

        if value is None or max_depth <= 0:
            return ""
        if _seen is None:
            _seen = set()
        oid = id(value)
        if oid in _seen:
            return ""
        _seen.add(oid)

        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            # Common dict payload patterns.
            for k in ("text", "value", "content"):
                v = value.get(k)
                if isinstance(v, str) and v.strip():
                    return v
                # Sometimes these keys hold nested structures.
                nested = _extract_text(v, max_depth=max_depth - 1, _seen=_seen)
                if nested.strip():
                    return nested
            return ""

        # Lists/tuples can appear in some SDK shapes.
        if isinstance(value, (list, tuple)):
            for item in value:
                nested = _extract_text(item, max_depth=max_depth - 1, _seen=_seen)
                if nested.strip():
                    return nested
            return ""

        # SDK model objects
        for attr in ("text", "value", "content"):
            v = getattr(value, attr, None)
            if isinstance(v, str) and v.strip():
                return v
            nested = _extract_text(v, max_depth=max_depth - 1, _seen=_seen)
            if nested.strip():
                return nested
        return ""

    def _extract_text_from_content(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                t = _extract_text(item)
                if t.strip():
                    parts.append(t.strip())
            return "\n".join(parts)
        return _extract_text(content)

    def _iter_text_candidates(obj: Any, *, max_depth: int = 5, _seen: Optional[set[int]] = None) -> List[str]:
        """Best-effort text extraction across SDK/dict/list response shapes."""

        if max_depth <= 0:
            return []
        if _seen is None:
            _seen = set()
        oid = id(obj)
        if oid in _seen:
            return []
        _seen.add(oid)

        out: List[str] = []
        if obj is None:
            return out
        if isinstance(obj, str):
            out.append(obj)
            return out
        if isinstance(obj, dict):
            for v in obj.values():
                out.extend(_iter_text_candidates(v, max_depth=max_depth - 1, _seen=_seen))
            return out
        if isinstance(obj, (list, tuple)):
            for v in obj:
                out.extend(_iter_text_candidates(v, max_depth=max_depth - 1, _seen=_seen))
            return out

        # Common SDK object patterns
        for attr in ("text", "value"):
            v = getattr(obj, attr, None)
            if isinstance(v, str):
                out.append(v)

        # OCI SDK model objects often provide to_dict(); use it to discover
        # string fields that may not be exposed as direct attrs.
        to_dict = getattr(obj, "to_dict", None)
        if callable(to_dict):
            try:
                d2 = to_dict()
                if isinstance(d2, dict):
                    out.extend(_iter_text_candidates(d2, max_depth=max_depth - 1, _seen=_seen))
            except Exception:
                pass

        d = getattr(obj, "__dict__", None)
        if isinstance(d, dict):
            # cap iteration to avoid weird objects exploding
            for v in list(d.values())[:50]:
                out.extend(_iter_text_candidates(v, max_depth=max_depth - 1, _seen=_seen))
        return out

    def _pick_best_text(candidates: List[str]) -> str:
        bad = {"user", "assistant", "system", "tool"}
        cleaned: List[str] = []
        for s in candidates:
            if not isinstance(s, str):
                continue
            t = s.strip()
            if not t:
                continue
            if t.lower() in bad:
                continue
            # Do not treat obvious identifiers/placeholders as "summary".
            if "ocid1." in t.lower() or "<ocid>" in t.lower() or "<url>" in t.lower():
                continue
            # Avoid selecting pure IDs/metadata-like strings.
            if len(t) < 12 and " " not in t and "\n" not in t and not t.startswith("-"):
                continue
            cleaned.append(t)
        if not cleaned:
            return ""
        # Prefer bullet-ish or longer content.
        def score(t: str) -> tuple[int, int]:
            return (
                1 if ("\n" in t or t.lstrip().startswith("-")) else 0,
                len(t),
            )

        cleaned.sort(key=score, reverse=True)
        return cleaned[0]

    def _status_code(exc: BaseException) -> Optional[int]:
        v = getattr(exc, "status", None)
        try:
            return int(v)
        except Exception:
            return None

    def _should_retry_with_cohere(exc: BaseException) -> bool:
        # Most runtime/model mismatches surface as 400.
        if _status_code(exc) == 400:
            return True
        # Fallback heuristic when status isn't available.
        msg = str(exc).lower()
        return "model ocid" in msg or "runtime" in msg or "llama" in msg or "cohere" in msg

    def _should_fallback_to_chat(exc: BaseException) -> bool:
        # We fall back to chat() when generate_text is unavailable for the model.
        # Observed cases:
        # - 400: "model OCID ... does not support TextGeneration" (chat-only models)
        # - 404: "Entity with key <model_ocid> not found" (on-demand generate_text models retired)
        sc = _status_code(exc)
        msg = str(exc).lower()
        if sc == 400 and "does not support textgeneration" in msg:
            return True
        if sc == 404 and "entity with key" in msg and "not found" in msg:
            return True
        return False

    def _looks_usable_summary(text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return False
        # Reject outputs that are only redaction placeholders.
        if t in {"<ocid>", "<url>"}:
            return False
        if re.fullmatch(r"(?:<ocid>|<url>|[\\s\\-•*#])+", t):
            return False
        # Reject outputs that are effectively only redactions.
        if t.startswith("[") and t.endswith("]") and "REDACT" in t.upper() and len(t) < 64:
            return False
        # Require at least some alphabetic characters.
        if not any(ch.isalpha() for ch in t):
            return False
        # Avoid accepting a single token / metadata-like string.
        if " " not in t and "\n" not in t and not t.lstrip().startswith("-") and len(t) < 40:
            return False
        return True

    def _do_chat(*, api_format_value: str) -> Any:
        # Chat-style inference (for CHAT-capable models). Some models support
        # only specific api_formats; we try GENERIC first and may retry COHERE
        # when the response contains no usable text.
        if api_format_value == BaseChatRequest.API_FORMAT_COHERE:
            from oci.generative_ai_inference.models import CohereChatRequest  # type: ignore

            chat_req = CohereChatRequest(
                api_format=BaseChatRequest.API_FORMAT_COHERE,
                message=prompt_red,
                is_stream=False,
                max_tokens=max_tokens,
                temperature=temp_val,
                top_p=0.9,
            )
        else:
            system_content = TextContent(
                text=(
                    "You are an SRE/Cloud inventory assistant. "
                    "Follow the user's instructions. Output Markdown text only. "
                    "Do not include secrets, OCIDs, URLs, or raw error dumps."
                )
            )
            user_content = TextContent(text=prompt_red)
            # Prefer a role-specific message type so the SDK serializes the
            # correct subtype reliably.
            messages = [SystemMessage(content=[system_content]), UserMessage(content=[user_content])]
            # Some model families accept maxCompletionTokens, others accept maxTokens.
            # Prefer maxCompletionTokens and fall back only when the service rejects it.
            chat_req = GenericChatRequest(
                api_format=BaseChatRequest.API_FORMAT_GENERIC,
                messages=messages,
                is_stream=False,
                max_completion_tokens=max_tokens,
                verbosity="LOW",
            )
            if temperature is not None:
                chat_req.temperature = temp_val

        chat_details = ChatDetails(
            compartment_id=cfg.compartment_id,
            serving_mode=OnDemandServingMode(model_id=cfg.base_model_id),
            chat_request=chat_req,
        )
        try:
            return client.chat(chat_details)
        except Exception as e:
            # If the model rejects maxCompletionTokens, retry using maxTokens.
            sc = _status_code(e)
            msg = str(e)
            if sc == 400 and "maxcompletiontokens" in msg.lower() and "unsupported" in msg.lower():
                if api_format_value != BaseChatRequest.API_FORMAT_GENERIC:
                    raise
                chat_details_2 = ChatDetails(
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
                return client.chat(chat_details_2)
            raise

    if api_format_u not in {"AUTO", BaseChatRequest.API_FORMAT_GENERIC, BaseChatRequest.API_FORMAT_COHERE}:
        api_format_u = "AUTO"

    used_runtime = ""

    # If prefer_chat is set, skip generate_text and use chat() directly.
    if prefer_chat:
        chat_format = (
            BaseChatRequest.API_FORMAT_COHERE
            if api_format_u == BaseChatRequest.API_FORMAT_COHERE
            else BaseChatRequest.API_FORMAT_GENERIC
        )
        resp = _do_chat(api_format_value=chat_format)
        used_runtime = "CHAT"
    # Otherwise: try generate_text first. If the model/runtime mismatches or the on-demand
    # generate_text model is retired/unavailable, fall back:
    # 1) LLAMA generate_text
    # 2) COHERE generate_text
    # 3) chat() for chat-only models
    else:
        try:
            req = GenerateTextDetails(
                compartment_id=cfg.compartment_id,
                serving_mode=OnDemandServingMode(model_id=cfg.base_model_id),
                inference_request=LlamaLlmInferenceRequest(
                    prompt=prompt_red,
                    is_stream=False,
                    num_generations=1,
                    temperature=temp_val,
                    top_p=0.9,
                    max_tokens=max_tokens,
                ),
            )
            resp = client.generate_text(req)
            used_runtime = "LLAMA"
        except Exception as e:
            if _should_fallback_to_chat(e):
                chat_format = (
                    BaseChatRequest.API_FORMAT_COHERE
                    if api_format_u == BaseChatRequest.API_FORMAT_COHERE
                    else BaseChatRequest.API_FORMAT_GENERIC
                )
                resp = _do_chat(api_format_value=chat_format)
                used_runtime = "CHAT"
            elif not _should_retry_with_cohere(e):
                raise
            else:
                try:
                    req = GenerateTextDetails(
                        compartment_id=cfg.compartment_id,
                        serving_mode=OnDemandServingMode(model_id=cfg.base_model_id),
                        inference_request=CohereLlmInferenceRequest(
                            prompt=prompt_red,
                            is_stream=False,
                            num_generations=1,
                            temperature=temp_val,
                            top_p=0.9,
                            max_tokens=max_tokens,
                        ),
                    )
                    resp = client.generate_text(req)
                    used_runtime = "COHERE"
                except Exception as e2:
                    if not _should_fallback_to_chat(e2):
                        raise

                    chat_format = (
                        BaseChatRequest.API_FORMAT_COHERE
                        if api_format_u == BaseChatRequest.API_FORMAT_COHERE
                        else BaseChatRequest.API_FORMAT_GENERIC
                    )
                    resp = _do_chat(api_format_value=chat_format)
                    used_runtime = "CHAT"

    # Parse response
    data = getattr(resp, "data", None)
    if data is None:
        raise RuntimeError("GenAI response missing data")

    out = ""
    debug_hint: str = ""

    if used_runtime in {"LLAMA", "COHERE"}:
        ir = getattr(data, "inference_response", None)
        choices = getattr(ir, "choices", None) if ir is not None else None
        if not choices:
            raise RuntimeError("GenAI response missing choices")
        text = getattr(choices[0], "text", "")
        out = str(text or "").strip()
    elif used_runtime == "CHAT":
        used_api_format = (
            BaseChatRequest.API_FORMAT_COHERE
            if api_format_u == BaseChatRequest.API_FORMAT_COHERE
            else BaseChatRequest.API_FORMAT_GENERIC
        )
        tried_cohere_format = False
        cohere_retry_error: str = ""

        choices = None
        choice0 = None
        msg = None
        content = None
        refusal = None

        cr = getattr(data, "chat_response", None)

        # Cohere chat responses expose the generated text directly.
        cr_text = getattr(cr, "text", None) if cr is not None else None
        if isinstance(cr_text, str) and cr_text.strip():
            out = cr_text.strip()
        else:
            # Some SDK shapes may put choices directly on data.
            choices = getattr(cr, "choices", None) if cr is not None else None
            if not choices:
                choices = getattr(data, "choices", None)
            if not choices:
                raise RuntimeError("GenAI chat response missing choices")
            choice0 = choices[0]
            msg = getattr(choice0, "message", None)
            if msg is None and isinstance(choice0, dict):
                msg = choice0.get("message")
            refusal = getattr(msg, "refusal", None) if msg is not None else None
            content = getattr(msg, "content", None) if msg is not None else None
            if content is None and isinstance(msg, dict):
                content = msg.get("content")
            out = _extract_text_from_content(content).strip()
            if not out and isinstance(refusal, str) and refusal.strip():
                out = refusal.strip()
            if not out:
                # Deep fallback across response objects
                candidates = []
                candidates.extend(_iter_text_candidates(data))
                candidates.extend(_iter_text_candidates(cr))
                candidates.extend(_iter_text_candidates(choices[0] if choices else None))
                out = _pick_best_text(candidates).strip()

        # If GENERIC format yielded no usable output, retry with COHERE format.
        # This must be evaluated after redaction to avoid treating an OCID-only
        # response as "non-empty".
        if not out or not _looks_usable_summary(redact_text(out).strip()):
            if api_format_u == "AUTO":
                try:
                    tried_cohere_format = True
                    resp2 = _do_chat(api_format_value=BaseChatRequest.API_FORMAT_COHERE)
                    data2 = getattr(resp2, "data", None)
                    cr2 = getattr(data2, "chat_response", None) if data2 is not None else None
                    cr2_text = getattr(cr2, "text", None) if cr2 is not None else None
                    if isinstance(cr2_text, str) and cr2_text.strip():
                        out = cr2_text.strip()
                        data = data2
                        cr = cr2
                        used_api_format = BaseChatRequest.API_FORMAT_COHERE
                except Exception as e_coh:
                    # Capture a safe hint only; do not dump server messages.
                    try:
                        sc = _status_code(e_coh)
                        cohere_retry_error = f"{type(e_coh).__name__}:{sc}" if sc is not None else type(e_coh).__name__
                    except Exception:
                        cohere_retry_error = "error"

        # Collect a tiny hint for troubleshooting without dumping full payloads.
        try:
            choices_len = len(choices) if choices else 0
            choice_t = type(choice0).__name__ if choice0 is not None else "None"
            msg_t = type(msg).__name__ if msg is not None else "None"
            content_t = type(content).__name__ if content is not None else "None"
            refusal_len = len(refusal.strip()) if isinstance(refusal, str) else 0

            tool_calls = getattr(msg, "tool_calls", None) if msg is not None else None
            tool_calls_len = len(tool_calls) if isinstance(tool_calls, list) else 0

            content_len = 0
            content_item_types: List[str] = []
            content0_text_len: Optional[int] = None
            content0_has_text: Optional[bool] = None
            if isinstance(content, list):
                content_len = len(content)
                for item in content[:5]:
                    content_item_types.append(type(item).__name__)
                if content:
                    c0 = content[0]
                    c0_text = _extract_text(c0).strip()
                    content0_text_len = len(c0_text)
                    content0_has_text = bool(c0_text)

            hint_parts = [
                f"choices={choices_len}",
                f"api_format={used_api_format}",
                f"tried_cohere={tried_cohere_format}",
                f"choice={choice_t}",
                f"message={msg_t}",
                f"content={content_t}",
                f"refusal_len={refusal_len}",
                f"tool_calls={tool_calls_len}",
            ]
            if cohere_retry_error:
                hint_parts.append(f"cohere_error={cohere_retry_error}")
            if isinstance(content, list):
                hint_parts.append(f"content_len={content_len}")
                if content_item_types:
                    hint_parts.append(f"content_items={'+'.join(content_item_types)}")
                if content0_text_len is not None and content0_has_text is not None:
                    hint_parts.append(f"content0_has_text={content0_has_text}")
                    hint_parts.append(f"content0_text_len={content0_text_len}")
            if used_api_format == BaseChatRequest.API_FORMAT_COHERE:
                hint_parts.append(f"cohere_text_len={len(out)}")
            debug_hint = ", ".join(hint_parts)
        except Exception:
            debug_hint = ""
    else:  # pragma: no cover
        raise RuntimeError(f"Unknown GenAI runtime: {used_runtime}")

    # Final safety pass: NEVER allow OCIDs or URLs into the report, even if the
    # model returns them. If redaction makes the output unusable, fail cleanly.
    out = redact_text(out).strip()

    if "ocid1." in out or "https://" in out or "http://" in out:
        raise RuntimeError("GenAI output contained disallowed identifiers")

    if not _looks_usable_summary(out):
        data_t = type(data).__name__
        cr_t = type(getattr(data, "chat_response", None)).__name__ if used_runtime == "CHAT" else ""
        hint = f", hint={debug_hint}" if debug_hint else ""
        raise RuntimeError(
            f"GenAI returned empty/invalid response (runtime={used_runtime}, data={data_t}, chat_response={cr_t}{hint})"
        )

    return out, used_runtime


def generate_executive_summary(
    *,
    genai_cfg: Optional[GenAIConfig] = None,
    status: str,
    started_at: str,
    finished_at: str,
    subscribed_regions: List[str],
    requested_regions: Optional[List[str]],
    excluded_regions: List[Dict[str, str]],
    metrics: Optional[Dict[str, Any]],
    architecture_facts: Optional[Dict[str, Any]] = None,
    report_md: Optional[str] = None,
) -> str:
    """
    Generate a short Markdown executive summary via OCI Generative AI Inference.

    This is intentionally best-effort and must be called only when explicitly enabled.
    """

    cfg = genai_cfg or load_genai_config()

    excluded_short = [
        {"region": str(x.get("region") or ""), "reason": str(x.get("reason") or "")}
        for x in excluded_regions
    ]

    run_facts: Dict[str, Any] = {
        "Status": status,
        "Started (UTC)": started_at,
        "Finished (UTC)": finished_at,
        "Subscribed regions": ", ".join(subscribed_regions),
        "Requested regions": ", ".join(requested_regions) if requested_regions else "(all subscribed)",
        "Excluded regions": ", ".join(sorted({x.get('region','') for x in excluded_short if x.get('region')}))
        if excluded_short
        else "none",
    }
    if metrics:
        run_facts["Discovered records"] = str(metrics.get("total_discovered", ""))
        cbes = metrics.get("counts_by_enrich_status") or {}
        if cbes:
            run_facts["Enrichment status"] = ", ".join([f"{k}={cbes[k]}" for k in sorted(cbes.keys())])

        cbrt = metrics.get("counts_by_resource_type") or {}
        if cbrt:
            # top 8 types
            top = sorted(((k, int(v)) for k, v in cbrt.items()), key=lambda kv: (-kv[1], kv[0]))[:8]
            run_facts["Top resource types"] = ", ".join([f"{k}={v}" for k, v in top])

    # Redact aggressively before sending to GenAI.
    run_facts = {k: redact_text(str(v)) for k, v in run_facts.items()}

    arch_facts_red: Optional[Dict[str, Any]] = None
    if architecture_facts:
        arch_facts_red = {k: redact_text(str(v)) for k, v in architecture_facts.items()}

    # Redact any report.md content before sending to GenAI.
    report_md_red = redact_text(report_md).strip() if report_md else None
    prompt = _build_prompt(run_facts=run_facts, architecture_facts=arch_facts_red, report_md=report_md_red)

    out, runtime = run_genai_best_effort_prompt(
        prompt=prompt,
        genai_cfg=cfg,
        prefer_chat=bool(report_md_red),
        api_format="AUTO",
        max_tokens=300,
        temperature=0.2,
    )
    LOG.info("Generated GenAI executive summary", extra={"chars": len(out), "runtime": runtime})
    return out
