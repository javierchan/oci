"""LLM client used to synthesize governed AI review summaries."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from app.core.config import Settings
from app.schemas.ai_review import AiReviewFinding, AiReviewMetric


@dataclass(frozen=True)
class LlmReviewResult:
    """Normalized result from the configured LLM provider."""

    status: Literal["not_configured", "completed", "failed", "skipped"]
    model: str | None
    summary: str | None
    error: str | None = None


@dataclass(frozen=True)
class OcaRuntimeConfig:
    """Resolved OCA runtime settings from environment plus optional Codex config."""

    api_key: str
    base_url: str
    wire_api: str
    model: str
    headers: dict[str, str]


def _responses_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/responses") else f"{normalized}/responses"


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


def _codex_provider_config(config_path: str) -> dict[str, Any]:
    config = _read_toml_file(config_path)
    providers = config.get("model_providers")
    if not isinstance(providers, dict):
        return {}
    provider = providers.get("oca")
    return provider if isinstance(provider, dict) else {}


def _codex_auth_key(auth_path: str) -> str:
    auth = _read_json_file(auth_path)
    for key_name in ("OCA_API_KEY", "oca_api_key", "OPENAI_API_KEY", "openai_api_key"):
        value = _string_value(auth.get(key_name))
        if value:
            return value
    return ""


def _resolved_oca_config(settings: Settings) -> OcaRuntimeConfig:
    provider = _codex_provider_config(settings.OCA_CONFIG_PATH)
    provider_headers = provider.get("http_headers")
    headers = {
        "client": settings.OCA_CLIENT_NAME,
        "client-version": settings.OCA_CLIENT_VERSION,
    }
    if isinstance(provider_headers, dict):
        headers.update(
            {
                str(key): str(value)
                for key, value in provider_headers.items()
                if isinstance(key, str) and isinstance(value, str) and value.strip()
            }
        )

    base_url = _string_value(provider.get("base_url")) or settings.OCA_BASE_URL
    wire_api = _string_value(provider.get("wire_api")) or settings.OCA_WIRE_API
    model = _string_value(provider.get("model")) or settings.OCA_MODEL
    api_key = settings.OCA_API_KEY.strip() or _codex_auth_key(settings.OCA_AUTH_JSON_PATH)
    return OcaRuntimeConfig(
        api_key=api_key,
        base_url=base_url,
        wire_api=wire_api,
        model=model,
        headers=headers,
    )


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        return payload

    # OCA's Responses endpoint returns a single server-sent event frame even
    # for non-streaming calls: "data: {json}\n\n".
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
        if isinstance(parsed, dict):
            return parsed
    return {}


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


def _build_prompt(
    *,
    project_name: str,
    readiness_score: int,
    readiness_label: str,
    deterministic_summary: str,
    metrics: list[AiReviewMetric],
    findings: list[AiReviewFinding],
    evidence_pack: list[str],
) -> list[dict[str, str]]:
    review_payload = {
        "project_name": project_name,
        "readiness_score": readiness_score,
        "readiness_label": readiness_label,
        "deterministic_summary": deterministic_summary,
        "metrics": _compact_metrics(metrics),
        "findings": _compact_findings(findings),
        "evidence_pack": evidence_pack,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are an OCI integration architecture review assistant. "
                "Use only the provided evidence. Do not invent facts, counts, services, or blockers. "
                "Return a concise executive review summary in US English, 70-110 words. "
                "Mention the readiness label, top risk theme, and the next architect action."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(review_payload, ensure_ascii=False, sort_keys=True),
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
) -> LlmReviewResult:
    """Use the configured OCA Responses API to synthesize an executive summary."""

    runtime_config = _resolved_oca_config(settings)
    if not runtime_config.api_key:
        return LlmReviewResult(status="not_configured", model=runtime_config.model, summary=None)
    if runtime_config.wire_api.strip().lower() != "responses":
        return LlmReviewResult(
            status="failed",
            model=runtime_config.model,
            summary=None,
            error=f"Unsupported OCA wire API: {runtime_config.wire_api}",
        )

    body = {
        "model": runtime_config.model,
        "input": _build_prompt(
            project_name=project_name,
            readiness_score=readiness_score,
            readiness_label=readiness_label,
            deterministic_summary=deterministic_summary,
            metrics=metrics,
            findings=findings,
            evidence_pack=evidence_pack,
        ),
        "max_output_tokens": 260,
    }
    headers = {
        "Authorization": f"Bearer {runtime_config.api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        **runtime_config.headers,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.OCA_REQUEST_TIMEOUT_SECONDS) as client:
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
