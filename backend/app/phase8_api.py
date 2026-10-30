from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.credential_verification import store_credential
from app.db import get_session
from app.governance8 import (
    collect_phase8_evidence,
    create_incident,
    create_inventory,
    create_risk_assessment,
    incident_details,
    phase8_dashboard,
    update_incident,
)
from app.labor_market import (
    build_trend_snapshot,
    import_bls_series,
    upsert_observation,
)
from app.learning_providers import (
    create_or_update_connection,
    search_learning_catalog,
    sync_connection,
)
from app.models import (
    AIIncident,
    AIRiskAssessment,
    AISystemInventory,
    CareerPortfolio,
    CareerPortfolioShare,
    GovernanceControlMapping,
    LearningProviderConnection,
    User,
    VerifiedCredential,
)
from app.portfolio import (
    build_portfolio,
    create_share,
    decrypt_portfolio,
    public_portfolio,
)
from app.schemas import (
    AIIncidentCreate,
    AIIncidentResponse,
    AIIncidentUpdate,
    AIRiskAssessmentIn,
    AIRiskAssessmentResponse,
    AISystemInventoryIn,
    AISystemInventoryResponse,
    BLSSeriesImportRequest,
    ControlMappingUpdate,
    CredentialImportRequest,
    CredentialResponse,
    LaborObservationIn,
    LaborTrendRequest,
    LaborTrendResponse,
    LearningCatalogItemResponse,
    LearningProviderConnectionRequest,
    LearningProviderConnectionResponse,
    Phase8GovernanceDashboard,
    PortfolioRequest,
    PortfolioResponse,
    PortfolioShareRequest,
    PortfolioShareResponse,
)
from app.services import audit
from app.tenancy import require_org_role, require_platform_admin


router = APIRouter()


async def platform_admin_user(
    user: User = Depends(current_user),
) -> User:
    require_platform_admin(user)
    return user


def credential_response(record: VerifiedCredential) -> CredentialResponse:
    return CredentialResponse(
        id=record.id,
        credential_format=record.credential_format,
        credential_type=record.credential_type,
        title=record.title,
        issuer_name=record.issuer_name,
        issuer_url=record.issuer_url,
        verification_level=record.verification_level,
        verification_status=record.verification_status,
        verification_method=record.verification_method,
        skills=record.skills,
        issued_at=record.issued_at,
        expires_at=record.expires_at,
        evidence=record.evidence_json,
        created_at=record.created_at,
    )


def connection_response(
    record: LearningProviderConnection,
) -> LearningProviderConnectionResponse:
    return LearningProviderConnectionResponse(
        id=record.id,
        organization_id=record.organization_id,
        provider=record.provider,
        base_url=record.base_url,
        enabled=record.enabled,
        last_sync_at=record.last_sync_at,
        metadata=record.metadata_json,
    )


def inventory_response(record: AISystemInventory) -> AISystemInventoryResponse:
    return AISystemInventoryResponse(
        id=record.id,
        organization_id=record.organization_id,
        system_key=record.system_key,
        version=record.version,
        name=record.name,
        owner=record.owner,
        intended_purpose=record.intended_purpose,
        operator_role=record.operator_role,
        lifecycle_status=record.lifecycle_status,
        jurisdictions=record.jurisdictions,
        model_names=record.model_names,
        data_categories=record.data_categories,
        employment_use=record.employment_use,
        education_use=record.education_use,
        profiles_natural_persons=record.profiles_natural_persons,
        materially_influences_decisions=record.materially_influences_decisions,
        human_oversight=record.human_oversight,
        iso42001_in_scope=record.iso42001_in_scope,
        eu_risk_class=record.eu_risk_class,
        eu_classification_basis=record.eu_classification_basis,
        applicable_from=record.applicable_from.isoformat() if record.applicable_from else None,
        last_reviewed_at=record.last_reviewed_at,
        created_at=record.created_at,
    )


def risk_response(record: AIRiskAssessment) -> AIRiskAssessmentResponse:
    return AIRiskAssessmentResponse(
        id=record.id,
        inventory_id=record.inventory_id,
        assessment_version=record.assessment_version,
        likelihood=record.likelihood,
        impact=record.impact,
        inherent_score=record.inherent_score,
        residual_score=record.residual_score,
        risk_level=record.risk_level,
        hazards=record.hazards_json,
        controls=record.controls_json,
        status=record.status,
        created_at=record.created_at,
        approved_at=record.approved_at,
    )


