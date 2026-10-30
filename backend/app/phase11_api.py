from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, current_user, enforce_auth_rate_limit, normalize_email
from app.config import settings
from app.crypto import encrypt_text
from app.db import get_session
from app.models import (
    ConfidentialWorkloadAttestation,
    CredentialIssuerProfile,
    CredentialStatusAssignment,
    CredentialVerifierProfile,
    CryptoInventoryItem,
    DidTrustRegistryEntry,
    IssuedCredentialRecord,
    PasskeyCredential,
    User,
    WalletKeyAttestation,
)
from app.phase11_schemas import (
    BitstringListCreateRequest,
    ConfidentialAttestationRequest,
    CryptoInventoryRequest,
    DidResolutionResponse,
    DidTrustEntryRequest,
    HAIPAssessmentRequest,
    MdocVerifyRequest,
    PasskeyLoginFinish,
    PasskeyLoginOptionsRequest,
    PasskeyRegistrationFinish,
    StatusAssignmentRequest,
    StatusSetRequest,
    WalletKeyAttestationRequest,
)
from app.phase11_services import (
    assign_status_slot,
    begin_passkey_authentication,
    begin_passkey_registration,
    create_status_list,
    finish_passkey_authentication,
    finish_passkey_registration,
    haip_assessment,
    quantum_risk_for_algorithm,
    resolve_did,
    set_credential_status,
    status_list_credential,
    validate_did_document,
    verify_mdoc,
)
from app.tenancy import ensure_personal_organization, refresh_platform_admin, require_org_role, require_platform_admin


router = APIRouter(prefix="/v1/phase11", tags=["phase11"])


