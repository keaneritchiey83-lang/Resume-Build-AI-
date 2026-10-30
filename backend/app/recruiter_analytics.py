from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crypto import decrypt_text
from app.models import (
    AnalyticsDaily,
    InboundApplication,
    InboundCandidate,
    Organization,
    WebhookEvent,
)
from app.schemas import RecruiterCandidateRow, RecruiterDashboardResponse


async def recruiter_dashboard(
    session: AsyncSession,
    organization_id: str,
) -> RecruiterDashboardResponse:
    candidates = int(
        await session.scalar(
            select(func.count(InboundCandidate.id)).where(
                InboundCandidate.organization_id == organization_id
            )
        )
        or 0
    )
    applications = int(
        await session.scalar(
            select(func.count(InboundApplication.id)).where(
                InboundApplication.organization_id == organization_id
            )
        )
        or 0
    )
    cutoff = datetime.now(UTC) - timedelta(days=30)
    recent = int(
        await session.scalar(
            select(func.count(InboundApplication.id)).where(
                InboundApplication.organization_id == organization_id,
                InboundApplication.received_at >= cutoff,
            )
        )
        or 0
    )

    stage_rows = (
        await session.execute(
            select(
                InboundApplication.status,
                func.count(InboundApplication.id),
            )
            .where(InboundApplication.organization_id == organization_id)
            .group_by(InboundApplication.status)
        )
    ).all()
    source_rows = (
        await session.execute(
            select(
                InboundApplication.provider,
                func.count(InboundApplication.id),
            )
            .where(InboundApplication.organization_id == organization_id)
            .group_by(InboundApplication.provider)
        )
    ).all()
    dead_letters = int(
        await session.scalar(
            select(func.count(WebhookEvent.id)).where(
                WebhookEvent.organization_id == organization_id,
                WebhookEvent.status == "dead_letter",
            )
        )
        or 0
    )

    return RecruiterDashboardResponse(
        organization_id=organization_id,
        candidates=candidates,
        applications=applications,
        applications_last_30_days=recent,
        by_stage={str(status): int(count) for status, count in stage_rows},
        by_source={str(source): int(count) for source, count in source_rows},
        webhook_dead_letters=dead_letters,
    )


async def recruiter_pipeline(
    session: AsyncSession,
    organization_id: str,
    *,
    status: str = "",
    limit: int = 100,
) -> list[RecruiterCandidateRow]:
    statement = (
        select(InboundApplication, InboundCandidate)
        .join(
            InboundCandidate,
            InboundCandidate.id == InboundApplication.candidate_id,
        )
        .where(InboundApplication.organization_id == organization_id)
    )

    if status:
        statement = statement.where(InboundApplication.status == status)

    rows = (
        await session.execute(
            statement.order_by(InboundApplication.received_at.desc()).limit(limit)
        )
    ).all()

    output: list[RecruiterCandidateRow] = []

    for application, candidate in rows:
        candidate_payload = json.loads(
            decrypt_text(
                candidate.encrypted_payload,
                aad=(
                    f"inbound-candidate:{organization_id}:"
                    f"{candidate.id}"
                ),
            )
        )
        output.append(
            RecruiterCandidateRow(
                application_id=application.id,
                candidate_id=candidate.id,
                full_name=str(candidate_payload.get("full_name", "")),
                email=str(candidate_payload.get("email", "")),
                provider=application.provider,
                external_job_id=application.external_job_id,
                source_attribution=application.source_attribution,
                status=application.status,
                received_at=application.received_at,
                processing_basis=candidate.processing_basis,
                privacy_notice_version=candidate.privacy_notice_version,
            )
        )

    return output


async def aggregate_organization_day(
    session: AsyncSession,
    organization_id: str,
    day: date,
) -> None:
    start = datetime.combine(day, time.min, tzinfo=UTC)
    end = start + timedelta(days=1)

    applications = (
        await session.scalars(
            select(InboundApplication).where(
                InboundApplication.organization_id == organization_id,
                InboundApplication.received_at >= start,
                InboundApplication.received_at < end,
            )
        )
    ).all()

    metrics: list[tuple[str, str, float, dict[str, Any]]] = [
        ("applications_received", "", float(len(applications)), {}),
    ]

    stages = Counter(item.status for item in applications)
    sources = Counter(item.provider for item in applications)

    for stage, count in stages.items():
        metrics.append(
            (
                "applications_by_stage",
                f"stage:{stage}",
                float(count),
                {"stage": stage},
            )
        )

    for source, count in sources.items():
        metrics.append(
            (
                "applications_by_source",
                f"source:{source}",
                float(count),
                {"source": source},
            )
        )

    for metric, dimension_key, value, dimensions in metrics:
        statement = insert(AnalyticsDaily).values(
            organization_id=organization_id,
            day=day,
            metric=metric,
            dimension_key=dimension_key,
            value=value,
            dimensions=dimensions,
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_analytics_daily_org_metric_dimension",
            set_={
                "value": statement.excluded.value,
                "dimensions": statement.excluded.dimensions,
            },
        )
        await session.execute(statement)

    await session.commit()


async def aggregate_all_organizations(
    session: AsyncSession,
    day: date | None = None,
) -> int:
    target_day = day or datetime.now(UTC).date()
    organizations = (await session.scalars(select(Organization))).all()

    for organization in organizations:
        await aggregate_organization_day(
            session,
            organization.id,
            target_day,
        )

    retention_cutoff = target_day - timedelta(days=settings.analytics_retention_days)
    await session.execute(
        delete(AnalyticsDaily).where(AnalyticsDaily.day < retention_cutoff)
    )
    await session.commit()
    return len(organizations)


async def analytics_series(
    session: AsyncSession,
    organization_id: str,
    days: int,
) -> list[dict[str, Any]]:
    cutoff = datetime.now(UTC).date() - timedelta(days=max(days - 1, 0))
    rows = (
        await session.scalars(
            select(AnalyticsDaily)
            .where(
                AnalyticsDaily.organization_id == organization_id,
                AnalyticsDaily.day >= cutoff,
            )
            .order_by(
                AnalyticsDaily.day.asc(),
                AnalyticsDaily.metric.asc(),
                AnalyticsDaily.dimension_key.asc(),
            )
        )
    ).all()

    return [
        {
            "day": row.day.isoformat(),
            "metric": row.metric,
            "dimension_key": row.dimension_key,
            "value": row.value,
            "dimensions": row.dimensions,
        }
        for row in rows
    ]
