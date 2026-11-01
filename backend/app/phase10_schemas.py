from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class IssuerProfileCreateRequest(BaseModel):
    organization_id: str
    slug: str = Field(min_length=2, max_length=200)
    display_name: str = Field(min_length=2, max_length=500)


class IssuerProfileResponse(BaseModel):
    id: str
    organization_id: str
    slug: str
    issuer_identifier: str
    display_name: str
    approval_status: str
    signing_alg: str
    public_jwk: dict[str, Any]
    created_at: datetime


class CredentialConfigurationRequest(BaseModel):
    configuration_id: str = Field(min_length=2, max_length=300)
    credential_format: Literal["jwt_vc_json", "dc+sd-jwt"]
    credential_type: str = Field(min_length=2, max_length=500)
    vct: str = Field(default="", max_length=2000)
    scope: str = Field(default="", max_length=300)
    claim_names: list[
        Literal[
            "full_name",
            "summary",
            "skills",
            "abilities",
            "core_values",
            "education",
            "certifications",
            "verified_credentials",
            "skills_passport",
        ]
    ] = Field(default_factory=list)
    selective_claims: list[str] = Field(default_factory=list, max_length=100)
    display: dict[str, Any] = Field(default_factory=dict)
    require_holder_binding: bool = True
    active: bool = True


class WalletClientRegistrationRequest(BaseModel):
    client_id: str = Field(min_length=3, max_length=500)
    display_name: str = Field(min_length=2, max_length=500)
    redirect_uris: list[HttpUrl] = Field(min_length=1, max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CredentialOfferRequest(BaseModel):
    configuration_id: str = Field(min_length=2, max_length=300)
    subject_user_id: str | None = None
    transaction_code_required: bool = False
    expires_in_seconds: int = Field(default=600, ge=60, le=3600)


class CredentialOfferResponse(BaseModel):
    offer_id: str
    credential_offer: dict[str, Any]
    credential_offer_uri: str
    transaction_code: str | None
    expires_at: datetime


class CredentialProofs(BaseModel):
    jwt: list[str] = Field(default_factory=list, max_length=10)


class CredentialRequest(BaseModel):
    credential_configuration_id: str = Field(min_length=2, max_length=300)
    proofs: CredentialProofs | None = None


class CredentialIssueResponse(BaseModel):
    credentials: list[dict[str, Any]]
    notification_id: str | None = None


class CredentialRevokeRequest(BaseModel):
    reason: str = Field(default="", max_length=2000)


class VerifierProfileCreateRequest(BaseModel):
    organization_id: str
    slug: str = Field(min_length=2, max_length=200)
    display_name: str = Field(min_length=2, max_length=500)


class VerifierProfileResponse(BaseModel):
    id: str
    organization_id: str
    slug: str
    display_name: str
    client_id: str
    response_uri: str
    approval_status: str
    vp_formats_supported: dict[str, Any]
    created_at: datetime


class TrustAnchorRequest(BaseModel):
    issuer_identifier: str = Field(min_length=3, max_length=2000)
    public_jwk: dict[str, Any]
    allowed_formats: list[
        Literal["jwt_vc_json", "dc+sd-jwt"]
    ] = Field(default_factory=lambda: ["jwt_vc_json", "dc+sd-jwt"])
    metadata: dict[str, Any] = Field(default_factory=dict)


class PresentationRequestCreate(BaseModel):
    dcql_query: dict[str, Any]
    expires_in_seconds: int = Field(default=300, ge=60, le=900)


class PresentationRequestResponse(BaseModel):
    request_id: str
    request_uri: str
    authorization_request: dict[str, Any]
    wallet_invocation_uri: str
    expires_at: datetime


class PresentationResultResponse(BaseModel):
    id: str
    request_id: str
    verification_status: str
    holder_identifier: str
    issuer_identifiers: list[str]
    disclosed_claims: dict[str, Any]
    created_at: datetime


class ConsentReceiptRequest(BaseModel):
    organization_id: str | None = None
    purpose: str = Field(min_length=2, max_length=200)
    action: Literal["grant", "revoke"]
    policy_version: str = Field(min_length=1, max_length=100)
    lawful_basis: str = Field(default="consent", max_length=200)
    processing_purposes: list[str] = Field(default_factory=list, max_length=50)
    data_categories: list[str] = Field(default_factory=list, max_length=100)


class ConsentReceiptResponse(BaseModel):
    id: str
    purpose: str
    action: str
    policy_version: str
    receipt_hash: str
    previous_receipt_hash: str
    occurred_at: datetime


class ClassificationRuleRequest(BaseModel):
    rule_key: str = Field(min_length=2, max_length=200)
    field_pattern: str = Field(min_length=1, max_length=500)
    classification: Literal[
        "direct_identifier",
        "contact",
        "authentication",
        "credential",
        "career_profile",
        "employment",
        "financial",
        "location",
        "sensitive",
        "security_secret",
        "audit",
        "operational",
    ]
    sensitivity: Literal["public", "internal", "confidential", "restricted"]
    enabled: bool = True


class DiscoveryScanResponse(BaseModel):
    id: str
    organization_id: str
    status: str
    finding_count: int
    findings: list[dict[str, Any]]
    started_at: datetime
    completed_at: datetime | None


class DeletionPlanRequest(BaseModel):
    dsar_id: str | None = None
    dry_run: bool = True


class DeletionWorkflowResponse(BaseModel):
    id: str
    status: str
    dry_run: bool
    legal_hold_blocked: bool
    steps: list[dict[str, Any]]
    requested_at: datetime
    completed_at: datetime | None


class PrivacyAnalyticsRequest(BaseModel):
    metric: Literal[
        "applications_total",
        "job_recommendations_total",
        "inbound_candidates_total",
    ]
    day: date
    epsilon: float = Field(default=0.5, gt=0.0, le=1.0)
    minimum_group_size: int = Field(default=20, ge=5, le=1000)


class PrivacyAnalyticsResponse(BaseModel):
    metric: str
    day: date
    epsilon: float
    minimum_group_size: int
    value: float | None
    suppressed: bool
    remaining_daily_epsilon: float
    disclaimer: str


class AuditLedgerAppendRequest(BaseModel):
    organization_id: str | None = None
    event_type: str = Field(min_length=2, max_length=200)
    subject_type: str = Field(default="", max_length=200)
    subject_id: str = Field(default="", max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditLedgerEntryResponse(BaseModel):
    id: str
    organization_id: str | None
    sequence: int
    event_type: str
    actor: str
    subject_type: str
    subject_id: str
    payload_digest: str
    previous_hash: str
    entry_hash: str
    signature: str
    signing_key_id: str
    created_at: datetime


class AuditLedgerVerifyResponse(BaseModel):
    organization_id: str | None
    valid: bool
    entries_checked: int
    first_invalid_sequence: int | None
    signed_entries: int
    unsigned_entries: int
