from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.models import (
    CandidateWallet,
    DataAsset,
    DataLineageEdge,
    DataSubjectRequest,
    Membership,
    PrivacyImpactAssessment,
    RedTeamCampaign,
    RetentionPolicy,
    SkillsPassport,
    User,
)
from app.phase9_schemas import (
    ContinuousControlResponse,
    DSARCreateRequest,
    DSARResponse,
    DSARStatusUpdate,
    DataAssetRequest,
    DataLineageEdgeRequest,
    EducationCareerPathwayRequest,
    EducationCareerPathwayResponse,
    PortableCareerRecordResponse,
    PrivacyImpactAssessmentRequest,
    PrivacyImpactAssessmentResponse,
    PrivacyImpactAssessmentUpdate,
    RedTeamCampaignRequest,
    RedTeamCampaignResponse,
    RetentionPolicyRequest,
    SkillsPassportRequest,
    SkillsPassportResponse,
    WalletRegistrationRequest,
    WalletRegistrationResponse,
)
from app.phase9_services import (
    build_dsar_export,
    build_skills_passport,
    continuous_control_snapshot,
    create_dsar,
    create_lineage_edge,
    create_privacy_assessment,
    decrypt_dsar_result,
    decrypt_skills_passport,
    education_to_career_pathway,
    enforce_retention_policy,
    portable_career_record,
    red_team_findings,
    register_wallet,
    run_red_team_campaign,
    update_dsar,
    upsert_data_asset,
    upsert_retention_policy,
)
from app.services import audit
from app.tenancy import require_org_role


router = APIRouter()


def wallet_response(record: CandidateWallet) -> WalletRegistrationResponse:
    return WalletRegistrationResponse(
        id=record.id,
        holder_did=record.holder_did,
        did_method=record.did_method,
        wallet_type=record.wallet_type,
        presentation_endpoint=record.presentation_endpoint,
        issuance_endpoint=record.issuance_endpoint,
        verification_status=record.verification_status,
        metadata=record.metadata_json,
        created_at=record.created_at,
    )


def dsar_response(record: DataSubjectRequest) -> DSARResponse:
    return DSARResponse(
        id=record.id,
        request_type=record.request_type,
        status=record.status,
        identity_verified=record.identity_verified,
        submitted_at=record.submitted_at,
        due_at=record.due_at,
        completed_at=record.completed_at,
        result_available=bool(record.encrypted_result),
        notes=record.notes,
    )


def pia_response(
    record: PrivacyImpactAssessment,
) -> PrivacyImpactAssessmentResponse:
    return PrivacyImpactAssessmentResponse(
        id=record.id,
        name=record.name,
        system_or_process=record.system_or_process,
        status=record.status,
        risk_level=record.risk_level,
        processing_purposes=record.processing_purposes,
        data_categories=record.data_categories,
        jurisdictions=record.jurisdictions,
        automated_decision_support=record.automated_decision_support,
        high_risk_processing=record.high_risk_processing,
        review_due_at=record.review_due_at,
        created_at=record.created_at,
    )


def red_team_response(record: RedTeamCampaign) -> RedTeamCampaignResponse:
    return RedTeamCampaignResponse(
        id=record.id,
        name=record.name,
        status=record.status,
        scope=record.scope,
        total_tests=record.total_tests,
        passed_tests=record.passed_tests,
        failed_tests=record.failed_tests,
        findings=red_team_findings(record),
        created_at=record.created_at,
        completed_at=record.completed_at,
    )


