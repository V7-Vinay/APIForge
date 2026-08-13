"""environment management

Revision ID: 0005_environments
Revises: 0004_collections_requests
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_environments"
down_revision = "0004_collections_requests"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "environments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "workspace_id", "name", name="uq_environment_workspace_name"
        ),
    )
    op.create_index("ix_environments_workspace_id", "environments", ["workspace_id"])
    op.create_table(
        "environment_variables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("environment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value_ciphertext", sa.Text(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["environment_id"], ["environments.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "environment_id", "key", name="uq_environment_variable_key"
        ),
    )
    op.create_index(
        "ix_environment_variables_environment_id",
        "environment_variables",
        ["environment_id"],
    )


def downgrade():
    op.drop_index(
        "ix_environment_variables_environment_id", table_name="environment_variables"
    )
    op.drop_table("environment_variables")
    op.drop_index("ix_environments_workspace_id", table_name="environments")
    op.drop_table("environments")
