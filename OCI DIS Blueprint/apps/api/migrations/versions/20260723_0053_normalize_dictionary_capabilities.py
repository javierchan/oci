"""Normalize governed Dictionary capabilities and optional availability semantics."""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20260723_0053"
down_revision = "20260722_0052"
branch_labels = None
depends_on = None


CAPABILITIES = (
    {
        "id": "05300000-0000-4000-8000-000000000001",
        "service_id": "SFTP_TRANSFER",
        "name": "SFTP File Transfer",
        "category": "FILE_TRANSFER_CAPABILITY",
        "pricing_model": "No standalone OCI SFTP SKU; select OIC File Server, OCI Compute, or an external endpoint.",
        "limits": {
            "oic_file_server_storage_gb": 500,
            "oic_file_server_concurrent_connections": 50,
            "oic_integration_file_limit_kb": 1048576,
            "oic_billing_increment_kb": 50,
            "deployment_variant_required": True,
            "label": "documented",
        },
        "architectural_fit": "Governed SFTP file-exchange capability with an explicit deployment variant.",
        "anti_patterns": "Do not treat SFTP as a standalone OCI SKU or silently map it to Object Storage.",
        "interoperability_notes": "Select OIC File Server, customer-managed SFTP on OCI Compute, or external SFTP.",
        "oracle_docs_urls": "https://docs.oracle.com/en/cloud/paas/application-integration/int-get-started/file-server.html|https://docs.oracle.com/en/cloud/paas/application-integration/file-server/file-server-faq.html|https://docs.oracle.com/en-us/iaas/integration/doc/monitoring-billable-messages.html",
        "policy": {
            "classification": "dependent_entitlement",
            "readiness": "input_required",
            "publication_policy": "dependencies_required",
            "tool_aliases": ["SFTP File Transfer", "SFTP"],
            "dependent_service_ids": ["OIC3"],
            "required_inputs": [
                "Deployment variant: OIC File Server, OCI Compute, or external endpoint",
                "For OIC File Server: OIC edition and message demand",
                "For OCI Compute: shape, runtime, storage, network, operations, and optional HA/DR",
            ],
            "guidance": "Keep the capability visible, then price only the explicitly selected deployment variant.",
            "source_urls": [
                "https://docs.oracle.com/en/cloud/paas/application-integration/int-get-started/file-server.html",
                "https://docs.oracle.com/en/cloud/paas/application-integration/file-server/file-server-faq.html",
            ],
        },
    },
    {
        "id": "05300000-0000-4000-8000-000000000002",
        "service_id": "OKE",
        "name": "OCI Kubernetes Engine (OKE)",
        "category": "CONTAINER_PLATFORM",
        "pricing_model": "Exact OKE option plus node, storage, network, and observability SKUs.",
        "limits": {
            "exact_node_shape_required": True,
            "runtime_hours_required": True,
            "ha_optional": True,
            "service_mesh_status": "OCI Service Mesh retired May 31, 2025; use Istio when required",
            "label": "documented",
        },
        "architectural_fit": "Managed Kubernetes platform for containerized integration workloads.",
        "anti_patterns": "Do not force HA or DR and do not select the retired OCI Service Mesh service.",
        "interoperability_notes": "Price every selected OKE dependency using its own governed meter.",
        "oracle_docs_urls": "https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm|https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengservice-mesh-intro-topic.htm",
        "policy": {
            "classification": "dependent_cost",
            "readiness": "input_required",
            "publication_policy": "dependencies_required",
            "tool_aliases": ["OCI Kubernetes Engine (OKE)", "OKE / Service Mesh", "OKE"],
            "dependent_service_ids": [],
            "required_inputs": [
                "OKE control-plane option and region",
                "Node shapes, quantities, and runtime",
                "Storage and network demand",
                "Optional HA multiplier and DR role",
            ],
            "guidance": "Quote the exact platform composition; 1× means standard capacity without additional HA.",
            "source_urls": [
                "https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm",
                "https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengservice-mesh-intro-topic.htm",
            ],
        },
    },
    {
        "id": "05300000-0000-4000-8000-000000000003",
        "service_id": "AI_SERVICES",
        "name": "OCI AI Services",
        "category": "AI_PRODUCT_FAMILY",
        "pricing_model": "Select the exact OCI AI product, model or capability, region, and billing metric.",
        "limits": {
            "exact_service_required": True,
            "model_or_capability_required": True,
            "region_required": True,
            "billing_metric_required": True,
            "label": "documented",
        },
        "architectural_fit": "Governed AI enrichment or inference capability attached to an integration route.",
        "anti_patterns": "Do not publish a generic OCI AI Services BOM line.",
        "interoperability_notes": "Price integration transport and the selected AI product independently.",
        "oracle_docs_urls": "https://docs.oracle.com/en-us/iaas/Content/ai-services.htm|https://www.oracle.com/artificial-intelligence/pricing/",
        "policy": {
            "classification": "dependent_cost",
            "readiness": "input_required",
            "publication_policy": "dependencies_required",
            "tool_aliases": ["OCI AI Services"],
            "dependent_service_ids": [],
            "required_inputs": [
                "Exact OCI AI service",
                "Model or capability",
                "Region and capacity mode",
                "Billing metric and demand",
            ],
            "guidance": "Resolve the family label to an approved commercial product before publication.",
            "source_urls": [
                "https://docs.oracle.com/en-us/iaas/Content/ai-services.htm",
                "https://www.oracle.com/artificial-intelligence/pricing/",
            ],
        },
    },
)


