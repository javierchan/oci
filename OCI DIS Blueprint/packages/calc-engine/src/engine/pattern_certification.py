"""Governed, tool-agnostic certification contracts for integration patterns."""

from __future__ import annotations

from dataclasses import dataclass
import json


CERTIFICATION_VERSION = "1.0.0"


@dataclass(frozen=True)
class PatternCertificationProfile:
    """Evidence and composition contract required for certified pattern use."""

    pattern_id: str
    name: str
    sizing_strategy: str
    required_evidence: tuple[str, ...]
    approved_core_tool_groups: tuple[tuple[str, ...], ...]
    approved_overlay_groups: tuple[tuple[str, ...], ...]
    commercial_service_ids: tuple[str, ...]
    external_dependencies: tuple[str, ...]
    validation_controls: tuple[str, ...]
    summary: str
    certification_version: str = CERTIFICATION_VERSION


def _profile(
    pattern_id: str,
    name: str,
    sizing_strategy: str,
    *,
    evidence: tuple[str, ...] = (),
    tools: tuple[tuple[str, ...], ...],
    overlays: tuple[tuple[str, ...], ...] = (),
    services: tuple[str, ...],
    external: tuple[str, ...] = (),
    controls: tuple[str, ...],
    summary: str,
) -> PatternCertificationProfile:
    return PatternCertificationProfile(
        pattern_id=pattern_id,
        name=name,
        sizing_strategy=sizing_strategy,
        required_evidence=evidence,
        approved_core_tool_groups=tools,
        approved_overlay_groups=overlays,
        commercial_service_ids=services,
        external_dependencies=external,
        validation_controls=controls,
        summary=summary,
    )


