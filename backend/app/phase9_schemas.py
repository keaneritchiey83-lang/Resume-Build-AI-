from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class WalletRegistrationRequest(BaseModel):
    holder_did: str = Field(min_length=7, max_length=2000)
    wallet_type: Literal["external", "openid4vc", "manual"] = "external"
    presentation_endpoint: HttpUrl | None = None
    issuance_endpoint: HttpUrl | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WalletRegistrationResponse(BaseModel):
    id: str
    holder_did: str
    did_method: str
    wallet_type: str
    presentation_endpoint: str
    issuance_endpoint: str
    verification_status: str
    metadata: dict[str, Any]
    created_at: datetime


class SkillsPassportRequest(BaseModel):
    title: str = Field(default="Career Skills Passport", min_length=2, max_length=300)
    include_profile_summary: bool = True
    include_experience: bool = True
    include_education: bool = True
    include_verified_credentials: bool = True
    include_unverified_credentials: bool = False
    include_contact: bool = False
    include_portfolio: bool = True


class SkillsPassportResponse(BaseModel):
    id: str
    version: int
    holder_did: str
    passport: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PortableCareerRecordResponse(BaseModel):
    format: str
    verification_status: str
    record: dict[str, Any]
    sha256: str


class EducationCareerPathwayRequest(BaseModel):
    occupation_code: str = Field(min_length=1, max_length=100)
    occupation_title: str = Field(min_length=1, max_length=1000)
    country_code: str = Field(default="", max_length=3)
    target_skills: list[str] = Field(default_factory=list, max_length=100)
    max_items: int = Field(default=20, ge=1, le=100)


class EducationCareerPathwayResponse(BaseModel):
    occupation_code: str
    occupation_title: str
    existing_skills: list[str]
    verified_skills: list[str]
    gaps: list[str]
    learning_options: list[dict[str, Any]]
    portable_evidence: list[dict[str, Any]]
    disclaimer: str


class PrivacyImpactAssessmentRequest(BaseModel):
    name: str = Field(min_length=2, max_length=500)
    system_or_process: str = Field(min_length=2, max_length=500)
    processing_purposes: list[str] = Field(default_factory=list, max_length=50)
    data_categories: list[str] = Field(default_factory=list, max_length=100)
    data_subjects: list[str] = Field(default_factory=list, max_length=50)
    jurisdictions: list[str] = Field(default_factory=list, max_length=50)
    lawful_bases: list[str] = Field(default_factory=list, max_length=50)
    recipients: list[str] = Field(default_factory=list, max_length=50)
    retention_summary: str = Field(default="", max_length=5000)
    international_transfers: bool = False
    automated_decision_support: bool = False
    high_risk_processing: bool = False
    mitigations: list[str] = Field(default_factory=list, max_length=100)


class PrivacyImpactAssessmentResponse(BaseModel):
    id: str
    name: str
    system_or_process: str
    status: str
    risk_level: str
    processing_purposes: list[str]
    data_categories: list[str]
    jurisdictions: list[str]
    automated_decision_support: bool
    high_risk_processing: bool
    review_due_at: datetime
    created_at: datetime




class PrivacyImpactAssessmentUpdate(BaseModel):
    status: Literal["draft", "in_review", "approved", "retired"]
    mitigations: list[str] | None = Field(default=None, max_length=100)
    review_due_at: datetime | None = None

class DataAssetRequest(BaseModel):
    asset_key: str = Field(min_length=2, max_length=200)
    name: str = Field(min_length=2, max_length=500)
    asset_type: Literal["database", "table", "object_store", "api", "model_input", "model_output", "log", "export"]
    data_categories: list[str] = Field(default_factory=list, max_length=100)
    contains_personal_data: bool = False
    contains_sensitive_data: bool = False
    system_owner: str = Field(default="", max_length=500)
    retention_class: str = Field(default="", max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataLineageEdgeRequest(BaseModel):
    upstream_asset_key: str = Field(min_length=2, max_length=200)
    downstream_asset_key: str = Field(min_length=2, max_length=200)
    transformation: str = Field(min_length=2, max_length=2000)
    purpose: str = Field(min_length=2, max_length=2000)


class RetentionPolicyRequest(BaseModel):
    record_type: Literal[
        "webhook_events",
        "inbound_candidates",
        "resume_documents",
        "career_recommendations",
        "agent_runs",
        "portfolio_shares",
        "audit_events",
        "red_team_runs",
    ]
    retention_days: int = Field(ge=1, le=3650)
    legal_hold: bool = False
    enabled: bool = True
    reason: str = Field(default="", max_length=2000)


class DSARCreateRequest(BaseModel):
    request_type: Literal[
        "access",
        "portability",
        "rectification",
        "erasure",
        "restriction",
        "objection",
    ]
    details: str = Field(default="", max_length=10_000)


class DSARResponse(BaseModel):
    id: str
    request_type: str
    status: str
    identity_verified: bool
    submitted_at: datetime
    due_at: datetime
    completed_at: datetime | None
    result_available: bool
    notes: str


class DSARStatusUpdate(BaseModel):
    status: Literal["received", "identity_check", "in_progress", "completed", "denied"]
    identity_verified: bool | None = None
    execution_confirmed: bool = False
    notes: str = Field(default="", max_length=5000)


class RedTeamCampaignRequest(BaseModel):
    name: str = Field(min_length=2, max_length=500)
    inventory_id: str | None = None
    scope: list[
        Literal[
            "prompt_injection",
            "protected_trait_ranking",
            "credential_fabrication",
            "autonomous_apply",
            "data_exfiltration",
            "cross_tenant_access",
            "unsupported_metrics",
        ]
    ] = Field(default_factory=lambda: [
        "prompt_injection",
        "protected_trait_ranking",
        "credential_fabrication",
        "autonomous_apply",
        "data_exfiltration",
    ])
    notes: str = Field(default="", max_length=5000)


class RedTeamCampaignResponse(BaseModel):
    id: str
    name: str
    status: str
    scope: list[str]
    total_tests: int
    passed_tests: int
    failed_tests: int
    findings: list[dict[str, Any]]
    created_at: datetime
    completed_at: datetime | None


class ContinuousControlResponse(BaseModel):
    organization_id: str
    generated_at: datetime
    overall_status: str
    checks: list[dict[str, Any]]
    open_findings: int