def _upsert_dictionary(
    bind: sa.Connection,
    *,
    code: str,
    value: str,
    description: str,
    sort_order: int,
) -> None:
    existing_id = bind.scalar(
        sa.text("SELECT id FROM dictionary_options WHERE category='OVERLAYS' AND code=:code"),
        {"code": code},
    )
    values = {
        "code": code,
        "value": value,
        "description": description,
        "sort_order": sort_order,
        "version": "1.0.0",
    }
    if existing_id is None:
        bind.execute(
            sa.text(
                "INSERT INTO dictionary_options "
                "(id, category, code, value, description, executions_per_day, is_volumetric, "
                "sort_order, is_active, version, created_at, updated_at) "
                "VALUES (:id, 'OVERLAYS', :code, :value, :description, NULL, false, "
                ":sort_order, true, :version, :now, :now)"
            ),
            {**values, "id": f"05310000-0000-4000-8000-{sort_order:012d}", "now": datetime.now(UTC)},
        )
    else:
        bind.execute(
            sa.text(
                "UPDATE dictionary_options SET value=:value, description=:description, "
                "sort_order=:sort_order, is_active=true, version=:version, updated_at=:now "
                "WHERE id=:id"
            ),
            {**values, "id": existing_id, "now": datetime.now(UTC)},
        )


def _limit_semantics(service_id: str, key: str) -> tuple[str, str, str | None]:
    """Return deterministic governance semantics for normalized capability limits."""

    if key == "oic_billing_increment_kb":
        return "billing_granularity", "calculate", "KB"
    if key in {
        "oic_file_server_storage_gb",
        "oic_file_server_concurrent_connections",
        "oic_integration_file_limit_kb",
    }:
        units = {
            "oic_file_server_storage_gb": "GB",
            "oic_file_server_concurrent_connections": "connections",
            "oic_integration_file_limit_kb": "KB",
        }
        return "hard_limit", "block_when_applicable", units[key]
    if key.endswith("_required"):
        return "required_configuration", "block", None
    if service_id == "OKE" and key == "service_mesh_status":
        return "product_lifecycle", "inform", None
    return "informational", "inform", None


