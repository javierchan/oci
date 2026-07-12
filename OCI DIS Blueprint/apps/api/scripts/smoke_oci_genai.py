"""Run one sanitized OCI Generative AI request against the configured private model."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.genai_client import synthesize_governed_summary


async def _run() -> int:
    """Execute a minimal evidence-grounded synthesis and return a process exit code."""

    result = await synthesize_governed_summary(
        settings=get_settings(),
        system_instruction=(
            "Use only the governed evidence. Return one sentence confirming the architecture review scope. "
            "Do not add services, costs, risks, or quantities."
        ),
        evidence={
            "application": "OCI DIS Architect",
            "scope": "OCI data integration architecture review",
            "evidence_policy": "deterministic-first",
        },
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "model": result.model,
                "opc_request_id": result.opc_request_id,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "summary": result.summary,
                "error": result.error,
            },
            indent=2,
        )
    )
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
