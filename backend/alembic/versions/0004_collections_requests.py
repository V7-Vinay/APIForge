"""collections, folders and requests

Revision ID: 0004_collections_requests
Revises: 0003_invitations
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_collections_requests"
down_revision = "0003_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collections_workspace_id", "collections", ["workspace_id"])
    op.create_index(
        "ix_collections_workspace_position", "collections", ["workspace_id", "position"]
    )

    op.create_table(
        "folders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
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
            ["collection_id"], ["collections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["folders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_folders_collection_id", "folders", ["collection_id"])
    op.create_index("ix_folders_parent_id", "folders", ["parent_id"])
    op.create_index(
        "ix_folders_collection_position", "folders", ["collection_id", "position"]
    )

    op.create_table(
        "requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("folder_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "query_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "auth_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
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
            ["collection_id"], ["collections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["folder_id"], ["folders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_requests_collection_id", "requests", ["collection_id"])
    op.create_index("ix_requests_folder_id", "requests", ["folder_id"])
    op.create_index(
        "ix_requests_collection_position", "requests", ["collection_id", "position"]
    )


def downgrade() -> None:
    op.drop_index("ix_requests_collection_position", table_name="requests")
    op.drop_index("ix_requests_folder_id", table_name="requests")
    op.drop_index("ix_requests_collection_id", table_name="requests")
    op.drop_table("requests")
    op.drop_index("ix_folders_collection_position", table_name="folders")
    op.drop_index("ix_folders_parent_id", table_name="folders")
    op.drop_index("ix_folders_collection_id", table_name="folders")
    op.drop_table("folders")
    op.drop_index("ix_collections_workspace_position", table_name="collections")
    op.drop_index("ix_collections_workspace_id", table_name="collections")
    op.drop_table("collections")
