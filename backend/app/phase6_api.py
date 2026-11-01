from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.config import settings
from app.db import get_session
from app.models import (
    CareerMonitorPolicy,
    ConsentEvent,
    InboundApplication,
    JobRecommendation,
    User,
)
from app.monitoring import (
    evaluate_user_monitor,
    get_agent_run,
    list_recommendations,
    policy_response,
    run_agent_for_recommendation,
    update_monitor_policy,
)
from app.recruiter_analytics import (
    aggregate_organization_day,
    analytics_series,
    recruiter_dashboard,
    recruiter_pipeline,
)
from app.schemas import (
    AnalyticsPoint,
    CareerAgentRunRequest,
    CareerAgentRunResponse,
    JobRecommendationResponse,
    MonitorPolicyRequest,
    MonitorPolicyResponse,
    RecommendationStateUpdate,
    RecruiterCandidateRow,
    RecruiterDashboardResponse,
    RecruiterStageUpdate,
)
from app.services import audit
from app.tenancy import require_org_role


router = APIRouter()


@router.get(
    "/v1/agent/monitoring-policy",
    response_model=MonitorPolicyResponse,
)
async def get_monitoring_policy(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    policy = await session.get(CareerMonitorPolicy, user.id)

    if policy is None:
        raise HTTPException(
            status_code=404,
            detail="Career monitoring has not been configured.",
        )

    return policy_response(policy)


@router.put(
    "/v1/agent/monitoring-policy",
    response_model=MonitorPolicyResponse,
)
async def put_monitoring_policy(
    payload: MonitorPolicyRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        policy = await update_monitor_policy(
            session,
            user.id,
            payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await audit(
        session,
        "career_monitor.policy_update",
        user.id,
        {
            "enabled": payload.enabled,
            "purposes": payload.purposes,
            "consent_version": settings.agent_consent_version,
        },
    )
    return policy_response(policy)


@router.get("/v1/agent/consent-history")
async def consent_history(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    records = (
        await session.scalars(
            select(ConsentEvent)
            .where(ConsentEvent.user_id == user.id)
            .order_by(ConsentEvent.occurred_at.desc())
            .limit(200)
        )
    ).all()

    return [
        {
            "id": record.id,
            "purpose": record.purpose,
            "action": record.action,
            "consent_version": record.consent_version,
            "source": record.source,
            "occurred_at": record.occurred_at,
        }
        for record in records
    ]


@router.post("/v1/agent/monitor/scan")
async def scan_now(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        recommendation_ids = await evaluate_user_monitor(session, user.id)
    except LookupError as exc:
        raise HTTPException(
            status_code=409,
            detail="Create a candidate profile before enabling monitoring.",
        ) from exc

    await audit(
        session,
        "career_monitor.manual_scan",
        user.id,
        {"recommendations": len(recommendation_ids)},
    )
    return {
        "recommendations": len(recommendation_ids),
        "recommendation_ids": recommendation_ids,
    }


@router.get(
    "/v1/agent/recommendations",
    response_model=list[JobRecommendationResponse],
)
async def recommendations(
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_recommendations(
        session,
        user.id,
        limit=limit,
    )


@router.patch(
    "/v1/agent/recommendations/{recommendation_id}",
    response_model=JobRecommendationResponse,
)
async def update_recommendation_state(
    recommendation_id: str,
    payload: RecommendationStateUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.scalar(
        select(JobRecommendation).where(
            JobRecommendation.id == recommendation_id,
            JobRecommendation.user_id == user.id,
        )
    )

    if record is None:
        raise HTTPException(status_code=404, detail="Recommendation not found.")

    record.state = payload.state
    await session.commit()

    values = await list_recommendations(
        session,
        user.id,
        limit=100,
    )
    return next(value for value in values if value.id == record.id)


@router.post(
    "/v1/agent/runs",
    response_model=CareerAgentRunResponse,
)
async def run_agent(
    payload: CareerAgentRunRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        response = await run_agent_for_recommendation(
            session,
            user.id,
            payload.recommendation_id,
            trigger="manual",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Agent guardrail rejected the output: {exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await audit(
        session,
        "career_agent.run",
        user.id,
        {
            "run_id": response.run_id,
            "recommendation_id": payload.recommendation_id,
            "total_tokens": response.total_tokens,
        },
    )
    return response


@router.get(
    "/v1/agent/runs/{run_id}",
    response_model=CareerAgentRunResponse,
)
async def agent_run(
    run_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await get_agent_run(session, user.id, run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/v1/organizations/{organization_id}/recruiter/dashboard",
    response_model=RecruiterDashboardResponse,
)
async def recruiter_dashboard_endpoint(
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
    return await recruiter_dashboard(
        session,
        organization_id,
    )


@router.get(
    "/v1/organizations/{organization_id}/recruiter/pipeline",
    response_model=list[RecruiterCandidateRow],
)
async def recruiter_pipeline_endpoint(
    organization_id: str,
    status: str = Query(default="", max_length=100),
    limit: int = Query(default=100, ge=1, le=250),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    return await recruiter_pipeline(
        session,
        organization_id,
        status=status,
        limit=limit,
    )


@router.patch(
    "/v1/organizations/{organization_id}/recruiter/applications/{application_id}"
)
async def update_recruiter_stage(
    organization_id: str,
    application_id: str,
    payload: RecruiterStageUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    application = await session.scalar(
        select(InboundApplication).where(
            InboundApplication.id == application_id,
            InboundApplication.organization_id == organization_id,
        )
    )

    if application is None:
        raise HTTPException(status_code=404, detail="Application not found.")

    previous = application.status
    application.status = payload.status
    await session.commit()
    await audit(
        session,
        "recruiter.application.stage_update",
        user.id,
        {
            "organization_id": organization_id,
            "application_id": application_id,
            "previous_status": previous,
            "status": payload.status,
        },
    )
    return {
        "application_id": application.id,
        "status": application.status,
    }


@router.get(
    "/v1/organizations/{organization_id}/analytics",
    response_model=list[AnalyticsPoint],
)
async def organization_analytics(
    organization_id: str,
    days: int = Query(default=30, ge=1, le=365),
    refresh_today: bool = Query(default=True),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )

    if refresh_today:
        await aggregate_organization_day(
            session,
            organization_id,
            datetime.now(UTC).date(),
        )

    return await analytics_series(
        session,
        organization_id,
        days,
    )
