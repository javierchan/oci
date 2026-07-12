"""Persisted governed agent runs, steps, approvals, and artifacts."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class AgentRunStatus(str, enum.Enum):
    """Lifecycle states for one governed agent execution."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRun(Base, UUIDMixin, TimestampMixin):
    """One auditable agent execution against a bounded application context."""

    __tablename__ = "agent_runs"

    agent_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    definition_version: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[Optional[str]] = mapped_column(ForeignKey("projects.id"), index=True)
    integration_id: Mapped[Optional[str]] = mapped_column(ForeignKey("catalog_integrations.id"))
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[AgentRunStatus] = mapped_column(
        SAEnum(AgentRunStatus, native_enum=False, values_callable=_enum_values),
        default=AgentRunStatus.PENDING,
        nullable=False,
        index=True,
    )
    context_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    error_details: Mapped[Optional[dict]] = mapped_column(JSON)
    legacy_job_type: Mapped[Optional[str]] = mapped_column(String(48))
    legacy_job_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255))
    provider_response_id: Mapped[Optional[str]] = mapped_column(String(255))
    opc_request_id: Mapped[Optional[str]] = mapped_column(String(255))
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    step_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AgentStep(Base, UUIDMixin, TimestampMixin):
    """One deterministic or OCI-provider step within an agent run."""

    __tablename__ = "agent_steps"

    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_name: Mapped[Optional[str]] = mapped_column(String(96))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    input_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    output_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    error_details: Mapped[Optional[dict]] = mapped_column(JSON)
    opc_request_id: Mapped[Optional[str]] = mapped_column(String(255))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AgentApproval(Base, UUIDMixin, TimestampMixin):
    """Human decision for a proposed agent mutation."""

    __tablename__ = "agent_approvals"

    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    proposed_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36))
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AgentArtifact(Base, UUIDMixin, TimestampMixin):
    """Traceable evidence or generated artifact linked to an agent run."""

    __tablename__ = "agent_artifacts"

    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(48), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    content_hash: Mapped[Optional[str]] = mapped_column(String(128))


class SupportConversation(Base, UUIDMixin, TimestampMixin):
    """One browser-session-isolated support conversation."""

    __tablename__ = "support_conversations"
    __table_args__ = (UniqueConstraint("session_id", "status", name="uq_support_conversation_session_status"),)

    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="App support")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)


class SupportMessage(Base, UUIDMixin, TimestampMixin):
    """One user or assistant turn in a support conversation."""

    __tablename__ = "support_messages"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("support_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed", index=True)
    agent_run_id: Mapped[Optional[str]] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    context_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    citations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class SupportAttachment(Base, UUIDMixin, TimestampMixin):
    """Explicit App component context pinned to a support message."""

    __tablename__ = "support_attachments"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("support_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[str] = mapped_column(
        ForeignKey("support_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attachment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(64))
    href: Mapped[str] = mapped_column(Text, nullable=False)
    context_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
