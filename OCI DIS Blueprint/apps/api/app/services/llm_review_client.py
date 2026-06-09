"""LLM client used to synthesize governed AI review summaries."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from app.core.config import Settings
from app.schemas.ai_review import AiReviewFinding, AiReviewMetric

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
class LlmReviewResult:
    """Normalized result from the configured LLM provider."""

    status: Literal["not_configured", "completed", "failed", "skipped"]
    model: str | None
    summary: str | None
    error: str | None = None


@dataclass(frozen=True)
class CodexRuntimeConfig:
    """Resolved Codex backend runtime settings from mounted Codex config/auth."""

    api_key: str
    account_id: str | None
    base_url: str
    wire_api: str
    model: str
    headers: dict[str, str]


def _responses_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/responses") else f"{normalized}/responses"


def _uses_chatgpt_codex_backend(base_url: str) -> bool:
    return "chatgpt.com/backend-api/codex" in base_url.rstrip("/")


def _read_json_file(path_value: str) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_toml_file(path_value: str) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _string_value(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _codex_provider_config(config_path: str, provider_name: str) -> dict[str, Any]:
    config = _read_toml_file(config_path)
    providers = config.get("model_providers")
    if not isinstance(providers, dict):
        return {}
    provider = providers.get(provider_name)
    return provider if isinstance(provider, dict) else {}


def _codex_auth_credentials(auth_path: str) -> tuple[str, str | None]:
    auth = _read_json_file(auth_path)
    for key_name in ("CODEX_API_KEY", "codex_api_key", "OPENAI_API_KEY", "openai_api_key"):
        value = _string_value(auth.get(key_name))
        if value:
            return value, None
    tokens = auth.get("tokens")
    if isinstance(tokens, dict):
        account_id = _string_value(tokens.get("account_id"))
        for key_name in ("access_token", "id_token"):
            value = _string_value(tokens.get(key_name))
            if value:
                return value, account_id
    return "", None


def _resolved_codex_config(settings: Settings) -> CodexRuntimeConfig:
    provider = _codex_provider_config(settings.CODEX_CONFIG_PATH, settings.CODEX_PROVIDER_NAME)
    provider_headers = provider.get("http_headers")
    headers = {
        "client": settings.CODEX_CLIENT_NAME,
        "client-version": settings.CODEX_CLIENT_VERSION,
    }
    if isinstance(provider_headers, dict):
        headers.update(
            {
                str(key): str(value)
                for key, value in provider_headers.items()
                if isinstance(key, str) and isinstance(value, str) and value.strip()
            }
        )

    base_url = _string_value(provider.get("base_url")) or settings.CODEX_BASE_URL
    wire_api = _string_value(provider.get("wire_api")) or settings.CODEX_WIRE_API
    model = _string_value(provider.get("model")) or settings.CODEX_MODEL
    api_key, account_id = _codex_auth_credentials(settings.CODEX_AUTH_JSON_PATH)
    return CodexRuntimeConfig(
        api_key=api_key,
        account_id=account_id,
        base_url=base_url,
        wire_api=wire_api,
        model=model,
        headers=headers,
    )


def provider_status_payload(
    settings: Settings,
    *,
    actor_jobs_today: int = 0,
) -> dict[str, object]:
    """Return provider health metadata without exposing credentials."""

    runtime_config = _resolved_codex_config(settings)
    daily_limit = max(0, settings.AI_REVIEW_DAILY_JOB_LIMIT)
    remaining = max(0, daily_limit - actor_jobs_today)
    configured = bool(runtime_config.api_key)
    mode: Literal["deterministic_only", "llm_available", "misconfigured"]
    if configured and runtime_config.wire_api.strip().lower() == "responses":
        mode = "llm_available"
        status_message = "LLM synthesis is configured; deterministic evidence remains the source of truth."
    elif configured:
        mode = "misconfigured"
        status_message = f"Codex backend is configured with unsupported wire API: {runtime_config.wire_api}."
    else:
        mode = "deterministic_only"
        status_message = "Codex backend auth is not mounted; AI Review will use deterministic governed evidence only."
    return {
        "provider": "codex",
        "configured": configured,
        "mode": mode,
        "model": runtime_config.model,
        "wire_api": runtime_config.wire_api,
        "base_url": runtime_config.base_url,
        "request_timeout_seconds": settings.CODEX_REQUEST_TIMEOUT_SECONDS,
        "quota": {
            "daily_job_limit": daily_limit,
            "actor_jobs_today": actor_jobs_today,
            "remaining_jobs_today": remaining,
            "llm_daily_job_limit": max(0, settings.AI_REVIEW_LLM_DAILY_JOB_LIMIT),
        },
        "data_retention_policy": (
            "The app persists deterministic review results and audit events. External LLM prompts are "
            "transient request payloads assembled from redacted evidence; provider retention is governed "
            "by the configured Codex backend contract."
        ),
        "prompt_redaction_policy": PROMPT_REDACTION_POLICY,
        "status_message": status_message,
    }


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        return payload

    text_chunks: list[str] = []
    final_payload: dict[str, Any] | None = None
    first_payload: dict[str, Any] | None = None
    for event in response.text.split("\n\n"):
        data_lines = [
            line.removeprefix("data:").strip()
            for line in event.splitlines()
            if line.startswith("data:")
        ]
        data = "\n".join(data_lines).strip()
        if not data or data == "[DONE]":
            continue
        parsed = json.loads(data)
        if not isinstance(parsed, dict):
            continue
        if first_payload is None:
            first_payload = parsed
        event_type = parsed.get("type")
        if event_type == "response.output_text.done":
            text = _string_value(parsed.get("text"))
            if text:
                return {"output_text": text}
        if event_type == "response.output_text.delta":
            delta = parsed.get("delta")
            if isinstance(delta, str):
                text_chunks.append(delta)
        if event_type == "response.completed":
            response_payload = parsed.get("response")
            if isinstance(response_payload, dict):
                final_payload = response_payload
    if text_chunks:
        return {"output_text": "".join(text_chunks).strip()}
    return final_payload or first_payload or {}


def _response_text(payload: dict[str, Any]) -> str | None:
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
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    return "\n".join(chunks).strip() or None


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
        {
            "label": metric.label,
            "value": metric.value,
            "detail": metric.detail,
        }
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
    redacted_payload = _redact_prompt_value(review_payload)
    return [
        {
            "role": "system",
            "content": (
                "You are an OCI integration architecture review assistant. "
                "Use only the provided evidence. Do not invent facts, counts, services, or blockers. "
                "Return a concise executive review summary in US English, 90-130 words. "
                "Mention the sign-off status, top risk theme, topology or stress signal if present, "
                "and the next architect action."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(redacted_payload, ensure_ascii=False, sort_keys=True),
        },
    ]


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
) -> LlmReviewResult:
    """Use the configured Codex backend Responses API to synthesize an executive summary."""

    runtime_config = _resolved_codex_config(settings)
    if not runtime_config.api_key:
        return LlmReviewResult(status="not_configured", model=runtime_config.model, summary=None)
    if runtime_config.wire_api.strip().lower() != "responses":
        return LlmReviewResult(
            status="failed",
            model=runtime_config.model,
            summary=None,
            error=f"Unsupported Codex wire API: {runtime_config.wire_api}",
        )

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
    if _uses_chatgpt_codex_backend(runtime_config.base_url):
        body = {
            "model": runtime_config.model,
            "instructions": prompt[0]["content"],
            "input": prompt[1:],
            "store": False,
            "stream": True,
        }
        accept_header = "text/event-stream"
    else:
        body = {
            "model": runtime_config.model,
            "input": prompt,
            "max_output_tokens": 260,
            "store": False,
        }
        accept_header = "application/json"
    headers = {
        "Authorization": f"Bearer {runtime_config.api_key}",
        "Content-Type": "application/json",
        "Accept": accept_header,
        **runtime_config.headers,
    }
    if runtime_config.account_id:
        headers["ChatGPT-Account-Id"] = runtime_config.account_id

    try:
        async with httpx.AsyncClient(timeout=settings.CODEX_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(_responses_url(runtime_config.base_url), headers=headers, json=body)
            response.raise_for_status()
            payload = _response_payload(response)
    except Exception as exc:  # pragma: no cover - exact network failures depend on provider.
        return LlmReviewResult(
            status="failed",
            model=runtime_config.model,
            summary=None,
            error=exc.__class__.__name__,
        )

    summary = _response_text(payload)
    if not summary:
        return LlmReviewResult(
            status="failed",
            model=runtime_config.model,
            summary=None,
            error="empty_response",
        )
    return LlmReviewResult(status="completed", model=runtime_config.model, summary=summary)
