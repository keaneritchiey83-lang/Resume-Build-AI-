
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class FederationTrustAnchorRequest(BaseModel):
    organization_id: str
    entity_id: str = Field(min_length=8, max_length=2000)
    display_name: str = Field(default="", max_length=500)
    jwks: dict[str, Any]
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    metadata_policy: dict[str, Any] = Field(default_factory=dict)


class FederationEntityRequest(BaseModel):
    organization_id: str
    entity_id: str = Field(min_length=8, max_length=2000)
    entity_type: str = Field(default="federation_entity", max_length=100)
    parent_entity_id: str = Field(default="", max_length=2000)
    jwks: dict[str, Any]
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    metadata_policy: dict[str, Any] = Field(default_factory=dict)
    trust_marks: list[dict[str, Any]] = Field(default_factory=list)
    self_statement_jwt: str = Field(default="", max_length=500_000)
    subordinate_statement_jwt: str = Field(default="", max_length=500_000)


class FederationValidationResponse(BaseModel):
    trusted: bool
    anchor_entity_id: str = ""
    path: list[str]
    reasons: list[str]
    effective_metadata: dict[str, Any] = Field(default_factory=dict)


class WalletAttestationTrustAnchorRequest(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=300)
    root_certificate_pem: str = Field(min_length=100, max_length=100_000)
    allowed_subjects: list[str] = Field(default_factory=list)


class WalletAttestationVerifyRequest(BaseModel):
    organization_id: str
    attestation_jwt: str = Field(min_length=10, max_length=1_000_000)
    expected_audience: str = Field(default="", max_length=2000)


class CredentialNegotiationPolicyRequest(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=300)
    purpose: str = Field(default="", max_length=300)
    accepted_formats: list[str] = Field(default_factory=lambda: ["dc+sd-jwt", "jwt_vc_json"])
    accepted_credential_types: list[str] = Field(default_factory=list)
    required_claims: list[str] = Field(default_factory=list)
    accepted_proof_algorithms: list[str] = Field(default_factory=lambda: ["ES256"])
    required_trust_frameworks: list[str] = Field(default_factory=list)
    require_wallet_attestation: bool = False
    require_hardware_backed_key: bool = False
    minimum_assurance_level: str = Field(default="", max_length=100)


class CredentialNegotiationRequest(BaseModel):
    formats: list[str] = Field(default_factory=list)
    credential_types: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    proof_algorithms: list[str] = Field(default_factory=list)
    trust_frameworks: list[str] = Field(default_factory=list)
    federation_entity_id: str = Field(default="", max_length=2000)
    assurance_level: str = Field(default="", max_length=100)
    wallet_attestation_evidence_id: str | None = None
    wallet_key_attestation_id: str | None = None


class CredentialNegotiationResponse(BaseModel):
    decision: Literal["allow", "deny", "review"]
    reasons: list[str]
    negotiated_formats: list[str]
    negotiated_credential_types: list[str]
    negotiated_proof_algorithms: list[str]


class HsmSigningKeyRequest(BaseModel):
    organization_id: str
    issuer_profile_id: str
    key_name: str = Field(min_length=2, max_length=300)
    provider: Literal["aws_kms", "azure_hsm"]
    key_reference: str = Field(min_length=5, max_length=4000)
    algorithm: Literal["ES256"] = "ES256"
    public_jwk: dict[str, Any]


class HsmSigningKeyApproval(BaseModel):
    approved: bool
    activate: bool = False


class ConfidentialInferencePolicyRequest(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=300)
    provider: Literal["aws_nitro", "azure_confidential", "nvidia_confidential", "other"]
    allowed_measurements: list[str] = Field(default_factory=list)
    allowed_data_categories: list[str] = Field(default_factory=list)
    require_attestation: bool = True
    fail_closed: bool = True


class ConfidentialInferenceAttestationRequest(BaseModel):
    policy_id: str
    measurement: str = Field(min_length=1, max_length=8000)
    evidence: dict[str, Any] = Field(default_factory=dict)
    verified: bool = False


class ConfidentialInferenceRequest(BaseModel):
    policy_id: str
    task: str = Field(min_length=2, max_length=200)
    input_text: str = Field(min_length=1, max_length=50_000)
    data_categories: list[str] = Field(default_factory=list)


class WorkloadIdentityPolicyRequest(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=300)
    spiffe_id_pattern: str = Field(min_length=8, max_length=1000)
    namespace: str = Field(default="", max_length=300)
    service_account: str = Field(default="", max_length=300)
    allowed_peer_patterns: list[str] = Field(default_factory=list)


class RuntimeSecurityEventRequest(BaseModel):
    organization_id: str | None = None
    source: Literal["falco", "tetragon", "cloud_runtime", "other"]
    severity: Literal["debug", "info", "notice", "warning", "error", "critical"]
    rule: str = Field(min_length=2, max_length=500)
    workload: str = Field(default="", max_length=500)
    namespace: str = Field(default="", max_length=300)
    details: dict[str, Any] = Field(default_factory=dict)


class ContainmentPolicyRequest(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=300)
    minimum_severity: Literal["notice", "warning", "error", "critical"] = "critical"
    rule_patterns: list[str] = Field(default_factory=list)
    actions: list[
        Literal[
            "disable_provider_integrations",
            "pause_career_agents",
            "request_network_quarantine",
            "request_workload_isolation",
        ]
    ] = Field(default_factory=list)
    auto_execute_reversible: bool = False


class ContainmentApprovalRequest(BaseModel):
    approved: bool


class Phase12ReadinessResponse(BaseModel):
    openid_federation_version: str
    spiffe_required: bool
    spiffe_endpoint_socket: str
    spiffe_socket_available: bool
    hsm_required: bool
    confidential_inference_configured: bool
    runtime_sensor_configured: bool
    notes: list[str]
