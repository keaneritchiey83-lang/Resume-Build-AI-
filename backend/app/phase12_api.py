from __future__ import annotations

import hashlib

import httpx
import secrets
from pathlib import Path
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.config import settings
from app.db import get_session
from app.models import (
    ConfidentialInferenceAttestation,
    ConfidentialInferencePolicy,
    ContainmentPolicy,
    CredentialIssuerProfile,
    CredentialNegotiationPolicy,
    FederationEntityRecord,
    FederationTrustAnchor,
    HsmSigningKey,
    IncidentContainmentAction,
    RuntimeSecurityEvent,
    User,
    WalletAttestationTrustAnchor,
    WorkloadIdentityPolicy,
)
from app.phase12_schemas import (
    ConfidentialInferenceAttestationRequest,
    ConfidentialInferencePolicyRequest,
    ConfidentialInferenceRequest,
    ContainmentApprovalRequest,
    ContainmentPolicyRequest,
    CredentialNegotiationPolicyRequest,
    CredentialNegotiationRequest,
    CredentialNegotiationResponse,
    FederationEntityRequest,
    FederationTrustAnchorRequest,
    FederationValidationResponse,
    HsmSigningKeyApproval,
    HsmSigningKeyRequest,
    Phase12ReadinessResponse,
    RuntimeSecurityEventRequest,
    WalletAttestationTrustAnchorRequest,
    WalletAttestationVerifyRequest,
    WorkloadIdentityPolicyRequest,
)
from app.phase12_services import (
    ingest_runtime_event,
    invoke_confidential_inference,
    negotiate_credential_policy,
    purge_runtime_security_events,
    validate_federation_chain,
    verify_wallet_attestation,
    execute_containment_action,
)
from app.tenancy import require_org_role, require_platform_admin


router = APIRouter(prefix="/v1/phase12", tags=["phase12"])


def _reject_private_jwk(jwk_value: dict) -> None:
    private_names = {
        "d",
        "p",
        "q",
        "dp",
        "dq",
        "qi",
        "oth",
        "k",
    }

    if private_names.intersection(jwk_value):
        raise HTTPException(
            status_code=400,
            detail="Only a public JWK may be registered.",
        )


async def _org_admin(
    session: AsyncSession,
    user: User,
    organization_id: str,
) -> None:
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )


@router.get("/readiness", response_model=Phase12ReadinessResponse)
async def phase12_readiness(
    _: User = Depends(current_user),
):
    return Phase12ReadinessResponse(
        openid_federation_version="1.1 Final",
        spiffe_required=settings.phase12_spiffe_required,
        spiffe_endpoint_socket=settings.phase12_spiffe_endpoint_socket,
        spiffe_socket_available=Path(
            settings.phase12_spiffe_endpoint_socket.removeprefix("unix://")
        ).exists(),
        hsm_required=settings.phase12_require_hsm_signing,
        confidential_inference_configured=bool(
            settings.phase12_confidential_inference_url
        ),
        runtime_sensor_configured=bool(
            settings.phase12_runtime_sensor_token.get_secret_value()
        ),
        notes=[
            "Remote federation metadata never becomes trusted merely by resolving.",
            "HSM records contain key references/public keys only.",
            "Infrastructure isolation actions require an authorized controller.",
        ],
    )


