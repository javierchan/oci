"""API coverage for governed Service Product Library endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.migrations.seed import SERVICE_INTEROPERABILITY_RULES, SERVICE_PROFILES
from app.models import (
    ServiceCapabilityProfile,
    ServiceEvidenceSource,
    ServiceVerificationFinding,
    ServiceInteroperabilityRule,
    ServiceLimit,
    ServiceProductVersion,
    ServiceVerificationJob,
)
from app.routers import service_products as service_products_router
from app.schemas.service_products import ServiceVerificationRunRequest
from app.services import service_product_service


def test_seed_service_products_cover_oracle_data_integration_portfolio() -> None:
    """Protect the governed Oracle Data Integration product portfolio seed."""

    service_ids = {str(profile["service_id"]) for profile in SERVICE_PROFILES}
    expected_products = {
        "DATA_INTEGRATION",
        "DATA_FLOW",
        "DATA_CATALOG",
        "GOLDENGATE",
        "GOLDENGATE_DATA_TRANSFORMS",
        "ODI",
        "STREAM_ANALYTICS",
        "ENTERPRISE_DATA_QUALITY",
    }
    assert expected_products.issubset(service_ids)

    rules = {
        (str(rule["source_service_id"]), str(rule["target_service_id"]), str(rule["relationship_type"]))
        for rule in SERVICE_INTEROPERABILITY_RULES
    }
    expected_rules = {
        ("DATA_INTEGRATION", "DATA_FLOW", "spark_task_execution"),
        ("DATA_INTEGRATION", "DATA_CATALOG", "lineage_metadata_publication"),
        ("GOLDENGATE", "GOLDENGATE_DATA_TRANSFORMS", "replication_transform_pair"),
        ("GOLDENGATE", "STREAM_ANALYTICS", "cdc_stream_analytics"),
        ("ENTERPRISE_DATA_QUALITY", "ODI", "quality_gate"),
    }
    assert expected_rules.issubset(rules)


@pytest.mark.asyncio
async def test_legacy_services_api_is_not_mounted(api_client: AsyncClient) -> None:
    """Protect the production API from the retired raw service-profile surface."""

    list_response = await api_client.get("/api/v1/services/")
    assert list_response.status_code == 404

    detail_response = await api_client.get("/api/v1/services/OIC3")
    assert detail_response.status_code == 404


@pytest.mark.asyncio
async def test_service_product_library_endpoints_return_normalized_governance(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        oic = ServiceCapabilityProfile(
            service_id="OIC3",
            name="Oracle Integration 3 (OIC Gen3)",
            category="ORCHESTRATION",
            sla_uptime_pct=99.9,
            pricing_model="Message pack",
            limits={"max_message_size_kb": 10240},
            architectural_fit="Adapter-heavy orchestration",
            anti_patterns="Avoid high-rate event streams",
            interoperability_notes="Integrates with OCI Streaming",
            oracle_docs_urls="https://docs.oracle.com/example",
        )
        streaming = ServiceCapabilityProfile(
            service_id="STREAMING",
            name="OCI Streaming",
            category="EVENT_BACKBONE",
            sla_uptime_pct=99.9,
            pricing_model="GB transferred",
            limits={"max_message_size_kb": 1024},
            architectural_fit="Event backbone",
            anti_patterns="Avoid work queue semantics",
            interoperability_notes="Kafka-compatible API",
            oracle_docs_urls="https://docs.oracle.com/streaming",
        )
        session.add_all([oic, streaming])
        await session.flush()
        session.add_all(
            [
                ServiceProductVersion(
                    service_profile_id=oic.id,
                    version_label="1.0.0",
                    description="Versioned OIC product evidence.",
                    capabilities={"adapter_catalog": 133},
                    use_cases=["Application integration"],
                    anti_patterns=["High-rate stream backbone"],
                    commercial_notes="Message pack",
                    product_metadata={"service_id": "OIC3"},
                    created_by="test",
                ),
                ServiceLimit(
                    service_profile_id=oic.id,
                    limit_key="max_message_size_kb",
                    label="Max Message Size",
                    scope="service",
                    limit_type="payload",
                    value=10240,
                    unit="KB",
                    can_request_increase=False,
                    source_url="https://docs.oracle.com/example",
                    confidence=0.9,
                ),
                ServiceEvidenceSource(
                    service_profile_id=oic.id,
                    source_type="official_docs",
                    url="https://docs.oracle.com/example",
                    title="OIC limits",
                    publisher="Oracle",
                    trust_tier="tier_1_official_docs",
                    retrieval_strategy="http_fetch",
                    expected_update_frequency_days=90,
                    status="seeded_pending_verification",
                ),
                ServiceInteroperabilityRule(
                    source_service_profile_id=oic.id,
                    target_service_profile_id=streaming.id,
                    relationship_type="kafka_adapter",
                    supported=True,
                    directionality="source_to_target",
                    patterns=["#02"],
                    required_components=["OIC Kafka adapter"],
                    constraints={"message_size": "1 MB stream record"},
                    risk_notes="Consumers must be idempotent.",
                    source_url="https://docs.oracle.com/example",
                    confidence=0.85,
                ),
                ServiceVerificationJob(
                    requested_by="analyst",
                    scope="OIC3",
                    status="pending",
                    services_checked=["OIC3"],
                    sources_checked=0,
                    changes_detected=0,
                    findings=[],
                    recommendations=[],
                ),
            ]
        )
        await session.commit()

    products_response = await api_client.get("/api/v1/service-products")
    assert products_response.status_code == 200
    products_payload = products_response.json()
    assert products_payload["total"] == 2
    oic_summary = next(item for item in products_payload["products"] if item["service_id"] == "OIC3")
    assert oic_summary["limits_count"] == 1
    assert oic_summary["evidence_count"] == 1
    assert oic_summary["verification_status"] == "pending_verification"

    detail_response = await api_client.get("/api/v1/service-products/OIC3")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["current_version"]["version_label"] == "1.0.0"
    assert detail_payload["limits"][0]["limit_key"] == "max_message_size_kb"
    assert detail_payload["evidence_sources"][0]["trust_tier"] == "tier_1_official_docs"
    assert detail_payload["interoperability_rules"][0]["target_service_id"] == "STREAMING"

    limits_response = await api_client.get("/api/v1/service-products/OIC3/limits")
    assert limits_response.status_code == 200
    assert limits_response.json()[0]["unit"] == "KB"

    matrix_response = await api_client.get("/api/v1/service-products/matrix")
    assert matrix_response.status_code == 200
    matrix_payload = matrix_response.json()
    assert matrix_payload["total_rules"] == 1
    assert matrix_payload["rules"][0]["relationship_type"] == "kafka_adapter"

    jobs_response = await api_client.get("/api/v1/service-products/verification-jobs")
    assert jobs_response.status_code == 200
    assert jobs_response.json()["jobs"][0]["scope"] == "OIC3"


@pytest.mark.asyncio
async def test_service_verification_agent_detects_changed_source_and_reviews_finding(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        oic = ServiceCapabilityProfile(
            service_id="OIC3",
            name="Oracle Integration 3 (OIC Gen3)",
            category="ORCHESTRATION",
            sla_uptime_pct=99.9,
            pricing_model="Message pack",
            limits={"max_message_size_kb": 10240},
            architectural_fit="Adapter-heavy orchestration",
            anti_patterns="Avoid high-rate event streams",
            interoperability_notes="Integrates with OCI Streaming",
            oracle_docs_urls="https://docs.oracle.com/example",
        )
        session.add(oic)
        await session.flush()
        session.add(
            ServiceEvidenceSource(
                service_profile_id=oic.id,
                source_type="official_docs",
                url="https://docs.oracle.com/example",
                title="OIC limits",
                publisher="Oracle",
                trust_tier="tier_1_official_docs",
                retrieval_strategy="http_fetch",
                expected_update_frequency_days=90,
                content_hash="old-hash",
                status="verified",
            )
        )
        await session.commit()

    async def fake_fetch_evidence_text(url: str) -> tuple[int, str]:
        assert url == "https://docs.oracle.com/example"
        return 200, "<html><main>Updated Oracle Integration service limit evidence.</main></html>"

    monkeypatch.setattr(service_product_service, "_fetch_evidence_text", fake_fetch_evidence_text)

    async with session_factory() as session:
        async with session.begin():
            created_job = await service_product_service.create_verification_job(
                ServiceVerificationRunRequest(service_ids=["OIC3"], max_sources=1, force=True),
                "architect",
                session,
            )
        async with session.begin():
            completed_job = await service_product_service.run_verification_job(created_job.id, session)
    job_payload = completed_job.model_dump(mode="json")

    assert job_payload["status"] == "completed"
    assert job_payload["sources_checked"] == 1
    assert job_payload["changes_detected"] == 1
    assert len(job_payload["findings"]) == 1
    assert job_payload["findings"][0]["finding_type"] == "source_content_changed"

    findings_response = await api_client.get(f"/api/v1/service-products/verification-jobs/{job_payload['id']}/findings")
    assert findings_response.status_code == 200
    findings_payload = findings_response.json()
    assert len(findings_payload) == 1
    finding_id = findings_payload[0]["id"]
    assert findings_payload[0]["review_status"] == "open"

    review_response = await api_client.post(
        f"/api/v1/service-products/verification-jobs/{job_payload['id']}/findings/{finding_id}/review",
        headers={"X-Actor-Id": "architect", "X-Actor-Role": "Admin"},
        json={"review_status": "dismissed", "note": "Hash-only change; no rule update needed."},
    )
    assert review_response.status_code == 200
    review_payload = review_response.json()
    assert review_payload["review_status"] == "dismissed"
    assert review_payload["reviewed_by"] == "architect"


@pytest.mark.asyncio
async def test_service_verification_job_dispatches_async_worker(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        oic = ServiceCapabilityProfile(
            service_id="OIC3",
            name="Oracle Integration 3 (OIC Gen3)",
            category="ORCHESTRATION",
            sla_uptime_pct=99.9,
            pricing_model="Message pack",
            limits={"max_message_size_kb": 10240},
            architectural_fit="Adapter-heavy orchestration",
            anti_patterns="Avoid high-rate event streams",
            interoperability_notes="Integrates with OCI Streaming",
            oracle_docs_urls="https://docs.oracle.com/example",
        )
        session.add(oic)
        await session.flush()
        session.add(
            ServiceEvidenceSource(
                service_profile_id=oic.id,
                source_type="official_docs",
                url="https://docs.oracle.com/example",
                title="OIC limits",
                publisher="Oracle",
                trust_tier="tier_1_official_docs",
                retrieval_strategy="http_fetch",
                expected_update_frequency_days=90,
                status="seeded_pending_verification",
            )
        )
        await session.commit()

    dispatched: dict[str, object] = {}

    def fake_apply_async(*, args: list[str], task_id: str) -> None:
        dispatched["args"] = args
        dispatched["task_id"] = task_id

    monkeypatch.setattr(service_products_router.execute_service_verification_job_task, "apply_async", fake_apply_async)

    run_response = await api_client.post(
        "/api/v1/service-products/verification-jobs",
        headers={"X-Actor-Id": "architect", "X-Actor-Role": "Admin"},
        json={"service_ids": ["OIC3"], "max_sources": 1, "force": True},
    )

    assert run_response.status_code == 202
    job_payload = run_response.json()
    assert job_payload["status"] == "pending"
    assert job_payload["request_payload"] == {"service_ids": ["OIC3"], "max_sources": 1, "force": True}
    assert dispatched["args"] == [job_payload["id"]]
    assert dispatched["task_id"] == job_payload["id"]


@pytest.mark.asyncio
async def test_service_verification_job_rejects_legacy_sync_mode(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/service-products/verification-jobs",
        headers={"X-Actor-Id": "architect", "X-Actor-Role": "Admin"},
        json={"execution_mode": "sync"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_service_verification_agent_applies_accepted_limit_claim(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        oic = ServiceCapabilityProfile(
            service_id="OIC3",
            name="Oracle Integration 3 (OIC Gen3)",
            category="ORCHESTRATION",
            sla_uptime_pct=99.9,
            pricing_model="Message pack",
            limits={"max_message_size_kb": 10240},
            architectural_fit="Adapter-heavy orchestration",
            anti_patterns="Avoid high-rate event streams",
            interoperability_notes="Integrates with OCI Streaming",
            oracle_docs_urls="https://docs.oracle.com/example",
        )
        session.add(oic)
        await session.flush()
        session.add_all(
            [
                ServiceLimit(
                    service_profile_id=oic.id,
                    limit_key="max_message_size_kb",
                    label="Max Message Size",
                    scope="service",
                    limit_type="payload",
                    value=10240,
                    unit="KB",
                    can_request_increase=False,
                    source_url="https://docs.oracle.com/example",
                    confidence=0.9,
                ),
                ServiceEvidenceSource(
                    service_profile_id=oic.id,
                    source_type="official_docs",
                    url="https://docs.oracle.com/example",
                    title="OIC limits",
                    publisher="Oracle",
                    trust_tier="tier_1_official_docs",
                    retrieval_strategy="http_fetch",
                    expected_update_frequency_days=90,
                    content_hash="old-hash",
                    status="verified",
                ),
            ]
        )
        await session.commit()

    async def fake_fetch_evidence_text(url: str) -> tuple[int, str]:
        assert url == "https://docs.oracle.com/example"
        return 200, "<html><main>Oracle Integration Max Message Size: 20 MB.</main></html>"

    monkeypatch.setattr(service_product_service, "_fetch_evidence_text", fake_fetch_evidence_text)

    async with session_factory() as session:
        async with session.begin():
            created_job = await service_product_service.create_verification_job(
                ServiceVerificationRunRequest(service_ids=["OIC3"], max_sources=1, force=True),
                "architect",
                session,
            )
        async with session.begin():
            completed_job = await service_product_service.run_verification_job(created_job.id, session)
    job_payload = completed_job.model_dump(mode="json")

    findings_response = await api_client.get(f"/api/v1/service-products/verification-jobs/{job_payload['id']}/findings")
    assert findings_response.status_code == 200
    findings_payload = findings_response.json()
    limit_finding = next(item for item in findings_payload if item["finding_type"] == "changed_limit")

    review_response = await api_client.post(
        f"/api/v1/service-products/verification-jobs/{job_payload['id']}/findings/{limit_finding['id']}/review",
        headers={"X-Actor-Id": "architect", "X-Actor-Role": "Admin"},
        json={"review_status": "accepted", "note": "Matches official source."},
    )
    assert review_response.status_code == 200
    assert review_response.json()["review_status"] == "accepted"

    limits_response = await api_client.get("/api/v1/service-products/OIC3/limits")
    assert limits_response.status_code == 200
    limits_payload = limits_response.json()
    updated_limit = next(item for item in limits_payload if item["limit_key"] == "max_message_size_kb")
    assert updated_limit["value"] == 20480
    assert updated_limit["unit"] == "KB"


@pytest.mark.asyncio
async def test_service_verification_alerts_return_stale_sources_and_open_findings(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        oic = ServiceCapabilityProfile(
            service_id="OIC3",
            name="Oracle Integration 3 (OIC Gen3)",
            category="ORCHESTRATION",
            sla_uptime_pct=99.9,
            pricing_model="Message pack",
            limits={"max_message_size_kb": 10240},
            architectural_fit="Adapter-heavy orchestration",
            anti_patterns="Avoid high-rate event streams",
            interoperability_notes="Integrates with OCI Streaming",
            oracle_docs_urls="https://docs.oracle.com/example",
        )
        session.add(oic)
        await session.flush()
        job = ServiceVerificationJob(
            requested_by="architect",
            scope="OIC3",
            request_payload={"service_ids": ["OIC3"], "max_sources": 1, "force": True},
            status="completed",
            services_checked=["OIC3"],
            sources_checked=1,
            changes_detected=1,
            findings=[],
            recommendations=[],
        )
        session.add(job)
        await session.flush()
        session.add_all(
            [
                ServiceEvidenceSource(
                    service_profile_id=oic.id,
                    source_type="official_docs",
                    url="https://docs.oracle.com/example",
                    title="OIC limits",
                    publisher="Oracle",
                    trust_tier="tier_1_official_docs",
                    retrieval_strategy="http_fetch",
                    expected_update_frequency_days=90,
                    status="seeded_pending_verification",
                ),
                ServiceVerificationFinding(
                    job_id=job.id,
                    service_profile_id=oic.id,
                    finding_type="changed_limit",
                    severity="high",
                    title="Potential service limit change",
                    summary="A governed limit may have changed.",
                    old_value={"value": 10240},
                    new_value={"value": 20480},
                    source_url="https://docs.oracle.com/example",
                    recommended_action="Review and accept if correct.",
                    review_status="open",
                ),
            ]
        )
        await session.commit()

    response = await api_client.get("/api/v1/service-products/verification-alerts")
    assert response.status_code == 200
    payload = response.json()
    assert payload["open_findings_count"] == 1
    assert payload["stale_evidence_count"] == 1
    assert {alert["alert_type"] for alert in payload["alerts"]} >= {"changed_limit", "stale_evidence"}
