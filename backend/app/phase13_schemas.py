from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class DeploymentRegionRequest(BaseModel):
    organization_id: str
    region_key: str = Field(min_length=2, max_length=200)
    display_name: str = Field(min_length=2, max_length=300)
    cloud_provider: Literal["aws", "azure", "gcp", "local", "other"]
    jurisdiction: str = Field(default="", max_length=100)
    spiffe_trust_domain: str = Field(min_length=3, max_length=500)
    federation_entity_id: str = Field(default="", max_length=2000)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RegionTrustLinkRequest(BaseModel):
    organization_id: str
    source_region_id: str
    peer_region_id: str
    peer_bundle_endpoint: HttpUrl | None = None
    peer_bundle_json: dict[str, Any] = Field(default_factory=dict)
    federation_anchor_entity_id: str = Field(default="", max_length=2000)


class CrossCloudWorkloadBindingRequest(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=300)
    spiffe_id: str = Field(min_length=9, max_length=1000)
    aws_role_arn: str = Field(default="", max_length=2000)
    azure_client_id: str = Field(default="", max_length=300)
    azure_tenant_id: str = Field(default="", max_length=300)
    audience: str = Field(default="", max_length=1000)
    allowed_regions: list[str] = Field(default_factory=list)


class TrustContinuitySnapshotRequest(BaseModel):
    organization_id: str
    region_id: str | None = None
    snapshot_version: str = Field(default="phase13-v1", max_length=100)


class RestoreApprovalRequest(BaseModel):
    approved: bool


class TransparencyAppendRequest(BaseModel):
    organization_id: str
    log_name: str = Field(default="career-trust", min_length=2, max_length=200)
    entry_type: str = Field(min_length=2, max_length=100)
    subject_id: str = Field(default="", max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)
    publish_external: bool = False


class ModelGatewayPolicyRequest(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=300)
    allowed_models: list[str] = Field(default_factory=list)
    allowed_tasks: list[str] = Field(default_factory=list)
    allowed_data_categories: list[str] = Field(default_factory=list)
    tools_allowed: bool = False
    require_signed_release: bool = True
    require_confidential_rag: bool = True
    block_injection_score: int = Field(default=70, ge=0, le=100)
    max_input_chars: int = Field(default=50_000, ge=1, le=200_000)
    max_output_tokens: int = Field(default=4_000, ge=1, le=16_000)


class ModelReleaseRequest(BaseModel):
    organization_id: str
    release_name: str = Field(min_length=2, max_length=300)
    version: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=300)
    model_snapshot: str = Field(default="", max_length=300)
    prompt_version: str = Field(min_length=1, max_length=200)
    eval_run_id: str
    policy_digest: str = Field(min_length=64, max_length=64)


class ModelReleaseApprovalRequest(BaseModel):
    approved: bool
    publish_transparency: bool = True


class AgentPermissionManifestRequest(BaseModel):
    organization_id: str
    agent_name: str = Field(min_length=2, max_length=300)
    version: str = Field(min_length=1, max_length=100)
    allowed_actions: list[str] = Field(default_factory=list)
    denied_actions: list[str] = Field(default_factory=list)
    allowed_data_categories: list[str] = Field(default_factory=list)
    allowed_destination_hosts: list[str] = Field(default_factory=list)
    max_external_calls: int = Field(default=0, ge=0, le=1000)
    require_human_approval_actions: list[str] = Field(default_factory=list)


class AgentManifestApprovalRequest(BaseModel):
    approved: bool
    activate: bool = False


class AgentActionCheckRequest(BaseModel):
    organization_id: str
    agent_name: str = Field(min_length=2, max_length=300)
    action: str = Field(min_length=1, max_length=200)
    destination_host: str = Field(default="", max_length=500)
    data_categories: list[str] = Field(default_factory=list)
    external_calls_used: int = Field(default=0, ge=0, le=100000)


class AgentActionCheckResponse(BaseModel):
    decision: Literal["allow", "deny", "review"]
    reasons: list[str]
    requires_human_approval: bool
    manifest_id: str | None = None


class PromptInjectionScanRequest(BaseModel):
    organization_id: str | None = None
    source_type: str = Field(default="manual", max_length=100)
    source_id: str = Field(default="", max_length=500)
    content: str = Field(min_length=1, max_length=200_000)


class PromptInjectionScanResponse(BaseModel):
    score: int
    decision: Literal["allow", "review", "block"]
    indicators: list[str]
    content_digest: str


class ModelGatewayRequest(BaseModel):
    organization_id: str
    policy_id: str
    task: str = Field(min_length=1, max_length=200)
    model: str = Field(min_length=1, max_length=300)
    prompt: str = Field(min_length=1, max_length=200_000)
    data_categories: list[str] = Field(default_factory=list)
    rag_query: str = Field(default="", max_length=10_000)


class ModelGatewayResponse(BaseModel):
    output_text: str
    model: str
    release_id: str | None = None
    rag_document_digests: list[str] = Field(default_factory=list)
    blocked_rag_document_digests: list[str] = Field(default_factory=list)
    injection_score: int
    warnings: list[str] = Field(default_factory=list)


class Phase13ReadinessResponse(BaseModel):
    phase: str
    region_id: str
    openid_federation_baseline: str
    spiffe_federation: bool
    transparency_log: bool
    external_transparency_configured: bool
    model_gateway: bool
    agent_manifest_required: bool
    notes: list[str]
