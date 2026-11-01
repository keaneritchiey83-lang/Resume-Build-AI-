from __future__ import annotations

import json
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.config import settings
from app.db import get_session
from app.models import (
    CredentialIssuerProfile,
    CredentialVerifierProfile,
    DeletionWorkflow,
    IssuedCredentialRecord,
    PresentationRequestRecord,
    PresentationSubmission,
    User,
)
from app.phase10_schemas import (
    AuditLedgerAppendRequest,
    AuditLedgerEntryResponse,
    AuditLedgerVerifyResponse,
    ClassificationRuleRequest,
    ConsentReceiptRequest,
    ConsentReceiptResponse,
    CredentialConfigurationRequest,
    CredentialIssueResponse,
    CredentialOfferRequest,
    CredentialOfferResponse,
    CredentialRequest,
    CredentialRevokeRequest,
    DeletionPlanRequest,
    DeletionWorkflowResponse,
    DiscoveryScanResponse,
    IssuerProfileCreateRequest,
    IssuerProfileResponse,
    PresentationRequestCreate,
    PresentationRequestResponse,
    PresentationResultResponse,
    PrivacyAnalyticsRequest,
    PrivacyAnalyticsResponse,
    TrustAnchorRequest,
    VerifierProfileCreateRequest,
    VerifierProfileResponse,
    WalletClientRegistrationRequest,
)
from app.phase10_services import (
    access_token_record,
    append_crypto_audit,
    approve_issuer_profile,
    approve_verifier_profile,
    authorization_server_metadata,
    authorize_wallet,
    create_credential_offer,
    create_issuer_profile,
    create_presentation_request,
    create_verifier_profile,
    discovery_findings,
    execute_deletion,
    issue_credential,
    issue_nonce,
    issuer_metadata,
    plan_deletion,
    presentation_request_object,
    presentation_result,
    privacy_preserving_release,
    record_consent_receipt,
    redeem_authorization_code,
    redeem_pre_authorized_code,
    register_wallet_client,
    revoke_issued_credential,
    run_data_discovery,
    upsert_classification_rule,
    upsert_credential_configuration,
    upsert_trust_anchor,
    verify_crypto_audit_chain,
    verify_presentation_response,
)
from app.tenancy import require_org_role, require_platform_admin


router = APIRouter(tags=["phase10"])


async def _issuer_by_slug(
    session: AsyncSession,
    slug: str,
    *,
    approved: bool = True,
) -> CredentialIssuerProfile:
    statement = select(CredentialIssuerProfile).where(
        CredentialIssuerProfile.slug == slug
    )

    if approved:
        statement = statement.where(
            CredentialIssuerProfile.approval_status == "approved"
        )

    issuer = await session.scalar(statement)

    if issuer is None:
        raise HTTPException(status_code=404, detail="Credential issuer not found.")

    return issuer


async def _verifier_by_slug(
    session: AsyncSession,
    slug: str,
    *,
    approved: bool = True,
) -> CredentialVerifierProfile:
    statement = select(CredentialVerifierProfile).where(
        CredentialVerifierProfile.slug == slug
    )

    if approved:
        statement = statement.where(
            CredentialVerifierProfile.approval_status == "approved"
        )

    verifier = await session.scalar(statement)

    if verifier is None:
        raise HTTPException(status_code=404, detail="Credential verifier not found.")

    return verifier


def _issuer_response(record: CredentialIssuerProfile) -> IssuerProfileResponse:
    return IssuerProfileResponse(
        id=record.id,
        organization_id=record.organization_id,
        slug=record.slug,
        issuer_identifier=record.issuer_identifier,
        display_name=record.display_name,
        approval_status=record.approval_status,
        signing_alg=record.signing_alg,
        public_jwk=dict(record.public_jwk),
        created_at=record.created_at,
    )


def _verifier_response(
    record: CredentialVerifierProfile,
) -> VerifierProfileResponse:
    return VerifierProfileResponse(
        id=record.id,
        organization_id=record.organization_id,
        slug=record.slug,
        display_name=record.display_name,
        client_id=record.client_id,
        response_uri=record.response_uri,
        approval_status=record.approval_status,
        vp_formats_supported=dict(record.vp_formats_supported),
        created_at=record.created_at,
    )


