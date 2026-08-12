"""create invitations table"""

from alembic import op
import sqlalchemy as sa

revision = "0003_invitations"
down_revision = "0002_workspaces"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'EDITOR', 'VIEWER')", name="ck_invitation_role"
        ),
    )
    op.create_index(
        "ix_invitations_workspace_id", "invitations", ["workspace_id"], unique=False
    )
    op.create_index("ix_invitations_email", "invitations", ["email"], unique=False)
    op.create_index(
        "ix_invitations_token_hash", "invitations", ["token_hash"], unique=True
    )


def downgrade():
    op.drop_index("ix_invitations_token_hash", table_name="invitations")
    op.drop_index("ix_invitations_email", table_name="invitations")
    op.drop_index("ix_invitations_workspace_id", table_name="invitations")
    op.drop_table("invitations")
