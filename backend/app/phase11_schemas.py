from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PasskeyRegistrationFinish(BaseModel):
    challenge_id: str
    credential: dict[str, Any]
    nickname: str = Field(default="", max_length=300)


class PasskeyLoginOptionsRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PasskeyLoginFinish(BaseModel):
    challenge_id: str
    credential: dict[str, Any]


class DidTrustEntryRequest(BaseModel):
    did: str = Field(min_length=7, max_length=2000)
    did_document: dict[str, Any]
    trust_status: Literal["pending", "trusted", "blocked"] = "pending"
    notes: str = Field(default="", max_length=4000)


class DidResolutionResponse(BaseModel):
    did: str
    did_document: dict[str, Any]
    source: str
    trusted: bool
    trust_status: str


class WalletKeyAttestationRequest(BaseModel):
    holder_did: str = Field(default="", max_length=2000)
    key_id: str = Field(min_length=1, max_length=2000)
    public_jwk: dict[str, Any]
    attestation_format: str = Field(default="", max_length=100)
    hardware_backed_claim: bool = False
    attestation: dict[str, Any] = Field(default_factory=dict)


class BitstringListCreateRequest(BaseModel):
    issuer_profile_id: str
    purpose: Literal["revocation", "suspension"] = "revocation"
    capacity_bits: int = Field(default=131072, ge=131072, le=8_388_608)


class StatusAssignmentRequest(BaseModel):
    issued_credential_id: str
    purpose: Literal["revocation", "suspension"] = "revocation"


class StatusSetRequest(BaseModel):
    value: bool


class MdocVerifyRequest(BaseModel):
    device_response_b64: str = Field(min_length=4, max_length=4_000_000)
    expected_doc_type: str = Field(default="", max_length=500)


class HAIPAssessmentRequest(BaseModel):
    issuer_profile_id: str | None = None
    verifier_profile_id: str | None = None


class CryptoInventoryRequest(BaseModel):
    component: str = Field(min_length=2, max_length=300)
    usage: str = Field(min_length=2, max_length=300)
    current_algorithm: str = Field(min_length=2, max_length=200)
    target_standard: str = Field(default="", max_length=200)
    migration_status: Literal["inventory", "planned", "testing", "migrated", "exception"] = "inventory"
    notes: str = Field(default="", max_length=4000)


class ConfidentialAttestationRequest(BaseModel):
    workload_name: str = Field(min_length=2, max_length=300)
    provider: Literal["aws_nitro", "azure_confidential", "other"]
    measurement: str = Field(default="", max_length=4000)
    verification_status: Literal["unverified", "verified", "failed"] = "unverified"
    evidence: dict[str, Any] = Field(default_factory=dict)