# ---------------------------------------------------------------------------
# OpenID4VCI issuer administration
# ---------------------------------------------------------------------------


@router.post("/v1/phase10/issuers", response_model=IssuerProfileResponse)
async def create_issuer(
    payload: IssuerProfileCreateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        payload.organization_id,
        {"owner", "admin"},
    )

    try:
        record = await create_issuer_profile(session, user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _issuer_response(record)


@router.post(
    "/v1/phase10/platform/issuers/{issuer_id}/{decision}",
    response_model=IssuerProfileResponse,
)
async def review_issuer(
    issuer_id: str,
    decision: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_platform_admin(user)

    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=422, detail="Decision must be approve or reject.")

    record = await session.get(CredentialIssuerProfile, issuer_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Issuer not found.")

    return _issuer_response(
        await approve_issuer_profile(
            session,
            record,
            user.id,
            approved=decision == "approve",
        )
    )


@router.put("/v1/phase10/issuers/{issuer_id}/configurations")
async def configure_issuer(
    issuer_id: str,
    payload: CredentialConfigurationRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    issuer = await session.get(CredentialIssuerProfile, issuer_id)

    if issuer is None:
        raise HTTPException(status_code=404, detail="Issuer not found.")

    await require_org_role(
        session,
        user,
        issuer.organization_id,
        {"owner", "admin"},
    )

    try:
        record = await upsert_credential_configuration(session, issuer, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "id": record.id,
        "configuration_id": record.configuration_id,
        "credential_format": record.credential_format,
        "credential_type": record.credential_type,
        "vct": record.vct,
        "scope": record.scope,
        "claim_names": record.claim_names,
        "selective_claims": record.selective_claims,
        "active": record.active,
    }


@router.post("/v1/phase10/platform/wallet-clients")
async def add_wallet_client(
    payload: WalletClientRegistrationRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_platform_admin(user)

    try:
        record = await register_wallet_client(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "id": record.id,
        "client_id": record.client_id,
        "display_name": record.display_name,
        "redirect_uris": record.redirect_uris,
        "approved": record.approved,
    }


@router.post(
    "/v1/phase10/issuers/{issuer_id}/offers",
    response_model=CredentialOfferResponse,
)
async def make_credential_offer(
    issuer_id: str,
    payload: CredentialOfferRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    issuer = await session.get(CredentialIssuerProfile, issuer_id)

    if issuer is None:
        raise HTTPException(status_code=404, detail="Issuer not found.")

    await require_org_role(
        session,
        user,
        issuer.organization_id,
        {"owner", "admin"},
    )

    if issuer.approval_status != "approved":
        raise HTTPException(status_code=409, detail="Issuer is not approved.")

    subject_user_id = payload.subject_user_id or user.id
    subject = await session.get(User, subject_user_id)

    if subject is None or not subject.is_active:
        raise HTTPException(status_code=404, detail="Credential subject user not found.")

    try:
        record, offer, tx_code = await create_credential_offer(
            session,
            issuer,
            subject_user_id,
            payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CredentialOfferResponse(
        offer_id=record.id,
        credential_offer=offer,
        credential_offer_uri=(
            "openid-credential-offer://?"
            + urlencode(
                {
                    "credential_offer": json.dumps(
                        offer,
                        separators=(",", ":"),
                    )
                }
            )
        ),
        transaction_code=tx_code,
        expires_at=record.expires_at,
    )


@router.post("/v1/phase10/credentials/{credential_id}/revoke")
async def revoke_credential(
    credential_id: str,
    payload: CredentialRevokeRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.get(IssuedCredentialRecord, credential_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Issued credential not found.")

    issuer = await session.get(CredentialIssuerProfile, record.issuer_profile_id)

    if issuer is None:
        raise HTTPException(status_code=404, detail="Issuer not found.")

    await require_org_role(
        session,
        user,
        issuer.organization_id,
        {"owner", "admin"},
    )
    await revoke_issued_credential(session, record)

    return {
        "id": record.id,
        "status": record.status,
        "reason_recorded": bool(payload.reason.strip()),
    }


# ---------------------------------------------------------------------------
# OpenID4VCI public protocol endpoints
# ---------------------------------------------------------------------------


@router.get("/.well-known/openid-credential-issuer/oid4vci/{slug}")
async def credential_issuer_metadata(
    slug: str,
    session: AsyncSession = Depends(get_session),
):
    issuer = await _issuer_by_slug(session, slug)
    from app.models import CredentialConfiguration

    configurations = list(
        (
            await session.scalars(
                select(CredentialConfiguration).where(
                    CredentialConfiguration.issuer_profile_id == issuer.id
                )
            )
        ).all()
    )
    return issuer_metadata(issuer, configurations)


@router.get("/.well-known/oauth-authorization-server/oid4vci/{slug}")
async def oauth_metadata(
    slug: str,
    session: AsyncSession = Depends(get_session),
):
    issuer = await _issuer_by_slug(session, slug)
    return authorization_server_metadata(issuer)


@router.get("/oid4vci/{slug}/authorize")
async def authorize(
    slug: str,
    client_id: str = Query(..., min_length=3),
    redirect_uri: str = Query(..., min_length=8),
    response_type: str = Query("code"),
    code_challenge: str = Query(..., min_length=20),
    code_challenge_method: str = Query("S256"),
    scope: str = Query(..., min_length=1),
    state: str = Query("", max_length=1000),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if response_type != "code":
        raise HTTPException(status_code=422, detail="Only response_type=code is supported.")

    issuer = await _issuer_by_slug(session, slug)
    await require_org_role(
        session,
        user,
        issuer.organization_id,
        {"owner", "admin", "recruiter", "member"},
    )

    try:
        raw_code = await authorize_wallet(
            session,
            issuer,
            user.id,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scope=scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    params = {"code": raw_code}
    if state:
        params["state"] = state

    separator = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        f"{redirect_uri}{separator}{urlencode(params)}",
        status_code=302,
    )


@router.post("/oid4vci/{slug}/token")
async def token_endpoint(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    issuer = await _issuer_by_slug(session, slug)
    form = await request.form()
    grant_type = str(form.get("grant_type") or "")

    try:
        if grant_type == "urn:ietf:params:oauth:grant-type:pre-authorized_code":
            raw_token, record = await redeem_pre_authorized_code(
                session,
                issuer,
                str(form.get("pre-authorized_code") or ""),
                str(form.get("tx_code") or ""),
            )
        elif grant_type == "authorization_code":
            raw_token, record = await redeem_authorization_code(
                session,
                issuer,
                code=str(form.get("code") or ""),
                client_id=str(form.get("client_id") or ""),
                redirect_uri=str(form.get("redirect_uri") or ""),
                code_verifier=str(form.get("code_verifier") or ""),
            )
        else:
            raise ValueError("Unsupported grant_type.")
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_grant", "error_description": str(exc)},
        )

    return {
        "access_token": raw_token,
        "token_type": "Bearer",
        "expires_in": max(
            0,
            int((record.expires_at - record.created_at).total_seconds()),
        ),
    }


async def _bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")

    if scheme.lower() != "bearer" or not value.strip():
        raise HTTPException(status_code=401, detail="Bearer token required.")

    return value.strip()


@router.post("/oid4vci/{slug}/nonce")
async def nonce_endpoint(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    issuer = await _issuer_by_slug(session, slug)

    try:
        token = await access_token_record(
            session,
            issuer,
            await _bearer_token(request),
        )
        nonce = await issue_nonce(session, token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return {"c_nonce": nonce}


@router.post(
    "/oid4vci/{slug}/credential",
    response_model=CredentialIssueResponse,
)
async def credential_endpoint(
    slug: str,
    payload: CredentialRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    issuer = await _issuer_by_slug(session, slug)

    try:
        token = await access_token_record(
            session,
            issuer,
            await _bearer_token(request),
        )
        proof_jwts = payload.proofs.jwt if payload.proofs else []

        if len(proof_jwts) > 1:
            raise ValueError(
                "This reference endpoint supports one JWT proof per request; "
                "batch issuance is not advertised."
            )

        credential, record = await issue_credential(
            session,
            issuer,
            token,
            payload.credential_configuration_id,
            proof_jwts[0] if proof_jwts else None,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_credential_request", "error_description": str(exc)},
        )

    return CredentialIssueResponse(
        credentials=[
            {
                "credential": credential,
                "credential_id": record.id,
                "format": record.credential_format,
            }
        ],
        notification_id=None,
    )


@router.get("/oid4vci/{slug}/status/{jti}")
async def local_credential_status(
    slug: str,
    jti: str,
    session: AsyncSession = Depends(get_session),
):
    issuer = await _issuer_by_slug(session, slug)
    record = await session.scalar(
        select(IssuedCredentialRecord).where(
            IssuedCredentialRecord.issuer_profile_id == issuer.id,
            IssuedCredentialRecord.jti == jti,
        )
    )

    if record is None:
        raise HTTPException(status_code=404, detail="Credential status not found.")

    return {
        "id": f"{issuer.issuer_identifier}/status/{jti}",
        "type": "PlatformCredentialStatus2026",
        "status": record.status,
        "expires_at": record.expires_at,
        "note": (
            "Project-local status profile. It is not represented as a W3C "
            "Bitstring Status List credential."
        ),
    }


# ---------------------------------------------------------------------------
# OpenID4VP verifier administration and public protocol endpoints
# ---------------------------------------------------------------------------


@router.post("/v1/phase10/verifiers", response_model=VerifierProfileResponse)
async def create_verifier(
    payload: VerifierProfileCreateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        payload.organization_id,
        {"owner", "admin"},
    )

    try:
        record = await create_verifier_profile(session, user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _verifier_response(record)


@router.post(
    "/v1/phase10/platform/verifiers/{verifier_id}/{decision}",
    response_model=VerifierProfileResponse,
)
async def review_verifier(
    verifier_id: str,
    decision: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_platform_admin(user)

    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=422, detail="Decision must be approve or reject.")

    record = await session.get(CredentialVerifierProfile, verifier_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Verifier not found.")

    return _verifier_response(
        await approve_verifier_profile(
            session,
            record,
            user.id,
            approved=decision == "approve",
        )
    )


@router.put("/v1/phase10/verifiers/{verifier_id}/trust-anchors")
async def add_trust_anchor(
    verifier_id: str,
    payload: TrustAnchorRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    verifier = await session.get(CredentialVerifierProfile, verifier_id)

    if verifier is None:
        raise HTTPException(status_code=404, detail="Verifier not found.")

    await require_org_role(
        session,
        user,
        verifier.organization_id,
        {"owner", "admin"},
    )

    try:
        record = await upsert_trust_anchor(
            session,
            verifier.organization_id,
            payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "id": record.id,
        "issuer_identifier": record.issuer_identifier,
        "allowed_formats": record.allowed_formats,
        "active": record.active,
    }


@router.post(
    "/v1/phase10/verifiers/{verifier_id}/requests",
    response_model=PresentationRequestResponse,
)
async def start_presentation(
    verifier_id: str,
    payload: PresentationRequestCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    verifier = await session.get(CredentialVerifierProfile, verifier_id)

    if verifier is None:
        raise HTTPException(status_code=404, detail="Verifier not found.")

    await require_org_role(
        session,
        user,
        verifier.organization_id,
        {"owner", "admin", "recruiter"},
    )

    try:
        record, _, request_object, wallet_uri = await create_presentation_request(
            session,
            verifier,
            user.id,
            payload.dcql_query,
            payload.expires_in_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return PresentationRequestResponse(
        request_id=record.id,
        request_uri=(
            f"{settings.phase10_public_base_url.rstrip('/')}"
            f"/oid4vp/requests/{record.id}"
        ),
        authorization_request=request_object,
        wallet_invocation_uri=wallet_uri,
        expires_at=record.expires_at,
    )


@router.get("/oid4vp/requests/{request_id}")
async def oid4vp_request_object(
    request_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        _, _, request_object = await presentation_request_object(session, request_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return request_object


@router.post("/oid4vp/{slug}/response")
async def oid4vp_direct_post(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    verifier = await _verifier_by_slug(session, slug)
    form = await request.form()
    state = str(form.get("state") or "")
    vp_token = str(form.get("vp_token") or "")

    if not state or not vp_token:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_request", "error_description": "state and vp_token are required."},
        )

    request_record = await session.scalar(
        select(PresentationRequestRecord).where(
            PresentationRequestRecord.verifier_profile_id == verifier.id,
            PresentationRequestRecord.state_hash.is_not(None),
        ).order_by(PresentationRequestRecord.created_at.desc())
    )

    # Never trust "latest" as the security binding. Resolve the specific request
    # by comparing its state digest among active requests for this verifier.
    if request_record is None:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_request", "error_description": "Presentation request not found."},
        )

    from hashlib import sha256
    state_hash = sha256(state.encode("utf-8")).hexdigest()
    request_record = await session.scalar(
        select(PresentationRequestRecord).where(
            PresentationRequestRecord.verifier_profile_id == verifier.id,
            PresentationRequestRecord.state_hash == state_hash,
        )
    )

    if request_record is None:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_request", "error_description": "Presentation state is unknown."},
        )

    try:
        submission = await verify_presentation_response(
            session,
            verifier,
            request_record,
            state,
            vp_token,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_vp_token", "error_description": str(exc)},
        )

    return {}


@router.get(
    "/v1/phase10/presentations/{submission_id}",
    response_model=PresentationResultResponse,
)
async def read_presentation(
    submission_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    submission = await session.get(PresentationSubmission, submission_id)

    if submission is None:
        raise HTTPException(status_code=404, detail="Presentation result not found.")

    request_record = await session.get(
        PresentationRequestRecord,
        submission.request_id,
    )
    verifier = (
        await session.get(
            CredentialVerifierProfile,
            request_record.verifier_profile_id,
        )
        if request_record
        else None
    )

    if verifier is None:
        raise HTTPException(status_code=404, detail="Verifier not found.")

    await require_org_role(
        session,
        user,
        verifier.organization_id,
        {"owner", "admin", "recruiter"},
    )

    return PresentationResultResponse(
        id=submission.id,
        request_id=submission.request_id,
        verification_status=submission.verification_status,
        holder_identifier=submission.holder_identifier,
        issuer_identifiers=submission.issuer_identifiers,
        disclosed_claims=presentation_result(submission),
        created_at=submission.created_at,
    )


# ---------------------------------------------------------------------------
# Privacy engineering
# ---------------------------------------------------------------------------


@router.post(
    "/v1/phase10/privacy/consent-receipts",
    response_model=ConsentReceiptResponse,
)
async def consent_receipt(
    payload: ConsentReceiptRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if payload.organization_id:
        await require_org_role(
            session,
            user,
            payload.organization_id,
            {"owner", "admin", "recruiter", "member"},
        )

    record = await record_consent_receipt(session, user.id, payload)
    return ConsentReceiptResponse(
        id=record.id,
        purpose=record.purpose,
        action=record.action,
        policy_version=record.policy_version,
        receipt_hash=record.receipt_hash,
        previous_receipt_hash=record.previous_receipt_hash,
        occurred_at=record.occurred_at,
    )


@router.put("/v1/phase10/privacy/{organization_id}/classification-rules")
async def classification_rule(
    organization_id: str,
    payload: ClassificationRuleRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})

    try:
        record = await upsert_classification_rule(session, organization_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "id": record.id,
        "rule_key": record.rule_key,
        "field_pattern": record.field_pattern,
        "classification": record.classification,
        "sensitivity": record.sensitivity,
        "enabled": record.enabled,
    }


@router.post(
    "/v1/phase10/privacy/{organization_id}/discovery",
    response_model=DiscoveryScanResponse,
)
async def discovery_scan(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})

    record = await run_data_discovery(session, organization_id)
    findings = await discovery_findings(session, record.id)

    return DiscoveryScanResponse(
        id=record.id,
        organization_id=record.organization_id,
        status=record.status,
        finding_count=record.finding_count,
        findings=[
            {
                "id": item.id,
                "table_name": item.table_name,
                "field_name": item.field_name,
                "classification": item.classification,
                "sensitivity": item.sensitivity,
                "confidence": item.confidence,
                "evidence": item.evidence,
            }
            for item in findings
        ],
        started_at=record.started_at,
        completed_at=record.completed_at,
    )


@router.post(
    "/v1/phase10/privacy/deletion/plan",
    response_model=DeletionWorkflowResponse,
)
async def deletion_plan(
    payload: DeletionPlanRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await plan_deletion(
        session,
        user.id,
        payload.dsar_id,
        payload.dry_run,
    )

    return DeletionWorkflowResponse(
        id=record.id,
        status=record.status,
        dry_run=record.dry_run,
        legal_hold_blocked=record.legal_hold_blocked,
        steps=record.steps_json,
        requested_at=record.requested_at,
        completed_at=record.completed_at,
    )


@router.post(
    "/v1/phase10/privacy/deletion/{workflow_id}/execute",
    response_model=DeletionWorkflowResponse,
)
async def deletion_execute(
    workflow_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.get(DeletionWorkflow, workflow_id)

    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Deletion workflow not found.")

    try:
        record = await execute_deletion(session, record)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return DeletionWorkflowResponse(
        id=record.id,
        status=record.status,
        dry_run=record.dry_run,
        legal_hold_blocked=record.legal_hold_blocked,
        steps=record.steps_json,
        requested_at=record.requested_at,
        completed_at=record.completed_at,
    )


@router.post(
    "/v1/phase10/privacy/{organization_id}/analytics",
    response_model=PrivacyAnalyticsResponse,
)
async def privacy_analytics(
    organization_id: str,
    payload: PrivacyAnalyticsRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )

    try:
        release, remaining = await privacy_preserving_release(
            session,
            organization_id,
            payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    return PrivacyAnalyticsResponse(
        metric=release.metric,
        day=release.day,
        epsilon=release.epsilon,
        minimum_group_size=release.minimum_group_size,
        value=release.noisy_value,
        suppressed=release.suppressed,
        remaining_daily_epsilon=remaining,
        disclaimer=(
            "Differentially private count. Small cohorts are suppressed; "
            "noise is added to released counts and the daily epsilon budget "
            "is consumed per query."
        ),
    )


@router.post(
    "/v1/phase10/audit",
    response_model=AuditLedgerEntryResponse,
)
async def audit_append(
    payload: AuditLedgerAppendRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if payload.organization_id:
        await require_org_role(
            session,
            user,
            payload.organization_id,
            {"owner", "admin"},
        )
    elif not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required.")

    record = await append_crypto_audit(session, user.id, payload)

    return AuditLedgerEntryResponse(
        id=record.id,
        organization_id=record.organization_id,
        sequence=record.sequence,
        event_type=record.event_type,
        actor=record.actor,
        subject_type=record.subject_type,
        subject_id=record.subject_id,
        payload_digest=record.payload_digest,
        previous_hash=record.previous_hash,
        entry_hash=record.entry_hash,
        signature=record.signature,
        signing_key_id=record.signing_key_id,
        created_at=record.created_at,
    )


@router.get(
    "/v1/phase10/audit/verify",
    response_model=AuditLedgerVerifyResponse,
)
async def audit_verify(
    organization_id: str | None = Query(default=None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if organization_id:
        await require_org_role(
            session,
            user,
            organization_id,
            {"owner", "admin"},
        )
    else:
        require_platform_admin(user)

    result = await verify_crypto_audit_chain(session, organization_id)
    return AuditLedgerVerifyResponse(**result)
