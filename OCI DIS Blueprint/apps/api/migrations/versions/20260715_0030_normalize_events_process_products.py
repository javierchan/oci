"""Normalize Events and Process Automation as governed Service Products."""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20260715_0030"
down_revision = "20260715_0029"
branch_labels = None
depends_on = None


PROFILES = [
    {
        "id": "03000000-0000-4000-8000-000000000001",
        "service_id": "EVENTS",
        "name": "OCI Events",
        "category": "EVENT_ROUTING",
        "sla_uptime_pct": None,
        "pricing_model": "No standalone Events service charge. Price invoked targets and downstream services separately.",
        "limits": {
            "delivery_model": "At-least-once event delivery to supported targets",
            "rule_scope": "Rules match OCI service events and custom CloudEvents",
            "billable_dependencies": ["FUNCTIONS", "STREAMING", "OBJECT_STORAGE", "NOTIFICATIONS"],
            "label": "documented",
        },
        "architectural_fit": "Event routing for OCI resource-state changes and custom CloudEvents into supported targets.",
        "anti_patterns": "Not a durable work queue, ordered event log, or business-process orchestrator.",
        "interoperability_notes": "Routes matching events to Functions, Streaming, Notifications, and other supported targets; downstream products retain their own limits and meters.",
        "oracle_docs_urls": "https://docs.oracle.com/en-us/iaas/Content/Events/Concepts/eventsoverview.htm|https://docs.oracle.com/en-us/iaas/Content/Events/Concepts/eventsgetstarted.htm|https://www.oracle.com/cloud/price-list/",
    },
    {
        "id": "03000000-0000-4000-8000-000000000002",
        "service_id": "PROCESS_AUTOMATION",
        "name": "Oracle Integration Process Automation",
        "category": "BUSINESS_PROCESS_AUTOMATION",
        "sla_uptime_pct": None,
        "pricing_model": "Capability governed with Oracle Integration commercial entitlement; edition and contract eligibility require review.",
        "limits": {
            "commercial_dependency": "OIC3",
            "edition_review_required": True,
            "process_scope": "Human workflow and business process automation",
            "label": "documented",
        },
        "architectural_fit": "Human-centric workflow, approvals, forms, and business process automation associated with Oracle Integration.",
        "anti_patterns": "Not a replacement for high-volume system integration, streaming, queues, or batch data movement.",
        "interoperability_notes": "Works with Oracle Integration application integrations and human tasks; preserve edition, BYOL, and entitlement evidence.",
        "oracle_docs_urls": "https://docs.oracle.com/en/cloud/paas/process-automation/|https://docs.oracle.com/en-us/iaas/application-integration/index.html|https://www.oracle.com/integration/pricing/",
    },
]


POLICIES = [
    {
        "id": "03030000-0000-4000-8000-000000000001",
        "service_id": "EVENTS",
        "classification": "included_non_billable",
        "readiness": "quote_ready",
        "publication_policy": "included_zero",
        "tool_aliases": ["OCI Events", "Events"],
        "dependent_service_ids": [],
        "required_inputs": [],
        "guidance": "Keep OCI Events visible as an included line and price each invoked target or downstream service separately.",
        "source_urls": ["https://docs.oracle.com/en-us/iaas/Content/Events/Concepts/eventsoverview.htm"],
    },
    {
        "id": "03030000-0000-4000-8000-000000000002",
        "service_id": "PROCESS_AUTOMATION",
        "classification": "dependent_entitlement",
        "readiness": "input_required",
        "publication_policy": "dependencies_required",
        "tool_aliases": ["Oracle Integration Process Automation", "Process Automation", "OCI Process Automation"],
        "dependent_service_ids": ["OIC3"],
        "required_inputs": ["Oracle Integration edition, BYOL decision, and contractual Process Automation entitlement"],
        "guidance": "Confirm that the selected Oracle Integration edition and contract include Process Automation before publication.",
        "source_urls": ["https://docs.oracle.com/en/cloud/paas/process-automation/", "https://www.oracle.com/integration/pricing/"],
    },
]


