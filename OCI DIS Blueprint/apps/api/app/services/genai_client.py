"""OCI Generative AI API-key client for evidence-grounded architecture summaries."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import random
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Literal

import httpx
import structlog

from app.core.config import Settings
from app.schemas.ai_review import AiReviewFinding, AiReviewMetric
from app.services.genai_telemetry import record_genai_metric

LOGGER = structlog.get_logger(__name__)

RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
RESPONSES_UNSUPPORTED_STATUS_CODES = frozenset({404, 405})
_RESPONSES_CAPABILITY_CACHE: dict[str, tuple[bool, float]] = {}

PROMPT_REDACTION_POLICY = [
    "email addresses",
    "bearer/api tokens",
    "password/secret assignments",
    "long opaque key strings",
]

SENSITIVE_TEXT_PATTERNS = [
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s,;]{4,}"),
    re.compile(r"\b[A-Za-z0-9_-]{32,}\b"),
]


@dataclass(frozen=True)
class GenAiResult:
    """Normalized OCI Generative AI synthesis result."""

    status: Literal["not_configured", "completed", "failed", "skipped"]
    model: str | None
    summary: str | None
    error: str | None = None
    opc_request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    transport: Literal["responses", "chat_completions"] | None = None
    retry_count: int = 0
    guardrails_status: Literal["completed", "blocked", "failed", "skipped"] = "skipped"


@dataclass(frozen=True)
class GenAiAgentResult:
    """Normalized result of one governed OCI Chat Completions tool-call loop."""

    status: Literal["not_configured", "completed", "failed", "skipped"]
    model: str | None
    summary: str | None
    tool_name: str
    tool_output: dict[str, object] | None = None
    error: str | None = None
    response_id: str | None = None
    opc_request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    transport: Literal["responses", "chat_completions"] | None = None
    retry_count: int = 0
    guardrails_status: Literal["completed", "blocked", "failed", "skipped"] = "skipped"


@dataclass(frozen=True)
class GuardrailCheck:
    """Sanitized result of one OCI Guardrails input or output evaluation."""

    status: Literal["completed", "blocked", "failed", "skipped"]
    content: str
    retry_count: int = 0
    pii_count: int = 0
    error: str | None = None


@dataclass(frozen=True)
class ModelResponse:
    """One provider response plus transport and retry metadata."""

    response: httpx.Response
    transport: Literal["responses", "chat_completions"]
    retry_count: int


@dataclass(frozen=True)
class NormalizedToolCall:
    """Transport-neutral function call selected by the model."""

    call_id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class OciGenAiRuntimeConfig:
    """Resolved non-secret OCI Generative AI API-key configuration."""

    region: str
    base_url: str
    model_id: str
    model_name: str
    compartment_id: str
    api_key_file: str
    transport_mode: str
    connect_timeout_seconds: float
    read_timeout_seconds: float
    max_output_tokens: int

    @property
    def configured(self) -> bool:
        """Return whether a non-empty API key secret is mounted."""

        return bool(self.base_url and self.model_id and _read_api_key(self.api_key_file))


def _read_api_key(path_value: str) -> str:
    """Read the OCI GenAI secret from a mounted file without logging its value."""

    path = Path(path_value)
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _resolved_oci_config(settings: Settings) -> OciGenAiRuntimeConfig:
    """Resolve OCI GenAI settings without returning credential contents."""

    base_url = settings.OCI_GENAI_BASE_URL.strip() or (
        f"https://inference.generativeai.{settings.OCI_GENAI_REGION}.oci.oraclecloud.com/openai/v1"
    )
    return OciGenAiRuntimeConfig(
        region=settings.OCI_GENAI_REGION.strip(),
        base_url=base_url.rstrip("/"),
        model_id=settings.OCI_GENAI_MODEL_ID.strip(),
        model_name=settings.OCI_GENAI_MODEL_NAME.strip(),
        compartment_id=settings.OCI_GENAI_COMPARTMENT_ID.strip(),
        api_key_file=settings.OCI_GENAI_API_KEY_FILE,
        transport_mode=settings.OCI_GENAI_TRANSPORT_MODE.strip().lower(),
        connect_timeout_seconds=settings.OCI_GENAI_CONNECT_TIMEOUT_SECONDS,
        read_timeout_seconds=settings.OCI_GENAI_READ_TIMEOUT_SECONDS,
        max_output_tokens=settings.OCI_GENAI_MAX_OUTPUT_TOKENS,
    )


def _responses_url(runtime: OciGenAiRuntimeConfig) -> str:
    """Return OCI's API-key Responses endpoint for the configured inference host."""

    openai_suffix = "/openai/v1"
    if runtime.base_url.endswith(openai_suffix):
        origin = runtime.base_url[: -len(openai_suffix)]
        return f"{origin}/20231130/actions/v1/responses"
    if runtime.base_url.endswith("/20231130/actions/v1"):
        return f"{runtime.base_url}/responses"
    return f"{runtime.base_url}/responses"