def _upsert_normalized_artifacts(
    bind: sa.Connection,
    *,
    capability: dict[str, object],
    profile_id: str,
    index: int,
    now: datetime,
) -> None:
    """Persist versioned metadata, limits, and official evidence with the profile."""

    service_id = str(capability["service_id"])
    version_exists = bind.scalar(
        sa.text(
            "SELECT id FROM service_product_versions "
            "WHERE service_profile_id=:profile_id AND version_label='1.0.0'"
        ),
        {"profile_id": profile_id},
    )
    if version_exists is None:
        bind.execute(
            sa.text(
                "INSERT INTO service_product_versions "
                "(id, service_profile_id, version_label, description, capabilities, use_cases, "
                "anti_patterns, regional_availability, commercial_notes, security_notes, "
                "deprecation_notes, metadata, effective_from, created_by, created_at, updated_at) "
                "VALUES (:id, :profile_id, '1.0.0', :description, :capabilities, :use_cases, "
                ":anti_patterns, NULL, :commercial_notes, NULL, :deprecation_notes, :metadata, "
                "NULL, 'migration', :now, :now)"
            ).bindparams(
                sa.bindparam("capabilities", type_=sa.JSON()),
                sa.bindparam("use_cases", type_=sa.JSON()),
                sa.bindparam("anti_patterns", type_=sa.JSON()),
                sa.bindparam("metadata", type_=sa.JSON()),
            ),
            {
                "id": f"05330000-0000-4000-8000-{index:012d}",
                "profile_id": profile_id,
                "description": capability["architectural_fit"],
                "capabilities": capability["limits"],
                "use_cases": [capability["architectural_fit"]],
                "anti_patterns": [capability["anti_patterns"]],
                "commercial_notes": capability["pricing_model"],
                "deprecation_notes": (
                    "OCI Service Mesh retired May 31, 2025; use Istio only when required."
                    if service_id == "OKE"
                    else None
                ),
                "metadata": {"service_id": service_id, "source_profile_version": "1.0.0"},
                "now": now,
            },
        )

    source_urls = str(capability["oracle_docs_urls"]).split("|")
    for source_index, source_url in enumerate(source_urls, start=1):
        source_exists = bind.scalar(
            sa.text(
                "SELECT id FROM service_evidence_sources "
                "WHERE service_profile_id=:profile_id AND url=:url"
            ),
            {"profile_id": profile_id, "url": source_url},
        )
        if source_exists is not None:
            continue
        is_docs = "docs.oracle.com" in source_url
        bind.execute(
            sa.text(
                "INSERT INTO service_evidence_sources "
                "(id, service_profile_id, source_type, url, title, publisher, trust_tier, "
                "retrieval_strategy, expected_update_frequency_days, last_checked_at, "
                "last_changed_at, content_hash, status, created_at, updated_at) "
                "VALUES (:id, :profile_id, :source_type, :url, :title, 'Oracle', :trust_tier, "
                "'http_fetch', 90, NULL, NULL, NULL, 'seeded_pending_verification', :now, :now)"
            ),
            {
                "id": f"0534{index:04d}-0000-4000-8000-{source_index:012d}",
                "profile_id": profile_id,
                "source_type": "official_docs" if is_docs else "official_pricing",
                "url": source_url,
                "title": f"{capability['name']} official {'documentation' if is_docs else 'pricing'}",
                "trust_tier": "tier_1_official_docs" if is_docs else "tier_2_official_commercial",
                "now": now,
            },
        )

    for limit_index, (key, value) in enumerate(dict(capability["limits"]).items(), start=1):
        if key == "label":
            continue
        limit_exists = bind.scalar(
            sa.text(
                "SELECT id FROM service_limits "
                "WHERE service_profile_id=:profile_id AND limit_key=:limit_key"
            ),
            {"profile_id": profile_id, "limit_key": key},
        )
        if limit_exists is not None:
            continue
        constraint_kind, enforcement, unit = _limit_semantics(service_id, key)
        bind.execute(
            sa.text(
                "INSERT INTO service_limits "
                "(id, service_profile_id, limit_key, label, scope, limit_type, constraint_kind, "
                "enforcement, applicability, value, unit, default_value, can_request_increase, "
                "source_url, source_retrieved_at, confidence, notes, is_active, created_at, updated_at) "
                "VALUES (:id, :profile_id, :limit_key, :label, 'service', 'operational', "
                ":constraint_kind, :enforcement, :applicability, :value, :unit, NULL, false, "
                ":source_url, NULL, 0.9, NULL, true, :now, :now)"
            ).bindparams(
                sa.bindparam("applicability", type_=sa.JSON()),
                sa.bindparam("value", type_=sa.JSON()),
            ),
            {
                "id": f"0535{index:04d}-0000-4000-8000-{limit_index:012d}",
                "profile_id": profile_id,
                "limit_key": key,
                "label": key.replace("_", " ").title(),
                "constraint_kind": constraint_kind,
                "enforcement": enforcement,
                "applicability": {"component": service_id.casefold()},
                "value": value,
                "unit": unit,
                "source_url": source_urls[0],
                "now": now,
            },
        )


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)

    bind.execute(
        sa.text(
            "DELETE FROM dictionary_options WHERE category='TOOLS' AND value='SFTP' "
            "AND is_active=false AND code IS NULL"
        )
    )
    _upsert_dictionary(
        bind,
        code="AO08",
        value="OCI AI Services",
        description=(
            "Type: Governed product-family overlay. Capture the exact OCI AI service, "
            "model, region, and billing metric before quoting."
        ),
        sort_order=8,
    )
    _upsert_dictionary(
        bind,
        code="AO09",
        value="OCI Kubernetes Engine (OKE)",
        description=(
            "Type: Governed platform overlay. Select node shapes, runtime, storage, and optional "
            "HA/DR explicitly; OCI Service Mesh is retired and Istio is used when mesh behavior is required."
        ),
        sort_order=9,
    )
    _upsert_dictionary(
        bind,
        code="AO10",
        value="SFTP File Transfer",
        description=(
            "Type: Governed transfer capability. Select Oracle Integration File Server, "
            "customer-managed SFTP on OCI Compute, or an external SFTP endpoint."
        ),
        sort_order=10,
    )

    for capability_index, capability in enumerate(CAPABILITIES, start=1):
        service_id = capability["service_id"]
        profile_id = bind.scalar(
            sa.text("SELECT id FROM service_capability_profiles WHERE service_id=:service_id"),
            {"service_id": service_id},
        )
        profile_values = {
            key: capability[key]
            for key in (
                "service_id",
                "name",
                "category",
                "pricing_model",
                "limits",
                "architectural_fit",
                "anti_patterns",
                "interoperability_notes",
                "oracle_docs_urls",
            )
        }
        if profile_id is None:
            profile_id = capability["id"]
            bind.execute(
                sa.text(
                    "INSERT INTO service_capability_profiles "
                    "(id, service_id, name, category, sla_uptime_pct, pricing_model, limits, "
                    "architectural_fit, anti_patterns, interoperability_notes, oracle_docs_urls, "
                    "is_active, version, created_at, updated_at) "
                    "VALUES (:id, :service_id, :name, :category, NULL, :pricing_model, :limits, "
                    ":architectural_fit, :anti_patterns, :interoperability_notes, :oracle_docs_urls, "
                    "true, '1.0.0', :now, :now)"
                ).bindparams(sa.bindparam("limits", type_=sa.JSON())),
                {**profile_values, "id": profile_id, "now": now},
            )
        else:
            bind.execute(
                sa.text(
                    "UPDATE service_capability_profiles SET name=:name, category=:category, "
                    "pricing_model=:pricing_model, limits=:limits, architectural_fit=:architectural_fit, "
                    "anti_patterns=:anti_patterns, interoperability_notes=:interoperability_notes, "
                    "oracle_docs_urls=:oracle_docs_urls, is_active=true, version='1.0.0', updated_at=:now "
                    "WHERE id=:id"
                ).bindparams(sa.bindparam("limits", type_=sa.JSON())),
                {**profile_values, "id": profile_id, "now": now},
            )

        policy = capability["policy"]
        policy_id = bind.scalar(
            sa.text("SELECT id FROM service_commercial_policies WHERE service_id=:service_id"),
            {"service_id": service_id},
        )
        policy_values = {
            **policy,
            "service_profile_id": profile_id,
            "service_id": service_id,
            "now": now,
        }
        json_keys = (
            "tool_aliases",
            "dependent_service_ids",
            "required_inputs",
            "source_urls",
        )
        if policy_id is None:
            bind.execute(
                sa.text(
                    "INSERT INTO service_commercial_policies "
                    "(id, service_profile_id, service_id, classification, readiness, publication_policy, "
                    "tool_aliases, dependent_service_ids, required_inputs, guidance, source_urls, "
                    "status, version, confidence, created_at, updated_at) "
                    "VALUES (:id, :service_profile_id, :service_id, :classification, :readiness, "
                    ":publication_policy, :tool_aliases, :dependent_service_ids, :required_inputs, "
                    ":guidance, :source_urls, 'approved', '1.0.0', 1.0, :now, :now)"
                ).bindparams(*(sa.bindparam(key, type_=sa.JSON()) for key in json_keys)),
                {**policy_values, "id": f"05320000-0000-4000-8000-{capability_index:012d}"},
            )
        else:
            bind.execute(
                sa.text(
                    "UPDATE service_commercial_policies SET service_profile_id=:service_profile_id, "
                    "classification=:classification, readiness=:readiness, publication_policy=:publication_policy, "
                    "tool_aliases=:tool_aliases, dependent_service_ids=:dependent_service_ids, "
                    "required_inputs=:required_inputs, guidance=:guidance, source_urls=:source_urls, "
                    "status='approved', version='1.0.0', confidence=1.0, updated_at=:now WHERE id=:id"
                ).bindparams(*(sa.bindparam(key, type_=sa.JSON()) for key in json_keys)),
                {**policy_values, "id": policy_id},
            )
        _upsert_normalized_artifacts(
            bind,
            capability=capability,
            profile_id=profile_id,
            index=capability_index,
            now=now,
        )


