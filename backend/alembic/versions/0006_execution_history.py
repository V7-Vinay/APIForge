"""execution history

Revision ID: 0006_execution_history
Revises: 0005_environments
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0006_execution_history"
down_revision = "0005_environments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column(
            "response_size_bytes", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "response_headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(length=200), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["environment_id"], ["environments.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_execution_history_request_created",
        "execution_history",
        ["request_id", "created_at"],
    )
    op.create_index(
        "ix_execution_history_workspace_created",
        "execution_history",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_execution_history_user_created",
        "execution_history",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_execution_history_user_created", table_name="execution_history")
    op.drop_index(
        "ix_execution_history_workspace_created", table_name="execution_history"
    )
    op.drop_index(
        "ix_execution_history_request_created", table_name="execution_history"
    )
    op.drop_table("execution_history")
