"""Sanitized real-provider smoke for OCI Responses-first function calling."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.genai_client import run_governed_tool_agent


async def main() -> int:
    """Require one governed tool call and one evidence-only final response."""

    async def health_tool(_: dict[str, object]) -> dict[str, object]:
        return {
            "evidence_id": "SMOKE-001",
            "status": "ready",
            "authority": "deterministic_test_fixture",
        }

    result = await run_governed_tool_agent(
        settings=get_settings(),
        instruction=(
            "Use the required tool. Then return one plain sentence confirming the governed status and evidence ID. "
            "Do not invent any other facts."
        ),
        user_message="Inspect the governed runtime status.",
        tool_name="get_governed_runtime_status",
        tool_description="Return deterministic runtime status evidence.",
        tool_parameters={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        tool_executor=health_tool,
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "model": result.model,
                "tool": result.tool_name,
                "tool_called": result.tool_output is not None,
                "summary_present": bool(result.summary),
                "opc_request_id_present": bool(result.opc_request_id),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "error": result.error,
            },
            sort_keys=True,
        )
    )
    return 0 if result.status == "completed" and result.tool_output is not None else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
