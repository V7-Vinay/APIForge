"""audit logs

Revision ID: 0007_audit_logs
Revises: 0006_execution_history
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_audit_logs"
down_revision = "0006_execution_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_logs_workspace_created", "audit_logs", ["workspace_id", "created_at"])
    op.create_index("ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at"])
    op.create_index("ix_audit_logs_action_created", "audit_logs", ["action", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_action_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_workspace_created", table_name="audit_logs")
    op.drop_table("audit_logs")