def _capability_cache_key(runtime: OciGenAiRuntimeConfig, settings: Settings) -> str:
    """Return a non-secret cache key for one OCI Responses capability scope."""

    return f"{_responses_url(runtime)}|{runtime.model_id}|{settings.OCI_GENAI_PROJECT_ID.strip()}"


def _cached_responses_capability(
    runtime: OciGenAiRuntimeConfig,
    settings: Settings,
) -> Literal["available", "unavailable", "unverified", "disabled"]:
    """Return the process-local observed Responses capability without network I/O."""

    if runtime.transport_mode == "chat_completions":
        return "disabled"
    cached = _RESPONSES_CAPABILITY_CACHE.get(_capability_cache_key(runtime, settings))
    if cached is None or cached[1] <= time.monotonic():
        return "unverified"
    return "available" if cached[0] else "unavailable"


def _mark_responses_capability(
    runtime: OciGenAiRuntimeConfig,
    settings: Settings,
    *,
    available: bool,
) -> None:
    """Cache an observed capability so unsupported endpoints are not probed per request."""

    ttl = max(1, settings.OCI_GENAI_RESPONSES_UNAVAILABLE_TTL_SECONDS)
    _RESPONSES_CAPABILITY_CACHE[_capability_cache_key(runtime, settings)] = (
        available,
        time.monotonic() + ttl,
    )


def _preferred_transport(
    runtime: OciGenAiRuntimeConfig,
    settings: Settings,
) -> Literal["responses", "chat_completions"]:
    """Select Responses first unless configuration or observed capability requires Chat."""

    if runtime.transport_mode == "chat_completions":
        return "chat_completions"
    if runtime.transport_mode == "responses":
        return "responses"
    return (
        "chat_completions"
        if _cached_responses_capability(runtime, settings) == "unavailable"
        else "responses"
    )


def _safety_identifier(api_key: str, subject: str | None) -> str:
    """Derive a stable privacy-preserving identifier without sending App identity."""

    normalized = (subject or "system").strip() or "system"
    secret = api_key.encode("utf-8")
    return hmac.new(secret, f"oci-dis:{normalized}".encode("utf-8"), hashlib.sha256).hexdigest()


