"""Phase 3 baseline schema.

Revision ID: 0001_phase3
Revises:
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR


revision = "0001_phase3"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "candidate_profiles",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "resume_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("encrypted_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("user_id", "sha256", name="uq_resume_user_sha"),
    )
    op.create_index("ix_resume_documents_user_id", "resume_documents", ["user_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(500), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("organization", sa.String(500), nullable=False, server_default=""),
        sa.Column("location", sa.String(500), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("apply_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("source", "external_id", name="uq_job_source_external"),
    )
    op.create_index("ix_jobs_source", "jobs", ["source"])
    op.create_index("ix_jobs_title", "jobs", ["title"])
    op.create_index("ix_jobs_location", "jobs", ["location"])

    op.create_table(
        "career_concepts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(1000), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("embedding", VECTOR(384), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "source",
            "external_id",
            name="uq_career_concept_source_external",
        ),
    )
    op.create_index("ix_career_concepts_source", "career_concepts", ["source"])
    op.create_index("ix_career_concepts_kind", "career_concepts", ["kind"])
    op.create_index("ix_career_concepts_title", "career_concepts", ["title"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_career_concepts_embedding_hnsw "
        "ON career_concepts USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(300), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("license", sa.String(500), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="staged"),
        sa.Column("embedding", VECTOR(384), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("checksum", name="uq_knowledge_checksum"),
    )
    op.create_index("ix_knowledge_documents_source", "knowledge_documents", ["source"])
    op.create_index("ix_knowledge_documents_checksum", "knowledge_documents", ["checksum"], unique=True)
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_embedding_hnsw "
        "ON knowledge_documents USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.String(64),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("organization", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("encrypted_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_applications_user_id", "applications", ["user_id"])
    op.create_index("ix_applications_status", "applications", ["status"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event", sa.String(200), nullable=False),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_audit_events_event", "audit_events", ["event"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("applications")
    op.drop_table("knowledge_documents")
    op.drop_table("career_concepts")
    op.drop_table("jobs")
    op.drop_table("resume_documents")
    op.drop_table("candidate_profiles")
    op.drop_table("users")