def incident_response(record: AIIncident) -> AIIncidentResponse:
    return AIIncidentResponse(
        id=record.id,
        organization_id=record.organization_id,
        inventory_id=record.inventory_id,
        severity=record.severity,
        category=record.category,
        status=record.status,
        serious_incident_candidate=record.serious_incident_candidate,
        detected_at=record.detected_at,
        contained_at=record.contained_at,
        closed_at=record.closed_at,
        external_reported_at=record.external_reported_at,
        details=incident_details(record),
    )


@router.post(
    "/v1/credentials",
    response_model=CredentialResponse,
)
async def import_credential(
    payload: CredentialImportRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        record = await store_credential(
            session,
            user.id,
            payload.credential,
            use_remote_verifier=payload.verifier == "configured_remote",
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await audit(
        session,
        "phase8.credential.import",
        user.id,
        {
            "credential_id": record.id,
            "verification_level": record.verification_level,
            "verification_status": record.verification_status,
        },
    )
    return credential_response(record)


@router.get(
    "/v1/credentials",
    response_model=list[CredentialResponse],
)
async def list_credentials(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):

    records = list(
        (
            await session.scalars(
                select(VerifiedCredential)
                .where(VerifiedCredential.user_id == user.id)
                .order_by(VerifiedCredential.created_at.desc())
            )
        ).all()
    )
    return [credential_response(record) for record in records]


@router.delete("/v1/credentials/{credential_id}")
async def delete_credential(
    credential_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.get(VerifiedCredential, credential_id)

    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Credential not found.")

    await session.delete(record)
    await session.commit()
    await audit(
        session,
        "phase8.credential.delete",
        user.id,
        {"credential_id": credential_id},
    )
    return {"deleted": True}


@router.post(
    "/v1/organizations/{organization_id}/learning/connections",
    response_model=LearningProviderConnectionResponse,
)
async def configure_learning_connection(
    organization_id: str,
    payload: LearningProviderConnectionRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )

    try:
        record = await create_or_update_connection(
            session,
            organization_id,
            payload.provider,
            payload.base_url,
            payload.credentials,
            payload.enabled,
            payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await audit(
        session,
        "phase8.learning.connection",
        user.id,
        {
            "organization_id": organization_id,
            "provider": payload.provider,
            "connection_id": record.id,
        },
    )
    return connection_response(record)


@router.get(
    "/v1/organizations/{organization_id}/learning/connections",
    response_model=list[LearningProviderConnectionResponse],
)
async def list_learning_connections(
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
                select(LearningProviderConnection)
                .where(LearningProviderConnection.organization_id == organization_id)
                .order_by(LearningProviderConnection.provider.asc())
            )
        ).all()
    )
    return [connection_response(record) for record in records]


@router.post(
    "/v1/organizations/{organization_id}/learning/connections/{connection_id}/sync"
)
async def sync_learning_connection(
    organization_id: str,
    connection_id: str,
    query: str = Query(default="", max_length=300),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )
    connection = await session.get(LearningProviderConnection, connection_id)

    if connection is None or connection.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Learning connection not found.")

    try:
        count = await sync_connection(session, connection, query=query)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Learning provider sync failed: {type(exc).__name__}",
        ) from exc

    await audit(
        session,
        "phase8.learning.sync",
        user.id,
        {
            "organization_id": organization_id,
            "connection_id": connection_id,
            "records": count,
        },
    )
    return {"records": count}


@router.get(
    "/v1/organizations/{organization_id}/learning/catalog",
    response_model=list[LearningCatalogItemResponse],
)
async def learning_catalog(
    organization_id: str,
    q: str = Query(default="", max_length=300),
    skill: list[str] = Query(default=[]),
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter", "member"},
    )
    records = await search_learning_catalog(
        session,
        organization_id,
        q,
        skill,
        limit,
    )
    return [
        LearningCatalogItemResponse(
            id=item.id,
            provider=item.provider,
            external_id=item.external_id,
            title=item.title,
            description=item.description,
            learning_type=item.learning_type,
            skills=item.skills,
            level=item.level,
            language=item.language,
            duration_hours=item.duration_hours,
            credential_offered=item.credential_offered,
            source_url=item.source_url,
            provenance=item.provenance_json,
        )
        for item in records
    ]


@router.post("/v1/admin/phase8/labor/observations")
async def import_labor_observation(
    payload: LaborObservationIn,
    user: User = Depends(platform_admin_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        await upsert_observation(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await audit(
        session,
        "phase8.labor.observation",
        user.id,
        {
            "source": payload.source,
            "occupation_code": payload.occupation_code,
            "metric": payload.metric,
            "period": payload.period,
        },
    )
    return {"status": "upserted"}


@router.post("/v1/admin/phase8/labor/bls-series")
async def import_bls(
    payload: BLSSeriesImportRequest,
    user: User = Depends(platform_admin_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        count = await import_bls_series(session, payload)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"BLS API import failed: {type(exc).__name__}",
        ) from exc

    await audit(
        session,
        "phase8.labor.bls_import",
        user.id,
        {
            "series_id": payload.series_id,
            "records": count,
        },
    )
    return {"records": count}


@router.post(
    "/v1/career/labor-trend",
    response_model=LaborTrendResponse,
)
async def labor_trend(
    payload: LaborTrendRequest,
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        record = await build_trend_snapshot(
            session,
            payload.source,
            payload.country_code,
            payload.region_code,
            payload.occupation_code,
            payload.metric,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return LaborTrendResponse(
        id=record.id,
        source=record.source,
        country_code=record.country_code,
        region_code=record.region_code,
        occupation_code=record.occupation_code,
        occupation_title=record.occupation_title,
        metric=record.metric,
        method_version=record.method_version,
        input_count=record.input_count,
        start_period=record.start_period,
        end_period=record.end_period,
        start_value=record.start_value,
        end_value=record.end_value,
        linear_slope=record.linear_slope,
        annualized_change=record.annualized_change,
        volatility=record.volatility,
        direction=record.direction,
        confidence=record.confidence,
        projected_next_value=record.projected_next_value,
        provenance=record.provenance_json,
        disclaimer=(
            "This is a deterministic historical trend projection, not a prediction "
            "of hiring, wages, promotion, or an individual's employment outcome."
        ),
    )


@router.put(
    "/v1/portfolio",
    response_model=PortfolioResponse,
)
async def put_portfolio(
    payload: PortfolioRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        record, portfolio = await build_portfolio(session, user.id, payload)
    except LookupError as exc:
        raise HTTPException(
            status_code=409,
            detail="Create your candidate profile first.",
        ) from exc

    await audit(
        session,
        "phase8.portfolio.update",
        user.id,
        {"portfolio_id": record.id, "version": record.version},
    )
    return PortfolioResponse(
        id=record.id,
        version=record.version,
        portfolio=portfolio,
        updated_at=record.updated_at,
    )


@router.get(
    "/v1/portfolio",
    response_model=PortfolioResponse,
)
async def get_portfolio(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.scalar(
        select(CareerPortfolio).where(CareerPortfolio.user_id == user.id)
    )

    if record is None:
        raise HTTPException(status_code=404, detail="Portfolio not found.")

    return PortfolioResponse(
        id=record.id,
        version=record.version,
        portfolio=decrypt_portfolio(record),
        updated_at=record.updated_at,
    )


@router.post(
    "/v1/portfolio/shares",
    response_model=PortfolioShareResponse,
)
async def share_portfolio(
    payload: PortfolioShareRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    portfolio = await session.scalar(
        select(CareerPortfolio).where(CareerPortfolio.user_id == user.id)
    )

    if portfolio is None:
        raise HTTPException(status_code=404, detail="Create your portfolio first.")

    if payload.include_contact:
        decision = await evaluate_policy(
            "portfolio.share_contact",
            {"explicit_contact_sharing": True},
        )

        if not decision.get("allow"):
            raise HTTPException(
                status_code=403,
                detail="; ".join(decision.get("reasons", []))
                or "Portfolio contact sharing was denied by policy.",
            )

    share, token = await create_share(session, portfolio, payload)
    await audit(
        session,
        "phase8.portfolio.share",
        user.id,
        {
            "portfolio_id": portfolio.id,
            "share_id": share.id,
            "expires_at": share.expires_at.isoformat(),
            "include_contact": payload.include_contact,
        },
    )
    return PortfolioShareResponse(
        share_id=share.id,
        token=token,
        public_path=f"/v1/public/portfolio/{token}",
        expires_at=share.expires_at,
    )


@router.delete("/v1/portfolio/shares/{share_id}")
async def revoke_portfolio_share(
    share_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    share = await session.get(CareerPortfolioShare, share_id)

    if share is None:
        raise HTTPException(status_code=404, detail="Portfolio share not found.")

    portfolio = await session.get(CareerPortfolio, share.portfolio_id)

    if portfolio is None or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="Portfolio share not found.")

    share.revoked_at = datetime.now(UTC)
    await session.commit()
    return {"revoked": True}


@router.get("/v1/public/portfolio/{token}")
async def read_public_portfolio(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await public_portfolio(session, token)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/v1/organizations/{organization_id}/ai-inventory",
    response_model=AISystemInventoryResponse,
)
async def add_ai_inventory(
    organization_id: str,
    payload: AISystemInventoryIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )

    try:
        record = await create_inventory(session, organization_id, payload)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="AI system version already exists.",
        ) from exc

    await audit(
        session,
        "phase8.ai_inventory.create",
        user.id,
        {
            "organization_id": organization_id,
            "inventory_id": record.id,
            "eu_risk_class": record.eu_risk_class,
        },
    )
    return inventory_response(record)


@router.get(
    "/v1/organizations/{organization_id}/ai-inventory",
    response_model=list[AISystemInventoryResponse],
)
async def list_ai_inventory(
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
                select(AISystemInventory)
                .where(AISystemInventory.organization_id == organization_id)
                .order_by(AISystemInventory.created_at.desc())
            )
        ).all()
    )
    return [inventory_response(record) for record in records]


@router.post(
    "/v1/organizations/{organization_id}/ai-inventory/{inventory_id}/risk-assessments",
    response_model=AIRiskAssessmentResponse,
)
async def add_risk_assessment(
    organization_id: str,
    inventory_id: str,
    payload: AIRiskAssessmentIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )
    inventory = await session.get(AISystemInventory, inventory_id)

    if inventory is None or inventory.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="AI inventory item not found.")

    try:
        record = await create_risk_assessment(
            session,
            inventory,
            payload,
            user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await audit(
        session,
        "phase8.ai_risk_assessment.create",
        user.id,
        {
            "organization_id": organization_id,
            "inventory_id": inventory_id,
            "risk_level": record.risk_level,
            "status": record.status,
        },
    )
    return risk_response(record)


@router.post(
    "/v1/organizations/{organization_id}/ai-incidents",
    response_model=AIIncidentResponse,
)
async def add_ai_incident(
    organization_id: str,
    payload: AIIncidentCreate,
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
        record = await create_incident(
            session,
            organization_id,
            user.id,
            payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await audit(
        session,
        "phase8.ai_incident.create",
        user.id,
        {
            "organization_id": organization_id,
            "incident_id": record.id,
            "severity": record.severity,
            "serious_incident_candidate": record.serious_incident_candidate,
        },
    )
    return incident_response(record)


@router.get(
    "/v1/organizations/{organization_id}/ai-incidents",
    response_model=list[AIIncidentResponse],
)
async def list_ai_incidents(
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
                select(AIIncident)
                .where(AIIncident.organization_id == organization_id)
                .order_by(AIIncident.detected_at.desc())
            )
        ).all()
    )
    return [incident_response(record) for record in records]


@router.patch(
    "/v1/organizations/{organization_id}/ai-incidents/{incident_id}",
    response_model=AIIncidentResponse,
)
async def patch_ai_incident(
    organization_id: str,
    incident_id: str,
    payload: AIIncidentUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )
    record = await session.get(AIIncident, incident_id)

    if record is None or record.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="AI incident not found.")

    record = await update_incident(session, record, payload)
    return incident_response(record)


@router.get("/v1/organizations/{organization_id}/governance/phase8/controls")
async def controls(
    organization_id: str,
    inventory_id: str | None = Query(default=None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    statement = select(GovernanceControlMapping).where(
        GovernanceControlMapping.organization_id == organization_id
    )

    if inventory_id:
        statement = statement.where(
            GovernanceControlMapping.inventory_id == inventory_id
        )

    records = list(
        (
            await session.scalars(
                statement.order_by(
                    GovernanceControlMapping.framework.asc(),
                    GovernanceControlMapping.control_ref.asc(),
                )
            )
        ).all()
    )
    return [
        {
            "id": item.id,
            "inventory_id": item.inventory_id,
            "framework": item.framework,
            "control_ref": item.control_ref,
            "title": item.title,
            "implementation_status": item.implementation_status,
            "owner": item.owner,
            "evidence_requirements": item.evidence_requirements,
            "notes": item.notes,
        }
        for item in records
    ]


@router.patch(
    "/v1/organizations/{organization_id}/governance/phase8/controls/{control_id}"
)
async def update_control(
    organization_id: str,
    control_id: str,
    payload: ControlMappingUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )
    record = await session.get(GovernanceControlMapping, control_id)

    if record is None or record.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Control mapping not found.")

    record.implementation_status = payload.implementation_status
    record.owner = payload.owner
    record.notes = payload.notes
    await session.commit()
    return {"updated": True}


@router.post("/v1/organizations/{organization_id}/governance/phase8/evidence")
async def collect_evidence(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )
    count = await collect_phase8_evidence(session, organization_id)
    await audit(
        session,
        "phase8.governance.evidence",
        user.id,
        {
            "organization_id": organization_id,
            "records_created": count,
        },
    )
    return {"records_created": count}


@router.get(
    "/v1/organizations/{organization_id}/governance/phase8/dashboard",
    response_model=Phase8GovernanceDashboard,
)
async def governance_dashboard(
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
    return Phase8GovernanceDashboard(
        **await phase8_dashboard(session, organization_id)
    )
