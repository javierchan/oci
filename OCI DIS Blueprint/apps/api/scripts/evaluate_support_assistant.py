"""End-to-end quality evaluation for the session-isolated App Assistant.

This script only creates disposable support conversations and AgentRun audit
records through the public API.  It never writes project, catalog, pricing, or
governance data.  Each case has a fresh browser-session UUID so dialogue from a
previous question cannot affect the result.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
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
    "/api/v1/",
)
ENGLISH_LEAKS_IN_SPANISH = (
    " exists to ",
    "use this ",
    "use the ",
    "open the ",
    "review the ",
    "download the ",
    "when to use",
    "how to proceed",
    "price evidence unavailable",
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
    forbidden_terms: tuple[str, ...] = ()


CASES: tuple[EvaluationCase, ...] = (
    EvaluationCase("app-overview", "App", "¿Qué resuelve OCI DIS Architect?", "/projects", "Projects", ("oci dis", "integr")),
    EvaluationCase("projects", "Projects", "¿Qué representa un proyecto y por qué sus datos son independientes?", "/projects", "Projects", ("proyecto", "independ")),
    EvaluationCase("import", "Import", "¿Cómo importo un archivo y qué ocurre si una columna no coincide con el estándar?", "/projects", "Projects", ("import", "column")),
    EvaluationCase(
        "capture",
        "Capture",
        "¿Cuándo debo usar Capture en vez de Import?",
        "/projects",
        "Projects",
        ("capture", "import"),
        True,
        ("discover resources", "descubra recursos", "captura automática", "subscription"),
    ),
    EvaluationCase("catalog", "Catalog", "¿Para qué sirve el catálogo de integraciones?", "/projects", "Projects", ("catalog", "integr")),
    EvaluationCase(
        "qa",
        "Quality",
        "¿Qué significa QA y cómo reviso una integración que requiere atención?",
        "/projects",
        "Projects",
        ("qa", "integr"),
        True,
        ("lista para producción", "ready for production", "abre un ticket", "turn qa green"),
    ),
    EvaluationCase("volumetry", "Volumetry", "¿Cómo usa la App la volumetría?", "/projects", "Projects", ("volum",)),
    EvaluationCase("dashboard", "Dashboard", "¿Qué puedo analizar en el Dashboard sin ver costos comerciales?", "/projects", "Projects", ("dashboard",)),
    EvaluationCase("topology", "Map", "¿Qué puedo investigar en el mapa de topología?", "/projects", "Projects", ("topolog",)),
    EvaluationCase("lineage", "Lineage", "¿Cómo sé de dónde proviene una integración importada?", "/projects", "Projects", ("lineage", "import")),
    EvaluationCase("patterns", "Patterns", "Explica el patrón request and reply", "/admin/patterns", "Patterns", ("request", "reply")),
    EvaluationCase("service-products", "Service Products", "¿Qué es un Service Product dentro de la App?", "/admin/services", "Service Products", ("service product",)),
    EvaluationCase("dictionaries", "Dictionaries", "¿Para qué sirven los diccionarios gobernados?", "/admin/dictionaries", "Dictionaries", ("diccion",)),
    EvaluationCase("assumptions", "Assumptions", "¿Qué guardan los Assumptions y qué no deben guardar?", "/admin/assumptions", "Assumptions", ("assumption",)),
    EvaluationCase("pricing", "Pricing", "¿Cómo se gobiernan las tarifas de OCI dentro de Pricing?", "/admin/pricing", "Pricing", ("pric", "tarif")),
    EvaluationCase("functions-billing", "Commercial", "¿Cómo se cobra OCI Functions a un cliente?", "/admin/pricing", "Pricing", ("gb", "invoc")),
    EvaluationCase("bom", "BOM", "¿Qué necesito antes de generar un BOM?", "/projects", "Projects", ("bom",)),
    EvaluationCase("scenario", "BOM", "¿Qué es un escenario de despliegue y cómo afecta el BOM?", "/projects", "Projects", ("escenario", "bom")),
    EvaluationCase("licensing", "BOM", "¿Qué significa License Included o BYOL en un escenario?", "/projects", "Projects", ("byol", "license")),
    EvaluationCase("export", "Exports", "¿Qué puedo exportar desde la App y qué evidencia conserva?", "/projects", "Projects", ("export",)),
    EvaluationCase("bom-export-formats", "Exports", "What export formats are available for a governed BOM?", "/projects", "Projects", ("xlsx", "json", "pdf"), False),
    EvaluationCase(
        "absent-cost-alerts",
        "Capabilities",
        "Can I set up automated email alerts when cost exceeds a threshold?",
        "/projects",
        "Projects",
        ("document",),
        False,
        ("external monitoring", "your own tools", "own monitoring", "outside the tool"),
    ),
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
            EvaluationCase("functions", "Commercial", "¿Cómo se cobra OCI Functions a un cliente?", "/admin/pricing", "Pricing", ("gb", "invoc")),
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

REQUIRED_TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "app": ("app", "aplicacion"),
    "context": ("context", "contexto", "conocimiento"),
    "function": ("function", "functions", "funcion", "funciones"),
    "lineage": ("lineage", "linaje"),
}


def _project_id_from_route(route: str) -> str | None:
    match = re.match(
        r"^/projects/([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})(?:/|$)",
        route,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None


def project_cases(project_id: str) -> tuple[EvaluationCase, ...]:
    route = f"/projects/{project_id}"
    return (
        EvaluationCase(
            "project-catalog-status",
            "Real project",
            "¿Cuántas integraciones tiene este proyecto y cuáles requieren atención?",
            route,
            "Project Dashboard",
            ("integr", "0"),
            True,
            ("ambiguous", "dos proyectos activos", "indique cuál"),
        ),
        EvaluationCase(
            "project-import-evidence",
            "Real project",
            "¿Qué evidencia conserva la última importación de este proyecto?",
            f"{route}/import",
            "Import",
            ("import",),
        ),
        EvaluationCase(
            "project-processes",
            "Real project",
            "Resume los procesos de negocio y las integraciones de este proyecto.",
            route,
            "Project Dashboard",
            ("proceso", "integr"),
            True,
            ("ambiguous", "dos proyectos activos", "indique cuál"),
        ),
        EvaluationCase(
            "project-bom-status",
            "Real project",
            "¿Cuál es el estado actual del BOM de este proyecto?",
            f"{route}/bom",
            "BOM & Cost",
            ("bom",),
            True,
            ("ambiguous", "dos proyectos activos", "indique cuál"),
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


def _evaluate(
    case: EvaluationCase,
    message: dict[str, Any],
    run: dict[str, Any] | None,
) -> dict[str, Any]:
    content = str(message.get("content") or "").strip()
    folded = re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKC", content).casefold(),
    )
    search_text = "".join(
        character
        for character in unicodedata.normalize("NFKD", folded)
        if not unicodedata.combining(character)
    )
    missing = []
    for term in case.required_terms:
        normalized_term = "".join(
            character
            for character in unicodedata.normalize("NFKD", term.casefold())
            if not unicodedata.combining(character)
        )
        accepted_terms = REQUIRED_TERM_ALIASES.get(normalized_term, (normalized_term,))
        if not any(candidate in search_text for candidate in accepted_terms):
            missing.append(term)
    violations = [
        term
        for term in (*BANNED_TEXT, *case.forbidden_terms)
        if term in folded
    ]
    language_leaks = [
        term.strip()
        for term in ENGLISH_LEAKS_IN_SPANISH
        if case.spanish and term in f" {folded} "
    ]
    spanish_signal = any(token in folded for token in (" el ", " la ", " de ", " para ", "qué", "cómo", "puede"))
    run_result = run.get("result") if isinstance(run, dict) else None
    result = run_result if isinstance(run_result, dict) else {}
    output_quality = result.get("output_quality")
    quality = output_quality if isinstance(output_quality, dict) else {}
    operational_pass = (
        isinstance(run, dict)
        and run.get("status") == "completed"
        and result.get("provider_status") == "completed"
        and result.get("delivery_status") == "delivered"
        and result.get("retrieval_embedding_space") == "provider"
        and quality.get("grounded") is True
        and quality.get("fallback_used") is False
    )
    passed = (
        message.get("status") in {"completed", "refused"}
        and bool(content)
        and not violations
        and not language_leaks
        and operational_pass
    )
    if case.id != "out-of-scope":
        passed = passed and not missing and (not case.spanish or spanish_signal)
    return {
        "id": case.id,
        "area": case.area,
        "status": message.get("status"),
        "passed": passed,
        "missing_terms": missing,
        "violations": violations,
        "language_leaks": language_leaks,
        "content": content,
        "citations": message.get("citations", []),
        "agent_run_id": message.get("agent_run_id"),
        "run_status": run.get("status") if isinstance(run, dict) else None,
        "provider_status": result.get("provider_status"),
        "delivery_status": result.get("delivery_status"),
        "embedding_space": result.get("retrieval_embedding_space"),
        "output_quality": quality,
    }


def run_case(case: EvaluationCase) -> dict[str, Any]:
    started_at = time.monotonic()
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
            "project_id": _project_id_from_route(case.route),
            "attachments": [],
        },
    )
    message = submitted["messages"][-1]
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while message["status"] == "pending" and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        message = _request(f"/support/conversations/{conversation_id}", "GET", session_id)["messages"][-1]
    run_id = message.get("agent_run_id")
    run = (
        _request(f"/agents/runs/{run_id}", "GET", session_id)
        if isinstance(run_id, str)
        else None
    )
    result = _evaluate(case, message, run)
    result["question"] = case.question
    result["timed_out"] = message["status"] == "pending"
    result["latency_seconds"] = round(time.monotonic() - started_at, 2)
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
            {
                "content": turn.question,
                "route": turn.route,
                "page_title": turn.page_title,
                "project_id": _project_id_from_route(turn.route),
                "attachments": [],
            },
        )
        message = submitted["messages"][-1]
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while message["status"] == "pending" and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
            message = _request(f"/support/conversations/{conversation_id}", "GET", session_id)["messages"][-1]
        run_id = message.get("agent_run_id")
        run = (
            _request(f"/agents/runs/{run_id}", "GET", session_id)
            if isinstance(run_id, str)
            else None
        )
        turns.append(_evaluate(turn, message, run))
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
    parser.add_argument(
        "--case-id",
        action="append",
        choices=[case.id for case in CASES],
        help="Run one named global case; repeat to run a focused set.",
    )
    parser.add_argument(
        "--conversation-id",
        action="append",
        choices=[case.id for case in CONVERSATION_CASES],
        help="Run one named conversation case; repeat to run a focused set.",
    )
    parser.add_argument("--project-id", help="Append real project-context evaluation cases.")
    parser.add_argument("--project-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.iteration <= 10:
        parser.error("--iteration must be between 1 and 10")
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.offset < 0 or args.offset >= len(CASES):
        parser.error(f"--offset must be between 0 and {len(CASES) - 1}")

    results: list[dict[str, Any]] = []
    if args.project_only and not args.project_id:
        parser.error("--project-only requires --project-id")
    selected_cases = (
        project_cases(args.project_id)
        if args.project_only and args.project_id
        else tuple(case for case in CASES if case.id in set(args.case_id or ()))
        if args.case_id
        else ()
        if args.conversations_only
        else CASES[args.offset : args.offset + args.limit]
    )
    for case in selected_cases:
        try:
            results.append(run_case(case))
        except (HTTPError, OSError, TimeoutError, ValueError) as exc:
            results.append({"id": case.id, "area": case.area, "question": case.question, "passed": False, "error": str(exc)})
    selected_conversations = (
        tuple(
            case
            for case in CONVERSATION_CASES
            if case.id in set(args.conversation_id or ())
        )
        if args.conversation_id
        else CONVERSATION_CASES
        if not args.project_only
        and (
            args.conversations_only
        or (not args.case_id and args.offset == 0 and args.limit >= len(CASES))
        )
        else ()
    )
    for case in selected_conversations:
        try:
            results.append(run_conversation_case(case))
        except (HTTPError, OSError, TimeoutError, ValueError) as exc:
            results.append({"id": case.id, "area": case.area, "passed": False, "error": str(exc)})
    if args.project_id and not args.project_only:
        for case in project_cases(args.project_id):
            try:
                results.append(run_case(case))
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
