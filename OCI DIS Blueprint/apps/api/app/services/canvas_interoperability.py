"""Backend helpers for governed canvas normalization and OCI interoperability checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, Sequence

from app.core.calc_engine import Assumptions
from app.services.serializers import split_csv

SOURCE_NODE_ID = "source-system"
DESTINATION_NODE_ID = "destination-system"

TOOL_TO_SERVICE_ID: dict[str, str] = {
    "OIC Gen3": "OIC3",
    "OCI API Gateway": "API_GATEWAY",
    "OCI Streaming": "STREAMING",
    "OCI Queue": "QUEUE",
    "OCI Functions": "FUNCTIONS",
    "Oracle Functions": "FUNCTIONS",
    "OCI Data Integration": "DATA_INTEGRATION",
    "Oracle ORDS": "ORDS",
    "Oracle DB": "ORDS",
    "OCI APM": "OBSERVABILITY",
    "Oracle GoldenGate": "GOLDENGATE",
    "OCI Connector Hub": "CONNECTOR_HUB",
    "OCI IAM": "IAM",
    "OCI Object Storage": "OBJECT_STORAGE",
    "SFTP": "OBJECT_STORAGE",
}

CONNECTOR_HUB_ALLOWED_SOURCES = frozenset({"QUEUE", "STREAMING"})
CONNECTOR_HUB_ALLOWED_TARGETS = frozenset({"FUNCTIONS", "STREAMING", "OBJECT_STORAGE"})
API_GATEWAY_ALLOWED_BACKENDS = frozenset({"FUNCTIONS", "OIC3", "ORDS"})


@dataclass(frozen=True)
class CanvasNode:
    """One canvas node persisted from the design surface."""

    instance_id: str
    tool_key: str
    label: str
    payload_note: str
    x: float
    y: float


@dataclass(frozen=True)
class CanvasEdge:
    """One directed connection between two canvas nodes."""

    edge_id: str
    source_instance_id: str
    target_instance_id: str
    label: str


@dataclass(frozen=True)
class ParsedCanvasState:
    """Sanitized canvas state after loading JSON or legacy overlay values."""

    mode: Literal["empty", "legacy_csv", "canvas_json"]
    nodes: tuple[CanvasNode, ...]
    edges: tuple[CanvasEdge, ...]
    core_tool_keys: tuple[str, ...]
    overlay_keys: tuple[str, ...]


@dataclass(frozen=True)
class CanvasSemantics:
    """Derived route semantics from the persisted design canvas."""

    has_directed_route: bool
    has_connected_route: bool
    core_tool_keys: tuple[str, ...]
    overlay_keys: tuple[str, ...]


@dataclass(frozen=True)
class CanvasInteroperabilityFinding:
    """One governed OCI finding for the active design."""

    id: str
    severity: Literal["blocker", "warning", "advisory"]
    title: str
    detail: str
    service_ids: tuple[str, ...]


@dataclass(frozen=True)
class CanvasInteroperabilityRoute:
    """One source-to-destination active route in the canvas."""

    node_ids: tuple[str, ...]
    tool_keys: tuple[str, ...]
    service_ids: tuple[str, ...]


@dataclass(frozen=True)
class CanvasInteroperabilityReport:
    """All interoperability findings collected for a design."""

    blockers: tuple[CanvasInteroperabilityFinding, ...]
    warnings: tuple[CanvasInteroperabilityFinding, ...]
    advisories: tuple[CanvasInteroperabilityFinding, ...]
    routes: tuple[CanvasInteroperabilityRoute, ...]


@dataclass(frozen=True)
class NormalizedCanvasDesign:
    """Normalized storage payload for core tools and canvas state."""

    mode: Literal["empty", "legacy_csv", "canvas_json"]
    core_tools_csv: str | None
    additional_tools_value: str | None
    semantics: CanvasSemantics
    report: CanvasInteroperabilityReport


class CanvasDesignValidationError(Exception):
    """Validation failure raised while normalizing design-canvas inputs."""

    def __init__(
        self,
        detail: str,
        error_code: str,
        findings: Sequence[CanvasInteroperabilityFinding] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error_code = error_code
        self.findings = tuple(findings or ())

    def as_http_detail(self) -> dict[str, object]:
        """Return the structured FastAPI detail payload."""

        payload: dict[str, object] = {
            "detail": self.detail,
            "error_code": self.error_code,
        }
        if self.findings:
            payload["findings"] = [
                {
                    "id": finding.id,
                    "severity": finding.severity,
                    "title": finding.title,
                    "detail": finding.detail,
                    "service_ids": list(finding.service_ids),
                }
                for finding in self.findings
            ]
        return payload


def _unique_sorted(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({value.strip() for value in values if value and value.strip()}))


def _normalize_text(value: str | None) -> str:
    return value.strip().upper() if value else ""


def _includes_any(value: str | None, keywords: Sequence[str]) -> bool:
    normalized = _normalize_text(value)
    return any(keyword.upper() in normalized for keyword in keywords)


def _format_limit_kb(value_kb: float | int) -> str:
    if value_kb >= 1024 and value_kb % 1024 == 0:
        return f"{int(value_kb / 1024)} MB"
    if value_kb >= 1024:
        return f"{value_kb / 1024:.1f} MB"
    return f"{int(value_kb)} KB"


def _join_csv(values: Sequence[str]) -> str | None:
    normalized = _unique_sorted(values)
    return ", ".join(normalized) if normalized else None


def _node_from_payload(value: object) -> CanvasNode | None:
    if not isinstance(value, dict):
        return None
    instance_id = str(value.get("instanceId") or value.get("i") or "").strip()
    tool_key = str(value.get("toolKey") or value.get("t") or "").strip()
    if not instance_id or not tool_key:
        return None
    label = str(value.get("label") or value.get("l") or tool_key).strip() or tool_key
    payload_note = str(value.get("payloadNote") or value.get("p") or "").strip()
    raw_x = value.get("x", 240)
    raw_y = value.get("y", 80)
    x = float(raw_x) if isinstance(raw_x, (int, float)) else 240.0
    y = float(raw_y) if isinstance(raw_y, (int, float)) else 80.0
    return CanvasNode(
        instance_id=instance_id,
        tool_key=tool_key,
        label=label,
        payload_note=payload_note,
        x=x,
        y=y,
    )


def _edge_from_payload(value: object, index: int) -> CanvasEdge | None:
    if not isinstance(value, dict):
        return None
    source_instance_id = str(value.get("sourceInstanceId") or value.get("s") or "").strip()
    target_instance_id = str(value.get("targetInstanceId") or value.get("t") or "").strip()
    if not source_instance_id or not target_instance_id:
        return None
    edge_id = str(value.get("edgeId") or f"edge-{index}").strip() or f"edge-{index}"
    label = str(value.get("label") or value.get("l") or "").strip()
    return CanvasEdge(
        edge_id=edge_id,
        source_instance_id=source_instance_id,
        target_instance_id=target_instance_id,
        label=label,
    )


def _create_default_node(tool_key: str, index: int) -> CanvasNode:
    return CanvasNode(
        instance_id=f"default-node-{index + 1}",
        tool_key=tool_key,
        label=tool_key,
        payload_note="",
        x=240.0 + (index % 4) * 220.0,
        y=80.0 + (index // 4) * 140.0,
    )


def _build_default_nodes(core_tool_keys: Sequence[str]) -> tuple[CanvasNode, ...]:
    return tuple(_create_default_node(tool_key, index) for index, tool_key in enumerate(core_tool_keys))


def _build_default_edges(nodes: Sequence[CanvasNode]) -> tuple[CanvasEdge, ...]:
    if not nodes:
        return ()

    edges: list[CanvasEdge] = []
    previous_id = SOURCE_NODE_ID
    for index, node in enumerate(nodes, start=1):
        edges.append(
            CanvasEdge(
                edge_id=f"default-edge-{index}",
                source_instance_id=previous_id,
                target_instance_id=node.instance_id,
                label="",
            )
        )
        previous_id = node.instance_id

    edges.append(
        CanvasEdge(
            edge_id=f"default-edge-{len(nodes) + 1}",
            source_instance_id=previous_id,
            target_instance_id=DESTINATION_NODE_ID,
            label="",
        )
    )
    return tuple(edges)


def _sanitize_canvas_state(
    nodes: Sequence[CanvasNode],
    edges: Sequence[CanvasEdge],
) -> tuple[tuple[CanvasNode, ...], tuple[CanvasEdge, ...]]:
    unique_nodes: dict[str, CanvasNode] = {}
    for node in nodes:
        unique_nodes[node.instance_id] = CanvasNode(
            instance_id=node.instance_id,
            tool_key=node.tool_key,
            label=node.label or node.tool_key,
            payload_note=node.payload_note,
            x=node.x,
            y=node.y,
        )

    valid_ids = {SOURCE_NODE_ID, DESTINATION_NODE_ID, *unique_nodes.keys()}
    seen_pairs: set[tuple[str, str]] = set()
    sanitized_edges: list[CanvasEdge] = []
    for edge in edges:
        pair = (edge.source_instance_id, edge.target_instance_id)
        if (
            edge.source_instance_id == edge.target_instance_id
            or pair == (SOURCE_NODE_ID, DESTINATION_NODE_ID)
            or edge.source_instance_id not in valid_ids
            or edge.target_instance_id not in valid_ids
            or pair in seen_pairs
        ):
            continue
        seen_pairs.add(pair)
        sanitized_edges.append(edge)

    return tuple(unique_nodes.values()), tuple(sanitized_edges)


def parse_canvas_state(value: str | None, core_tool_keys: Sequence[str]) -> ParsedCanvasState:
    """Parse persisted canvas JSON or legacy overlay strings into a normalized state."""

    normalized_core_tool_keys = _unique_sorted(core_tool_keys)
    if not value or not value.strip():
        default_nodes = _build_default_nodes(normalized_core_tool_keys)
        return ParsedCanvasState(
            mode="empty",
            nodes=default_nodes,
            edges=_build_default_edges(default_nodes),
            core_tool_keys=normalized_core_tool_keys,
            overlay_keys=(),
        )

    stripped = value.strip()
    if not stripped.startswith("{") and not stripped.startswith("["):
        default_nodes = _build_default_nodes(normalized_core_tool_keys)
        return ParsedCanvasState(
            mode="legacy_csv",
            nodes=default_nodes,
            edges=_build_default_edges(default_nodes),
            core_tool_keys=normalized_core_tool_keys,
            overlay_keys=_unique_sorted(split_csv(stripped)),
        )

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise CanvasDesignValidationError(
            "Canvas state is malformed JSON. Re-save the design from the integration detail page.",
            "INVALID_CANVAS_STATE",
        ) from exc

    if not isinstance(parsed, dict):
        raise CanvasDesignValidationError(
            "Canvas state must be stored as a JSON object.",
            "INVALID_CANVAS_STATE",
        )

    version = parsed.get("v")
    nodes: list[CanvasNode] = []
    edges: list[CanvasEdge] = []
    overlay_keys: tuple[str, ...] = ()
    core_keys_from_payload = normalized_core_tool_keys

    if version == 3:
        raw_nodes = parsed.get("nodes")
        raw_edges = parsed.get("edges")
        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise CanvasDesignValidationError(
                "Canvas state is missing nodes or edges.",
                "INVALID_CANVAS_STATE",
            )
        nodes = [node for item in raw_nodes if (node := _node_from_payload(item)) is not None]
        edges = [
            edge
            for index, item in enumerate(raw_edges, start=1)
            if (edge := _edge_from_payload(item, index)) is not None
        ]
        payload_core_keys = parsed.get("coreToolKeys")
        payload_overlay_keys = parsed.get("overlayKeys")
        if isinstance(payload_core_keys, list):
            core_keys_from_payload = _unique_sorted([str(value) for value in payload_core_keys])
        if isinstance(payload_overlay_keys, list):
            overlay_keys = _unique_sorted([str(value) for value in payload_overlay_keys])
    elif version == 2:
        raw_nodes = parsed.get("nodes")
        raw_edges = parsed.get("edges")
        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise CanvasDesignValidationError(
                "Canvas state is missing nodes or edges.",
                "INVALID_CANVAS_STATE",
            )
        nodes = [node for item in raw_nodes if (node := _node_from_payload(item)) is not None]
        edges = [
            edge
            for index, item in enumerate(raw_edges, start=1)
            if (edge := _edge_from_payload(item, index)) is not None
        ]
    elif version == 1:
        raw_nodes = parsed.get("n")
        raw_edges = parsed.get("e")
        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise CanvasDesignValidationError(
                "Canvas state is missing nodes or edges.",
                "INVALID_CANVAS_STATE",
            )
        nodes = [node for item in raw_nodes if (node := _node_from_payload(item)) is not None]
        edges = [
            edge
            for index, item in enumerate(raw_edges, start=1)
            if (edge := _edge_from_payload(item, index)) is not None
        ]
    else:
        raise CanvasDesignValidationError(
            "Canvas state version is not recognized. Re-save the design from the integration detail page.",
            "INVALID_CANVAS_STATE",
        )

    sanitized_nodes, sanitized_edges = _sanitize_canvas_state(nodes, edges)
    return ParsedCanvasState(
        mode="canvas_json",
        nodes=sanitized_nodes,
        edges=sanitized_edges,
        core_tool_keys=core_keys_from_payload,
        overlay_keys=overlay_keys,
    )


def is_canvas_json_state(value: str | None) -> bool:
    """Return whether the persisted additional-tools field is a canvas JSON payload."""

    return bool(value and value.strip().startswith("{"))


def _reachable_node_ids(edges: Sequence[CanvasEdge], start_id: str) -> set[str]:
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source_instance_id, []).append(edge.target_instance_id)

    visited: set[str] = set()
    queue: list[str] = [start_id]
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                queue.append(neighbor)
    return visited


def _reverse_reachable_node_ids(edges: Sequence[CanvasEdge], target_id: str) -> set[str]:
    reversed_edges = [
        CanvasEdge(
            edge_id=edge.edge_id,
            source_instance_id=edge.target_instance_id,
            target_instance_id=edge.source_instance_id,
            label=edge.label,
        )
        for edge in edges
    ]
    return _reachable_node_ids(reversed_edges, target_id)


def _has_directed_path(edges: Sequence[CanvasEdge], source_id: str, target_id: str) -> bool:
    return target_id in _reachable_node_ids(edges, source_id)


def derive_canvas_semantics(
    nodes: Sequence[CanvasNode],
    edges: Sequence[CanvasEdge],
    overlay_tool_keys: Sequence[str],
) -> CanvasSemantics:
    """Derive active-route semantics from a normalized design canvas."""

    overlay_tool_set = set(overlay_tool_keys)
    has_directed_route = _has_directed_path(edges, SOURCE_NODE_ID, DESTINATION_NODE_ID)
    forward_reachable = _reachable_node_ids(edges, SOURCE_NODE_ID)
    backward_reachable = _reverse_reachable_node_ids(edges, DESTINATION_NODE_ID)
    active_node_ids = {
        node.instance_id
        for node in nodes
        if node.instance_id in forward_reachable and node.instance_id in backward_reachable
    }

    active_core_tool_keys = _unique_sorted(
        [node.tool_key for node in nodes if node.instance_id in active_node_ids and node.tool_key not in overlay_tool_set]
    )
    active_overlay_keys = _unique_sorted(
        [node.tool_key for node in nodes if node.instance_id in active_node_ids and node.tool_key in overlay_tool_set]
    )
    return CanvasSemantics(
        has_directed_route=has_directed_route,
        has_connected_route=has_directed_route and len(active_core_tool_keys) > 0,
        core_tool_keys=active_core_tool_keys,
        overlay_keys=active_overlay_keys,
    )


def _resolve_canvas_service_id(tool_key: str) -> str | None:
    return TOOL_TO_SERVICE_ID.get(tool_key)


def _build_routes(
    nodes: Sequence[CanvasNode],
    edges: Sequence[CanvasEdge],
) -> tuple[CanvasInteroperabilityRoute, ...]:
    node_by_id = {node.instance_id: node for node in nodes}
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source_instance_id, []).append(edge.target_instance_id)

    raw_routes: list[list[str]] = []
    max_depth = len(nodes) + 2

    def walk(current_id: str, path: list[str]) -> None:
        if len(path) > max_depth:
            return
        if current_id == DESTINATION_NODE_ID:
            raw_routes.append(path[:])
            return
        for next_id in adjacency.get(current_id, []):
            if next_id in path:
                continue
            walk(next_id, [*path, next_id])

    walk(SOURCE_NODE_ID, [SOURCE_NODE_ID])

    deduped: dict[tuple[str, ...], CanvasInteroperabilityRoute] = {}
    for path in raw_routes:
        tool_nodes = [
            node_by_id[node_id]
            for node_id in path[1:-1]
            if node_id in node_by_id
        ]
        route = CanvasInteroperabilityRoute(
            node_ids=tuple(path),
            tool_keys=tuple(node.tool_key for node in tool_nodes),
            service_ids=tuple(
                service_id
                for node in tool_nodes
                if (service_id := _resolve_canvas_service_id(node.tool_key)) is not None
            ),
        )
        deduped[route.node_ids] = route
    return tuple(deduped.values())


def _push_unique_finding(
    findings: list[CanvasInteroperabilityFinding],
    finding: CanvasInteroperabilityFinding,
) -> None:
    if not any(entry.id == finding.id for entry in findings):
        findings.append(finding)


def _payload_blockers(
    payload_kb: float | None,
    tool_keys: set[str],
    assumptions: Assumptions,
) -> list[CanvasInteroperabilityFinding]:
    if payload_kb is None:
        return []

    blockers: list[CanvasInteroperabilityFinding] = []
    checks = [
        (
            "oic-payload-limit",
            {"OIC Gen3"},
            assumptions.oic_rest_max_payload_kb,
            "OIC payload exceeds the documented message limit",
            "Route the payload through object storage or reduce the synchronous message size before using OIC Gen3 on the active path.",
            ("OIC3",),
        ),
        (
            "functions-payload-limit",
            {"OCI Functions", "Oracle Functions"},
            assumptions.functions_max_invoke_body_kb,
            "Functions payload exceeds the documented invoke limit",
            "Oracle Functions cannot accept this payload body size on the active path. Use OIC or externalize the payload before invocation.",
            ("FUNCTIONS",),
        ),
        (
            "gateway-payload-limit",
            {"OCI API Gateway"},
            assumptions.api_gw_max_body_kb,
            "API Gateway payload exceeds the documented request-body limit",
            "The gateway edge cannot carry this request size. Reduce the body or move the payload off-band before API Gateway.",
            ("API_GATEWAY",),
        ),
        (
            "queue-payload-limit",
            {"OCI Queue"},
            assumptions.queue_max_message_kb,
            "Queue payload exceeds the documented message limit",
            "OCI Queue should carry a lightweight reference, not the full payload. Externalize the document and enqueue a token or pointer.",
            ("QUEUE",),
        ),
        (
            "streaming-payload-limit",
            {"OCI Streaming"},
            assumptions.streaming_max_message_kb,
            "Streaming payload exceeds the documented message limit",
            "OCI Streaming enforces a 1 MB message ceiling. Store the large document elsewhere and publish only the event reference.",
            ("STREAMING",),
        ),
    ]
    for finding_id, supported_tools, limit_kb, title, detail, service_ids in checks:
        if tool_keys.isdisjoint(supported_tools) or payload_kb <= limit_kb:
            continue
        blockers.append(
            CanvasInteroperabilityFinding(
                id=finding_id,
                severity="blocker",
                title=title,
                detail=f"{detail} Payload {_format_limit_kb(payload_kb)} exceeds {_format_limit_kb(limit_kb)}.",
                service_ids=service_ids,
            )
        )
    return blockers


def _connector_hub_blockers(
    routes: Sequence[CanvasInteroperabilityRoute],
    edges: Sequence[CanvasEdge],
    overlay_tool_keys: set[str],
) -> list[CanvasInteroperabilityFinding]:
    blockers: list[CanvasInteroperabilityFinding] = []
    active_node_ids = {node_id for route in routes for node_id in route.node_ids}

    for route_index, route in enumerate(routes):
        for index, service_id in enumerate(route.service_ids):
            if service_id != "CONNECTOR_HUB":
                continue

            connector_node_id = route.node_ids[index + 1]
            previous_tool_key = route.tool_keys[index - 1] if index > 0 else None
            next_tool_key = route.tool_keys[index + 1] if index + 1 < len(route.tool_keys) else None
            previous_service_id = _resolve_canvas_service_id(previous_tool_key) if previous_tool_key else None
            next_service_id = _resolve_canvas_service_id(next_tool_key) if next_tool_key else None

            if previous_service_id is None or previous_service_id not in CONNECTOR_HUB_ALLOWED_SOURCES:
                _push_unique_finding(
                    blockers,
                    CanvasInteroperabilityFinding(
                        id=f"connector-hub-source-{route_index}",
                        severity="blocker",
                        title="Connector Hub source is not Oracle-supported for this route",
                        detail=(
                            "OCI Connector Hub is documented for OCI-native service sources such as Queue or Streaming. "
                            "Model an OCI event source before Connector Hub instead of connecting it directly to the external system or an unsupported service."
                        ),
                        service_ids=tuple(filter(None, ("CONNECTOR_HUB", previous_service_id))),
                    ),
                )

            if next_service_id is None or next_service_id not in CONNECTOR_HUB_ALLOWED_TARGETS:
                _push_unique_finding(
                    blockers,
                    CanvasInteroperabilityFinding(
                        id=f"connector-hub-target-{route_index}",
                        severity="blocker",
                        title="Connector Hub target is not Oracle-supported for this route",
                        detail=(
                            "Connector Hub is documented as a source -> optional task -> target flow. "
                            "On the modeled palette it should hand off to OCI Functions, OCI Streaming, or OCI Object Storage."
                        ),
                        service_ids=tuple(filter(None, ("CONNECTOR_HUB", next_service_id))),
                    ),
                )

            inbound_count = sum(
                1
                for edge in edges
                if edge.target_instance_id == connector_node_id
                and edge.source_instance_id in active_node_ids
                and edge.target_instance_id in active_node_ids
            )
            outbound_count = sum(
                1
                for edge in edges
                if edge.source_instance_id == connector_node_id
                and edge.source_instance_id in active_node_ids
                and edge.target_instance_id in active_node_ids
            )
            if inbound_count > 1 or outbound_count > 1:
                _push_unique_finding(
                    blockers,
                    CanvasInteroperabilityFinding(
                        id=f"connector-hub-parallel-{route_index}",
                        severity="blocker",
                        title="Connector Hub is modeled as a parallel fan-out",
                        detail=(
                            "Oracle documents Connector Hub as a sequential source -> optional task -> target service. "
                            "Parallel branches from the same Connector Hub node should be modeled with another service pattern."
                        ),
                        service_ids=("CONNECTOR_HUB",),
                    ),
                )

            if previous_tool_key in overlay_tool_keys or next_tool_key in overlay_tool_keys:
                _push_unique_finding(
                    blockers,
                    CanvasInteroperabilityFinding(
                        id=f"connector-hub-overlay-{route_index}",
                        severity="blocker",
                        title="Connector Hub is chained directly to an overlay-only node",
                        detail=(
                            "Connector Hub should participate in the core data path, not chain directly through overlay-only controls. "
                            "Add a supported core service before or after the connector."
                        ),
                        service_ids=("CONNECTOR_HUB",),
                    ),
                )

    return blockers


def _gateway_findings(
    routes: Sequence[CanvasInteroperabilityRoute],
    trigger_type: str | None,
) -> list[CanvasInteroperabilityFinding]:
    findings: list[CanvasInteroperabilityFinding] = []
    is_soap_trigger = _includes_any(trigger_type, ["SOAP"])

    for route_index, route in enumerate(routes):
        for index, service_id in enumerate(route.service_ids):
            if service_id != "API_GATEWAY":
                continue

            next_service_id = route.service_ids[index + 1] if index + 1 < len(route.service_ids) else None
            if is_soap_trigger:
                _push_unique_finding(
                    findings,
                    CanvasInteroperabilityFinding(
                        id=f"gateway-soap-{route_index}",
                        severity="blocker",
                        title="API Gateway is modeled on a SOAP-triggered route",
                        detail=(
                            "The Oracle Integration API Gateway front-door is documented for REST-triggered integrations. "
                            "Keep SOAP routes off this gateway pattern or remodel the entry path as REST."
                        ),
                        service_ids=("API_GATEWAY", "OIC3"),
                    ),
                )

            if next_service_id is not None and next_service_id not in API_GATEWAY_ALLOWED_BACKENDS:
                _push_unique_finding(
                    findings,
                    CanvasInteroperabilityFinding(
                        id=f"gateway-backend-{route_index}",
                        severity="blocker",
                        title="API Gateway points to a backend that is not supported by this modeled route",
                        detail=(
                            "For the modeled OCI stack, API Gateway should front OIC, ORDS, or Functions. "
                            "Routing gateway traffic directly into Queue, Streaming, or batch services is not a supported edge pattern."
                        ),
                        service_ids=("API_GATEWAY", next_service_id),
                    ),
                )

    return findings


def _operational_findings(
    route_service_sets: Sequence[set[str]],
    trigger_type: str | None,
    is_real_time: bool | None,
    source_technology: str | None,
    destination_technology: str | None,
    integration_type: str | None,
) -> list[CanvasInteroperabilityFinding]:
    warnings: list[CanvasInteroperabilityFinding] = []
    is_rest_like = (
        _includes_any(trigger_type, ["REST"])
        or _includes_any(integration_type, ["REST"])
        or _includes_any(source_technology, ["REST"])
        or _includes_any(destination_technology, ["REST"])
    )
    is_event_like = (
        _includes_any(trigger_type, ["EVENT"])
        or _includes_any(integration_type, ["EVENT", "KAFKA", "STREAM"])
    )
    is_sync_like = bool(is_real_time) or is_rest_like or _includes_any(trigger_type, ["SOAP"])

    for route_services in route_service_sets:
        if "DATA_INTEGRATION" in route_services and (bool(is_real_time) or is_rest_like or is_event_like):
            _push_unique_finding(
                warnings,
                CanvasInteroperabilityFinding(
                    id="data-integration-low-latency-warning",
                    severity="warning",
                    title="Data Integration is on a low-latency path",
                    detail=(
                        "OCI Data Integration is a batch or micro-batch service and Oracle documents that pipelines are not designed for low-latency operational mediation. "
                        "Keep it on scheduled data movement instead of the synchronous or event critical path."
                    ),
                    service_ids=("DATA_INTEGRATION",),
                ),
            )

        if "FUNCTIONS" in route_services and is_sync_like:
            _push_unique_finding(
                warnings,
                CanvasInteroperabilityFinding(
                    id="functions-sync-warning",
                    severity="warning",
                    title="Functions is on a synchronous critical path",
                    detail=(
                        "Oracle Functions works well for lightweight compute, but this route behaves like a synchronous user or API path. "
                        "Review cold-start, error handling, and the lower service SLA before treating it as the primary critical-path hop."
                    ),
                    service_ids=("FUNCTIONS",),
                ),
            )

        if "OIC3" in route_services and "STREAMING" in route_services and is_event_like:
            _push_unique_finding(
                warnings,
                CanvasInteroperabilityFinding(
                    id="oic-streaming-connectivity-warning",
                    severity="warning",
                    title="OIC + Streaming route still needs deployment-context validation",
                    detail=(
                        "Oracle supports Streaming with OIC through the Streaming or Kafka adapter, but the exact inbound or outbound pattern depends on connectivity mode and deployment context. "
                        "Validate connectivity-agent or private-endpoint details during design review."
                    ),
                    service_ids=("OIC3", "STREAMING"),
                ),
            )

    return warnings


def _advisories(
    route_service_sets: Sequence[set[str]],
    trigger_type: str | None,
    source_technology: str | None,
    destination_technology: str | None,
    integration_type: str | None,
) -> list[CanvasInteroperabilityFinding]:
    advisories: list[CanvasInteroperabilityFinding] = []
    is_rest_like = (
        _includes_any(trigger_type, ["REST"])
        or _includes_any(integration_type, ["REST"])
        or _includes_any(source_technology, ["REST"])
        or _includes_any(destination_technology, ["REST"])
    )
    route_services = set().union(*route_service_sets) if route_service_sets else set()

    if is_rest_like and "ORDS" in route_services and "API_GATEWAY" not in route_services:
        advisories.append(
            CanvasInteroperabilityFinding(
                id="ords-gateway-advisory",
                severity="advisory",
                title="Consider fronting ORDS with API Gateway",
                detail=(
                    "ORDS is a solid database REST facade, but Oracle architecture guidance is stronger when public REST traffic is fronted by API Gateway for rate limiting, token validation, and edge policy control."
                ),
                service_ids=("ORDS", "API_GATEWAY"),
            )
        )

    if is_rest_like and "API_GATEWAY" not in route_services and {"OIC3", "FUNCTIONS", "ORDS"} & route_services:
        advisories.append(
            CanvasInteroperabilityFinding(
                id="rest-route-gateway-advisory",
                severity="advisory",
                title="Public REST edge is missing API Gateway",
                detail=(
                    "If this route is exposed beyond the tenancy boundary, consider API Gateway for JWT or OIDC validation, mTLS, throttling, and centralized edge observability."
                ),
                service_ids=("API_GATEWAY",),
            )
        )

    return advisories


def evaluate_canvas_interoperability(
    nodes: Sequence[CanvasNode],
    edges: Sequence[CanvasEdge],
    overlay_tool_keys: Sequence[str],
    assumptions: Assumptions,
    payload_kb: float | None,
    trigger_type: str | None,
    is_real_time: bool | None,
    source_technology: str | None,
    destination_technology: str | None,
    integration_type: str | None,
) -> CanvasInteroperabilityReport:
    """Evaluate full route-aware interoperability checks from a canvas payload."""

    overlay_tool_set = set(overlay_tool_keys)
    routes = _build_routes(nodes, edges)
    active_tool_keys = {tool_key for route in routes for tool_key in route.tool_keys}
    gateway_findings = _gateway_findings(routes, trigger_type)
    route_service_sets = [set(route.service_ids) for route in routes]
    blockers = [
        *_payload_blockers(payload_kb, active_tool_keys, assumptions),
        *_connector_hub_blockers(routes, edges, overlay_tool_set),
        *(finding for finding in gateway_findings if finding.severity == "blocker"),
    ]
    warnings = [
        *(finding for finding in gateway_findings if finding.severity == "warning"),
        *_operational_findings(
            route_service_sets,
            trigger_type,
            is_real_time,
            source_technology,
            destination_technology,
            integration_type,
        ),
    ]
    advisories = _advisories(
        route_service_sets,
        trigger_type,
        source_technology,
        destination_technology,
        integration_type,
    )
    return CanvasInteroperabilityReport(
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        advisories=tuple(advisories),
        routes=routes,
    )


def _evaluate_toolset_interoperability(
    core_tool_keys: Sequence[str],
    overlay_tool_keys: Sequence[str],
    assumptions: Assumptions,
    payload_kb: float | None,
    trigger_type: str | None,
    is_real_time: bool | None,
    source_technology: str | None,
    destination_technology: str | None,
    integration_type: str | None,
) -> CanvasInteroperabilityReport:
    all_tool_keys = set(core_tool_keys) | set(overlay_tool_keys)
    route_service_sets = [
        {
            service_id
            for tool_key in all_tool_keys
            if (service_id := _resolve_canvas_service_id(tool_key)) is not None
        }
    ]
    blockers = _payload_blockers(payload_kb, all_tool_keys, assumptions)
    if "OCI API Gateway" in all_tool_keys and _includes_any(trigger_type, ["SOAP"]):
        blockers.append(
            CanvasInteroperabilityFinding(
                id="gateway-soap-toolset",
                severity="blocker",
                title="API Gateway is modeled on a SOAP-triggered route",
                detail=(
                    "The Oracle Integration API Gateway front-door is documented for REST-triggered integrations. "
                    "Keep SOAP routes off this gateway pattern or remodel the entry path as REST."
                ),
                service_ids=("API_GATEWAY", "OIC3"),
            )
        )

    warnings = _operational_findings(
        route_service_sets,
        trigger_type,
        is_real_time,
        source_technology,
        destination_technology,
        integration_type,
    )
    advisories = _advisories(
        route_service_sets,
        trigger_type,
        source_technology,
        destination_technology,
        integration_type,
    )
    return CanvasInteroperabilityReport(
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        advisories=tuple(advisories),
        routes=(),
    )


def serialize_canvas_state(
    nodes: Sequence[CanvasNode],
    edges: Sequence[CanvasEdge],
    semantics: CanvasSemantics,
) -> str:
    """Serialize a normalized V3 canvas payload back to storage."""

    payload = {
        "v": 3,
        "nodes": [
            {
                "instanceId": node.instance_id,
                "toolKey": node.tool_key,
                "label": node.label,
                "payloadNote": node.payload_note,
                "x": node.x,
                "y": node.y,
            }
            for node in nodes
        ],
        "edges": [
            {
                "edgeId": edge.edge_id,
                "sourceInstanceId": edge.source_instance_id,
                "targetInstanceId": edge.target_instance_id,
                "label": edge.label,
            }
            for edge in edges
        ],
        "coreToolKeys": list(semantics.core_tool_keys),
        "overlayKeys": list(semantics.overlay_keys),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def normalize_canvas_design(
    *,
    core_tools: str | None,
    additional_tools_overlays: str | None,
    allowed_core_tools: Sequence[str],
    allowed_overlay_tools: Sequence[str],
    assumptions: Assumptions,
    payload_kb: float | None,
    trigger_type: str | None,
    is_real_time: bool | None,
    source_technology: str | None,
    destination_technology: str | None,
    integration_type: str | None,
    enforce_canvas_route: bool,
    enforce_blockers: bool,
) -> NormalizedCanvasDesign:
    """Validate and normalize persisted design fields for catalog writes."""

    allowed_core_tool_set = set(allowed_core_tools)
    allowed_overlay_tool_set = set(allowed_overlay_tools)
    requested_core_tools = _unique_sorted(split_csv(core_tools))
    invalid_requested_core_tools = [
        tool_key for tool_key in requested_core_tools if tool_key not in allowed_core_tool_set
    ]
    if invalid_requested_core_tools:
        raise CanvasDesignValidationError(
            f"Unknown core tool values: {', '.join(invalid_requested_core_tools)}.",
            "INVALID_CORE_TOOLS",
        )

    parsed = parse_canvas_state(additional_tools_overlays, requested_core_tools)
    invalid_overlay_keys = [
        tool_key for tool_key in parsed.overlay_keys if tool_key not in allowed_overlay_tool_set
    ]
    if invalid_overlay_keys:
        raise CanvasDesignValidationError(
            f"Unknown overlay values: {', '.join(invalid_overlay_keys)}.",
            "INVALID_OVERLAY_TOOLS",
        )

    if parsed.mode == "canvas_json":
        invalid_node_tools = [
            node.tool_key
            for node in parsed.nodes
            if node.tool_key not in allowed_core_tool_set and node.tool_key not in allowed_overlay_tool_set
        ]
        if invalid_node_tools:
            raise CanvasDesignValidationError(
                f"Canvas includes ungoverned tools: {', '.join(_unique_sorted(invalid_node_tools))}.",
                "INVALID_CANVAS_TOOLS",
            )

        semantics = derive_canvas_semantics(parsed.nodes, parsed.edges, parsed.overlay_keys)
        invalid_semantic_core_tools = [
            tool_key for tool_key in semantics.core_tool_keys if tool_key not in allowed_core_tool_set
        ]
        if invalid_semantic_core_tools:
            raise CanvasDesignValidationError(
                f"Canvas marks overlay-only services as core tools: {', '.join(invalid_semantic_core_tools)}.",
                "INVALID_CANVAS_CORE_TOOLS",
            )
        if enforce_canvas_route and not semantics.has_connected_route:
            raise CanvasDesignValidationError(
                "Connect the source and destination through at least one governed core tool before saving the canvas.",
                "CANVAS_ROUTE_INCOMPLETE",
            )
        if requested_core_tools and requested_core_tools != semantics.core_tool_keys:
            raise CanvasDesignValidationError(
                "Provided core_tools do not match the active canvas route. Save the canvas with the active route or send matching core_tools values.",
                "CANVAS_CORE_TOOLS_MISMATCH",
            )

        report = evaluate_canvas_interoperability(
            nodes=parsed.nodes,
            edges=parsed.edges,
            overlay_tool_keys=parsed.overlay_keys,
            assumptions=assumptions,
            payload_kb=payload_kb,
            trigger_type=trigger_type,
            is_real_time=is_real_time,
            source_technology=source_technology,
            destination_technology=destination_technology,
            integration_type=integration_type,
        )
        if enforce_blockers and report.blockers:
            titles = "; ".join(finding.title for finding in report.blockers)
            raise CanvasDesignValidationError(
                f"Oracle-backed canvas blockers detected: {titles}.",
                "INVALID_CANVAS_DESIGN",
                findings=report.blockers,
            )
        return NormalizedCanvasDesign(
            mode="canvas_json",
            core_tools_csv=_join_csv(semantics.core_tool_keys),
            additional_tools_value=serialize_canvas_state(parsed.nodes, parsed.edges, semantics),
            semantics=semantics,
            report=report,
        )

    semantics = CanvasSemantics(
        has_directed_route=len(requested_core_tools) > 0,
        has_connected_route=len(requested_core_tools) > 0,
        core_tool_keys=requested_core_tools,
        overlay_keys=parsed.overlay_keys,
    )
    report = _evaluate_toolset_interoperability(
        core_tool_keys=requested_core_tools,
        overlay_tool_keys=parsed.overlay_keys,
        assumptions=assumptions,
        payload_kb=payload_kb,
        trigger_type=trigger_type,
        is_real_time=is_real_time,
        source_technology=source_technology,
        destination_technology=destination_technology,
        integration_type=integration_type,
    )
    if enforce_blockers and report.blockers:
        titles = "; ".join(finding.title for finding in report.blockers)
        raise CanvasDesignValidationError(
            f"Oracle-backed design blockers detected: {titles}.",
            "INVALID_CANVAS_DESIGN",
            findings=report.blockers,
        )
    return NormalizedCanvasDesign(
        mode=parsed.mode,
        core_tools_csv=_join_csv(requested_core_tools),
        additional_tools_value=_join_csv(parsed.overlay_keys) if parsed.mode == "legacy_csv" else None,
        semantics=semantics,
        report=report,
    )


def build_design_constraint_messages(
    *,
    core_tools: str | None,
    additional_tools_overlays: str | None,
    assumptions: Assumptions,
    payload_kb: float | None,
    trigger_type: str | None,
    is_real_time: bool | None,
    source_technology: str | None,
    destination_technology: str | None,
    integration_type: str | None,
) -> list[str]:
    """Convert current design findings into snapshot-friendly warning strings."""

    try:
        parsed = parse_canvas_state(additional_tools_overlays, split_csv(core_tools))
    except CanvasDesignValidationError as exc:
        return [f"Blocker: {exc.detail}"]

    if parsed.mode == "canvas_json":
        report = evaluate_canvas_interoperability(
            nodes=parsed.nodes,
            edges=parsed.edges,
            overlay_tool_keys=parsed.overlay_keys,
            assumptions=assumptions,
            payload_kb=payload_kb,
            trigger_type=trigger_type,
            is_real_time=is_real_time,
            source_technology=source_technology,
            destination_technology=destination_technology,
            integration_type=integration_type,
        )
    else:
        report = _evaluate_toolset_interoperability(
            core_tool_keys=split_csv(core_tools),
            overlay_tool_keys=parsed.overlay_keys,
            assumptions=assumptions,
            payload_kb=payload_kb,
            trigger_type=trigger_type,
            is_real_time=is_real_time,
            source_technology=source_technology,
            destination_technology=destination_technology,
            integration_type=integration_type,
        )

    messages: list[str] = []
    for severity, findings in (
        ("Blocker", report.blockers),
        ("Warning", report.warnings),
        ("Advisory", report.advisories),
    ):
        for finding in findings:
            messages.append(f"{severity}: {finding.title}. {finding.detail}")
    return messages