PATTERN_CERTIFICATIONS: dict[str, PatternCertificationProfile] = {
    "#01": _profile("#01", "Request-Reply", "request_response", evidence=("target_latency_sla",), tools=(("oic",), ("functions",)), services=("OIC3", "FUNCTIONS", "API_GATEWAY"), controls=("timeout budget", "request and response payload", "endpoint availability"), summary="Synchronous request and response sized from governed message, invocation, and API-edge demand."),
    "#02": _profile("#02", "Event-Driven / Pub-Sub", "event_backbone", evidence=("idempotency",), tools=(("streaming",), ("queue",), ("oic", "functions")), services=("OIC3", "STREAMING", "QUEUE", "FUNCTIONS", "EVENTS"), controls=("at-least-once delivery", "partition or queue throughput", "consumer idempotency"), summary="Event traffic is sized through its governed broker, consumer, and orchestration products."),
    "#03": _profile("#03", "API Facade", "api_edge", evidence=("target_latency_sla", "data_security_classification"), tools=(("oic",), ("functions",)), overlays=(("api gateway",),), services=("API_GATEWAY", "OIC3", "FUNCTIONS"), controls=("authentication", "rate limiting", "backend timeout"), summary="API ingress, transformation, and backend calls are validated and sized as one protected route."),
    "#04": _profile("#04", "Saga / Compensation", "stateful_orchestration", evidence=("business_criticality", "retry_policy", "idempotency"), tools=(("oic",),), services=("OIC3", "PROCESS_AUTOMATION", "QUEUE"), controls=("compensation ownership", "durable state", "bounded retries"), summary="Stateful orchestration uses governed OIC demand with explicit compensation and recovery controls."),
    "#05": _profile("#05", "CDC — Change Data Capture", "data_movement", evidence=("retention_processing_window", "data_security_classification"), tools=(("goldengate",), ("data integration",), ("data integrator",)), services=("GOLDENGATE", "DATA_INTEGRATION", "ODI", "STREAMING"), controls=("change retention", "replication lag", "schema evolution"), summary="Change volume is sized through governed replication and downstream data-processing products."),
    "#06": _profile("#06", "Strangler Fig Runtime", "migration_coexistence", evidence=("business_criticality", "target_latency_sla"), tools=(("oic",),), overlays=(("api gateway",),), services=("API_GATEWAY", "OIC3", "OBSERVABILITY"), controls=("route ownership", "rollback", "traffic migration"), summary="Legacy and target routes are governed as an observable, reversible migration path."),
    "#07": _profile("#07", "Scatter-Gather", "parallel_fanout", evidence=("fan_out_targets", "target_latency_sla"), tools=(("oic",),), services=("OIC3", "FUNCTIONS"), controls=("parallel branch limit", "aggregate timeout", "partial failure policy"), summary="Parallel branches are validated from target count and sized through their orchestration demand."),
    "#08": _profile("#08", "Circuit Breaker", "resilient_delivery", evidence=("retry_policy", "target_latency_sla"), tools=(("oic",), ("queue",)), services=("OIC3", "QUEUE", "OBSERVABILITY"), controls=("failure threshold", "open interval", "fallback behavior"), summary="Steady-state demand remains product-driven while failure isolation and recovery are explicitly governed."),
    "#09": _profile("#09", "Transactional Outbox", "transactional_event", evidence=("idempotency", "retention_processing_window"), tools=(("streaming",), ("goldengate",)), services=("GOLDENGATE", "STREAMING", "FUNCTIONS", "OBJECT_STORAGE"), controls=("atomic write", "relay lag", "deduplication"), summary="Outbox relay and event transport are sized from governed change and message demand."),
    "#10": _profile("#10", "CQRS + Event Sourcing", "event_projection", evidence=("idempotency", "retention_processing_window", "data_security_classification"), tools=(("streaming", "functions"),), services=("STREAMING", "FUNCTIONS", "OBJECT_STORAGE"), controls=("event retention", "projection rebuild", "schema compatibility"), summary="Commands, events, and projections are governed through broker, compute, and archive demand."),
    "#11": _profile("#11", "BFF — Backend for Frontend", "experience_api", evidence=("target_latency_sla", "data_security_classification"), tools=(("oic",), ("functions",)), overlays=(("api gateway",),), services=("API_GATEWAY", "OIC3", "FUNCTIONS"), controls=("client-specific contract", "latency budget", "authentication"), summary="Client-facing aggregation is sized as a protected API plus governed orchestration or serverless compute."),
    "#12": _profile("#12", "Data Mesh", "governed_data_product", evidence=("business_criticality", "retention_processing_window", "data_security_classification"), tools=(("data integration",), ("data integrator",), ("goldengate",)), overlays=(("data catalog", "object storage"),), services=("DATA_INTEGRATION", "ODI", "GOLDENGATE", "DATA_CATALOG", "OBJECT_STORAGE", "IAM"), controls=("domain ownership", "data contract", "lineage and access policy"), summary="Data products are certified through processing, catalog, storage, and access-governance evidence."),
    "#13": _profile("#13", "Zero-Trust Integration", "zero_trust_policy", evidence=("data_security_classification", "target_latency_sla"), tools=(("oic",), ("functions",)), overlays=(("api gateway", "iam"),), services=("API_GATEWAY", "IAM", "OBSERVABILITY", "OIC3", "FUNCTIONS"), controls=("least privilege", "strong identity", "encrypted transport"), summary="Every route is certified with an identity boundary, protected edge, and observable workload."),
    "#14": _profile("#14", "AsyncAPI + Event Catalog", "event_contract", evidence=("data_security_classification", "retention_processing_window"), tools=(("streaming",), ("queue",), ("oic", "functions")), overlays=(("data catalog",),), services=("STREAMING", "QUEUE", "EVENTS", "DATA_CATALOG"), controls=("event schema", "owner and consumer", "compatibility policy"), summary="Event demand remains broker-driven while contracts and ownership are governed in the catalog."),
    "#15": _profile("#15", "AI-Augmented Integration", "ai_inference", evidence=("data_security_classification", "target_latency_sla"), tools=(("functions",), ("oic", "functions")), overlays=(("ai services",),), services=("FUNCTIONS", "OIC3", "API_GATEWAY"), external=("OCI Language or OCI Data Science model",), controls=("confidence threshold", "human fallback", "sensitive-data handling"), summary="Integration and inference demand are separated, with external model capacity declared explicitly."),
    "#16": _profile("#16", "Integration Mesh", "service_mesh", evidence=("business_criticality", "data_security_classification", "target_latency_sla"), tools=(("oic",), ("functions",)), overlays=(("service mesh", "observability", "iam"),), services=("API_GATEWAY", "IAM", "OBSERVABILITY"), external=("OKE and Istio capacity",), controls=("mTLS", "traffic policy", "platform ownership"), summary="The App certifies integration traffic and policy evidence while declaring OKE/Istio as an external capacity dependency."),
    "#17": _profile("#17", "Webhook Fanout", "webhook_fanout", evidence=("fan_out_targets", "retry_policy", "idempotency"), tools=(("oic", "queue"), ("oic", "streaming")), overlays=(("api gateway",),), services=("API_GATEWAY", "OIC3", "QUEUE", "STREAMING", "FUNCTIONS"), controls=("signature verification", "backpressure", "subscriber isolation"), summary="Inbound calls, buffering, and subscriber fan-out are validated and sized as one governed delivery path."),
    "#18": _profile("#18", "Scheduled Batch / File Transfer", "scheduled_batch", evidence=("retention_processing_window",), tools=(("data integration",), ("data integrator",), ("oic",)), overlays=(("object storage",),), services=("OIC3", "DATA_INTEGRATION", "ODI", "OBJECT_STORAGE"), external=("SFTP endpoint capacity when used",), controls=("batch window", "restart point", "reconciliation"), summary="Batch runs and transferred data are sized in real service units with an explicit staging and recovery window."),
    "#19": _profile("#19", "Async Request-Reply (Correlation)", "async_correlation", evidence=("target_latency_sla", "retry_policy", "idempotency"), tools=(("oic", "queue"), ("queue", "functions")), services=("API_GATEWAY", "OIC3", "QUEUE", "FUNCTIONS"), controls=("correlation expiry", "callback security", "bounded retries"), summary="Request, work queue, callback, and compute demand are governed as a correlated asynchronous exchange."),
    "#20": _profile("#20", "Claim Check", "claim_check", evidence=("retention_processing_window", "data_security_classification"), tools=(("oic",), ("queue",), ("streaming",)), overlays=(("object storage",),), services=("OBJECT_STORAGE", "QUEUE", "STREAMING", "OIC3"), controls=("object lifecycle", "reference expiry", "orphan cleanup"), summary="Payload storage and reference transport are modeled separately to preserve limits and lifecycle governance."),
    "#21": _profile("#21", "DLQ / Retry with Backoff", "retry_dlq", evidence=("retry_policy", "idempotency"), tools=(("queue",), ("oic", "queue")), overlays=(("observability",),), services=("QUEUE", "OIC3", "OBSERVABILITY"), controls=("retry classification", "DLQ ownership", "audited replay"), summary="Normal delivery, bounded retry, dead-letter isolation, and operational visibility form one certified route."),
}


