"""Provider-neutral users, credentials, sessions, API tokens, and project access."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class AppUser(Base, UUIDMixin, TimestampMixin):
    """One human identity shared by local auth and future OCI IAM identities."""

    __tablename__ = "app_users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="Viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_authenticated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AuthIdentity(Base, UUIDMixin, TimestampMixin):
    """A provider subject linked to one App user."""

    __tablename__ = "auth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_auth_identity_provider_subject"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_authenticated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class LocalCredential(Base, TimestampMixin):
    """Argon2id verifier for a local identity; plaintext is never persisted."""

    __tablename__ = "local_credentials"

    identity_id: Mapped[str] = mapped_column(
        ForeignKey("auth_identities.id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuthSession(Base, UUIDMixin, TimestampMixin):
    """Revocable browser session identified only by a SHA-256 token digest."""

    __tablename__ = "auth_sessions"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identity_id: Mapped[str] = mapped_column(
        ForeignKey("auth_identities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)


class ApiToken(Base, UUIDMixin, TimestampMixin):
    """Read-only external API credential, stored as a digest and shown once."""

    __tablename__ = "api_tokens"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=lambda: ["api:read"])
    allowed_project_ids: Mapped[Optional[list]] = mapped_column(JSON)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)


class ProjectMembership(Base, UUIDMixin, TimestampMixin):
    """Explicit user access to one project; global roles never bypass membership."""

    __tablename__ = "project_memberships"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_membership_project_user"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_role: Mapped[str] = mapped_column(String(32), nullable=False, default="Viewer")
    granted_by: Mapped[str] = mapped_column(String(36), nullable=False)
