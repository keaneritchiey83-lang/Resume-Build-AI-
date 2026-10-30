"""Phase 4 enterprise identity, tenancy and provider integrations.

Revision ID: 0002_phase4
Revises: 0001_phase3
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_phase4"
down_revision = "0001_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("oidc_subject", sa.String(1000), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        "UPDATE users SET is_platform_admin = is_admin "
        "WHERE is_admin = TRUE"
    )
    op.drop_column("users", "is_admin")

    op.add_column(
        "users",
        sa.Column(
            "mfa_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "mfa_secret_encrypted",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "mfa_pending_secret_encrypted",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.create_index(
        "ix_users_oidc_subject",
        "users",
        ["oidc_subject"],
        unique=True,
    )

    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("slug", sa.String(300), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    op.create_table(
        "memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_membership_org_user",
        ),
    )
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])

    op.create_table(
        "provider_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            name="uq_provider_credential_org_provider",
        ),
    )
    op.create_index(
        "ix_provider_credentials_organization_id",
        "provider_credentials",
        ["organization_id"],
    )
    op.create_index(
        "ix_provider_credentials_provider",
        "provider_credentials",
        ["provider"],
    )

    op.create_table(
        "provider_publications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("external_job_id", sa.String(500), nullable=False),
        sa.Column("provider_job_id", sa.String(1000), nullable=False, server_default=""),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("status", sa.String(100), nullable=False, server_default="submitted"),
        sa.Column(
            "response_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "external_job_id",
            name="uq_publication_org_provider_job",
        ),
    )
    op.create_index(
        "ix_provider_publications_organization_id",
        "provider_publications",
        ["organization_id"],
    )
    op.create_index(
        "ix_provider_publications_provider",
        "provider_publications",
        ["provider"],
    )


def downgrade() -> None:
    op.drop_table("provider_publications")
    op.drop_table("provider_credentials")
    op.drop_table("memberships")
    op.drop_table("organizations")
    op.drop_index("ix_users_oidc_subject", table_name="users")
    op.drop_column("users", "mfa_pending_secret_encrypted")
    op.drop_column("users", "mfa_secret_encrypted")
    op.drop_column("users", "mfa_enabled")
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        "UPDATE users SET is_admin = is_platform_admin "
        "WHERE is_platform_admin = TRUE"
    )
    op.drop_column("users", "is_platform_admin")
    op.drop_column("users", "oidc_subject")
