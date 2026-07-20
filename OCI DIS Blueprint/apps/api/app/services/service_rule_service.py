"""Authoritative runtime assembly for normalized Service Product rules."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.calc_engine import Assumptions
from app.models import (
    ServiceCapabilityProfile,
    ServiceEvidenceSource,
    ServiceInteroperabilityRule,
    ServiceLimit,
    ServiceVerificationFinding,
)


@dataclass(frozen=True)
class GovernedRelationship:
    """One active directional relationship from the normalized matrix."""

    source_service_id: str
    target_service_id: str
    relationship_type: str
    risk_notes: str | None
    confidence: float


@dataclass(frozen=True)
class GovernedServiceLimit:
    """One runtime rule with its governed semantics and applicability context."""

    service_id: str
    limit_key: str
    value: object
    unit: str | None
    scope: str
    limit_type: str
    constraint_kind: str
    enforcement: str
    applicability: Mapping[str, object]
    source_url: str | None
    confidence: float


@dataclass(frozen=True)
class ServiceRuleBundle:
    """Immutable view consumed by canvas, calculation, review, and reporting."""

    version: str
    source: str
    freshness_status: str
    limits_by_service: Mapping[str, Mapping[str, object]]
    definitions_by_service: Mapping[str, Mapping[str, GovernedServiceLimit]]
    relationships: tuple[GovernedRelationship, ...]
    stale_evidence_count: int
    open_findings_count: int
    last_verified_at: datetime | None

    @property
    def available(self) -> bool:
        """Return whether normalized service products were loaded."""

        return self.source == "normalized_service_products"

    def value(self, service_id: str, limit_key: str) -> object | None:
        """Return one active normalized limit value."""

        return self.limits_by_service.get(service_id, {}).get(limit_key)

    def numeric_limit(self, service_id: str, limit_key: str) -> float | None:
        """Return a numeric normalized limit without coercing booleans."""

        value = self.value(service_id, limit_key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    def definition(self, service_id: str, limit_key: str) -> GovernedServiceLimit | None:
        """Return the full governed rule definition, including enforcement semantics."""

        return self.definitions_by_service.get(service_id, {}).get(limit_key)

    def string_values(self, service_id: str, limit_key: str) -> frozenset[str]:
        """Return a normalized string set from a list-valued service rule."""

        value = self.value(service_id, limit_key)
        if not isinstance(value, list):
            return frozenset()
        return frozenset(str(item).strip().upper() for item in value if str(item).strip())

    def targets_for(self, source_service_id: str) -> frozenset[str]:
        """Return supported targets for one source service."""

        return frozenset(
            relationship.target_service_id
            for relationship in self.relationships
            if relationship.source_service_id == source_service_id
        )

    def relationship(self, source_service_id: str, target_service_id: str) -> GovernedRelationship | None:
        """Return one governed directional relationship when present."""

        return next(
            (
                relationship
                for relationship in self.relationships
                if relationship.source_service_id == source_service_id
                and relationship.target_service_id == target_service_id
            ),
            None,
        )

    def metadata(self) -> dict[str, object]:
        """Serialize provenance for immutable snapshots and downstream evidence."""

        return {
            "version": self.version,
            "source": self.source,
            "freshness_status": self.freshness_status,
            "stale_evidence_count": self.stale_evidence_count,
            "open_findings_count": self.open_findings_count,
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else None,
        }


EMPTY_SERVICE_RULE_BUNDLE = ServiceRuleBundle(
    version="unavailable",
    source="unavailable",
    freshness_status="unavailable",
    limits_by_service=MappingProxyType({}),
    definitions_by_service=MappingProxyType({}),
    relationships=(),
    stale_evidence_count=0,
    open_findings_count=0,
    last_verified_at=None,
)


# Service rules override compatibility keys from historical AssumptionSet JSON.
# The tuple's final value converts the normalized unit into the calc-engine unit.
ASSUMPTION_RULE_BINDINGS: dict[str, tuple[str, str, float]] = {
    "oic_billing_threshold_kb": ("OIC3", "billing_threshold_kb", 1.0),
    "oic_pack_size_msgs_per_hour": ("OIC3", "pack_size_msgs_per_hour_new_license", 1.0),
    "oic_byol_pack_size_msgs_per_hour": ("OIC3", "pack_size_msgs_per_hour_byol", 1.0),
    "oic_pack_size_msgs_per_hour_byol": ("OIC3", "pack_size_msgs_per_hour_byol", 1.0),
    "oic_rest_max_payload_kb": ("OIC3", "rest_trigger_structured_max_payload_kb", 1.0),
    "oic_ftp_max_payload_kb": ("OIC3", "ftp_structured_cloud_max_payload_kb", 1.0),
    "oic_kafka_max_payload_kb": ("OIC3", "kafka_schema_max_payload_kb", 1.0),
    "oic_rest_raw_max_payload_kb": ("OIC3", "rest_raw_max_payload_kb", 1.0),
    "oic_rest_attachment_max_payload_kb": ("OIC3", "rest_attachment_max_payload_kb", 1.0),
    "oic_rest_json_schema_max_payload_kb": ("OIC3", "rest_json_schema_sample_max_kb", 1.0),
    "oic_soap_max_payload_kb": ("OIC3", "soap_structured_max_payload_kb", 1.0),
    "oic_soap_attachment_max_payload_kb": ("OIC3", "soap_attachment_max_payload_kb", 1.0),
    "oic_ftp_stage_file_max_payload_kb": ("OIC3", "stage_read_entire_file_max_payload_kb", 1.0),
    "oic_sync_max_duration_s": ("OIC3", "sync_flow_max_duration_s", 1.0),
    "oic_timeout_s": ("OIC3", "sync_flow_max_duration_s", 1.0),
    "oic_async_max_duration_s": ("OIC3", "async_scheduled_flow_max_duration_s", 1.0),
    "oic_max_parallel_branches": ("OIC3", "max_parallel_branches", 1.0),
    "oic_max_invocation_depth": ("OIC3", "max_invocation_depth", 1.0),
    "oic_sync_concurrency_new": ("OIC3", "sync_concurrency_per_pack_new", 1.0),
    "oic_sync_concurrency_byol": ("OIC3", "sync_concurrency_per_pack_byol", 1.0),
    "oic_async_concurrency_new": ("OIC3", "async_concurrency_per_pack_new", 1.0),
    "oic_async_concurrency_byol": ("OIC3", "async_concurrency_per_pack_byol", 1.0),
    "oic_db_polling_max_payload_kb": ("OIC3", "database_polling_agent_max_payload_kb", 1.0),
    "oic_project_max_integrations": ("OIC3", "project_max_integrations", 1.0),
    "oic_project_max_connections": ("OIC3", "project_max_connections", 1.0),
    "oic_project_max_deployments": ("OIC3", "project_max_deployments", 1.0),
    "streaming_partition_throughput_mb_s": ("STREAMING", "write_throughput_mb_s_per_partition", 1.0),
    "streaming_max_message_kb": ("STREAMING", "max_message_size_kb", 1.0),
    "streaming_max_message_size_mb": ("STREAMING", "max_message_size_kb", 1.0 / 1024.0),
    "streaming_retention_days": ("STREAMING", "retention_max_d", 1.0),
    "streaming_get_rps_per_consumer_group_per_partition": (
        "STREAMING",
        "get_requests_per_s_per_consumer_group_per_partition",
        1.0,
    ),
    "streaming_max_consumer_groups_per_stream": ("STREAMING", "max_consumer_groups_per_stream", 1.0),
    "streaming_max_partitions_muc": ("STREAMING", "max_partitions_monthly_universal_credits", 1.0),
    "streaming_max_partitions_payg": ("STREAMING", "max_partitions_payg", 1.0),
    "functions_max_invoke_body_kb": ("FUNCTIONS", "max_invoke_body_kb", 1.0),
    "queue_max_message_kb": ("QUEUE", "max_message_size_kb", 1.0),
    "queue_max_inflight_messages": ("QUEUE", "max_inflight_messages_per_queue", 1.0),
    "queue_max_queues_per_region": ("QUEUE", "max_queues_per_tenancy_per_region", 1.0),
    "queue_ingress_throughput_mb_s": ("QUEUE", "ingress_throughput_mb_s_per_queue", 1.0),
    "queue_egress_throughput_mb_s": ("QUEUE", "egress_throughput_mb_s_per_queue", 1.0),
    "queue_max_storage_per_queue_gb": ("QUEUE", "max_storage_per_queue_gb", 1.0),
    "queue_retention_days": ("QUEUE", "retention_max_d", 1.0),
    "api_gw_max_body_kb": ("API_GATEWAY", "max_request_body_kb", 1.0),
    "api_gw_max_function_body_kb": ("API_GATEWAY", "max_function_backend_body_kb", 1.0),
    "api_gw_backend_timeout_max_s": ("API_GATEWAY", "backend_read_send_timeout_max_s", 1.0),
    "api_gw_max_routes_per_deployment": ("API_GATEWAY", "max_routes_per_deployment", 1.0),
    "api_gw_max_deployments_per_gateway": ("API_GATEWAY", "max_deployments_per_gateway", 1.0),
}


def apply_service_rules(base: Assumptions, bundle: ServiceRuleBundle) -> Assumptions:
    """Overlay normalized service limits onto compatible calc-engine inputs."""

    values = {field.name: getattr(base, field.name) for field in fields(Assumptions)}
    for assumption_key, (service_id, limit_key, scale) in ASSUMPTION_RULE_BINDINGS.items():
        normalized_value = bundle.numeric_limit(service_id, limit_key)
        if normalized_value is None:
            continue
        current_value = values[assumption_key]
        resolved_value = normalized_value * scale
        values[assumption_key] = int(resolved_value) if isinstance(current_value, int) else resolved_value
    return Assumptions(**values)


async def load_service_rule_bundle(db: AsyncSession) -> ServiceRuleBundle:
    """Load one deterministic bundle from active normalized service governance."""

    profiles = list(
        (
            await db.scalars(
                select(ServiceCapabilityProfile)
                .where(ServiceCapabilityProfile.is_active.is_(True))
                .order_by(ServiceCapabilityProfile.service_id)
            )
        ).all()
    )
    if not profiles:
        return EMPTY_SERVICE_RULE_BUNDLE

    profile_ids = [profile.id for profile in profiles]
    profile_by_id = {profile.id: profile for profile in profiles}
    limits = list(
        (
            await db.scalars(
                select(ServiceLimit)
                .where(
                    ServiceLimit.service_profile_id.in_(profile_ids),
                    ServiceLimit.is_active.is_(True),
                )
                .order_by(ServiceLimit.service_profile_id, ServiceLimit.limit_key)
            )
        ).all()
    )
    rules = list(
        (
            await db.scalars(
                select(ServiceInteroperabilityRule)
                .where(
                    ServiceInteroperabilityRule.source_service_profile_id.in_(profile_ids),
                    ServiceInteroperabilityRule.target_service_profile_id.in_(profile_ids),
                    ServiceInteroperabilityRule.is_active.is_(True),
                    ServiceInteroperabilityRule.supported.is_(True),
                )
                .order_by(
                    ServiceInteroperabilityRule.source_service_profile_id,
                    ServiceInteroperabilityRule.target_service_profile_id,
                    ServiceInteroperabilityRule.relationship_type,
                )
            )
        ).all()
    )
    evidence = list(
        (
            await db.scalars(
                select(ServiceEvidenceSource).where(ServiceEvidenceSource.service_profile_id.in_(profile_ids))
            )
        ).all()
    )
    open_findings_count = int(
        await db.scalar(
            select(func.count(ServiceVerificationFinding.id)).where(
                ServiceVerificationFinding.review_status == "open"
            )
        )
        or 0
    )

    mutable_limits: dict[str, dict[str, object]] = {profile.service_id: {} for profile in profiles}
    mutable_definitions: dict[str, dict[str, GovernedServiceLimit]] = {
        profile.service_id: {} for profile in profiles
    }
    for limit in limits:
        profile = profile_by_id.get(limit.service_profile_id)
        if profile is not None:
            mutable_limits[profile.service_id][limit.limit_key] = limit.value
            mutable_definitions[profile.service_id][limit.limit_key] = GovernedServiceLimit(
                service_id=profile.service_id,
                limit_key=limit.limit_key,
                value=limit.value,
                unit=limit.unit,
                scope=limit.scope,
                limit_type=limit.limit_type,
                constraint_kind=limit.constraint_kind,
                enforcement=limit.enforcement,
                applicability=MappingProxyType(dict(limit.applicability or {})),
                source_url=limit.source_url,
                confidence=limit.confidence,
            )
    limits_by_service: Mapping[str, Mapping[str, object]] = MappingProxyType(
        {
            service_id: MappingProxyType(service_limits)
            for service_id, service_limits in mutable_limits.items()
        }
    )
    definitions_by_service: Mapping[str, Mapping[str, GovernedServiceLimit]] = MappingProxyType(
        {
            service_id: MappingProxyType(service_limits)
            for service_id, service_limits in mutable_definitions.items()
        }
    )

    relationships = tuple(
        GovernedRelationship(
            source_service_id=profile_by_id[rule.source_service_profile_id].service_id,
            target_service_id=profile_by_id[rule.target_service_profile_id].service_id,
            relationship_type=rule.relationship_type,
            risk_notes=rule.risk_notes,
            confidence=rule.confidence,
        )
        for rule in rules
    )
    stale_statuses = {"stale", "seeded_pending_verification", "pending_verification", "failed"}
    stale_evidence_count = sum(1 for source in evidence if source.status in stale_statuses)
    verified_dates = [source.last_checked_at for source in evidence if source.last_checked_at]
    verified_dates.extend(rule.last_verified_at for rule in rules if rule.last_verified_at)
    last_verified_at = max(verified_dates) if verified_dates else None
    freshness_status = (
        "stale"
        if stale_evidence_count
        else "needs_review"
        if open_findings_count
        else "current"
    )

    version_payload = {
        "profiles": [(profile.service_id, profile.version) for profile in profiles],
        "limits": [
            (profile_by_id[limit.service_profile_id].service_id, limit.limit_key, limit.value)
            for limit in limits
        ],
        "relationships": [
            (
                relationship.source_service_id,
                relationship.target_service_id,
                relationship.relationship_type,
                relationship.confidence,
            )
            for relationship in relationships
        ],
    }
    digest = sha256(
        json.dumps(version_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()[:16]
    return ServiceRuleBundle(
        version=f"service-rules-{digest}",
        source="normalized_service_products",
        freshness_status=freshness_status,
        limits_by_service=limits_by_service,
        definitions_by_service=definitions_by_service,
        relationships=relationships,
        stale_evidence_count=stale_evidence_count,
        open_findings_count=open_findings_count,
        last_verified_at=last_verified_at,
    )
