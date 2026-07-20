"""Regression coverage for authoritative normalized Service Product rules."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.calc_engine import Assumptions
from app.core.config import Settings
from app.models import ServiceCapabilityProfile, ServiceEvidenceSource, ServiceLimit
from app.services.canvas_interoperability import build_design_constraint_messages
from app.services.service_rule_service import apply_service_rules, load_service_rule_bundle


def test_service_limits_are_not_environment_settings() -> None:
    """Keep normalized service limits out of the process configuration contract."""

    deprecated_fields = {
        "OIC_BILLING_THRESHOLD_KB",
        "OIC_PACK_SIZE_MSGS_PER_HOUR",
        "PAYLOAD_MONTH_DAYS",
    }
    assert deprecated_fields.isdisjoint(Settings.model_fields)


@pytest.mark.asyncio
async def test_normalized_limits_override_historical_assumption_values(
    test_engine: AsyncEngine,
) -> None:
    """Runtime calculations and canvas checks must use normalized limits."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        queue = ServiceCapabilityProfile(
            service_id="QUEUE",
            name="OCI Queue",
            category="MESSAGING",
            limits={},
        )
        session.add(queue)
        await session.flush()
        queue_limit = ServiceLimit(
            service_profile_id=queue.id,
            limit_key="max_message_size_kb",
            label="Max message size",
            scope="service",
            limit_type="payload",
            constraint_kind="hard_limit",
            enforcement="block_when_applicable",
            applicability={"service": "QUEUE", "payload_mode": "message"},
            value=256,
            unit="KB",
            confidence=1.0,
        )
        session.add_all(
            [
                queue_limit,
                ServiceEvidenceSource(
                    service_profile_id=queue.id,
                    url="https://docs.oracle.com/queue/limits",
                    title="OCI Queue limits",
                    status="current",
                    last_checked_at=datetime.now(UTC),
                ),
            ]
        )
        await session.commit()

        bundle = await load_service_rule_bundle(session)
        runtime = apply_service_rules(Assumptions(queue_max_message_kb=999), bundle)

        assert bundle.available is True
        assert bundle.freshness_status == "current"
        assert runtime.queue_max_message_kb == 256
        metadata_version = bundle.metadata()["version"]
        assert isinstance(metadata_version, str)
        assert metadata_version.startswith("service-rules-")

        messages = build_design_constraint_messages(
            core_tools="OCI Queue",
            additional_tools_overlays=None,
            assumptions=Assumptions(queue_max_message_kb=999),
            payload_kb=512,
            trigger_type="Event Trigger",
            is_real_time=True,
            source_technology="REST",
            destination_technology="REST",
            integration_type="Event",
            service_rules=bundle,
        )
        assert any("Queue payload exceeds" in message for message in messages)

        first_version = bundle.version
        queue_limit.value = 128
        await session.commit()
        updated_bundle = await load_service_rule_bundle(session)

        assert updated_bundle.numeric_limit("QUEUE", "max_message_size_kb") == 128
        assert updated_bundle.version != first_version
