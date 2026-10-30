from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.db import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, default="")
    oidc_subject: Mapped[str | None] = mapped_column(
        String(1000), unique=True, nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret_encrypted: Mapped[str] = mapped_column(Text, default="")
    mfa_pending_secret_encrypted: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(300))
    slug: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(50), default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "provider", name="uq_provider_credential_org_provider"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(100), index=True)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ProviderPublication(Base):
    __tablename__ = "provider_publications"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            "external_job_id",
            name="uq_publication_org_provider_job",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(100), index=True)
    external_job_id: Mapped[str] = mapped_column(String(500))
    provider_job_id: Mapped[str] = mapped_column(String(1000), default="")
    operation: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(100), default="submitted")
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CandidateProfileRecord(Base):
    __tablename__ = "candidate_profiles"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    encrypted_payload: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ResumeDocument(Base):
    __tablename__ = "resume_documents"
    __table_args__ = (
        UniqueConstraint("user_id", "sha256", name="uq_resume_user_sha"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    encrypted_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_job_source_external"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    external_id: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(500), index=True)
    organization: Mapped[str] = mapped_column(String(500), default="")
    location: Mapped[str] = mapped_column(String(500), default="", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    apply_url: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CareerConcept(Base):
    __tablename__ = "career_concepts"
    __table_args__ = (
        UniqueConstraint(
            "source", "external_id", name="uq_career_concept_source_external"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(100), index=True)
    external_id: Mapped[str] = mapped_column(String(1000))
    kind: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(1000), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(
        VECTOR(settings.embedding_dimensions), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


Index(
    "ix_career_concepts_embedding_hnsw",
    CareerConcept.embedding,
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(300), index=True)
    title: Mapped[str] = mapped_column(String(1000))
    content: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, default="")
    license: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="staged", index=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        VECTOR(settings.embedding_dimensions), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


Index(
    "ix_knowledge_embedding_hnsw",
    KnowledgeDocument.embedding,
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500))
    organization: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), index=True)
    encrypted_notes: Mapped[str] = mapped_column(Text, default="")
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class WebhookEvent(Base):
    """Durable inbox record for verified partner webhook deliveries."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            "event_id",
            name="uq_webhook_event_org_provider_event",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(100), index=True)
    event_id: Mapped[str] = mapped_column(String(1000))
    event_type: Mapped[str] = mapped_column(String(200), default="application")
    body_sha256: Mapped[str] = mapped_column(String(64), index=True)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="received", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InboundCandidate(Base):
    """Encrypted candidate record created from an authorized application webhook."""

    __tablename__ = "inbound_candidates"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            "provider_candidate_id",
            name="uq_inbound_candidate_org_provider_candidate",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(100), index=True)
    provider_candidate_id: Mapped[str] = mapped_column(String(1000))
    email_hash: Mapped[str] = mapped_column(String(64), index=True, default="")
    encrypted_payload: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(200))
    processing_basis: Mapped[str] = mapped_column(String(200), default="job_application")
    privacy_notice_version: Mapped[str] = mapped_column(String(100), default="")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InboundApplication(Base):
    """Organization-scoped application linked to an encrypted inbound candidate."""

    __tablename__ = "inbound_applications"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            "provider_application_id",
            name="uq_inbound_application_org_provider_application",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(100), index=True)
    provider_application_id: Mapped[str] = mapped_column(String(1000))
    external_job_id: Mapped[str] = mapped_column(String(500), index=True, default="")
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inbound_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    source_attribution: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(100), default="received", index=True)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class InboundAttachment(Base):
    """Encrypted inbound application attachment retained with the candidate."""

    __tablename__ = "inbound_attachments"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "candidate_id",
            "sha256",
            name="uq_inbound_attachment_candidate_sha",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inbound_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    application_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("inbound_applications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(100), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    encrypted_base64: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConsentEvent(Base):
    """Append-only consent ledger for automated career-agent purposes."""

    __tablename__ = "consent_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    consent_version: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(100), default="user")
    evidence_hash: Mapped[str] = mapped_column(String(64), default="")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class CareerMonitorPolicy(Base):
    """Encrypted job-monitoring preferences backed by explicit consent."""

    __tablename__ = "career_monitor_policies"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    encrypted_preferences: Mapped[str] = mapped_column(Text)
    minimum_match_score: Mapped[float] = mapped_column(Float, default=65.0)
    cadence: Mapped[str] = mapped_column(String(50), default="daily")
    allow_ai_analysis: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_version: Mapped[str] = mapped_column(String(100))
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_scanned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class JobRecommendation(Base):
    """Encrypted candidate-specific analysis for a normalized job."""

    __tablename__ = "job_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "job_id",
            name="uq_job_recommendation_user_job",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[float] = mapped_column(Float, index=True)
    encrypted_analysis: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(50), default="new", index=True)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent_analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CareerAgentRun(Base):
    """Auditable bounded agent run. Results are encrypted because they are personal."""

    __tablename__ = "career_agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_type: Mapped[str] = mapped_column(String(100), index=True)
    trigger: Mapped[str] = mapped_column(String(100), default="manual")
    status: Mapped[str] = mapped_column(String(50), default="running", index=True)
    input_digest: Mapped[str] = mapped_column(String(64))
    encrypted_result: Mapped[str] = mapped_column(Text, default="")
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AnalyticsDaily(Base):
    """Organization-scoped aggregate metrics without protected-trait dimensions."""

    __tablename__ = "analytics_daily"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "day",
            "metric",
            "dimension_key",
            name="uq_analytics_daily_org_metric_dimension",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date, index=True)
    metric: Mapped[str] = mapped_column(String(100), index=True)
    dimension_key: Mapped[str] = mapped_column(String(300), default="")
    value: Mapped[float] = mapped_column(Float, default=0.0)
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event: Mapped[str] = mapped_column(String(200), index=True)
    actor: Mapped[str] = mapped_column(String(200))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

class SalaryBenchmark(Base):
    """Provenance-preserving occupational wage benchmark."""

    __tablename__ = "salary_benchmarks"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "data_vintage",
            "country_code",
            "region_code",
            "occupation_code",
            name="uq_salary_benchmark_source_vintage_geo_occ",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(200), index=True)
    data_vintage: Mapped[str] = mapped_column(String(100), index=True)
    country_code: Mapped[str] = mapped_column(String(3), index=True)
    region_code: Mapped[str] = mapped_column(String(100), default="", index=True)
    occupation_code: Mapped[str] = mapped_column(String(100), index=True)
    occupation_title: Mapped[str] = mapped_column(String(1000), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    wage_p10: Mapped[float | None] = mapped_column(Float, nullable=True)
    wage_p25: Mapped[float | None] = mapped_column(Float, nullable=True)
    wage_median: Mapped[float | None] = mapped_column(Float, nullable=True)
    wage_p75: Mapped[float | None] = mapped_column(Float, nullable=True)
    wage_p90: Mapped[float | None] = mapped_column(Float, nullable=True)
    annual_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    employment: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, default="")
    license: Mapped[str] = mapped_column(String(500), default="")
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class EducationPathway(Base):
    """Approved education/certification pathway with source provenance."""

    __tablename__ = "education_pathways"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_id",
            name="uq_education_pathway_source_external",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(200), index=True)
    external_id: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(1000), index=True)
    provider: Mapped[str] = mapped_column(String(500), default="")
    pathway_type: Mapped[str] = mapped_column(String(100), index=True)
    country_code: Mapped[str] = mapped_column(String(3), default="", index=True)
    occupation_code: Mapped[str] = mapped_column(String(100), default="", index=True)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    license: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(50), default="approved", index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class MobilityMapping(Base):
    """Evidence-backed occupation mapping across taxonomies/jurisdictions."""

    __tablename__ = "mobility_mappings"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "from_country",
            "from_occupation_code",
            "to_country",
            "to_occupation_code",
            name="uq_mobility_mapping_route",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(200), index=True)
    from_country: Mapped[str] = mapped_column(String(3), index=True)
    from_occupation_code: Mapped[str] = mapped_column(String(100), index=True)
    from_title: Mapped[str] = mapped_column(String(1000))
    to_country: Mapped[str] = mapped_column(String(3), index=True)
    to_occupation_code: Mapped[str] = mapped_column(String(100), index=True)
    to_title: Mapped[str] = mapped_column(String(1000))
    common_taxonomy: Mapped[str] = mapped_column(String(100), default="ISCO-08")
    common_code: Mapped[str] = mapped_column(String(100), default="", index=True)
    skill_overlap: Mapped[float] = mapped_column(Float, default=0.0)
    transition_effort: Mapped[str] = mapped_column(String(50), default="unknown")
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_url: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CareerForecast(Base):
    """Encrypted user-specific career pathway scenario."""

    __tablename__ = "career_forecasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    target_country: Mapped[str] = mapped_column(String(3), default="USA", index=True)
    method_version: Mapped[str] = mapped_column(String(100))
    data_version: Mapped[str] = mapped_column(String(200))
    encrypted_result: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class LearningPlan(Base):
    """Encrypted skills-gap plan generated from verified facts and approved pathways."""

    __tablename__ = "learning_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    target_occupation_code: Mapped[str] = mapped_column(String(100), index=True)
    target_occupation_title: Mapped[str] = mapped_column(String(1000))
    encrypted_plan: Mapped[str] = mapped_column(Text)
    method_version: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class GovernancePolicy(Base):
    """Versioned policy-as-code metadata; policy source lives in the repository."""

    __tablename__ = "governance_policies"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "policy_key",
            "version",
            name="uq_governance_policy_org_key_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    policy_key: Mapped[str] = mapped_column(String(200), index=True)
    version: Mapped[str] = mapped_column(String(100), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class ModelEvalSuite(Base):
    """Reusable evaluation suite for career AI behavior."""

    __tablename__ = "model_eval_suites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(300), index=True)
    version: Mapped[str] = mapped_column(String(100))
    cases_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class ModelEvalRun(Base):
    """Evaluation run with aggregate results; no candidate PII is required."""

    __tablename__ = "model_eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    suite_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("model_eval_suites.id", ondelete="CASCADE"), index=True
    )
    model_name: Mapped[str] = mapped_column(String(300), index=True)
    status: Mapped[str] = mapped_column(String(50), default="running", index=True)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    results_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class FairnessSnapshot(Base):
    """Aggregate-only fairness monitoring result with minimum cohort sizes."""

    __tablename__ = "fairness_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    process_name: Mapped[str] = mapped_column(String(200), index=True)
    metric: Mapped[str] = mapped_column(String(100), index=True)
    reference_group: Mapped[str] = mapped_column(String(200))
    minimum_group_size: Mapped[int] = mapped_column(Integer, default=20)
    results_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class HumanReviewItem(Base):
    """Human review queue for policy, eval, fairness and high-risk exceptions."""

    __tablename__ = "human_review_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(50), default="medium", index=True)
    subject_type: Mapped[str] = mapped_column(String(100), index=True)
    subject_id: Mapped[str] = mapped_column(String(200), default="", index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="open", index=True)
    assigned_to_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    encrypted_context: Mapped[str] = mapped_column(Text, default="")
    resolution: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ComplianceEvidence(Base):
    """Automated control evidence artifact; not an audit opinion or attestation."""

    __tablename__ = "compliance_evidence"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "framework",
            "control_id",
            "artifact_hash",
            name="uq_compliance_evidence_artifact",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    framework: Mapped[str] = mapped_column(String(100), index=True)
    control_id: Mapped[str] = mapped_column(String(100), index=True)
    evidence_type: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(300))
    artifact_hash: Mapped[str] = mapped_column(String(64), index=True)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

class VerifiedCredential(Base):
    """Candidate credential with explicit verification level and encrypted source payload."""

    __tablename__ = "verified_credentials"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "credential_hash",
            name="uq_verified_credential_user_hash",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    credential_hash: Mapped[str] = mapped_column(String(64), index=True)
    credential_id: Mapped[str] = mapped_column(String(2000), default="")
    credential_format: Mapped[str] = mapped_column(String(100), index=True)
    credential_type: Mapped[str] = mapped_column(String(300), default="")
    title: Mapped[str] = mapped_column(String(1000), index=True)
    issuer_name: Mapped[str] = mapped_column(String(1000), default="")
    issuer_url: Mapped[str] = mapped_column(Text, default="")
    subject_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    verification_level: Mapped[str] = mapped_column(
        String(100), default="structural", index=True
    )
    verification_method: Mapped[str] = mapped_column(String(300), default="")
    verification_status: Mapped[str] = mapped_column(
        String(100), default="unverified", index=True
    )
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    encrypted_payload: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class LearningProviderConnection(Base):
    """Authorized organization-scoped learning catalog integration."""

    __tablename__ = "learning_provider_connections"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            "base_url",
            name="uq_learning_provider_org_provider_url",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(100), index=True)
    base_url: Mapped[str] = mapped_column(Text)
    encrypted_credentials: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class LearningCatalogItem(Base):
    """Normalized course, certification, program, or learning pathway."""

    __tablename__ = "learning_catalog_items"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            "external_id",
            name="uq_learning_catalog_org_provider_external",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("learning_provider_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(100), index=True)
    external_id: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(1000), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    learning_type: Mapped[str] = mapped_column(String(100), default="course", index=True)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    level: Mapped[str] = mapped_column(String(100), default="")
    language: Mapped[str] = mapped_column(String(50), default="")
    duration_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    credential_offered: Mapped[bool] = mapped_column(Boolean, default=False)
    source_url: Mapped[str] = mapped_column(Text, default="")
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, index=True
    )


class LaborMarketObservation(Base):
    """Provenance-bearing labor-market time-series observation."""

    __tablename__ = "labor_market_observations"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "country_code",
            "region_code",
            "occupation_code",
            "metric",
            "period",
            name="uq_labor_observation_series_period",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(200), index=True)
    data_vintage: Mapped[str] = mapped_column(String(100), index=True)
    country_code: Mapped[str] = mapped_column(String(3), index=True)
    region_code: Mapped[str] = mapped_column(String(100), default="", index=True)
    occupation_code: Mapped[str] = mapped_column(String(100), index=True)
    occupation_title: Mapped[str] = mapped_column(String(1000), index=True)
    metric: Mapped[str] = mapped_column(String(100), index=True)
    period: Mapped[str] = mapped_column(String(50), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(100), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    license: Mapped[str] = mapped_column(String(500), default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class LaborTrendSnapshot(Base):
    """Deterministic trend projection; never a hiring probability."""

    __tablename__ = "labor_trend_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(200), index=True)
    country_code: Mapped[str] = mapped_column(String(3), index=True)
    region_code: Mapped[str] = mapped_column(String(100), default="", index=True)
    occupation_code: Mapped[str] = mapped_column(String(100), index=True)
    occupation_title: Mapped[str] = mapped_column(String(1000))
    metric: Mapped[str] = mapped_column(String(100), index=True)
    method_version: Mapped[str] = mapped_column(String(100))
    input_count: Mapped[int] = mapped_column(Integer)
    start_period: Mapped[str] = mapped_column(String(50))
    end_period: Mapped[str] = mapped_column(String(50))
    start_value: Mapped[float] = mapped_column(Float)
    end_value: Mapped[float] = mapped_column(Float)
    linear_slope: Mapped[float] = mapped_column(Float)
    annualized_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    volatility: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(50), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    projected_next_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class CareerPortfolio(Base):
    """Encrypted candidate-controlled career portfolio."""

    __tablename__ = "career_portfolios"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_career_portfolio_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    encrypted_payload: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CareerPortfolioShare(Base):
    """Revocable and expiring public portfolio share token."""

    __tablename__ = "career_portfolio_shares"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    portfolio_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("career_portfolios.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    visibility_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AISystemInventory(Base):
    """Organization AI inventory record for lifecycle and regulatory governance."""

    __tablename__ = "ai_system_inventory"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "system_key",
            "version",
            name="uq_ai_inventory_org_key_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    system_key: Mapped[str] = mapped_column(String(200), index=True)
    version: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(500))
    owner: Mapped[str] = mapped_column(String(500), default="")
    intended_purpose: Mapped[str] = mapped_column(Text)
    operator_role: Mapped[str] = mapped_column(String(50), default="deployer")
    lifecycle_status: Mapped[str] = mapped_column(String(50), default="development", index=True)
    jurisdictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_names: Mapped[list[str]] = mapped_column(JSON, default=list)
    data_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    employment_use: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    education_use: Mapped[bool] = mapped_column(Boolean, default=False)
    profiles_natural_persons: Mapped[bool] = mapped_column(Boolean, default=False)
    materially_influences_decisions: Mapped[bool] = mapped_column(Boolean, default=False)
    human_oversight: Mapped[bool] = mapped_column(Boolean, default=True)
    eu_risk_class: Mapped[str] = mapped_column(String(100), default="not_assessed", index=True)
    eu_classification_basis: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    iso42001_in_scope: Mapped[bool] = mapped_column(Boolean, default=True)
    applicable_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class AIRiskAssessment(Base):
    """Versioned AI risk assessment with residual-risk and approval state."""

    __tablename__ = "ai_risk_assessments"
    __table_args__ = (
        UniqueConstraint(
            "inventory_id",
            "assessment_version",
            name="uq_ai_risk_inventory_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    inventory_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_system_inventory.id", ondelete="CASCADE"), index=True
    )
    assessment_version: Mapped[str] = mapped_column(String(100))
    likelihood: Mapped[int] = mapped_column(Integer)
    impact: Mapped[int] = mapped_column(Integer)
    inherent_score: Mapped[int] = mapped_column(Integer)
    residual_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(50), index=True)
    hazards_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    controls_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AIIncident(Base):
    """AI incident record with encrypted details and governance clocks."""

    __tablename__ = "ai_incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    inventory_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_system_inventory.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    severity: Mapped[str] = mapped_column(String(50), index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(50), default="open", index=True)
    serious_incident_candidate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    encrypted_details: Mapped[str] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    contained_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    external_reported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class GovernanceControlMapping(Base):
    """Implementation crosswalk metadata; not a substitute for licensed standards."""

    __tablename__ = "governance_control_mappings"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "framework",
            "control_ref",
            "inventory_id",
            name="uq_governance_control_mapping_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    inventory_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_system_inventory.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
    framework: Mapped[str] = mapped_column(String(100), index=True)
    control_ref: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(500))
    implementation_status: Mapped[str] = mapped_column(
        String(50), default="not_started", index=True
    )
    owner: Mapped[str] = mapped_column(String(500), default="")
    evidence_requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

class CandidateWallet(Base):
    """Candidate-owned wallet registration. No private keys are stored."""

    __tablename__ = "candidate_wallets"
    __table_args__ = (
        UniqueConstraint("user_id", "holder_did", name="uq_candidate_wallet_user_did"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    holder_did: Mapped[str] = mapped_column(Text)
    did_method: Mapped[str] = mapped_column(String(100), index=True)
    wallet_type: Mapped[str] = mapped_column(String(100), default="external")
    presentation_endpoint: Mapped[str] = mapped_column(Text, default="")
    issuance_endpoint: Mapped[str] = mapped_column(Text, default="")
    verification_status: Mapped[str] = mapped_column(
        String(100), default="registered", index=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SkillsPassport(Base):
    """Encrypted candidate-controlled portable skills passport."""

    __tablename__ = "skills_passports"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_skills_passport_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    wallet_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("candidate_wallets.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    encrypted_payload: Mapped[str] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class PrivacyImpactAssessment(Base):
    """Organization privacy impact assessment / DPIA-style governance record."""

    __tablename__ = "privacy_impact_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(500))
    system_or_process: Mapped[str] = mapped_column(String(500), index=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    risk_level: Mapped[str] = mapped_column(String(50), default="medium", index=True)
    processing_purposes: Mapped[list[str]] = mapped_column(JSON, default=list)
    data_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    data_subjects: Mapped[list[str]] = mapped_column(JSON, default=list)
    jurisdictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    lawful_bases: Mapped[list[str]] = mapped_column(JSON, default=list)
    recipients: Mapped[list[str]] = mapped_column(JSON, default=list)
    retention_summary: Mapped[str] = mapped_column(Text, default="")
    international_transfers: Mapped[bool] = mapped_column(Boolean, default=False)
    automated_decision_support: Mapped[bool] = mapped_column(Boolean, default=False)
    high_risk_processing: Mapped[bool] = mapped_column(Boolean, default=False)
    mitigations: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    review_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class DataAsset(Base):
    """Metadata-only registry of systems/tables/APIs used for data lineage."""

    __tablename__ = "data_assets"
    __table_args__ = (
        UniqueConstraint("organization_id", "asset_key", name="uq_data_asset_org_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    asset_key: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(500))
    asset_type: Mapped[str] = mapped_column(String(100), index=True)
    data_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    contains_personal_data: Mapped[bool] = mapped_column(Boolean, default=False)
    contains_sensitive_data: Mapped[bool] = mapped_column(Boolean, default=False)
    system_owner: Mapped[str] = mapped_column(String(500), default="")
    retention_class: Mapped[str] = mapped_column(String(100), default="", index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class DataLineageEdge(Base):
    """Purpose-bearing data-flow edge between registered assets."""

    __tablename__ = "data_lineage_edges"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "upstream_asset_id",
            "downstream_asset_id",
            "purpose_hash",
            name="uq_data_lineage_edge",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    upstream_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_assets.id", ondelete="CASCADE"), index=True
    )
    downstream_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_assets.id", ondelete="CASCADE"), index=True
    )
    transformation: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text)
    purpose_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class RetentionPolicy(Base):
    """Allowlisted retention policy applied by scheduled deletion jobs."""

    __tablename__ = "retention_policies"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "record_type",
            name="uq_retention_policy_org_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    record_type: Mapped[str] = mapped_column(String(100), index=True)
    retention_days: Mapped[int] = mapped_column(Integer)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_deleted_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class DataSubjectRequest(Base):
    """Candidate privacy-rights request with encrypted request/result details."""

    __tablename__ = "data_subject_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    request_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(50), default="received", index=True)
    identity_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    encrypted_details: Mapped[str] = mapped_column(Text, default="")
    encrypted_result: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RedTeamCampaign(Base):
    """Governed AI red-team campaign metadata and encrypted findings."""

    __tablename__ = "red_team_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    inventory_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_system_inventory.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(500))
    scope: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default="planned", index=True)
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    passed_tests: Mapped[int] = mapped_column(Integer, default=0)
    failed_tests: Mapped[int] = mapped_column(Integer, default=0)
    encrypted_findings: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ContinuousControlSnapshot(Base):
    """Continuous privacy/security/governance control signal snapshot."""

    __tablename__ = "continuous_control_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    overall_status: Mapped[str] = mapped_column(String(50), index=True)
    checks_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    open_findings: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

class CredentialIssuerProfile(Base):
    """Organization-owned OpenID4VCI issuer profile with an envelope-encrypted key."""

    __tablename__ = "credential_issuer_profiles"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_credential_issuer_slug"),
        UniqueConstraint("issuer_identifier", name="uq_credential_issuer_identifier"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(200), index=True)
    issuer_identifier: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(500))
    approval_status: Mapped[str] = mapped_column(
        String(50), default="pending", index=True
    )
    signing_alg: Mapped[str] = mapped_column(String(50), default="ES256")
    public_jwk: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    encrypted_private_key: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CredentialConfiguration(Base):
    """Credential configuration published through OpenID4VCI metadata."""

    __tablename__ = "credential_configurations"
    __table_args__ = (
        UniqueConstraint(
            "issuer_profile_id",
            "configuration_id",
            name="uq_credential_configuration_issuer_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issuer_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    configuration_id: Mapped[str] = mapped_column(String(300), index=True)
    credential_format: Mapped[str] = mapped_column(String(100), index=True)
    credential_type: Mapped[str] = mapped_column(String(500))
    vct: Mapped[str] = mapped_column(Text, default="")
    scope: Mapped[str] = mapped_column(String(300), default="")
    claim_names: Mapped[list[str]] = mapped_column(JSON, default=list)
    selective_claims: Mapped[list[str]] = mapped_column(JSON, default=list)
    display_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    require_holder_binding: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class CredentialWalletClient(Base):
    """Pre-registered wallet client for OpenID4VCI authorization-code flows."""

    __tablename__ = "credential_wallet_clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(500))
    redirect_uris: Mapped[list[str]] = mapped_column(JSON, default=list)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class CredentialIssuanceOffer(Base):
    """Single-use OpenID4VCI credential offer."""

    __tablename__ = "credential_issuance_offers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issuer_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    credential_configuration_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credential_configurations.id", ondelete="CASCADE"),
        index=True,
    )
    pre_authorized_code_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True
    )
    transaction_code_hash: Mapped[str] = mapped_column(String(64), default="")
    transaction_code_required: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class CredentialAuthorizationCode(Base):
    """Single-use OAuth authorization code for wallet-driven issuance."""

    __tablename__ = "credential_authorization_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issuer_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[str] = mapped_column(String(500), index=True)
    credential_configuration_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credential_configurations.id", ondelete="CASCADE"),
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    code_challenge: Mapped[str] = mapped_column(String(200))
    redirect_uri: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class CredentialAccessToken(Base):
    """Hashed bearer token authorizing one credential configuration."""

    __tablename__ = "credential_access_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issuer_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    credential_configuration_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credential_configurations.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    holder_jwk: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    nonce_hash: Mapped[str] = mapped_column(String(64), default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class IssuedCredentialRecord(Base):
    """Audit/status record for a credential issued by the platform."""

    __tablename__ = "issued_credential_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issuer_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    credential_configuration_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credential_configurations.id", ondelete="CASCADE"),
        index=True,
    )
    credential_format: Mapped[str] = mapped_column(String(100), index=True)
    jti: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    credential_hash: Mapped[str] = mapped_column(String(64), index=True)
    encrypted_credential: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CredentialVerifierProfile(Base):
    """Organization-owned OpenID4VP verifier profile."""

    __tablename__ = "credential_verifier_profiles"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_credential_verifier_slug"),
        UniqueConstraint("client_id", name="uq_credential_verifier_client"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(200), index=True)
    display_name: Mapped[str] = mapped_column(String(500))
    client_id: Mapped[str] = mapped_column(Text)
    response_uri: Mapped[str] = mapped_column(Text)
    approval_status: Mapped[str] = mapped_column(
        String(50), default="pending", index=True
    )
    vp_formats_supported: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class CredentialTrustAnchor(Base):
    """Static issuer trust material used by the verifier; no arbitrary URL fetching."""

    __tablename__ = "credential_trust_anchors"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "issuer_identifier",
            name="uq_credential_trust_anchor_org_issuer",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    issuer_identifier: Mapped[str] = mapped_column(Text)
    public_jwk: Mapped[dict[str, Any]] = mapped_column(JSON)
    allowed_formats: Mapped[list[str]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class PresentationRequestRecord(Base):
    """OpenID4VP request state for replay-safe direct_post processing."""

    __tablename__ = "presentation_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    verifier_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credential_verifier_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    nonce: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(200))
    state_hash: Mapped[str] = mapped_column(String(64), index=True)
    dcql_query: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class PresentationSubmission(Base):
    """Encrypted verification result for an OpenID4VP response."""

    __tablename__ = "presentation_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("presentation_requests.id", ondelete="CASCADE"),
        index=True,
    )
    holder_identifier: Mapped[str] = mapped_column(Text, default="")
    verification_status: Mapped[str] = mapped_column(
        String(50), default="received", index=True
    )
    issuer_identifiers: Mapped[list[str]] = mapped_column(JSON, default=list)
    encrypted_result: Mapped[str] = mapped_column(Text)
    raw_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class ConsentReceipt(Base):
    """Versioned, hash-addressed receipt for a candidate consent action."""

    __tablename__ = "consent_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    purpose: Mapped[str] = mapped_column(String(200), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    policy_version: Mapped[str] = mapped_column(String(100))
    lawful_basis: Mapped[str] = mapped_column(String(200), default="consent")
    processing_purposes: Mapped[list[str]] = mapped_column(JSON, default=list)
    data_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    receipt_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    previous_receipt_hash: Mapped[str] = mapped_column(String(64), default="")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class DataClassificationRule(Base):
    """Metadata-only discovery/classification rule."""

    __tablename__ = "data_classification_rules"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "rule_key", name="uq_data_classification_rule_org_key"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    rule_key: Mapped[str] = mapped_column(String(200), index=True)
    field_pattern: Mapped[str] = mapped_column(String(500))
    classification: Mapped[str] = mapped_column(String(100), index=True)
    sensitivity: Mapped[str] = mapped_column(String(50), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class DataDiscoveryScan(Base):
    """A metadata-only data discovery scan."""

    __tablename__ = "data_discovery_scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(50), default="running", index=True)
    scope: Mapped[str] = mapped_column(String(200), default="application_schema")
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DataDiscoveryFinding(Base):
    """Classified table/column metadata; no discovered plaintext values are stored."""

    __tablename__ = "data_discovery_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_discovery_scans.id", ondelete="CASCADE"), index=True
    )
    table_name: Mapped[str] = mapped_column(String(300), index=True)
    field_name: Mapped[str] = mapped_column(String(300), index=True)
    classification: Mapped[str] = mapped_column(String(100), index=True)
    sensitivity: Mapped[str] = mapped_column(String(50), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence: Mapped[str] = mapped_column(Text, default="")


class DeletionWorkflow(Base):
    """Auditable user-data erasure plan and execution status."""

    __tablename__ = "deletion_workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    dsar_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("data_subject_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), default="planned", index=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    legal_hold_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    steps_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PrivacyAnalyticsBudget(Base):
    """Daily differential-privacy budget per organization."""

    __tablename__ = "privacy_analytics_budgets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "day", name="uq_privacy_analytics_budget_org_day"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date, index=True)
    epsilon_limit: Mapped[float] = mapped_column(Float, default=2.0)
    epsilon_used: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class PrivacyAnalyticsRelease(Base):
    """A fixed-query differentially private analytics release."""

    __tablename__ = "privacy_analytics_releases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    metric: Mapped[str] = mapped_column(String(100), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    epsilon: Mapped[float] = mapped_column(Float)
    minimum_group_size: Mapped[int] = mapped_column(Integer)
    source_count: Mapped[int] = mapped_column(Integer)
    noisy_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class CryptographicAuditEntry(Base):
    """Append-only per-organization hash chain over security-relevant events."""

    __tablename__ = "cryptographic_audit_entries"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "sequence", name="uq_crypto_audit_org_sequence"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(200), index=True)
    actor: Mapped[str] = mapped_column(String(200))
    subject_type: Mapped[str] = mapped_column(String(200), default="")
    subject_id: Mapped[str] = mapped_column(String(200), default="")
    payload_digest: Mapped[str] = mapped_column(String(64))
    previous_hash: Mapped[str] = mapped_column(String(64), default="")
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    signature: Mapped[str] = mapped_column(Text, default="")
    signing_key_id: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

class PasskeyCredential(Base):
    """WebAuthn passkey public credential. No private key material is stored."""

    __tablename__ = "passkey_credentials"
    __table_args__ = (
        UniqueConstraint("credential_id_b64", name="uq_passkey_credential_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    credential_id_b64: Mapped[str] = mapped_column(String(2000), unique=True, index=True)
    public_key_b64: Mapped[str] = mapped_column(Text)
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    device_type: Mapped[str] = mapped_column(String(100), default="")
    backed_up: Mapped[bool] = mapped_column(Boolean, default=False)
    transports: Mapped[list[str]] = mapped_column(JSON, default=list)
    nickname: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebAuthnChallenge(Base):
    """Single-use WebAuthn ceremony challenge."""

    __tablename__ = "webauthn_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(30), index=True)
    challenge_b64: Mapped[str] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DidTrustRegistryEntry(Base):
    """Organization-scoped DID document/trust record."""

    __tablename__ = "did_trust_registry_entries"
    __table_args__ = (
        UniqueConstraint("organization_id", "did", name="uq_did_trust_org_did"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    did: Mapped[str] = mapped_column(Text)
    did_document: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    trust_status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    source: Mapped[str] = mapped_column(String(200), default="manual")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    reviewed_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BitstringStatusListRecord(Base):
    """W3C Bitstring Status List v1.0 issuer-managed list."""

    __tablename__ = "bitstring_status_lists"
    __table_args__ = (
        UniqueConstraint("issuer_profile_id", "purpose", "sequence", name="uq_status_list_issuer_purpose_sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issuer_profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(100), default="revocation", index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    capacity_bits: Mapped[int] = mapped_column(Integer, default=131072)
    next_index: Mapped[int] = mapped_column(Integer, default=0)
    bitstring_b64: Mapped[str] = mapped_column(Text)
    status_list_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CredentialStatusAssignment(Base):
    """Maps an issued credential to its status-list slot."""

    __tablename__ = "credential_status_assignments"
    __table_args__ = (
        UniqueConstraint("issued_credential_id", "purpose", name="uq_credential_status_purpose"),
        UniqueConstraint("status_list_id", "status_index", name="uq_status_list_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issued_credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("issued_credential_records.id", ondelete="CASCADE"), index=True
    )
    status_list_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bitstring_status_lists.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(100), index=True)
    status_index: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WalletKeyAttestation(Base):
    """Public wallet-key attestation metadata; never stores holder private keys."""

    __tablename__ = "wallet_key_attestations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    holder_did: Mapped[str] = mapped_column(Text, default="")
    key_id: Mapped[str] = mapped_column(Text)
    public_jwk: Mapped[dict[str, Any]] = mapped_column(JSON)
    attestation_format: Mapped[str] = mapped_column(String(100), default="")
    hardware_backed_claim: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    encrypted_attestation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CryptoInventoryItem(Base):
    """Cryptographic dependency inventory used for post-quantum migration planning."""

    __tablename__ = "crypto_inventory_items"
    __table_args__ = (
        UniqueConstraint("organization_id", "component", "usage", name="uq_crypto_inventory_component_usage"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    component: Mapped[str] = mapped_column(String(300), index=True)
    usage: Mapped[str] = mapped_column(String(300), index=True)
    current_algorithm: Mapped[str] = mapped_column(String(200))
    quantum_risk: Mapped[str] = mapped_column(String(50), default="unknown", index=True)
    target_standard: Mapped[str] = mapped_column(String(200), default="")
    migration_status: Mapped[str] = mapped_column(String(50), default="inventory", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ConfidentialWorkloadAttestation(Base):
    """Recorded attestation result for an explicitly configured confidential workload."""

    __tablename__ = "confidential_workload_attestations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    workload_name: Mapped[str] = mapped_column(String(300), index=True)
    provider: Mapped[str] = mapped_column(String(100), index=True)
    measurement: Mapped[str] = mapped_column(Text, default="")
    verification_status: Mapped[str] = mapped_column(String(50), default="unverified", index=True)
    evidence_digest: Mapped[str] = mapped_column(String(64), default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SecurityTestRun(Base):
    """Continuous DAST/pentest workflow record. Findings do not auto-close themselves."""

    __tablename__ = "security_test_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    test_type: Mapped[str] = mapped_column(String(100), index=True)
    tool: Mapped[str] = mapped_column(String(200))
    target: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="scheduled", index=True)
    findings_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    report_digest: Mapped[str] = mapped_column(String(64), default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)



class FederationTrustAnchor(Base):
    """Organization-approved OpenID Federation trust anchor."""

    __tablename__ = "federation_trust_anchors"
    __table_args__ = (
        UniqueConstraint("organization_id", "entity_id", name="uq_federation_anchor_org_entity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(500), default="")
    jwks: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    approved_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class FederationEntityRecord(Base):
    """Locally reviewed federation entity and optional parent linkage."""

    __tablename__ = "federation_entities"
    __table_args__ = (
        UniqueConstraint("organization_id", "entity_id", name="uq_federation_entity_org_entity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(String(100), default="federation_entity", index=True)
    parent_entity_id: Mapped[str] = mapped_column(Text, default="")
    jwks: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    trust_marks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    self_statement_jwt: Mapped[str] = mapped_column(Text, default="")
    subordinate_statement_jwt: Mapped[str] = mapped_column(Text, default="")
    trust_status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    validation_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    reviewed_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class WalletAttestationTrustAnchor(Base):
    """Public certificate trust anchor for high-assurance wallet attestations."""

    __tablename__ = "wallet_attestation_trust_anchors"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_wallet_attestation_anchor_org_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(300))
    root_certificate_pem: Mapped[str] = mapped_column(Text)
    allowed_subjects: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WalletAttestationEvidence(Base):
    """Verified wallet-attestation result; raw attestation is not retained."""

    __tablename__ = "wallet_attestation_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    trust_anchor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("wallet_attestation_trust_anchors.id", ondelete="RESTRICT")
    )
    subject: Mapped[str] = mapped_column(Text, default="")
    issuer: Mapped[str] = mapped_column(Text, default="")
    attestation_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    claims_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    verification_status: Mapped[str] = mapped_column(String(50), default="verified", index=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CredentialNegotiationPolicy(Base):
    """Organization policy for credential-format and wallet-capability negotiation."""

    __tablename__ = "credential_negotiation_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_credential_policy_org_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(300))
    purpose: Mapped[str] = mapped_column(String(300), default="")
    accepted_formats: Mapped[list[str]] = mapped_column(JSON, default=list)
    accepted_credential_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_claims: Mapped[list[str]] = mapped_column(JSON, default=list)
    accepted_proof_algorithms: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_trust_frameworks: Mapped[list[str]] = mapped_column(JSON, default=list)
    require_wallet_attestation: Mapped[bool] = mapped_column(Boolean, default=False)
    require_hardware_backed_key: Mapped[bool] = mapped_column(Boolean, default=False)
    minimum_assurance_level: Mapped[str] = mapped_column(String(100), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CredentialNegotiationDecision(Base):
    """Auditable result of credential-policy negotiation."""

    __tablename__ = "credential_negotiation_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    policy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credential_negotiation_policies.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    decision: Mapped[str] = mapped_column(String(50), index=True)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    negotiated_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    input_digest: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class HsmSigningKey(Base):
    """Reference to a non-exportable credential signing key held by an HSM/KMS."""

    __tablename__ = "hsm_signing_keys"
    __table_args__ = (
        UniqueConstraint("issuer_profile_id", "key_name", name="uq_hsm_key_issuer_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    issuer_profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"), index=True
    )
    key_name: Mapped[str] = mapped_column(String(300))
    provider: Mapped[str] = mapped_column(String(100), index=True)
    key_reference: Mapped[str] = mapped_column(Text)
    algorithm: Mapped[str] = mapped_column(String(100), default="ES256")
    public_jwk: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    approval_status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConfidentialInferencePolicy(Base):
    """Attestation-gated policy for confidential AI inference."""

    __tablename__ = "confidential_inference_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_confidential_inference_policy_org_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(300))
    provider: Mapped[str] = mapped_column(String(100), index=True)
    allowed_measurements: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_data_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    require_attestation: Mapped[bool] = mapped_column(Boolean, default=True)
    fail_closed: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConfidentialInferenceAttestation(Base):
    """Short-lived verified evidence for a confidential inference workload."""

    __tablename__ = "confidential_inference_attestations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    policy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("confidential_inference_policies.id", ondelete="CASCADE"), index=True
    )
    measurement: Mapped[str] = mapped_column(Text)
    evidence_digest: Mapped[str] = mapped_column(String(64), index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class WorkloadIdentityPolicy(Base):
    """SPIFFE/SPIRE workload-identity allow policy."""

    __tablename__ = "workload_identity_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_workload_identity_policy_org_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(300))
    spiffe_id_pattern: Mapped[str] = mapped_column(String(1000))
    namespace: Mapped[str] = mapped_column(String(300), default="")
    service_account: Mapped[str] = mapped_column(String(300), default="")
    allowed_peer_patterns: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RuntimeSecurityEvent(Base):
    """Normalized runtime threat-detection event."""

    __tablename__ = "runtime_security_events"
    __table_args__ = (
        UniqueConstraint("event_digest", name="uq_runtime_security_event_digest"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(50), index=True)
    rule: Mapped[str] = mapped_column(String(500), index=True)
    workload: Mapped[str] = mapped_column(String(500), default="")
    namespace: Mapped[str] = mapped_column(String(300), default="")
    event_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="open", index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContainmentPolicy(Base):
    """Bounded incident-containment policy with reversible auto-actions."""

    __tablename__ = "containment_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_containment_policy_org_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(300))
    minimum_severity: Mapped[str] = mapped_column(String(50), default="critical")
    rule_patterns: Mapped[list[str]] = mapped_column(JSON, default=list)
    actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    auto_execute_reversible: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class IncidentContainmentAction(Base):
    """Planned/executed containment action linked to a runtime event."""

    __tablename__ = "incident_containment_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runtime_security_events.id", ondelete="CASCADE"), index=True
    )
    policy_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("containment_policies.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    reversible: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DeploymentRegion(Base):
    """Registered deployment region participating in trust continuity."""

    __tablename__ = "deployment_regions"
    __table_args__ = (
        UniqueConstraint("organization_id", "region_key", name="uq_deployment_region_org_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    region_key: Mapped[str] = mapped_column(String(200), index=True)
    display_name: Mapped[str] = mapped_column(String(300))
    cloud_provider: Mapped[str] = mapped_column(String(100), index=True)
    jurisdiction: Mapped[str] = mapped_column(String(100), default="")
    spiffe_trust_domain: Mapped[str] = mapped_column(String(500))
    federation_entity_id: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RegionTrustLink(Base):
    """Explicit cross-region trust link with pinned bundle digests."""

    __tablename__ = "region_trust_links"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "source_region_id",
            "peer_region_id",
            name="uq_region_trust_link_org_pair",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    source_region_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deployment_regions.id", ondelete="CASCADE"), index=True
    )
    peer_region_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deployment_regions.id", ondelete="CASCADE"), index=True
    )
    peer_bundle_endpoint: Mapped[str] = mapped_column(Text, default="")
    peer_bundle_digest: Mapped[str] = mapped_column(String(64), index=True)
    peer_bundle_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    federation_anchor_entity_id: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    verification_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CrossCloudWorkloadBinding(Base):
    """Maps a SPIFFE workload identity to approved cloud-native identity claims."""

    __tablename__ = "cross_cloud_workload_bindings"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_cross_cloud_binding_org_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(300))
    spiffe_id: Mapped[str] = mapped_column(String(1000), index=True)
    aws_role_arn: Mapped[str] = mapped_column(Text, default="")
    azure_client_id: Mapped[str] = mapped_column(String(300), default="")
    azure_tenant_id: Mapped[str] = mapped_column(String(300), default="")
    audience: Mapped[str] = mapped_column(String(1000), default="")
    allowed_regions: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class TransparencyLogEntry(Base):
    """Organization-scoped append-only hash-chain transparency record."""

    __tablename__ = "transparency_log_entries"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "log_name", "sequence", name="uq_transparency_log_sequence"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    log_name: Mapped[str] = mapped_column(String(200), default="career-trust", index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    entry_type: Mapped[str] = mapped_column(String(100), index=True)
    subject_id: Mapped[str] = mapped_column(String(500), default="", index=True)
    payload_digest: Mapped[str] = mapped_column(String(64), index=True)
    previous_entry_hash: Mapped[str] = mapped_column(String(64), default="")
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    external_log_url: Mapped[str] = mapped_column(Text, default="")
    external_log_entry_id: Mapped[str] = mapped_column(String(500), default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class TrustContinuitySnapshot(Base):
    """Signed/digested trust snapshot used for controlled disaster recovery."""

    __tablename__ = "trust_continuity_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    region_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("deployment_regions.id", ondelete="SET NULL"), nullable=True
    )
    snapshot_version: Mapped[str] = mapped_column(String(100))
    snapshot_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    encrypted_snapshot: Mapped[str] = mapped_column(Text)
    signature: Mapped[str] = mapped_column(Text, default="")
    signing_key_id: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(50), default="sealed", index=True)
    transparency_entry_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("transparency_log_entries.id", ondelete="SET NULL"), nullable=True
    )
    approved_for_restore_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ModelGatewayPolicy(Base):
    """Organization policy for model access and retrieval boundaries."""

    __tablename__ = "model_gateway_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_model_gateway_policy_org_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(300))
    allowed_models: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_tasks: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_data_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    tools_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    require_signed_release: Mapped[bool] = mapped_column(Boolean, default=True)
    require_confidential_rag: Mapped[bool] = mapped_column(Boolean, default=True)
    block_injection_score: Mapped[int] = mapped_column(Integer, default=70)
    max_input_chars: Mapped[int] = mapped_column(Integer, default=50000)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=4000)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ModelRelease(Base):
    """Signed release manifest binding model, prompt, evaluation and policy versions."""

    __tablename__ = "model_releases"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "release_name", "version", name="uq_model_release_org_name_version"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    release_name: Mapped[str] = mapped_column(String(300), index=True)
    version: Mapped[str] = mapped_column(String(100))
    model_name: Mapped[str] = mapped_column(String(300), index=True)
    model_snapshot: Mapped[str] = mapped_column(String(300), default="")
    prompt_version: Mapped[str] = mapped_column(String(200))
    eval_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("model_eval_runs.id", ondelete="RESTRICT"), index=True
    )
    policy_digest: Mapped[str] = mapped_column(String(64))
    manifest_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    signature: Mapped[str] = mapped_column(Text, default="")
    signing_key_id: Mapped[str] = mapped_column(String(300), default="")
    release_status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    transparency_entry_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("transparency_log_entries.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentPermissionManifest(Base):
    """Explicit capabilities granted to a named autonomous-agent workflow."""

    __tablename__ = "agent_permission_manifests"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "agent_name", "version", name="uq_agent_manifest_org_name_version"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    agent_name: Mapped[str] = mapped_column(String(300), index=True)
    version: Mapped[str] = mapped_column(String(100))
    allowed_actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    denied_actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_data_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_destination_hosts: Mapped[list[str]] = mapped_column(JSON, default=list)
    max_external_calls: Mapped[int] = mapped_column(Integer, default=0)
    require_human_approval_actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    manifest_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentActionDecision(Base):
    """Auditable permission decision for an attempted agent action."""

    __tablename__ = "agent_action_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    manifest_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agent_permission_manifests.id", ondelete="SET NULL"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(300), index=True)
    action: Mapped[str] = mapped_column(String(200), index=True)
    destination_host: Mapped[str] = mapped_column(String(500), default="")
    data_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    decision: Mapped[str] = mapped_column(String(50), index=True)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PromptInjectionEvent(Base):
    """Detection record for untrusted content entering an AI context."""

    __tablename__ = "prompt_injection_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_type: Mapped[str] = mapped_column(String(100), index=True)
    source_id: Mapped[str] = mapped_column(String(500), default="")
    content_digest: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(50), index=True)
    indicators: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConfidentialRagAudit(Base):
    """Audit record for approved retrieval content supplied to the model gateway."""

    __tablename__ = "confidential_rag_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    query_digest: Mapped[str] = mapped_column(String(64), index=True)
    document_digests: Mapped[list[str]] = mapped_column(JSON, default=list)
    blocked_document_digests: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_release_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("model_releases.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