def _guardrails_url(runtime: OciGenAiRuntimeConfig) -> str:
    """Derive the OCI-native ApplyGuardrails endpoint from the inference region."""

    origin = runtime.base_url.split("/openai/v1", 1)[0]
    return f"{origin}/20231130/actions/applyGuardrails"


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Parse the numeric Retry-After form emitted by inference endpoints."""

    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(0.0, (parsed - datetime.now(UTC)).total_seconds())


async def _post_with_retry(
    client: httpx.AsyncClient,
    *,
    url: str,
    headers: dict[str, str],
    json_payload: dict[str, object],
    settings: Settings,
    operation: str,
) -> tuple[httpx.Response, int]:
    """POST with bounded retries for transport failures, throttling, and OCI 5xx errors."""

    max_retries = max(0, settings.OCI_GENAI_MAX_RETRIES)
    base_delay = max(0.0, settings.OCI_GENAI_RETRY_BASE_SECONDS)
    max_delay = max(base_delay, settings.OCI_GENAI_RETRY_MAX_SECONDS)
    retries = 0
    while True:
        await record_genai_metric(settings, "requests_total")
        try:
            response = await client.post(url, headers=headers, json=json_payload)
            if response.is_success:
                await record_genai_metric(settings, "successful_requests_total")
            if response.status_code == 429:
                await record_genai_metric(settings, "http_429_total")
            elif response.status_code >= 500:
                await record_genai_metric(settings, "http_5xx_total")
            if response.status_code not in RETRYABLE_STATUS_CODES or retries >= max_retries:
                return response, retries
            retry_after = _retry_after_seconds(response)
        except httpx.TransportError as exc:
            await record_genai_metric(settings, "transport_errors_total")
            if retries >= max_retries:
                raise
            response = None
            retry_after = None
            await LOGGER.awarning(
                "oci_genai_transport_retry",
                operation=operation,
                attempt=retries + 1,
                error_type=exc.__class__.__name__,
            )
        retries += 1
        await record_genai_metric(settings, "retries_total")
        exponential_cap = min(max_delay, base_delay * (2 ** (retries - 1)))
        delay = retry_after if retry_after is not None else random.uniform(0.0, exponential_cap)
        await LOGGER.awarning(
            "oci_genai_http_retry",
            operation=operation,
            attempt=retries,
            status_code=response.status_code if response is not None else None,
            delay_seconds=round(delay, 3),
        )
        await asyncio.sleep(delay)


def _guardrail_value(value: object, *keys: str) -> object:
    """Read a response field that may use OCI camelCase or SDK kebab-case naming."""

    if not isinstance(value, dict):
        return None
    for key in keys:
        if key in value:
            return value[key]
    return None


def _redact_guardrail_pii(content: str, results: object) -> tuple[str, int]:
    """Redact OCI-detected PII spans before model inference or UI persistence."""

    items = _guardrail_value(
        results,
        "personallyIdentifiableInformation",
        "personally-identifiable-information",
    )
    if not isinstance(items, list):
        return content, 0
    spans: list[tuple[int, int]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        offset = item.get("offset")
        length = item.get("length")
        if isinstance(offset, int) and isinstance(length, int) and 0 <= offset < len(content) and length > 0:
            spans.append((offset, min(len(content), offset + length)))
    redacted = content
    for start, end in sorted(spans, reverse=True):
        redacted = f"{redacted[:start]}[REDACTED]{redacted[end:]}"
    return redacted, len(spans)


def _guardrails_blocked(results: object) -> bool:
    """Treat harmful content or prompt injection as a blocking safety decision."""

    moderation = _guardrail_value(results, "contentModeration", "content-moderation")
    categories = _guardrail_value(moderation, "categories")
    if isinstance(categories, list):
        for category in categories:
            if (
                isinstance(category, dict)
                and str(category.get("name") or "").upper() == "OVERALL"
                and float(category.get("score") or 0.0) >= 1.0
            ):
                return True
    injection = _guardrail_value(results, "promptInjection", "prompt-injection")
    score = _guardrail_value(injection, "score")
    return isinstance(score, (int, float)) and float(score) >= 1.0


async def _apply_guardrails(
    client: httpx.AsyncClient,
    *,
    settings: Settings,
    runtime: OciGenAiRuntimeConfig,
    api_key: str,
    content: str,
    stage: Literal["input", "output"],
    request_id: str,
) -> GuardrailCheck:
    """Evaluate and sanitize one text payload with OCI native Guardrails."""

    if not settings.OCI_GENAI_GUARDRAILS_ENABLED:
        return GuardrailCheck(status="skipped", content=content)
    if not runtime.compartment_id:
        status: Literal["failed", "skipped"] = (
            "failed" if settings.OCI_GENAI_GUARDRAILS_FAILURE_MODE == "closed" else "skipped"
        )
        if status == "failed":
            await record_genai_metric(settings, "guardrail_failures_total")
            await record_genai_metric(settings, "provider_degradations_total")
        return GuardrailCheck(status=status, content=content, error="guardrails_compartment_not_configured")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "opc-request-id": f"{request_id}-{stage}",
        "opc-retry-token": str(uuid.uuid4()),
    }
    body: dict[str, object] = {
        "compartmentId": runtime.compartment_id,
        "guardrailConfigs": {
            "contentModerationConfig": {"categories": ["OVERALL"]},
            "promptInjectionConfig": {},
            "personallyIdentifiableInformationConfig": {},
        },
        "guardrailVersionConfig": {"guardrailVersion": settings.OCI_GENAI_GUARDRAILS_VERSION},
        "input": {"type": "TEXT", "content": content},
    }
    try:
        response, retries = await _post_with_retry(
            client,
            url=_guardrails_url(runtime),
            headers=headers,
            json_payload=body,
            settings=settings,
            operation=f"guardrails_{stage}",
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # pragma: no cover - provider behavior is environment-specific.
        await record_genai_metric(settings, "guardrail_failures_total")
        await record_genai_metric(settings, "provider_degradations_total")
        await LOGGER.awarning(
            "oci_genai_guardrails_failed",
            stage=stage,
            error_type=exc.__class__.__name__,
            request_id=request_id,
        )
        status = "failed" if settings.OCI_GENAI_GUARDRAILS_FAILURE_MODE == "closed" else "skipped"
        return GuardrailCheck(status=status, content=content, error="guardrails_unavailable")
    results = payload.get("results") if isinstance(payload, dict) else None
    sanitized, pii_count = _redact_guardrail_pii(content, results)
    blocked = _guardrails_blocked(results)
    if blocked:
        await record_genai_metric(settings, "guardrail_blocks_total")
    await LOGGER.ainfo(
        "oci_genai_guardrails_completed",
        stage=stage,
        blocked=blocked,
        pii_count=pii_count,
        retry_count=retries,
        request_id=request_id,
    )
    return GuardrailCheck(
        status="blocked" if blocked else "completed",
        content=sanitized,
        retry_count=retries,
        pii_count=pii_count,
        error="guardrails_blocked" if blocked else None,
    )


async def _post_model_request(
    client: httpx.AsyncClient,
    *,
    runtime: OciGenAiRuntimeConfig,
    settings: Settings,
    headers: dict[str, str],
    responses_payload: dict[str, object],
    chat_payload: dict[str, object],
    operation: str,
    force_transport: Literal["responses", "chat_completions"] | None = None,
) -> ModelResponse:
    """Call Responses first and cache an unsupported-endpoint fallback to Chat Completions."""

    transport = force_transport or _preferred_transport(runtime, settings)
    retries = 0
    if transport == "responses":
        response, response_retries = await _post_with_retry(
            client,
            url=_responses_url(runtime),
            headers=headers,
            json_payload=responses_payload,
            settings=settings,
            operation=f"{operation}_responses",
        )
        retries += response_retries
        if (
            response.status_code in RESPONSES_UNSUPPORTED_STATUS_CODES
            and runtime.transport_mode == "auto"
        ):
            _mark_responses_capability(runtime, settings, available=False)
            transport = "chat_completions"
            await record_genai_metric(settings, "responses_fallbacks_total")
            await LOGGER.ainfo(
                "oci_genai_responses_unavailable",
                status_code=response.status_code,
                model=runtime.model_name,
                region=runtime.region,
            )
        else:
            if response.is_success:
                _mark_responses_capability(runtime, settings, available=True)
            return ModelResponse(response=response, transport="responses", retry_count=retries)
    response, chat_retries = await _post_with_retry(
        client,
        url=f"{runtime.base_url}/chat/completions",
        headers=headers,
        json_payload=chat_payload,
        settings=settings,
        operation=f"{operation}_chat_completions",
    )
    return ModelResponse(
        response=response,
        transport="chat_completions",
        retry_count=retries + chat_retries,
    )


def provider_status_payload(
    settings: Settings,
    *,
    actor_jobs_today: int = 0,
    last_provider_status: Literal["completed", "failed"] | None = None,
) -> dict[str, object]:
    """Return configuration and observed provider health without exposing secrets."""

    runtime = _resolved_oci_config(settings)
    daily_limit = max(0, settings.AI_REVIEW_DAILY_JOB_LIMIT)
    remaining = max(0, daily_limit - actor_jobs_today)
    project_configured = bool(settings.OCI_GENAI_PROJECT_ID.strip())
    if runtime.configured and project_configured:
        if last_provider_status == "completed":
            mode = "llm_available"
            status_message = (
                "OCI Generative AI is available and verified by the latest completed synthesis; "
                "governed deterministic evidence remains the source of truth."
            )
        elif last_provider_status == "failed":
            mode = "llm_degraded"
            status_message = (
                "OCI Generative AI is configured, but the latest synthesis failed; "
                "AI Review will continue with governed deterministic evidence."
            )
        else:
            mode = "llm_configured"
            status_message = (
                "OCI Generative AI is configured but has not completed a verified synthesis yet; "
                "governed deterministic evidence remains available."
            )
    elif not runtime.configured:
        mode = "deterministic_only"
        status_message = (
            "OCI Generative AI API key is not mounted; AI Review will use governed deterministic evidence only."
        )
    else:
        mode = "misconfigured"
        status_message = (
            "OCI Generative AI Project OCID is not configured; AI Review will use governed deterministic evidence only."
        )
    return {
        "provider": "oci_genai",
        "configured": runtime.configured and project_configured,
        "mode": mode,
        "model": runtime.model_name,
        "transport": "oci-openai-responses-first-auto",
        "transport_strategy": {
            "preferred": "responses",
            "fallback": "chat_completions",
            "configured_mode": runtime.transport_mode,
            "responses_capability": _cached_responses_capability(runtime, settings),
        },
        "region": runtime.region,
        "auth_mode": "api_key",
        "endpoint": runtime.base_url,
        "request_timeout_seconds": runtime.read_timeout_seconds,
        "retry_policy": {
            "max_retries": max(0, settings.OCI_GENAI_MAX_RETRIES),
            "strategy": "exponential_full_jitter",
            "retryable_status_codes": sorted(RETRYABLE_STATUS_CODES),
            "respects_retry_after": True,
        },
        "safety": {
            "safety_identifier": "hmac_sha256",
            "guardrails_enabled": settings.OCI_GENAI_GUARDRAILS_ENABLED,
            "guardrails_version": settings.OCI_GENAI_GUARDRAILS_VERSION,
            "guardrails_failure_mode": settings.OCI_GENAI_GUARDRAILS_FAILURE_MODE,
            "input_protections": ["content_moderation", "prompt_injection", "pii_redaction"],
            "output_protections": ["content_moderation", "prompt_injection", "pii_redaction"],
        },
        "quota": {
            "daily_job_limit": daily_limit,
            "actor_jobs_today": actor_jobs_today,
            "remaining_jobs_today": remaining,
            "llm_daily_job_limit": max(0, settings.AI_REVIEW_LLM_DAILY_JOB_LIMIT),
        },
        "data_retention_policy": (
            "The app persists deterministic review results and audit events. OCI Generative AI prompts are "
            "transient, redacted evidence payloads; OCI tenancy policy governs provider-side retention."
        ),
        "prompt_redaction_policy": PROMPT_REDACTION_POLICY,
        "status_message": status_message,
    }


def _compact_findings(findings: list[AiReviewFinding]) -> list[dict[str, object]]:
    return [
        {
            "id": finding.id,
            "severity": finding.severity,
            "title": finding.title,
            "summary": finding.summary,
            "evidence": finding.evidence[:5],
        }
        for finding in findings[:8]
    ]


def _compact_metrics(metrics: list[AiReviewMetric]) -> list[dict[str, str]]:
    return [
        {"label": metric.label, "value": metric.value, "detail": metric.detail}
        for metric in metrics
    ]


def _redact_sensitive_text(value: str) -> str:
    redacted = value
    for pattern in SENSITIVE_TEXT_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _redact_prompt_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_sensitive_text(value)
    if isinstance(value, list):
        return [_redact_prompt_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_prompt_value(item) for key, item in value.items()}
    return value


def _build_prompt(
    *,
    project_name: str,
    readiness_score: int,
    readiness_label: str,
    deterministic_summary: str,
    metrics: list[AiReviewMetric],
    findings: list[AiReviewFinding],
    evidence_pack: list[str],
    decision_brief: dict[str, object] | None = None,
    topology_insights: list[dict[str, object]] | None = None,
    stress_scenarios: list[dict[str, object]] | None = None,
    remediation_plan: list[dict[str, object]] | None = None,
) -> list[dict[str, str]]:
    """Build the redacted architecture-review instruction and evidence messages."""

    review_payload = {
        "project_name": project_name,
        "readiness_score": readiness_score,
        "readiness_label": readiness_label,
        "deterministic_summary": deterministic_summary,
        "metrics": _compact_metrics(metrics),
        "findings": _compact_findings(findings),
        "decision_brief": decision_brief or {},
        "topology_insights": topology_insights or [],
        "stress_scenarios": stress_scenarios or [],
        "remediation_plan": remediation_plan or [],
        "evidence_pack": evidence_pack,
    }
    return [
        {
            "role": "instruction",
            "content": (
                "You are an OCI integration architecture review assistant. Use only the provided evidence. "
                "Do not invent facts, counts, services, or blockers. Return a concise executive review summary "
                "in US English, 90-130 words. Mention the sign-off status, top risk theme, topology or stress "
                "signal if present, and the next architect action."
            ),
        },
        {
            "role": "evidence",
            "content": json.dumps(
                _redact_prompt_value(review_payload),
                ensure_ascii=False,
                sort_keys=True,
            ),
        },
    ]


def _response_text(payload: dict[str, Any]) -> str | None:
    """Extract only the provider's user-visible assistant message.

    Responses payloads may contain reasoning, function calls, and other internal
    items alongside the final assistant message. Those items are never valid
    presentation content, even when a provider includes a ``text`` field.
    """

    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    output = payload.get("output")
    if not isinstance(output, list):
        return None
    chunks: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message" or item.get("role") != "assistant":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "output_text":
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    return "\n".join(chunks).strip() or None


def _token_usage(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
    return (
        input_tokens if isinstance(input_tokens, int) else None,
        output_tokens if isinstance(output_tokens, int) else None,
    )


def _normalize_summary(value: str | None) -> str | None:
    """Remove common Markdown emphasis so shared plain-text UI surfaces remain clean."""

    if not value:
        return None
    normalized = re.sub(r"\*\*(.+?)\*\*", r"\1", value)
    normalized = re.sub(r"__(.+?)__", r"\1", normalized)
    normalized = normalized.replace("`", "")
    normalized = re.sub(r"(?m)^#{1,6}\s+", "", normalized)
    return normalized.strip() or None


def _safe_http_error(response: httpx.Response) -> str:
    """Return bounded OCI error metadata without headers, request bodies, or credentials."""

    try:
        payload = response.json()
    except ValueError:
        return f"http_{response.status_code}"
    if not isinstance(payload, dict):
        return f"http_{response.status_code}"
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        code = error.get("code") or error.get("type")
        safe = f"{code}: {message}" if code and message else message or code
        if isinstance(safe, str):
            return _redact_sensitive_text(safe)[:500]
    detail = payload.get("detail") or payload.get("message")
    return _redact_sensitive_text(str(detail))[:500] if detail else f"http_{response.status_code}"


async def _synthesize(
    *,
    settings: Settings,
    system_instruction: str,
    evidence: dict[str, object],
    safety_subject: str | None,
) -> GenAiResult:
    runtime = _resolved_oci_config(settings)
    api_key = _read_api_key(runtime.api_key_file)
    if not api_key:
        return GenAiResult(status="not_configured", model=runtime.model_name, summary=None)
    project_id = settings.OCI_GENAI_PROJECT_ID.strip()
    if not project_id:
        return GenAiResult(
            status="not_configured",
            model=runtime.model_name,
            summary=None,
            error="oci_genai_project_not_configured",
        )
    client_request_id = str(uuid.uuid4())
    retry_count = 0
    prompt = (
        "INSTRUCTIONS\n"
        "Return plain text only, without Markdown, HTML, headings, or emphasis markers.\n"
        f"{system_instruction.strip()}\n\n"
        "GOVERNED EVIDENCE (JSON)\n"
        f"{json.dumps(_redact_prompt_value(evidence), ensure_ascii=False, sort_keys=True)}"
    )
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                runtime.read_timeout_seconds,
                connect=runtime.connect_timeout_seconds,
            )
        ) as client:
            input_guard = await _apply_guardrails(
                client,
                settings=settings,
                runtime=runtime,
                api_key=api_key,
                content=prompt,
                stage="input",
                request_id=client_request_id,
            )
            retry_count += input_guard.retry_count
            if input_guard.status in {"blocked", "failed"}:
                return GenAiResult(
                    status="failed",
                    model=runtime.model_name,
                    summary=None,
                    error=f"input_{input_guard.error or input_guard.status}",
                    opc_request_id=client_request_id,
                    retry_count=retry_count,
                    guardrails_status=input_guard.status,
                )
            safety_identifier = _safety_identifier(api_key, safety_subject)
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "opc-request-id": client_request_id,
                "OpenAI-Project": project_id,
            }
            model_response = await _post_model_request(
                client,
                runtime=runtime,
                settings=settings,
                headers=headers,
                responses_payload={
                    "model": runtime.model_id,
                    "instructions": system_instruction.strip(),
                    "input": input_guard.content,
                    "max_output_tokens": runtime.max_output_tokens,
                    "safety_identifier": safety_identifier,
                },
                chat_payload={
                    "model": runtime.model_id,
                    "messages": [
                        {"role": "system", "content": system_instruction.strip()},
                        {"role": "user", "content": input_guard.content},
                    ],
                    "max_completion_tokens": runtime.max_output_tokens,
                    "safety_identifier": safety_identifier,
                },
                operation="synthesis",
            )
            retry_count += model_response.retry_count
            response = model_response.response
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                payload = {}
            raw_summary = _normalize_summary(_response_text(payload))
            if not raw_summary:
                await record_genai_metric(settings, "provider_degradations_total")
                return GenAiResult(
                    status="failed",
                    model=runtime.model_name,
                    summary=None,
                    error="empty_response",
                    opc_request_id=response.headers.get("opc-request-id", client_request_id),
                    transport=model_response.transport,
                    retry_count=retry_count,
                    guardrails_status=input_guard.status,
                )
            output_guard = await _apply_guardrails(
                client,
                settings=settings,
                runtime=runtime,
                api_key=api_key,
                content=raw_summary,
                stage="output",
                request_id=client_request_id,
            )
            retry_count += output_guard.retry_count
            if output_guard.status in {"blocked", "failed"}:
                return GenAiResult(
                    status="failed",
                    model=runtime.model_name,
                    summary=None,
                    error=f"output_{output_guard.error or output_guard.status}",
                    opc_request_id=response.headers.get("opc-request-id", client_request_id),
                    transport=model_response.transport,
                    retry_count=retry_count,
                    guardrails_status=output_guard.status,
                )
            summary = output_guard.content
    except Exception as exc:  # pragma: no cover - OCI/network failures are environment-specific.
        await record_genai_metric(settings, "provider_degradations_total")
        await LOGGER.awarning(
            "oci_genai_request_failed",
            error_type=exc.__class__.__name__,
            model=runtime.model_name,
            region=runtime.region,
            client_request_id=client_request_id,
        )
        return GenAiResult(
            status="failed",
            model=runtime.model_name,
            summary=None,
            error=(
                _safe_http_error(exc.response)
                if isinstance(exc, httpx.HTTPStatusError)
                else exc.__class__.__name__
            ),
            opc_request_id=client_request_id,
            retry_count=retry_count,
        )
    opc_request_id = response.headers.get("opc-request-id", client_request_id)
    input_tokens, output_tokens = _token_usage(payload)
    await LOGGER.ainfo(
        "oci_genai_request_completed",
        model=runtime.model_name,
        region=runtime.region,
        opc_request_id=opc_request_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        transport=model_response.transport,
        retry_count=retry_count,
        guardrails_status=output_guard.status,
    )
    return GenAiResult(
        status="completed",
        model=runtime.model_name,
        summary=summary,
        opc_request_id=opc_request_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        transport=model_response.transport,
        retry_count=retry_count,
        guardrails_status=output_guard.status,
    )


async def synthesize_review_summary(
    *,
    settings: Settings,
    project_name: str,
    readiness_score: int,
    readiness_label: str,
    deterministic_summary: str,
    metrics: list[AiReviewMetric],
    findings: list[AiReviewFinding],
    evidence_pack: list[str],
    decision_brief: dict[str, object] | None = None,
    topology_insights: list[dict[str, object]] | None = None,
    stress_scenarios: list[dict[str, object]] | None = None,
    remediation_plan: list[dict[str, object]] | None = None,
    safety_subject: str | None = None,
) -> GenAiResult:
    """Synthesize an evidence-only architecture review with OCI Generative AI."""

    prompt = _build_prompt(
        project_name=project_name,
        readiness_score=readiness_score,
        readiness_label=readiness_label,
        deterministic_summary=deterministic_summary,
        metrics=metrics,
        findings=findings,
        evidence_pack=evidence_pack,
        decision_brief=decision_brief,
        topology_insights=topology_insights,
        stress_scenarios=stress_scenarios,
        remediation_plan=remediation_plan,
    )
    return await _synthesize(
        settings=settings,
        system_instruction=prompt[0]["content"],
        evidence=json.loads(prompt[1]["content"]),
        safety_subject=safety_subject,
    )


async def synthesize_governed_summary(
    *,
    settings: Settings,
    system_instruction: str,
    evidence: dict[str, object],
    safety_subject: str | None = None,
) -> GenAiResult:
    """Synthesize a short evidence-only summary for any governed product workflow."""

    return await _synthesize(
        settings=settings,
        system_instruction=system_instruction,
        evidence=evidence,
        safety_subject=safety_subject,
    )


def _normalized_tool_calls(payload: dict[str, Any]) -> list[NormalizedToolCall]:
    """Extract function calls from either Responses or Chat Completions."""

    normalized: list[NormalizedToolCall] = []
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict):
            calls = message.get("tool_calls")
            if isinstance(calls, list):
                for item in calls:
                    function = item.get("function") if isinstance(item, dict) else None
                    if not isinstance(function, dict):
                        continue
                    arguments_value = function.get("arguments", "{}")
                    try:
                        arguments = (
                            json.loads(arguments_value)
                            if isinstance(arguments_value, str)
                            else arguments_value
                        )
                    except json.JSONDecodeError:
                        continue
                    if isinstance(arguments, dict) and isinstance(function.get("name"), str):
                        normalized.append(
                            NormalizedToolCall(
                                call_id=str(item.get("id") or ""),
                                name=str(function["name"]),
                                arguments={str(key): value for key, value in arguments.items()},
                            )
                        )
                return normalized

    output = payload.get("output")
    if not isinstance(output, list):
        return normalized
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        arguments_value = item.get("arguments", "{}")
        try:
            arguments = json.loads(arguments_value) if isinstance(arguments_value, str) else arguments_value
        except json.JSONDecodeError:
            continue
        if isinstance(arguments, dict) and isinstance(item.get("name"), str):
            normalized.append(
                NormalizedToolCall(
                    call_id=str(item.get("call_id") or item.get("id") or ""),
                    name=str(item["name"]),
                    arguments={str(key): value for key, value in arguments.items()},
                )
            )
    return normalized


async def run_governed_tool_agent(
    *,
    settings: Settings,
    instruction: str,
    user_message: str,
    tool_name: str,
    tool_description: str,
    tool_parameters: dict[str, object],
    tool_executor: Callable[[dict[str, object]], Awaitable[dict[str, object]]],
    safety_subject: str | None = None,
) -> GenAiAgentResult:
    """Run one bounded Responses-first tool call and governed evidence synthesis."""

    runtime = _resolved_oci_config(settings)
    api_key = _read_api_key(runtime.api_key_file)
    if not api_key:
        return GenAiAgentResult(
            status="not_configured", model=runtime.model_name, summary=None, tool_name=tool_name
        )
    request_id = str(uuid.uuid4())
    tool_output: dict[str, object] | None = None
    retry_count = 0
    project_id = settings.OCI_GENAI_PROJECT_ID.strip()
    if not project_id:
        return GenAiAgentResult(
            status="not_configured",
            model=runtime.model_name,
            summary=None,
            tool_name=tool_name,
            error="oci_genai_project_not_configured",
        )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "opc-request-id": request_id,
        "OpenAI-Project": project_id,
    }
    chat_tool = {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": tool_description,
            "parameters": tool_parameters,
            "strict": True,
        },
    }
    responses_tool = {
        "type": "function",
        "name": tool_name,
        "description": tool_description,
        "parameters": tool_parameters,
        "strict": True,
    }
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(runtime.read_timeout_seconds, connect=runtime.connect_timeout_seconds)
        ) as client:
            input_guard = await _apply_guardrails(
                client,
                settings=settings,
                runtime=runtime,
                api_key=api_key,
                content=user_message,
                stage="input",
                request_id=request_id,
            )
            retry_count += input_guard.retry_count
            if input_guard.status in {"blocked", "failed"}:
                return GenAiAgentResult(
                    status="failed",
                    model=runtime.model_name,
                    summary=None,
                    tool_name=tool_name,
                    error=f"input_{input_guard.error or input_guard.status}",
                    opc_request_id=request_id,
                    retry_count=retry_count,
                    guardrails_status=input_guard.status,
                )
            safety_identifier = _safety_identifier(api_key, safety_subject)
            first_model = await _post_model_request(
                client,
                runtime=runtime,
                settings=settings,
                headers=headers,
                responses_payload={
                    "model": runtime.model_id,
                    "instructions": instruction,
                    "input": input_guard.content,
                    "tools": [responses_tool],
                    "tool_choice": "required",
                    "max_output_tokens": runtime.max_output_tokens,
                    "safety_identifier": safety_identifier,
                },
                chat_payload={
                    "model": runtime.model_id,
                    "messages": [
                        {"role": "system", "content": instruction},
                        {"role": "user", "content": input_guard.content},
                    ],
                    "tools": [chat_tool],
                    "tool_choice": "required",
                    "max_completion_tokens": runtime.max_output_tokens,
                    "safety_identifier": safety_identifier,
                },
                operation="agent_tool_selection",
            )
            retry_count += first_model.retry_count
            first = first_model.response
            first.raise_for_status()
            first_payload = first.json()
            if not isinstance(first_payload, dict):
                raise ValueError("invalid_agent_response")
            calls = _normalized_tool_calls(first_payload)
            if len(calls) != 1 or calls[0].name != tool_name:
                raise ValueError("required_tool_not_called")
            call = calls[0]
            tool_output = await tool_executor(call.arguments)
            serialized_output = json.dumps(_redact_prompt_value(tool_output), ensure_ascii=False, sort_keys=True)
            if len(serialized_output) > settings.OCI_GENAI_AGENT_MAX_EVIDENCE_CHARS:
                serialized_output = serialized_output[: settings.OCI_GENAI_AGENT_MAX_EVIDENCE_CHARS] + "\n[TRUNCATED]"
            responses_input: list[object] = [
                {"role": "user", "content": input_guard.content},
                *(
                    first_payload.get("output", [])
                    if isinstance(first_payload.get("output"), list)
                    else []
                ),
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": serialized_output,
                },
            ]
            chat_message = first_payload.get("choices", [{}])[0].get("message", {})
            second_model = await _post_model_request(
                client,
                runtime=runtime,
                settings=settings,
                headers=headers,
                responses_payload={
                    "model": runtime.model_id,
                    "instructions": instruction,
                    "input": responses_input,
                    "max_output_tokens": runtime.max_output_tokens,
                    "safety_identifier": safety_identifier,
                },
                chat_payload={
                    "model": runtime.model_id,
                    "messages": [
                        {"role": "system", "content": instruction},
                        {"role": "user", "content": input_guard.content},
                        chat_message,
                        {
                            "role": "tool",
                            "tool_call_id": call.call_id,
                            "content": serialized_output,
                        },
                    ],
                    "tools": [chat_tool],
                    "tool_choice": "none",
                    "max_completion_tokens": runtime.max_output_tokens,
                    "safety_identifier": safety_identifier,
                },
                operation="agent_evidence_synthesis",
                force_transport=first_model.transport,
            )
            retry_count += second_model.retry_count
            second = second_model.response
            second.raise_for_status()
            second_payload = second.json()
            if not isinstance(second_payload, dict):
                raise ValueError("invalid_agent_summary_response")
            raw_summary = _normalize_summary(_response_text(second_payload))
            if not raw_summary:
                raise ValueError("empty_agent_summary")
            output_guard = await _apply_guardrails(
                client,
                settings=settings,
                runtime=runtime,
                api_key=api_key,
                content=raw_summary,
                stage="output",
                request_id=request_id,
            )
            retry_count += output_guard.retry_count
            if output_guard.status in {"blocked", "failed"}:
                return GenAiAgentResult(
                    status="failed",
                    model=runtime.model_name,
                    summary=None,
                    tool_name=tool_name,
                    tool_output=tool_output,
                    error=f"output_{output_guard.error or output_guard.status}",
                    opc_request_id=second.headers.get("opc-request-id", request_id),
                    transport=second_model.transport,
                    retry_count=retry_count,
                    guardrails_status=output_guard.status,
                )
            summary = output_guard.content
        first_in, first_out = _token_usage(first_payload)
        second_in, second_out = _token_usage(second_payload)
        return GenAiAgentResult(
            status="completed", model=runtime.model_name, summary=summary,
            tool_name=tool_name, tool_output=tool_output,
            response_id=str(second_payload.get("id") or first_payload.get("id") or "") or None,
            opc_request_id=second.headers.get("opc-request-id", request_id),
            input_tokens=(first_in or 0) + (second_in or 0),
            output_tokens=(first_out or 0) + (second_out or 0),
            transport=second_model.transport,
            retry_count=retry_count,
            guardrails_status=output_guard.status,
        )
    except Exception as exc:  # pragma: no cover - provider behavior is environment-specific.
        await record_genai_metric(settings, "provider_degradations_total")
        # Keep a bounded, redacted protocol reason for deterministic failures.  The
        # previous class-only diagnostic made a successful 200 response that did not
        # contain the expected function call indistinguishable from every other
        # ValueError, which prevented us from selecting the compatible transport.
        safe_error = (
            _safe_http_error(exc.response)
            if isinstance(exc, httpx.HTTPStatusError)
            else _redact_sensitive_text(str(exc))[:200]
            if isinstance(exc, ValueError) and str(exc)
            else exc.__class__.__name__
        )
        await LOGGER.awarning(
            "oci_genai_agent_request_failed", error_type=exc.__class__.__name__, error=safe_error,
            model=runtime.model_name, region=runtime.region,
            client_request_id=request_id, tool_name=tool_name,
        )
        return GenAiAgentResult(
            status="failed", model=runtime.model_name, summary=None, tool_name=tool_name,
            tool_output=tool_output, error=safe_error, opc_request_id=request_id,
            retry_count=retry_count,
        )
