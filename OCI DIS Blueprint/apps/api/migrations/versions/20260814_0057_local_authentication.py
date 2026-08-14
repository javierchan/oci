"""Add provider-neutral local authentication and project isolation.

Revision ID: 20260814_0057
Revises: 20260812_0056
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260814_0057"
down_revision = "20260812_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_app_users_email", "app_users", ["email"])

    op.create_table(
        "auth_identities",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("provider_metadata", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "subject", name="uq_auth_identity_provider_subject"),
    )
    op.create_index("ix_auth_identities_provider", "auth_identities", ["provider"])
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])

    op.create_table(
        "local_credentials",
        sa.Column("identity_id", sa.String(length=36), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["identity_id"], ["auth_identities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("identity_id"),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("identity_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["identity_id"], ["auth_identities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_index("ix_auth_sessions_identity_id", "auth_sessions", ["identity_id"])
    op.create_index("ix_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"])
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"])
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])

    op.create_table(
        "api_tokens",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_prefix", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("allowed_project_ids", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_api_tokens_expires_at", "api_tokens", ["expires_at"])
    op.create_index("ix_api_tokens_revoked_at", "api_tokens", ["revoked_at"])
    op.create_index("ix_api_tokens_token_hash", "api_tokens", ["token_hash"])
    op.create_index("ix_api_tokens_token_prefix", "api_tokens", ["token_prefix"])
    op.create_index("ix_api_tokens_user_id", "api_tokens", ["user_id"])

    op.create_table(
        "project_memberships",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("project_role", sa.String(length=32), nullable=False),
        sa.Column("granted_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_membership_project_user"),
    )
    op.create_index("ix_project_memberships_project_id", "project_memberships", ["project_id"])
    op.create_index("ix_project_memberships_user_id", "project_memberships", ["user_id"])

    op.drop_constraint(
        "uq_support_conversation_session_status",
        "support_conversations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_support_conversation_actor_session_status",
        "support_conversations",
        ["actor_id", "session_id", "status"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_support_conversation_actor_session_status",
        "support_conversations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_support_conversation_session_status",
        "support_conversations",
        ["session_id", "status"],
    )
    op.drop_index("ix_project_memberships_user_id", table_name="project_memberships")
    op.drop_index("ix_project_memberships_project_id", table_name="project_memberships")
    op.drop_table("project_memberships")
    op.drop_index("ix_api_tokens_user_id", table_name="api_tokens")
    op.drop_index("ix_api_tokens_token_prefix", table_name="api_tokens")
    op.drop_index("ix_api_tokens_token_hash", table_name="api_tokens")
    op.drop_index("ix_api_tokens_revoked_at", table_name="api_tokens")
    op.drop_index("ix_api_tokens_expires_at", table_name="api_tokens")
    op.drop_table("api_tokens")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_revoked_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_identity_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("local_credentials")
    op.drop_index("ix_auth_identities_user_id", table_name="auth_identities")
    op.drop_index("ix_auth_identities_provider", table_name="auth_identities")
    op.drop_table("auth_identities")
    op.drop_index("ix_app_users_email", table_name="app_users")
    op.drop_table("app_users")