@router.post(
    "/v1/wallets",
    response_model=WalletRegistrationResponse,
)
async def put_wallet(
    payload: WalletRegistrationRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        record = await register_wallet(session, user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await audit(
        session,
        "phase9.wallet.register",
        user.id,
        {
            "wallet_id": record.id,
            "did_method": record.did_method,
            "private_key_stored": False,
        },
    )
    return wallet_response(record)


@router.get(
    "/v1/wallets",
    response_model=list[WalletRegistrationResponse],
)
async def list_wallets(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    records = list(
        (
            await session.scalars(
                select(CandidateWallet)
                .where(CandidateWallet.user_id == user.id)
                .order_by(CandidateWallet.created_at.asc())
            )
        ).all()
    )
    return [wallet_response(record) for record in records]


@router.delete("/v1/wallets/{wallet_id}")
async def delete_wallet(
    wallet_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.get(CandidateWallet, wallet_id)

    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Wallet registration not found.")

    await session.delete(record)
    await session.commit()
    return {"deleted": True}


@router.put(
    "/v1/skills-passport",
    response_model=SkillsPassportResponse,
)
async def put_skills_passport(
    payload: SkillsPassportRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        record, passport = await build_skills_passport(session, user.id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await audit(
        session,
        "phase9.skills_passport.update",
        user.id,
        {
            "passport_id": record.id,
            "version": record.version,
            "payload_hash": record.payload_hash,
        },
    )
    return SkillsPassportResponse(
        id=record.id,
        version=record.version,
        holder_did=passport.get("holder", {}).get("did", ""),
        passport=passport,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get(
    "/v1/skills-passport",
    response_model=SkillsPassportResponse,
)
async def get_skills_passport(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.scalar(
        select(SkillsPassport).where(SkillsPassport.user_id == user.id)
    )

    if record is None:
        raise HTTPException(status_code=404, detail="Skills passport not found.")

    passport = decrypt_skills_passport(record)
    return SkillsPassportResponse(
        id=record.id,
        version=record.version,
        holder_did=passport.get("holder", {}).get("did", ""),
        passport=passport,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get(
    "/v1/portable-career-record",
    response_model=PortableCareerRecordResponse,
)
async def get_portable_career_record(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        record, digest = await portable_career_record(session, user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return PortableCareerRecordResponse(
        format="w3c-vc-data-model-2.0-shaped-json",
        verification_status="unsigned_portable_export",
        record=record,
        sha256=digest,
    )


@router.post(
    "/v1/organizations/{organization_id}/education-career-pathway",
    response_model=EducationCareerPathwayResponse,
)
async def education_career_pathway(
    organization_id: str,
    payload: EducationCareerPathwayRequest,
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
        result = await education_to_career_pathway(
            session,
            user.id,
            organization_id,
            payload,
        )
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return EducationCareerPathwayResponse(**result)


@router.post(
    "/v1/organizations/{organization_id}/privacy/assessments",
    response_model=PrivacyImpactAssessmentResponse,
)
async def add_privacy_assessment(
    organization_id: str,
    payload: PrivacyImpactAssessmentRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    record = await create_privacy_assessment(
        session,
        organization_id,
        user.id,
        payload,
    )
    await audit(
        session,
        "phase9.privacy_assessment.create",
        user.id,
        {"organization_id": organization_id, "assessment_id": record.id},
    )
    return pia_response(record)


@router.get(
    "/v1/organizations/{organization_id}/privacy/assessments",
    response_model=list[PrivacyImpactAssessmentResponse],
)
async def list_privacy_assessments(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    records = list(
        (
            await session.scalars(
                select(PrivacyImpactAssessment)
                .where(PrivacyImpactAssessment.organization_id == organization_id)
                .order_by(PrivacyImpactAssessment.created_at.desc())
            )
        ).all()
    )
    return [pia_response(record) for record in records]


@router.patch(
    "/v1/organizations/{organization_id}/privacy/assessments/{assessment_id}",
    response_model=PrivacyImpactAssessmentResponse,
)
async def update_privacy_assessment(
    organization_id: str,
    assessment_id: str,
    payload: PrivacyImpactAssessmentUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    record = await session.get(PrivacyImpactAssessment, assessment_id)

    if record is None or record.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Privacy assessment not found.")

    record.status = payload.status

    if payload.mitigations is not None:
        record.mitigations = list(payload.mitigations)

    if payload.review_due_at is not None:
        record.review_due_at = payload.review_due_at

    if payload.status == "approved":
        record.approved_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(record)
    await audit(
        session,
        "phase9.privacy_assessment.update",
        user.id,
        {
            "organization_id": organization_id,
            "assessment_id": assessment_id,
            "status": record.status,
        },
    )
    return pia_response(record)


@router.get("/v1/organizations/{organization_id}/retention")
async def list_retention_policies(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    records = list(
        (
            await session.scalars(
                select(RetentionPolicy)
                .where(RetentionPolicy.organization_id == organization_id)
                .order_by(RetentionPolicy.record_type.asc())
            )
        ).all()
    )
    return [
        {
            "id": record.id,
            "record_type": record.record_type,
            "retention_days": record.retention_days,
            "legal_hold": record.legal_hold,
            "enabled": record.enabled,
            "reason": record.reason,
            "last_run_at": record.last_run_at,
            "last_deleted_count": record.last_deleted_count,
        }
        for record in records
    ]


@router.post("/v1/organizations/{organization_id}/data-assets")
async def put_data_asset(
    organization_id: str,
    payload: DataAssetRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    record = await upsert_data_asset(session, organization_id, payload)
    return {
        "id": record.id,
        "asset_key": record.asset_key,
        "name": record.name,
        "asset_type": record.asset_type,
        "data_categories": record.data_categories,
        "contains_personal_data": record.contains_personal_data,
        "contains_sensitive_data": record.contains_sensitive_data,
        "retention_class": record.retention_class,
    }


@router.get("/v1/organizations/{organization_id}/data-assets")
async def list_data_assets(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    records = list(
        (
            await session.scalars(
                select(DataAsset)
                .where(DataAsset.organization_id == organization_id)
                .order_by(DataAsset.asset_key.asc())
            )
        ).all()
    )
    return [
        {
            "id": record.id,
            "asset_key": record.asset_key,
            "name": record.name,
            "asset_type": record.asset_type,
            "data_categories": record.data_categories,
            "contains_personal_data": record.contains_personal_data,
            "contains_sensitive_data": record.contains_sensitive_data,
            "system_owner": record.system_owner,
            "retention_class": record.retention_class,
            "metadata": record.metadata_json,
        }
        for record in records
    ]


@router.post("/v1/organizations/{organization_id}/data-lineage")
async def add_lineage(
    organization_id: str,
    payload: DataLineageEdgeRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})

    try:
        record = await create_lineage_edge(session, organization_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "id": record.id,
        "upstream_asset_id": record.upstream_asset_id,
        "downstream_asset_id": record.downstream_asset_id,
        "transformation": record.transformation,
        "purpose": record.purpose,
    }


@router.get("/v1/organizations/{organization_id}/data-lineage")
async def list_lineage(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    records = list(
        (
            await session.scalars(
                select(DataLineageEdge)
                .where(DataLineageEdge.organization_id == organization_id)
                .order_by(DataLineageEdge.created_at.asc())
            )
        ).all()
    )
    return [
        {
            "id": record.id,
            "upstream_asset_id": record.upstream_asset_id,
            "downstream_asset_id": record.downstream_asset_id,
            "transformation": record.transformation,
            "purpose": record.purpose,
        }
        for record in records
    ]


@router.put("/v1/organizations/{organization_id}/retention")
async def put_retention_policy(
    organization_id: str,
    payload: RetentionPolicyRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    record = await upsert_retention_policy(session, organization_id, payload)
    await audit(
        session,
        "phase9.retention.policy",
        user.id,
        {
            "organization_id": organization_id,
            "record_type": record.record_type,
            "retention_days": record.retention_days,
            "legal_hold": record.legal_hold,
        },
    )
    return {
        "id": record.id,
        "record_type": record.record_type,
        "retention_days": record.retention_days,
        "legal_hold": record.legal_hold,
        "enabled": record.enabled,
        "last_run_at": record.last_run_at,
        "last_deleted_count": record.last_deleted_count,
    }


@router.post("/v1/organizations/{organization_id}/retention/{policy_id}/run")
async def run_retention_policy(
    organization_id: str,
    policy_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    record = await session.get(RetentionPolicy, policy_id)

    if record is None or record.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Retention policy not found.")

    try:
        count = await enforce_retention_policy(session, record)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"deleted": count, "legal_hold": record.legal_hold}


@router.post(
    "/v1/privacy/requests",
    response_model=DSARResponse,
)
async def create_privacy_request(
    payload: DSARCreateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await create_dsar(session, user.id, payload)
    await audit(
        session,
        "phase9.dsar.create",
        user.id,
        {"dsar_id": record.id, "request_type": record.request_type},
    )
    return dsar_response(record)


@router.get(
    "/v1/privacy/requests",
    response_model=list[DSARResponse],
)
async def list_privacy_requests(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    records = list(
        (
            await session.scalars(
                select(DataSubjectRequest)
                .where(DataSubjectRequest.user_id == user.id)
                .order_by(DataSubjectRequest.submitted_at.desc())
            )
        ).all()
    )
    return [dsar_response(record) for record in records]


@router.get("/v1/privacy/requests/{request_id}/result")
async def privacy_request_result(
    request_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.get(DataSubjectRequest, request_id)

    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Privacy request not found.")

    result = decrypt_dsar_result(record)

    if result is None:
        raise HTTPException(status_code=409, detail="Result is not available yet.")

    return result


@router.get("/v1/organizations/{organization_id}/privacy/requests")
async def organization_privacy_requests(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    user_ids = select(Membership.user_id).where(
        Membership.organization_id == organization_id
    )
    records = list(
        (
            await session.scalars(
                select(DataSubjectRequest)
                .where(DataSubjectRequest.user_id.in_(user_ids))
                .order_by(DataSubjectRequest.due_at.asc())
            )
        ).all()
    )
    return [dsar_response(record).model_dump(mode="json") for record in records]


@router.patch(
    "/v1/organizations/{organization_id}/privacy/requests/{request_id}",
    response_model=DSARResponse,
)
async def organization_update_privacy_request(
    organization_id: str,
    request_id: str,
    payload: DSARStatusUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    record = await session.get(DataSubjectRequest, request_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Privacy request not found.")

    member = await session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == record.user_id,
        )
    )

    if member is None:
        raise HTTPException(status_code=404, detail="Privacy request not found.")

    record = await update_dsar(session, record, payload)
    await audit(
        session,
        "phase9.dsar.update",
        user.id,
        {
            "organization_id": organization_id,
            "dsar_id": record.id,
            "status": record.status,
        },
    )
    return dsar_response(record)


@router.post(
    "/v1/organizations/{organization_id}/red-team",
    response_model=RedTeamCampaignResponse,
)
async def run_red_team(
    organization_id: str,
    payload: RedTeamCampaignRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    record = await run_red_team_campaign(
        session,
        organization_id,
        user.id,
        payload,
    )
    await audit(
        session,
        "phase9.red_team.run",
        user.id,
        {
            "organization_id": organization_id,
            "campaign_id": record.id,
            "status": record.status,
        },
    )
    return red_team_response(record)


@router.get(
    "/v1/organizations/{organization_id}/red-team",
    response_model=list[RedTeamCampaignResponse],
)
async def list_red_team(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    records = list(
        (
            await session.scalars(
                select(RedTeamCampaign)
                .where(RedTeamCampaign.organization_id == organization_id)
                .order_by(RedTeamCampaign.created_at.desc())
            )
        ).all()
    )
    return [red_team_response(record) for record in records]


@router.post(
    "/v1/organizations/{organization_id}/continuous-controls",
    response_model=ContinuousControlResponse,
)
async def run_continuous_controls(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(session, user, organization_id, {"owner", "admin"})
    record = await continuous_control_snapshot(session, organization_id)
    return ContinuousControlResponse(
        organization_id=organization_id,
        generated_at=record.generated_at,
        overall_status=record.overall_status,
        checks=record.checks_json,
        open_findings=record.open_findings,
    )

@router.get(
    "/v1/organizations/{organization_id}/continuous-controls",
    response_model=ContinuousControlResponse,
)
async def latest_continuous_controls(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    from app.models import ContinuousControlSnapshot

    record = await session.scalar(
        select(ContinuousControlSnapshot)
        .where(ContinuousControlSnapshot.organization_id == organization_id)
        .order_by(ContinuousControlSnapshot.generated_at.desc())
        .limit(1)
    )

    if record is None:
        raise HTTPException(status_code=404, detail="No continuous-control snapshot exists yet.")

    return ContinuousControlResponse(
        organization_id=organization_id,
        generated_at=record.generated_at,
        overall_status=record.overall_status,
        checks=record.checks_json,
        open_findings=record.open_findings,
    )