def downgrade() -> None:
    bind = op.get_bind()
    service_ids = [item["service_id"] for item in CAPABILITIES]
    profile_ids = [
        row.id
        for row in bind.execute(
            sa.text(
                "SELECT id FROM service_capability_profiles WHERE service_id IN :service_ids"
            ).bindparams(sa.bindparam("service_ids", expanding=True)),
            {"service_ids": service_ids},
        )
    ]
    if profile_ids:
        for table_name in (
            "service_limits",
            "service_evidence_sources",
            "service_product_versions",
        ):
            bind.execute(
                sa.text(
                    f"DELETE FROM {table_name} WHERE service_profile_id IN :profile_ids"
                ).bindparams(sa.bindparam("profile_ids", expanding=True)),
                {"profile_ids": profile_ids},
            )
    bind.execute(
        sa.text("DELETE FROM service_commercial_policies WHERE service_id IN :service_ids")
        .bindparams(sa.bindparam("service_ids", expanding=True)),
        {"service_ids": service_ids},
    )
    bind.execute(
        sa.text("DELETE FROM service_capability_profiles WHERE service_id IN :service_ids")
        .bindparams(sa.bindparam("service_ids", expanding=True)),
        {"service_ids": service_ids},
    )
    bind.execute(sa.text("DELETE FROM dictionary_options WHERE category='OVERLAYS' AND code='AO10'"))
    bind.execute(
        sa.text(
            "UPDATE dictionary_options SET value='OKE / Service Mesh', "
            "description='Type: External-capacity overlay. Typical use: mTLS, mesh traffic policy, "
            "and platform-owned service routing; size OKE separately.' WHERE category='OVERLAYS' AND code='AO09'"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE dictionary_options SET description='Type: External-capacity overlay. Typical use: "
            "governed inference or model-assisted enrichment; size the selected AI service separately.' "
            "WHERE category='OVERLAYS' AND code='AO08'"
        )
    )
    if bind.scalar(
        sa.text(
            "SELECT id FROM dictionary_options "
            "WHERE category='TOOLS' AND value='SFTP' AND code IS NULL"
        )
    ) is None:
        now = datetime.now(UTC)
        bind.execute(
            sa.text(
                "INSERT INTO dictionary_options "
                "(id, category, code, value, description, executions_per_day, is_volumetric, "
                "sort_order, is_active, version, created_at, updated_at) "
                "VALUES ('05390000-0000-4000-8000-000000000001', 'TOOLS', NULL, 'SFTP', "
                "NULL, NULL, false, 999, false, '1.0.0', :now, :now)"
            ),
            {"now": now},
        )
