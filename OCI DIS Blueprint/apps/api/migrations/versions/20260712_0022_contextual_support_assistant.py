"""Add session-isolated contextual support conversations."""

from alembic import op
import sqlalchemy as sa


revision = "20260712_0022"
down_revision = "20260712_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_conversations",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "status", name="uq_support_conversation_session_status"),
    )
    op.create_index("ix_support_conversations_session_id", "support_conversations", ["session_id"])
    op.create_index("ix_support_conversations_status", "support_conversations", ["status"])

    op.create_table(
        "support_messages",
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["support_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_messages_conversation_id", "support_messages", ["conversation_id"])
    op.create_index("ix_support_messages_agent_run_id", "support_messages", ["agent_run_id"])
    op.create_index("ix_support_messages_status", "support_messages", ["status"])

    op.create_table(
        "support_attachments",
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("attachment_type", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("href", sa.Text(), nullable=False),
        sa.Column("context_payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["support_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["support_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_attachments_conversation_id", "support_attachments", ["conversation_id"])
    op.create_index("ix_support_attachments_message_id", "support_attachments", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_support_attachments_message_id", table_name="support_attachments")
    op.drop_index("ix_support_attachments_conversation_id", table_name="support_attachments")
    op.drop_table("support_attachments")
    op.drop_index("ix_support_messages_status", table_name="support_messages")
    op.drop_index("ix_support_messages_agent_run_id", table_name="support_messages")
    op.drop_index("ix_support_messages_conversation_id", table_name="support_messages")
    op.drop_table("support_messages")
    op.drop_index("ix_support_conversations_status", table_name="support_conversations")
    op.drop_index("ix_support_conversations_session_id", table_name="support_conversations")
    op.drop_table("support_conversations")