@router.post("/passkeys/register/options")
async def passkey_registration_options(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    challenge_id, options = await begin_passkey_registration(session, user)
    return {"challenge_id": challenge_id, "publicKey": options}


@router.post("/passkeys/register/finish")
async def passkey_registration_finish(
    payload: PasskeyRegistrationFinish,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await finish_passkey_registration(
        session,
        user,
        challenge_id=payload.challenge_id,
        credential=payload.credential,
        nickname=payload.nickname,
    )
    return {
        "id": record.id,
        "nickname": record.nickname,
        "device_type": record.device_type,
        "backed_up": record.backed_up,
    }


@router.get("/passkeys")
async def list_passkeys(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.scalars(
            select(PasskeyCredential).where(PasskeyCredential.user_id == user.id)
        )
    ).all()
    return [
        {
            "id": item.id,
            "nickname": item.nickname,
            "device_type": item.device_type,
            "backed_up": item.backed_up,
            "created_at": item.created_at,
            "last_used_at": item.last_used_at,
        }
        for item in rows
    ]


@router.delete("/passkeys/{passkey_id}")
async def delete_passkey(
    passkey_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.get(PasskeyCredential, passkey_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Passkey not found.")
    await session.delete(record)
    await session.commit()
    return {"deleted": True}


@router.post("/passkeys/login/options")
async def passkey_login_options(
    payload: PasskeyLoginOptionsRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    email = normalize_email(payload.email)
    client_host = request.client.host if request.client else "unknown"
    await enforce_auth_rate_limit(f"passkey:{client_host}:{email}")
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Passkey sign-in is unavailable.")
    challenge_id, options = await begin_passkey_authentication(session, user)
    return {"challenge_id": challenge_id, "publicKey": options}


@router.post("/passkeys/login/finish")
async def passkey_login_finish(
    payload: PasskeyLoginFinish,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    user = await finish_passkey_authentication(
        session,
        challenge_id=payload.challenge_id,
        credential=payload.credential,
    )
    if refresh_platform_admin(user):
        await session.commit()
    await ensure_personal_organization(session, user)

    response.set_cookie(
        "career_session",
        create_access_token(user.id),
        max_age=60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    import secrets
    response.set_cookie(
        "career_csrf",
        secrets.token_urlsafe(32),
        max_age=60 * 60,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return {
        "id": user.id,
        "email": user.email,
        "is_platform_admin": user.is_platform_admin,
        "mfa_enabled": user.mfa_enabled,
    }


@router.post("/organizations/{organization_id}/trust-registry/dids")
async def add_did_trust_entry(
    organization_id: str,
    payload: DidTrustEntryRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    validate_did_document(payload.did, payload.did_document)
    existing = await session.scalar(
        select(DidTrustRegistryEntry).where(
            DidTrustRegistryEntry.organization_id == organization_id,
            DidTrustRegistryEntry.did == payload.did,
        )
    )
    if existing:
        existing.did_document = payload.did_document
        existing.trust_status = payload.trust_status
        existing.notes = payload.notes
        existing.reviewed_by_user_id = user.id
        existing.reviewed_at = datetime.now(UTC)
        record = existing
    else:
        record = DidTrustRegistryEntry(
            organization_id=organization_id,
            did=payload.did,
            did_document=payload.did_document,
            trust_status=payload.trust_status,
            source="manual",
            notes=payload.notes,
            created_by_user_id=user.id,
            reviewed_by_user_id=user.id,
            reviewed_at=datetime.now(UTC),
        )
        session.add(record)
    await session.commit()
    await session.refresh(record)
    return {"id": record.id, "did": record.did, "trust_status": record.trust_status}


@router.get(
    "/organizations/{organization_id}/resolve-did",
    response_model=DidResolutionResponse,
)
async def resolve_did_endpoint(
    organization_id: str,
    did: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session, user, organization_id, {"owner", "admin", "recruiter", "member"}
    )
    document, source, trust_status = await resolve_did(session, organization_id, did)
    return DidResolutionResponse(
        did=did,
        did_document=document,
        source=source,
        trusted=trust_status == "trusted",
        trust_status=trust_status,
    )


@router.post("/wallet-key-attestations")
async def record_wallet_key_attestation(
    payload: WalletKeyAttestationRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if any(name in payload.public_jwk for name in ("d", "p", "q", "dp", "dq", "qi")):
        raise HTTPException(status_code=400, detail="Private key parameters are forbidden.")
    record = WalletKeyAttestation(
        user_id=user.id,
        holder_did=payload.holder_did,
        key_id=payload.key_id,
        public_jwk=payload.public_jwk,
        attestation_format=payload.attestation_format,
        hardware_backed_claim=payload.hardware_backed_claim,
        verification_status="pending",
        encrypted_attestation=encrypt_text(
            json.dumps(payload.attestation, separators=(",", ":"), sort_keys=True),
            aad=f"wallet-key-attestation:{user.id}:{payload.key_id}",
        ),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": record.id,
        "verification_status": record.verification_status,
        "hardware_backed_claim": record.hardware_backed_claim,
        "notice": "Hardware-backed status is a claim until its attestation is verified against an approved trust policy.",
    }


@router.post("/admin/wallet-key-attestations/{attestation_id}/{decision}")
async def review_wallet_attestation(
    attestation_id: str,
    decision: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_platform_admin(user)
    if decision not in {"verify", "reject"}:
        raise HTTPException(status_code=400, detail="Decision must be verify or reject.")
    record = await session.get(WalletKeyAttestation, attestation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Wallet key attestation not found.")
    record.verification_status = "verified" if decision == "verify" else "rejected"
    record.verified_at = datetime.now(UTC) if decision == "verify" else None
    await session.commit()
    return {"id": record.id, "verification_status": record.verification_status}


@router.post("/organizations/{organization_id}/status-lists")
async def create_status_list_endpoint(
    organization_id: str,
    payload: BitstringListCreateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    issuer = await session.get(CredentialIssuerProfile, payload.issuer_profile_id)
    if issuer is None or issuer.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Issuer profile not found.")
    if issuer.approval_status != "approved":
        raise HTTPException(status_code=409, detail="Issuer profile is not approved.")
    record = await create_status_list(
        session, issuer, payload.purpose, payload.capacity_bits
    )
    return {
        "id": record.id,
        "purpose": record.purpose,
        "capacity_bits": record.capacity_bits,
        "status_list_url": record.status_list_url,
    }


@router.post("/organizations/{organization_id}/credential-status/assign")
async def assign_credential_status(
    organization_id: str,
    payload: StatusAssignmentRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    credential = await session.get(IssuedCredentialRecord, payload.issued_credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Issued credential not found.")
    issuer = await session.get(CredentialIssuerProfile, credential.issuer_profile_id)
    if issuer is None or issuer.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Credential issuer is outside this organization.")
    assignment = await assign_status_slot(session, credential, issuer, payload.purpose)
    status_list = await session.get(__import__("app.models", fromlist=["BitstringStatusListRecord"]).BitstringStatusListRecord, assignment.status_list_id)
    return {
        "assignment_id": assignment.id,
        "statusListIndex": str(assignment.status_index),
        "statusListCredential": status_list.status_list_url if status_list else "",
        "statusPurpose": assignment.purpose,
        "type": "BitstringStatusListEntry",
    }


@router.post("/organizations/{organization_id}/credential-status/{assignment_id}")
async def set_credential_status_endpoint(
    organization_id: str,
    assignment_id: str,
    payload: StatusSetRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    assignment = await session.get(CredentialStatusAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Status assignment not found.")
    credential = await session.get(IssuedCredentialRecord, assignment.issued_credential_id)
    issuer = await session.get(CredentialIssuerProfile, credential.issuer_profile_id) if credential else None
    if issuer is None or issuer.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Status assignment is outside this organization.")
    await set_credential_status(session, assignment, payload.value)
    return {"id": assignment.id, "set": payload.value}


@router.get("/status-lists/{list_id}")
async def public_status_list(
    list_id: str,
    session: AsyncSession = Depends(get_session),
):
    from app.models import BitstringStatusListRecord
    record = await session.get(BitstringStatusListRecord, list_id)
    if record is None:
        # Also permit the public slug form generated by create_status_list.
        rows = (await session.scalars(select(BitstringStatusListRecord))).all()
        record = next(
            (item for item in rows if item.status_list_url.rstrip("/").endswith("/" + list_id)),
            None,
        )
    if record is None:
        raise HTTPException(status_code=404, detail="Status list not found.")
    issuer = await session.get(CredentialIssuerProfile, record.issuer_profile_id)
    if issuer is None or issuer.approval_status != "approved":
        raise HTTPException(status_code=404, detail="Status list issuer is unavailable.")
    return status_list_credential(record, issuer.issuer_identifier)


@router.post("/mdoc/verify")
async def verify_mdoc_endpoint(
    payload: MdocVerifyRequest,
    _: User = Depends(current_user),
):
    return await verify_mdoc(payload.device_response_b64, payload.expected_doc_type)


@router.post("/organizations/{organization_id}/haip-assessment")
async def assess_haip(
    organization_id: str,
    payload: HAIPAssessmentRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    issuer = (
        await session.get(CredentialIssuerProfile, payload.issuer_profile_id)
        if payload.issuer_profile_id
        else None
    )
    verifier = (
        await session.get(CredentialVerifierProfile, payload.verifier_profile_id)
        if payload.verifier_profile_id
        else None
    )
    if issuer and issuer.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Issuer profile not found.")
    if verifier and verifier.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Verifier profile not found.")
    return haip_assessment(issuer, verifier)


@router.post("/organizations/{organization_id}/crypto-inventory")
async def upsert_crypto_inventory(
    organization_id: str,
    payload: CryptoInventoryRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    risk, recommendation = quantum_risk_for_algorithm(payload.current_algorithm)
    existing = await session.scalar(
        select(CryptoInventoryItem).where(
            CryptoInventoryItem.organization_id == organization_id,
            CryptoInventoryItem.component == payload.component,
            CryptoInventoryItem.usage == payload.usage,
        )
    )
    if existing:
        record = existing
        record.current_algorithm = payload.current_algorithm
        record.target_standard = payload.target_standard
        record.migration_status = payload.migration_status
        record.notes = payload.notes
        record.quantum_risk = risk
    else:
        record = CryptoInventoryItem(
            organization_id=organization_id,
            component=payload.component,
            usage=payload.usage,
            current_algorithm=payload.current_algorithm,
            quantum_risk=risk,
            target_standard=payload.target_standard,
            migration_status=payload.migration_status,
            notes=payload.notes,
        )
        session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": record.id,
        "quantum_risk": risk,
        "recommendation": recommendation,
        "target_standard": record.target_standard,
        "migration_status": record.migration_status,
    }


@router.get("/organizations/{organization_id}/crypto-inventory")
async def list_crypto_inventory(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    rows = (
        await session.scalars(
            select(CryptoInventoryItem).where(
                CryptoInventoryItem.organization_id == organization_id
            )
        )
    ).all()
    return [
        {
            "id": item.id,
            "component": item.component,
            "usage": item.usage,
            "current_algorithm": item.current_algorithm,
            "quantum_risk": item.quantum_risk,
            "target_standard": item.target_standard,
            "migration_status": item.migration_status,
            "notes": item.notes,
        }
        for item in rows
    ]


@router.post("/organizations/{organization_id}/confidential-attestations")
async def record_confidential_attestation(
    organization_id: str,
    payload: ConfidentialAttestationRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    serialized = json.dumps(payload.evidence, sort_keys=True, separators=(",", ":"))
    record = ConfidentialWorkloadAttestation(
        organization_id=organization_id,
        workload_name=payload.workload_name,
        provider=payload.provider,
        measurement=payload.measurement,
        verification_status=payload.verification_status,
        evidence_digest=hashlib.sha256(serialized.encode()).hexdigest(),
        metadata_json={
            "notice": "Only the evidence digest and non-secret metadata are retained.",
        },
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": record.id,
        "verification_status": record.verification_status,
        "evidence_digest": record.evidence_digest,
    }


@router.get("/security/readiness")
async def security_readiness(_: User = Depends(current_user)):
    return {
        "webauthn_level": "WebAuthn Level 3",
        "did_resolution": "W3C DID Resolution v1 Candidate Recommendation Snapshot; static trust registry + allowlisted did:web only",
        "bitstring_status_list": "W3C Recommendation 2025",
        "haip": "OpenID4VC HAIP 1.0 Final; static readiness checks only, no certification claim",
        "mdoc": "mso_mdoc negotiation + configurable cryptographic verifier; structural fallback is manual_required",
        "pqc": {
            "standards": ["FIPS 203 ML-KEM", "FIPS 204 ML-DSA", "FIPS 205 SLH-DSA"],
            "mode": "inventory_and_migration_planning",
            "notice": "Do not replace protocol algorithms until the relevant protocol/ecosystem supports the PQC transition.",
        },
        "supply_chain": "SBOM + GitHub/Sigstore artifact attestations + image scanning workflow",
        "confidential_computing": "opt-in workload manifests and evidence recording; deployment-specific attestation remains required",
    }