INTEROPERABILITY_RULES = [
    ("EVENTS", "FUNCTIONS", "event_target", ["#02", "#17"], ["event rule", "Functions target", "idempotent handler"], {"delivery_model": "at_least_once"}, "Handlers must be idempotent and retain downstream failure evidence."),
    ("EVENTS", "STREAMING", "event_target", ["#02", "#15"], ["event rule", "Streaming target", "partition strategy"], {"downstream_limits_apply": True}, "Events does not replace Streaming retention, ordering, or partition design."),
    ("PROCESS_AUTOMATION", "OIC3", "workflow_integration", ["#04", "#05"], ["approved OIC edition", "process entitlement", "human-task design"], {"commercial_entitlement_review": True}, "Confirm edition and contractual entitlement before treating Process Automation as included."),
]


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)

    profile_table = sa.table(
        "service_capability_profiles",
        sa.column("id", sa.String()),
        sa.column("service_id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("category", sa.String()),
        sa.column("sla_uptime_pct", sa.Float()),
        sa.column("pricing_model", sa.String()),
        sa.column("limits", sa.JSON()),
        sa.column("architectural_fit", sa.Text()),
        sa.column("anti_patterns", sa.Text()),
        sa.column("interoperability_notes", sa.Text()),
        sa.column("oracle_docs_urls", sa.Text()),
        sa.column("is_active", sa.Boolean()),
        sa.column("version", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    for profile in PROFILES:
        existing_id = bind.scalar(
            sa.text("SELECT id FROM service_capability_profiles WHERE service_id = :service_id"),
            {"service_id": profile["service_id"]},
        )
        if existing_id is None:
            bind.execute(
                profile_table.insert().values(
                    **profile,
                    is_active=True,
                    version="1.0.0",
                    created_at=now,
                    updated_at=now,
                )
            )

    profile_ids = {
        row.service_id: row.id
        for row in bind.execute(
            sa.text(
                "SELECT id, service_id FROM service_capability_profiles "
                "WHERE service_id IN ('EVENTS', 'PROCESS_AUTOMATION')"
            )
        )
    }
    version_table = sa.table(
        "service_product_versions",
        sa.column("id", sa.String()),
        sa.column("service_profile_id", sa.String()),
        sa.column("version_label", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("capabilities", sa.JSON()),
        sa.column("use_cases", sa.JSON()),
        sa.column("anti_patterns", sa.JSON()),
        sa.column("regional_availability", sa.Text()),
        sa.column("commercial_notes", sa.Text()),
        sa.column("security_notes", sa.Text()),
        sa.column("deprecation_notes", sa.Text()),
        sa.column("metadata", sa.JSON()),
        sa.column("effective_from", sa.DateTime(timezone=True)),
        sa.column("created_by", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    evidence_table = sa.table(
        "service_evidence_sources",
        sa.column("id", sa.String()),
        sa.column("service_profile_id", sa.String()),
        sa.column("source_type", sa.String()),
        sa.column("url", sa.Text()),
        sa.column("title", sa.String()),
        sa.column("publisher", sa.String()),
        sa.column("trust_tier", sa.String()),
        sa.column("retrieval_strategy", sa.String()),
        sa.column("expected_update_frequency_days", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    limit_table = sa.table(
        "service_limits",
        sa.column("id", sa.String()),
        sa.column("service_profile_id", sa.String()),
        sa.column("limit_key", sa.String()),
        sa.column("label", sa.String()),
        sa.column("scope", sa.String()),
        sa.column("limit_type", sa.String()),
        sa.column("value", sa.JSON()),
        sa.column("unit", sa.String()),
        sa.column("default_value", sa.JSON()),
        sa.column("can_request_increase", sa.Boolean()),
        sa.column("source_url", sa.Text()),
        sa.column("source_retrieved_at", sa.DateTime(timezone=True)),
        sa.column("confidence", sa.Float()),
        sa.column("notes", sa.Text()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    policy_table = sa.table(
        "service_commercial_policies",
        sa.column("id", sa.String()),
        sa.column("service_profile_id", sa.String()),
        sa.column("service_id", sa.String()),
        sa.column("classification", sa.String()),
        sa.column("readiness", sa.String()),
        sa.column("publication_policy", sa.String()),
        sa.column("tool_aliases", sa.JSON()),
        sa.column("dependent_service_ids", sa.JSON()),
        sa.column("required_inputs", sa.JSON()),
        sa.column("guidance", sa.Text()),
        sa.column("source_urls", sa.JSON()),
        sa.column("status", sa.String()),
        sa.column("version", sa.String()),
        sa.column("confidence", sa.Float()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    for index, profile in enumerate(PROFILES, start=1):
        service_id = str(profile["service_id"])
        profile_id = profile_ids[service_id]
        if bind.scalar(sa.text("SELECT id FROM service_product_versions WHERE service_profile_id = :id AND version_label = '1.0.0'"), {"id": profile_id}) is None:
            bind.execute(version_table.insert().values(
                id=f"03010000-0000-4000-8000-{index:012d}",
                service_profile_id=profile_id,
                version_label="1.0.0",
                description=profile["architectural_fit"],
                capabilities=profile["limits"],
                use_cases=[profile["architectural_fit"]],
                anti_patterns=[profile["anti_patterns"]],
                regional_availability=None,
                commercial_notes=profile["pricing_model"],
                security_notes=None,
                deprecation_notes=None,
                metadata={"service_id": service_id, "source_profile_version": "1.0.0"},
                effective_from=None,
                created_by="migration",
                created_at=now,
                updated_at=now,
            ))
        source_urls = str(profile["oracle_docs_urls"]).split("|")
        for source_index, source_url in enumerate(source_urls, start=1):
            if bind.scalar(sa.text("SELECT id FROM service_evidence_sources WHERE service_profile_id = :id AND url = :url"), {"id": profile_id, "url": source_url}) is None:
                bind.execute(evidence_table.insert().values(
                    id=f"0302{index:04d}-0000-4000-8000-{source_index:012d}",
                    service_profile_id=profile_id,
                    source_type="official_docs" if "docs.oracle.com" in source_url else "official_pricing",
                    url=source_url,
                    title=f"{profile['name']} {'official documentation' if 'docs.oracle.com' in source_url else 'pricing'}",
                    publisher="Oracle",
                    trust_tier="tier_1_official_docs" if "docs.oracle.com" in source_url else "tier_2_official_commercial",
                    retrieval_strategy="http_fetch",
                    expected_update_frequency_days=90,
                    status="seeded_pending_verification",
                    created_at=now,
                    updated_at=now,
                ))
        for limit_index, (limit_key, value) in enumerate(dict(profile["limits"]).items(), start=1):
            if limit_key == "label":
                continue
            if bind.scalar(sa.text("SELECT id FROM service_limits WHERE service_profile_id = :id AND limit_key = :key"), {"id": profile_id, "key": limit_key}) is None:
                bind.execute(limit_table.insert().values(
                    id=f"0304{index:04d}-0000-4000-8000-{limit_index:012d}",
                    service_profile_id=profile_id,
                    limit_key=limit_key,
                    label=limit_key.replace("_", " ").title(),
                    scope="service",
                    limit_type="operational",
                    value=value,
                    unit=None,
                    default_value=None,
                    can_request_increase=False,
                    source_url=source_urls[0],
                    source_retrieved_at=None,
                    confidence=0.9,
                    notes=None,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ))

    for policy in POLICIES:
        service_id = str(policy["service_id"])
        if bind.scalar(sa.text("SELECT id FROM service_commercial_policies WHERE service_id = :service_id"), {"service_id": service_id}) is None:
            bind.execute(policy_table.insert().values(
                **policy,
                service_profile_id=profile_ids[service_id],
                status="approved",
                version="1.0.0",
                confidence=1.0,
                created_at=now,
                updated_at=now,
            ))

    bind.execute(sa.text(
        "UPDATE service_product_sku_mappings AS mapping "
        "SET service_profile_id = profile.id "
        "FROM service_capability_profiles AS profile "
        "WHERE mapping.service_id = profile.service_id "
        "AND mapping.service_id IN ('EVENTS', 'PROCESS_AUTOMATION')"
    ))
    bind.execute(sa.text(
        "UPDATE service_product_sku_mappings SET selection_policy = 'dependency' "
        "WHERE service_id = 'PROCESS_AUTOMATION'"
    ))

    all_profile_ids = {
        row.service_id: row.id
        for row in bind.execute(sa.text(
            "SELECT id, service_id FROM service_capability_profiles "
            "WHERE service_id IN ('EVENTS', 'FUNCTIONS', 'STREAMING', 'PROCESS_AUTOMATION', 'OIC3')"
        ))
    }
    rule_table = sa.table(
        "service_interoperability_rules",
        sa.column("id", sa.String()),
        sa.column("source_service_profile_id", sa.String()),
        sa.column("target_service_profile_id", sa.String()),
        sa.column("relationship_type", sa.String()),
        sa.column("supported", sa.Boolean()),
        sa.column("directionality", sa.String()),
        sa.column("patterns", sa.JSON()),
        sa.column("required_components", sa.JSON()),
        sa.column("constraints", sa.JSON()),
        sa.column("risk_notes", sa.Text()),
        sa.column("source_url", sa.Text()),
        sa.column("confidence", sa.Float()),
        sa.column("last_verified_at", sa.DateTime(timezone=True)),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    for index, (source_id, target_id, relationship, patterns, components, constraints, risk) in enumerate(INTEROPERABILITY_RULES, start=1):
        bind.execute(rule_table.insert().values(
            id=f"03050000-0000-4000-8000-{index:012d}",
            source_service_profile_id=all_profile_ids[source_id],
            target_service_profile_id=all_profile_ids[target_id],
            relationship_type=relationship,
            supported=True,
            directionality="source_to_target",
            patterns=patterns,
            required_components=components,
            constraints=constraints,
            risk_notes=risk,
            source_url=str(next(item for item in PROFILES if item["service_id"] == source_id)["oracle_docs_urls"]).split("|")[0],
            confidence=0.9,
            last_verified_at=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        ))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE service_product_sku_mappings SET service_profile_id = NULL, selection_policy = 'required' "
        "WHERE service_id IN ('EVENTS', 'PROCESS_AUTOMATION')"
    ))
    bind.execute(sa.text("DELETE FROM service_commercial_policies WHERE id LIKE '03030000-%'"))
    bind.execute(sa.text("DELETE FROM service_interoperability_rules WHERE id LIKE '03050000-%'"))
    bind.execute(sa.text("DELETE FROM service_limits WHERE id LIKE '0304%'"))
    bind.execute(sa.text("DELETE FROM service_evidence_sources WHERE id LIKE '03020000-%'"))
    bind.execute(sa.text("DELETE FROM service_evidence_sources WHERE id LIKE '0302____-%'"))
    bind.execute(sa.text("DELETE FROM service_product_versions WHERE id LIKE '03010000-%'"))
    bind.execute(sa.text("DELETE FROM service_capability_profiles WHERE id LIKE '03000000-%'"))