def get_pattern_certification(pattern_id: str | None) -> PatternCertificationProfile | None:
    """Return the governed certification contract for one known system pattern."""

    if pattern_id is None:
        return None
    return PATTERN_CERTIFICATIONS.get(pattern_id)


def _normalized_items(value: str | None) -> set[str]:
    if not value:
        return set()
    candidates: list[str] = []
    try:
        decoded = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        decoded = None
    if isinstance(decoded, dict):
        for collection_name in ("coreToolKeys", "overlayKeys"):
            collection = decoded.get(collection_name)
            if isinstance(collection, list):
                candidates.extend(
                    item for item in collection if isinstance(item, str) and item.strip()
                )
        for collection_name in ("nodes", "overlays"):
            collection = decoded.get(collection_name)
            if not isinstance(collection, list):
                continue
            for item in collection:
                if not isinstance(item, dict):
                    continue
                for key in ("toolKey", "label", "name", "value"):
                    candidate = item.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        candidates.append(candidate)
    if not candidates:
        candidates = value.replace("|", ",").split(",")
    return {
        " ".join(item.strip().lower().replace("oci ", "").split())
        for item in candidates
        if item.strip()
    }


def _group_matches(group: tuple[str, ...], actual: set[str]) -> bool:
    return all(any(required in item for item in actual) for required in group)


def composition_issues(
    pattern_id: str | None,
    core_tools: str | None,
    overlays: str | None,
) -> tuple[str, ...]:
    """Return stable reason codes when a pattern composition is not certified."""

    profile = get_pattern_certification(pattern_id)
    if pattern_id and profile is None:
        return ("PATTERN_NOT_CERTIFIED",)
    if profile is None:
        return ()

    tools = _normalized_items(core_tools)
    overlay_items = _normalized_items(overlays)
    issues: list[str] = []
    if profile.approved_core_tool_groups and not any(
        _group_matches(group, tools) for group in profile.approved_core_tool_groups
    ):
        issues.append("PATTERN_CORE_TOOLS_NOT_CERTIFIED")
    if profile.approved_overlay_groups and not any(
        _group_matches(group, overlay_items) for group in profile.approved_overlay_groups
    ):
        issues.append("PATTERN_OVERLAYS_NOT_CERTIFIED")
    return tuple(issues)