@router.post("/federation/trust-anchors")
async def create_federation_anchor(
    payload: FederationTrustAnchorRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_platform_admin(user)
    _reject_private_jwk({"keys": []})

    for key in payload.jwks.get("keys", []):
        if isinstance(key, dict):
            _reject_private_jwk(key)

    record = FederationTrustAnchor(
        organization_id=payload.organization_id,
        entity_id=payload.entity_id.rstrip("/"),
        display_name=payload.display_name.strip(),
        jwks=payload.jwks,
        metadata_json=payload.metadata_json,
        metadata_policy=payload.metadata_policy,
        approved_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": record.id,
        "entity_id": record.entity_id,
        "enabled": record.enabled,
    }


@router.get("/federation/{organization_id}/trust-anchors")
async def list_federation_anchors(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter", "member"},
    )
    records = list(
        (
            await session.scalars(
                select(FederationTrustAnchor).where(
                    FederationTrustAnchor.organization_id == organization_id
                )
            )
        ).all()
    )
    return [
        {
            "id": row.id,
            "entity_id": row.entity_id,
            "display_name": row.display_name,
            "enabled": row.enabled,
        }
        for row in records
    ]


@router.post("/federation/entities")
async def create_federation_entity(
    payload: FederationEntityRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)

    for key in payload.jwks.get("keys", []):
        if isinstance(key, dict):
            _reject_private_jwk(key)

    record = FederationEntityRecord(
        organization_id=payload.organization_id,
        entity_id=payload.entity_id.rstrip("/"),
        entity_type=payload.entity_type,
        parent_entity_id=payload.parent_entity_id.rstrip("/"),
        jwks=payload.jwks,
        metadata_json=payload.metadata_json,
        metadata_policy=payload.metadata_policy,
        trust_marks=payload.trust_marks,
        self_statement_jwt=payload.self_statement_jwt,
        subordinate_statement_jwt=payload.subordinate_statement_jwt,
        trust_status="pending",
        created_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": record.id,
        "entity_id": record.entity_id,
        "trust_status": record.trust_status,
    }


@router.post(
    "/federation/{organization_id}/validate",
    response_model=FederationValidationResponse,
)
async def validate_federation_entity(
    organization_id: str,
    entity_id: str = Query(min_length=8, max_length=2000),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter", "member"},
    )

    try:
        return await validate_federation_chain(
            session,
            organization_id,
            entity_id.rstrip("/"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/wallet-attestation/trust-anchors")
async def create_wallet_attestation_anchor(
    payload: WalletAttestationTrustAnchorRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_platform_admin(user)
    record = WalletAttestationTrustAnchor(
        organization_id=payload.organization_id,
        name=payload.name.strip(),
        root_certificate_pem=payload.root_certificate_pem,
        allowed_subjects=payload.allowed_subjects,
        created_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": record.id,
        "name": record.name,
        "enabled": record.enabled,
    }


@router.post("/wallet-attestation/verify")
async def verify_wallet_attestation_endpoint(
    payload: WalletAttestationVerifyRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        payload.organization_id,
        {"owner", "admin", "recruiter", "member"},
    )

    try:
        evidence = await verify_wallet_attestation(
            session,
            organization_id=payload.organization_id,
            user_id=user.id,
            attestation_jwt=payload.attestation_jwt,
            expected_audience=payload.expected_audience,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "id": evidence.id,
        "verification_status": evidence.verification_status,
        "subject": evidence.subject,
        "issuer": evidence.issuer,
        "expires_at": evidence.expires_at,
    }


@router.post("/credential-policies")
async def create_credential_policy(
    payload: CredentialNegotiationPolicyRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)
    record = CredentialNegotiationPolicy(
        organization_id=payload.organization_id,
        name=payload.name.strip(),
        purpose=payload.purpose.strip(),
        accepted_formats=payload.accepted_formats,
        accepted_credential_types=payload.accepted_credential_types,
        required_claims=payload.required_claims,
        accepted_proof_algorithms=payload.accepted_proof_algorithms,
        required_trust_frameworks=payload.required_trust_frameworks,
        require_wallet_attestation=payload.require_wallet_attestation,
        require_hardware_backed_key=payload.require_hardware_backed_key,
        minimum_assurance_level=payload.minimum_assurance_level,
        created_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {"id": record.id, "name": record.name, "enabled": record.enabled}


@router.post(
    "/credential-policies/{policy_id}/negotiate",
    response_model=CredentialNegotiationResponse,
)
async def negotiate_policy(
    policy_id: str,
    payload: CredentialNegotiationRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    policy = await session.get(CredentialNegotiationPolicy, policy_id)

    if policy is None or not policy.enabled:
        raise HTTPException(status_code=404, detail="Credential policy not found.")

    await require_org_role(
        session,
        user,
        policy.organization_id,
        {"owner", "admin", "recruiter", "member"},
    )

    decision = await negotiate_credential_policy(
        session,
        policy=policy,
        user_id=user.id,
        capabilities=payload.model_dump(),
    )
    negotiated = decision.negotiated_json
    return CredentialNegotiationResponse(
        decision=decision.decision,
        reasons=decision.reasons,
        negotiated_formats=list(negotiated.get("formats", [])),
        negotiated_credential_types=list(
            negotiated.get("credential_types", [])
        ),
        negotiated_proof_algorithms=list(
            negotiated.get("proof_algorithms", [])
        ),
    )


@router.post("/hsm/keys")
async def register_hsm_key(
    payload: HsmSigningKeyRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)
    issuer = await session.get(CredentialIssuerProfile, payload.issuer_profile_id)

    if issuer is None or issuer.organization_id != payload.organization_id:
        raise HTTPException(status_code=404, detail="Issuer profile not found.")

    _reject_private_jwk(payload.public_jwk)
    record = HsmSigningKey(
        organization_id=payload.organization_id,
        issuer_profile_id=payload.issuer_profile_id,
        key_name=payload.key_name.strip(),
        provider=payload.provider,
        key_reference=payload.key_reference,
        algorithm=payload.algorithm,
        public_jwk=payload.public_jwk,
        active=False,
        approval_status="pending",
        created_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": record.id,
        "approval_status": record.approval_status,
        "active": record.active,
    }


@router.post("/hsm/keys/{key_id}/approve")
async def approve_hsm_key(
    key_id: str,
    payload: HsmSigningKeyApproval,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_platform_admin(user)
    record = await session.get(HsmSigningKey, key_id)

    if record is None:
        raise HTTPException(status_code=404, detail="HSM key not found.")

    record.approval_status = "approved" if payload.approved else "rejected"
    record.active = bool(payload.approved and payload.activate)
    record.approved_by_user_id = user.id

    if record.active:
        other_keys = list(
            (
                await session.scalars(
                    select(HsmSigningKey).where(
                        HsmSigningKey.issuer_profile_id == record.issuer_profile_id,
                        HsmSigningKey.id != record.id,
                        HsmSigningKey.active.is_(True),
                    )
                )
            ).all()
        )

        for other in other_keys:
            other.active = False
            other.rotated_at = datetime.now(UTC)

    await session.commit()
    return {
        "id": record.id,
        "approval_status": record.approval_status,
        "active": record.active,
    }


@router.post("/confidential-inference/policies")
async def create_confidential_inference_policy(
    payload: ConfidentialInferencePolicyRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)
    record = ConfidentialInferencePolicy(
        organization_id=payload.organization_id,
        name=payload.name.strip(),
        provider=payload.provider,
        allowed_measurements=payload.allowed_measurements,
        allowed_data_categories=payload.allowed_data_categories,
        require_attestation=payload.require_attestation,
        fail_closed=payload.fail_closed,
        created_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {"id": record.id, "enabled": record.enabled}


@router.post("/confidential-inference/attestations")
async def record_confidential_attestation(
    payload: ConfidentialInferenceAttestationRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_platform_admin(user)
    policy = await session.get(ConfidentialInferencePolicy, payload.policy_id)

    if policy is None:
        raise HTTPException(status_code=404, detail="Inference policy not found.")

    evidence_digest = hashlib.sha256(
        repr(sorted(payload.evidence.items())).encode("utf-8")
    ).hexdigest()
    record = ConfidentialInferenceAttestation(
        policy_id=payload.policy_id,
        measurement=payload.measurement,
        evidence_digest=evidence_digest,
        verified=payload.verified,
        metadata_json={
            "provider": policy.provider,
            "evidence_keys": sorted(payload.evidence.keys()),
        },
        expires_at=datetime.now(UTC)
        + timedelta(seconds=settings.phase12_confidential_attestation_max_age_seconds),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": record.id,
        "verified": record.verified,
        "expires_at": record.expires_at,
    }


@router.post("/confidential-inference/run")
async def run_confidential_inference(
    payload: ConfidentialInferenceRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    policy = await session.get(ConfidentialInferencePolicy, payload.policy_id)

    if policy is None:
        raise HTTPException(status_code=404, detail="Inference policy not found.")

    await require_org_role(
        session,
        user,
        policy.organization_id,
        {"owner", "admin", "recruiter", "member"},
    )

    try:
        return await invoke_confidential_inference(
            session,
            policy,
            task=payload.task,
            input_text=payload.input_text,
            data_categories=payload.data_categories,
        )
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=502 if isinstance(exc, httpx.HTTPError) else 422,
            detail=str(exc),
        ) from exc


@router.post("/workload-identity/policies")
async def create_workload_identity_policy(
    payload: WorkloadIdentityPolicyRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)

    if not payload.spiffe_id_pattern.startswith("spiffe://"):
        raise HTTPException(status_code=400, detail="SPIFFE ID pattern is invalid.")

    record = WorkloadIdentityPolicy(
        organization_id=payload.organization_id,
        name=payload.name.strip(),
        spiffe_id_pattern=payload.spiffe_id_pattern,
        namespace=payload.namespace,
        service_account=payload.service_account,
        allowed_peer_patterns=payload.allowed_peer_patterns,
        created_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {"id": record.id, "enabled": record.enabled}


@router.post("/containment/policies")
async def create_containment_policy(
    payload: ContainmentPolicyRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)
    record = ContainmentPolicy(
        organization_id=payload.organization_id,
        name=payload.name.strip(),
        minimum_severity=payload.minimum_severity,
        rule_patterns=payload.rule_patterns,
        actions=payload.actions,
        auto_execute_reversible=payload.auto_execute_reversible,
        created_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {"id": record.id, "enabled": record.enabled}


@router.post("/runtime/events")
async def runtime_event_ingest(
    payload: RuntimeSecurityEventRequest,
    x_runtime_sensor_token: str | None = Header(
        default=None,
        alias="X-Runtime-Sensor-Token",
    ),
    session: AsyncSession = Depends(get_session),
):
    expected = settings.phase12_runtime_sensor_token.get_secret_value()

    if (
        not expected
        or not x_runtime_sensor_token
        or not secrets.compare_digest(expected, x_runtime_sensor_token)
    ):
        raise HTTPException(status_code=401, detail="Invalid runtime sensor credential.")

    event = await ingest_runtime_event(
        session,
        payload.model_dump(),
    )
    return {
        "id": event.id,
        "status": event.status,
        "event_digest": event.event_digest,
    }


@router.get("/runtime/{organization_id}/events")
async def list_runtime_events(
    organization_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, organization_id)
    rows = list(
        (
            await session.scalars(
                select(RuntimeSecurityEvent)
                .where(RuntimeSecurityEvent.organization_id == organization_id)
                .order_by(RuntimeSecurityEvent.detected_at.desc())
                .limit(limit)
            )
        ).all()
    )
    return [
        {
            "id": row.id,
            "source": row.source,
            "severity": row.severity,
            "rule": row.rule,
            "workload": row.workload,
            "namespace": row.namespace,
            "status": row.status,
            "detected_at": row.detected_at,
        }
        for row in rows
    ]


@router.get("/runtime/events/{event_id}/actions")
async def list_containment_actions(
    event_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    event = await session.get(RuntimeSecurityEvent, event_id)

    if event is None or event.organization_id is None:
        raise HTTPException(status_code=404, detail="Runtime event not found.")

    await _org_admin(session, user, event.organization_id)
    rows = list(
        (
            await session.scalars(
                select(IncidentContainmentAction).where(
                    IncidentContainmentAction.event_id == event_id
                )
            )
        ).all()
    )
    return [
        {
            "id": row.id,
            "action": row.action,
            "status": row.status,
            "reversible": row.reversible,
            "requires_human_approval": row.requires_human_approval,
            "result": row.result_json,
        }
        for row in rows
    ]


@router.post("/runtime/actions/{action_id}/approve")
async def approve_containment_action(
    action_id: str,
    payload: ContainmentApprovalRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    action = await session.get(IncidentContainmentAction, action_id)

    if action is None:
        raise HTTPException(status_code=404, detail="Containment action not found.")

    event = await session.get(RuntimeSecurityEvent, action.event_id)

    if event is None or event.organization_id is None:
        raise HTTPException(status_code=404, detail="Runtime event not found.")

    await _org_admin(session, user, event.organization_id)

    if not payload.approved:
        action.status = "rejected"
        action.approved_by_user_id = user.id
        await session.commit()
        return {"id": action.id, "status": action.status}

    action.approved_by_user_id = user.id
    action.requires_human_approval = False
    await session.commit()

    try:
        action = await execute_containment_action(session, action)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "id": action.id,
        "status": action.status,
        "result": action.result_json,
    }
