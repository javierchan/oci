"""End-to-end quality evaluation for the session-isolated App Assistant.

This script only creates disposable support conversations and AgentRun audit
records through the public API.  It never writes project, catalog, pricing, or
governance data.  Each case has a fresh browser-session UUID so dialogue from a
previous question cannot affect the result.
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_URL = "http://localhost:8000/api/v1"
POLL_SECONDS = 2.0
TIMEOUT_SECONDS = 90.0
BANNED_TEXT = (
    "answer from governed app context",
    "next action: add the relevant app context",
    "[redacted]",
    "[tool",
    "[system",
    "we need to",
    "the user asks",
    "it returned a content",
    "the fallback answer",
    "so we must",
)


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    area: str
    question: str
    route: str
    page_title: str
    required_terms: tuple[str, ...]
    spanish: bool = True


CASES: tuple[EvaluationCase, ...] = (
    EvaluationCase("app-overview", "App", "¿Qué resuelve OCI DIS Architect?", "/projects", "Projects", ("oci dis", "integr")),
    EvaluationCase("projects", "Projects", "¿Qué representa un proyecto y por qué sus datos son independientes?", "/projects", "Projects", ("proyecto", "independ")),
    EvaluationCase("import", "Import", "¿Cómo importo un archivo y qué ocurre si una columna no coincide con el estándar?", "/projects", "Projects", ("import", "column")),
    EvaluationCase("capture", "Capture", "¿Cuándo debo usar Capture en vez de Import?", "/projects", "Projects", ("capture", "import")),
    EvaluationCase("catalog", "Catalog", "¿Para qué sirve el catálogo de integraciones?", "/projects", "Projects", ("catalog", "integr")),
    EvaluationCase("qa", "Quality", "¿Qué significa QA y cómo reviso una integración que requiere atención?", "/projects", "Projects", ("qa", "integr")),
    EvaluationCase("volumetry", "Volumetry", "¿Cómo usa la App la volumetría?", "/projects", "Projects", ("volum",)),
    EvaluationCase("dashboard", "Dashboard", "¿Qué puedo analizar en el Dashboard sin ver costos comerciales?", "/projects", "Projects", ("dashboard",)),
    EvaluationCase("topology", "Map", "¿Qué puedo investigar en el mapa de topología?", "/projects", "Projects", ("topolog",)),
    EvaluationCase("lineage", "Lineage", "¿Cómo sé de dónde proviene una integración importada?", "/projects", "Projects", ("lineage", "import")),
    EvaluationCase("patterns", "Patterns", "Explica el patrón request and reply", "/admin/patterns", "Patterns", ("request", "reply")),
    EvaluationCase("service-products", "Service Products", "¿Qué es un Service Product dentro de la App?", "/admin/services", "Service Products", ("service product",)),
    EvaluationCase("dictionaries", "Dictionaries", "¿Para qué sirven los diccionarios gobernados?", "/admin/dictionaries", "Dictionaries", ("diccion",)),
    EvaluationCase("assumptions", "Assumptions", "¿Qué guardan los Assumptions y qué no deben guardar?", "/admin/assumptions", "Assumptions", ("assumption",)),
    EvaluationCase("pricing", "Pricing", "¿Cómo se gobiernan las tarifas de OCI dentro de Pricing?", "/admin/pricing", "Pricing", ("pric", "tarif")),
    EvaluationCase("functions-billing", "Commercial", "¿Cómo se cobra OCI Functions a un cliente?", "/admin/pricing", "Pricing", ("function", "precio")),
    EvaluationCase("bom", "BOM", "¿Qué necesito antes de generar un BOM?", "/projects", "Projects", ("bom",)),
    EvaluationCase("scenario", "BOM", "¿Qué es un escenario de despliegue y cómo afecta el BOM?", "/projects", "Projects", ("escenario", "bom")),
    EvaluationCase("licensing", "BOM", "¿Qué significa License Included o BYOL en un escenario?", "/projects", "Projects", ("byol", "license")),
    EvaluationCase("export", "Exports", "¿Qué puedo exportar desde la App y qué evidencia conserva?", "/projects", "Projects", ("export",)),
    EvaluationCase("agents", "Agents", "¿Qué hacen los agentes de OCI DIS y qué no pueden cambiar?", "/admin/agents", "Agents", ("agent",)),
    EvaluationCase("assistant", "Assistant", "¿Qué contexto puede usar este asistente y qué preguntas rechaza?", "/projects", "Projects", ("context", "app")),
    EvaluationCase("out-of-scope", "Safety", "¿Cuál será el clima mañana en Ciudad de México?", "/projects", "Projects", ("oci dis",), True),
)


@dataclass(frozen=True)
class ConversationCase:
    id: str
    area: str
    turns: tuple[EvaluationCase, ...]
    final_required_terms: tuple[str, ...]
    final_forbidden_terms: tuple[str, ...] = ()


CONVERSATION_CASES: tuple[ConversationCase, ...] = (
    ConversationCase(
        "commercial-follow-up",
        "Conversation memory",
        (
            EvaluationCase("functions", "Commercial", "¿Cómo se cobra OCI Functions a un cliente?", "/admin/pricing", "Pricing", ("function",)),
            EvaluationCase("functions-follow-up", "Commercial", "¿Qué métricas se suman para ese servicio?", "/admin/pricing", "Pricing", ("function",)),
        ),
        ("function",),
    ),
    ConversationCase(
        "intent-switch",
        "Conversation memory",
        (
            EvaluationCase("price", "Commercial", "¿Cómo se cobra OCI Functions a un cliente?", "/admin/pricing", "Pricing", ("function",)),
            EvaluationCase("pattern", "Patterns", "Ahora explica el patrón request and reply", "/admin/patterns", "Patterns", ("request", "reply")),
        ),
        ("request", "reply"),
        ("function", "per_item", "answer from governed"),
    ),
)


def _request(path: str, method: str, session_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "X-Actor-Id": "assistant-eval",
        "X-Actor-Role": "Viewer",
        "X-Support-Session-Id": session_id,
    }
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode()
    request = Request(f"{API_URL}{path}", data=payload, headers=headers, method=method)
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def _evaluate(case: EvaluationCase, message: dict[str, Any]) -> dict[str, Any]:
    content = str(message.get("content") or "").strip()
    folded = content.casefold()
    missing = [term for term in case.required_terms if term.casefold() not in folded]
    violations = [term for term in BANNED_TEXT if term in folded]
    spanish_signal = any(token in folded for token in (" el ", " la ", " de ", " para ", "qué", "cómo", "puede"))
    passed = message.get("status") in {"completed", "refused"} and bool(content) and not violations
    if case.id != "out-of-scope":
        passed = passed and not missing and (not case.spanish or spanish_signal)
    else:
        passed = passed and message.get("status") == "refused"
    return {
        "id": case.id,
        "area": case.area,
        "status": message.get("status"),
        "passed": passed,
        "missing_terms": missing,
        "violations": violations,
        "content": content,
        "citations": message.get("citations", []),
        "agent_run_id": message.get("agent_run_id"),
    }


def run_case(case: EvaluationCase) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    conversation = _request("/support/conversations/current", "POST", session_id)
    conversation_id = str(conversation["id"])
    submitted = _request(
        f"/support/conversations/{conversation_id}/messages",
        "POST",
        session_id,
        {
            "content": case.question,
            "route": case.route,
            "page_title": case.page_title,
            "attachments": [],
        },
    )
    message = submitted["messages"][-1]
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while message["status"] == "pending" and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        message = _request(f"/support/conversations/{conversation_id}", "GET", session_id)["messages"][-1]
    result = _evaluate(case, message)
    result["question"] = case.question
    result["timed_out"] = message["status"] == "pending"
    return result


def run_conversation_case(case: ConversationCase) -> dict[str, Any]:
    """Exercise dialogue continuity in one isolated browser-session conversation."""

    session_id = str(uuid.uuid4())
    conversation_id = str(_request("/support/conversations/current", "POST", session_id)["id"])
    turns: list[dict[str, Any]] = []
    for turn in case.turns:
        submitted = _request(
            f"/support/conversations/{conversation_id}/messages",
            "POST",
            session_id,
            {"content": turn.question, "route": turn.route, "page_title": turn.page_title, "attachments": []},
        )
        message = submitted["messages"][-1]
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while message["status"] == "pending" and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
            message = _request(f"/support/conversations/{conversation_id}", "GET", session_id)["messages"][-1]
        turns.append(_evaluate(turn, message))
    final = turns[-1]
    folded = str(final.get("content") or "").casefold()
    missing = [term for term in case.final_required_terms if term.casefold() not in folded]
    leaked = [term for term in case.final_forbidden_terms if term.casefold() in folded]
    return {
        "id": case.id,
        "area": case.area,
        "passed": all(bool(turn.get("passed")) for turn in turns) and not missing and not leaked,
        "missing_terms": missing,
        "leaked_terms": leaked,
        "turns": turns,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--limit", type=int, default=len(CASES))
    parser.add_argument("--offset", type=int, default=0, help="Zero-based case offset for bounded batches.")
    parser.add_argument("--report", help="Write the JSON report to this path as well as stdout.")
    parser.add_argument("--conversations-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.iteration <= 10:
        parser.error("--iteration must be between 1 and 10")
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.offset < 0 or args.offset >= len(CASES):
        parser.error(f"--offset must be between 0 and {len(CASES) - 1}")

    results: list[dict[str, Any]] = []
    selected_cases = () if args.conversations_only else CASES[args.offset : args.offset + args.limit]
    for case in selected_cases:
        try:
            results.append(run_case(case))
        except (HTTPError, OSError, TimeoutError, ValueError) as exc:
            results.append({"id": case.id, "area": case.area, "question": case.question, "passed": False, "error": str(exc)})
    if args.conversations_only or (args.offset == 0 and args.limit >= len(CASES)):
        for case in CONVERSATION_CASES:
            try:
                results.append(run_conversation_case(case))
            except (HTTPError, OSError, TimeoutError, ValueError) as exc:
                results.append({"id": case.id, "area": case.area, "passed": False, "error": str(exc)})
    passed = sum(1 for result in results if result.get("passed"))
    report = {
        "iteration": args.iteration,
        "offset": args.offset,
        "passed": passed,
        "total": len(results),
        "results": results,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    print(rendered)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
