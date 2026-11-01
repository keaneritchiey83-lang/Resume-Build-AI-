"""Phase 5 verified webhook inbox and candidate ingestion.

Revision ID: 0003_phase5
Revises: 0002_phase4
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_phase5"
down_revision = "0002_phase4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("event_id", sa.String(1000), nullable=False),
        sa.Column("event_type", sa.String(200), nullable=False, server_default="application"),
        sa.Column("body_sha256", sa.String(64), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="received"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "event_id",
            name="uq_webhook_event_org_provider_event",
        ),
    )
    op.create_index(
        "ix_webhook_events_organization_id",
        "webhook_events",
        ["organization_id"],
    )
    op.create_index("ix_webhook_events_provider", "webhook_events", ["provider"])
    op.create_index("ix_webhook_events_status", "webhook_events", ["status"])
    op.create_index(
        "ix_webhook_events_body_sha256",
        "webhook_events",
        ["body_sha256"],
    )
    op.create_index(
        "ix_webhook_events_received_at",
        "webhook_events",
        ["received_at"],
    )

    op.create_table(
        "inbound_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("provider_candidate_id", sa.String(1000), nullable=False),
        sa.Column("email_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column(
            "processing_basis",
            sa.String(200),
            nullable=False,
            server_default="job_application",
        ),
        sa.Column(
            "privacy_notice_version",
            sa.String(100),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "provider_candidate_id",
            name="uq_inbound_candidate_org_provider_candidate",
        ),
    )
    op.create_index(
        "ix_inbound_candidates_organization_id",
        "inbound_candidates",
        ["organization_id"],
    )
    op.create_index(
        "ix_inbound_candidates_provider",
        "inbound_candidates",
        ["provider"],
    )
    op.create_index(
        "ix_inbound_candidates_email_hash",
        "inbound_candidates",
        ["email_hash"],
    )
    op.create_index(
        "ix_inbound_candidates_received_at",
        "inbound_candidates",
        ["received_at"],
    )

    op.create_table(
        "inbound_applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("provider_application_id", sa.String(1000), nullable=False),
        sa.Column("external_job_id", sa.String(500), nullable=False, server_default=""),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("inbound_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_attribution", sa.String(200), nullable=False),
        sa.Column("status", sa.String(100), nullable=False, server_default="received"),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "provider_application_id",
            name="uq_inbound_application_org_provider_application",
        ),
    )
    op.create_index(
        "ix_inbound_applications_organization_id",
        "inbound_applications",
        ["organization_id"],
    )
    op.create_index(
        "ix_inbound_applications_provider",
        "inbound_applications",
        ["provider"],
    )
    op.create_index(
        "ix_inbound_applications_external_job_id",
        "inbound_applications",
        ["external_job_id"],
    )
    op.create_index(
        "ix_inbound_applications_candidate_id",
        "inbound_applications",
        ["candidate_id"],
    )
    op.create_index(
        "ix_inbound_applications_status",
        "inbound_applications",
        ["status"],
    )
    op.create_index(
        "ix_inbound_applications_received_at",
        "inbound_applications",
        ["received_at"],
    )

    op.create_table(
        "inbound_attachments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("inbound_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            sa.String(36),
            sa.ForeignKey("inbound_applications.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(200), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("encrypted_base64", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "candidate_id",
            "sha256",
            name="uq_inbound_attachment_candidate_sha",
        ),
    )
    op.create_index(
        "ix_inbound_attachments_organization_id",
        "inbound_attachments",
        ["organization_id"],
    )
    op.create_index(
        "ix_inbound_attachments_candidate_id",
        "inbound_attachments",
        ["candidate_id"],
    )
    op.create_index(
        "ix_inbound_attachments_application_id",
        "inbound_attachments",
        ["application_id"],
    )
    op.create_index(
        "ix_inbound_attachments_provider",
        "inbound_attachments",
        ["provider"],
    )
    op.create_index(
        "ix_inbound_attachments_sha256",
        "inbound_attachments",
        ["sha256"],
    )


def downgrade() -> None:
    op.drop_table("inbound_attachments")
    op.drop_table("inbound_applications")
    op.drop_table("inbound_candidates")
    op.drop_table("webhook_events")
