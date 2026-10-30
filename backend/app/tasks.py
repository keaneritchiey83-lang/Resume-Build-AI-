from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.celery_app import celery
from app.config import settings
from app.db import SessionFactory
from app.models import CareerMonitorPolicy, LearningProviderConnection, Organization, RetentionPolicy
from app.monitoring import (
    consent_allows,
    evaluate_user_monitor,
    policy_is_due,
    run_agent_for_recommendation,
)
from app.recruiter_analytics import aggregate_all_organizations
from app.webhook_pipeline import (
    mark_dead_letter,
    process_event_in_session,
)


async def _process_webhook(event_id: str) -> None:
    async with SessionFactory() as session:
        await process_event_in_session(session, event_id)


@celery.task(
    bind=True,
    max_retries=6,
    name="career.process_webhook_event",
)
def process_webhook_event(self, event_id: str) -> None:
    try:
        asyncio.run(_process_webhook(event_id))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(
                mark_dead_letter(
                    event_id,
                    f"{type(exc).__name__}: {str(exc)}",
                )
            )
            raise

        countdown = min(3600, 15 * (2 ** self.request.retries))
        raise self.retry(exc=exc, countdown=countdown)


def enqueue_webhook_event(event_id: str) -> None:
    process_webhook_event.delay(event_id)


async def _scan_monitor_policies() -> int:
    if not settings.agent_monitor_enabled:
        return 0

    queued = 0

    async with SessionFactory() as session:
        policies = (
            await session.scalars(
                select(CareerMonitorPolicy).where(
                    CareerMonitorPolicy.enabled.is_(True)
                )
            )
        ).all()

        now = datetime.now(UTC)

        for policy in policies:
            try:
                if policy_is_due(policy, now):
                    evaluate_job_monitor.delay(policy.user_id)
                    queued += 1
            except Exception:
                continue

    return queued


@celery.task(name="career.scan_job_monitors")
def scan_job_monitors() -> int:
    return asyncio.run(_scan_monitor_policies())


async def _evaluate_job_monitor(user_id: str) -> list[str]:
    async with SessionFactory() as session:
        recommendation_ids = await evaluate_user_monitor(session, user_id)
        policy = await session.get(CareerMonitorPolicy, user_id)

        if (
            policy is not None
            and consent_allows(policy, "ai_career_analysis")
            and settings.openai_api_key.get_secret_value()
        ):
            for recommendation_id in recommendation_ids[
                : settings.agent_auto_analysis_limit
            ]:
                run_agent_recommendation.delay(user_id, recommendation_id)

        return recommendation_ids


@celery.task(
    bind=True,
    max_retries=3,
    name="career.evaluate_job_monitor",
)
def evaluate_job_monitor(self, user_id: str) -> list[str]:
    try:
        return asyncio.run(_evaluate_job_monitor(user_id))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            raise

        countdown = min(1800, 60 * (2 ** self.request.retries))
        raise self.retry(exc=exc, countdown=countdown)


async def _run_agent_recommendation(
    user_id: str,
    recommendation_id: str,
) -> str:
    async with SessionFactory() as session:
        response = await run_agent_for_recommendation(
            session,
            user_id,
            recommendation_id,
            trigger="automated_monitor",
        )
        return response.run_id


@celery.task(
    bind=True,
    max_retries=2,
    name="career.run_agent_recommendation",
)
def run_agent_recommendation(
    self,
    user_id: str,
    recommendation_id: str,
) -> str:
    try:
        return asyncio.run(
            _run_agent_recommendation(
                user_id,
                recommendation_id,
            )
        )
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            raise

        raise self.retry(
            exc=exc,
            countdown=min(1800, 120 * (2 ** self.request.retries)),
        )


@celery.task(name="career.aggregate_recruiter_analytics")
def aggregate_recruiter_analytics() -> int:
    async def run() -> int:
        async with SessionFactory() as session:
            today = datetime.now(UTC).date()
            count = await aggregate_all_organizations(session, today)
            await aggregate_all_organizations(
                session,
                today - timedelta(days=1),
            )
            return count

    return asyncio.run(run())


@celery.task(name="career.collect_phase7_compliance_evidence")
def collect_phase7_compliance_evidence() -> int:
    async def run() -> int:
        from sqlalchemy import select

        from app.governance import collect_soc2_evidence
        async with SessionFactory() as session:
            organization_ids = list(
                (
                    await session.scalars(
                        select(Organization.id)
                    )
                ).all()
            )
            captured = 0

            for organization_id in organization_ids:
                records = await collect_soc2_evidence(
                    session,
                    organization_id,
                )
                captured += len(records)

            return captured

    return asyncio.run(run())

@celery.task(name="career.sync_phase8_learning_catalogs")
def sync_phase8_learning_catalogs() -> int:
    async def run() -> int:
        from app.learning_providers import sync_connection

        async with SessionFactory() as session:
            connections = list(
                (
                    await session.scalars(
                        select(LearningProviderConnection).where(
                            LearningProviderConnection.enabled.is_(True)
                        )
                    )
                ).all()
            )
            synced = 0

            for connection in connections:
                try:
                    synced += await sync_connection(session, connection)
                except Exception:
                    continue

            return synced

    return asyncio.run(run())


@celery.task(name="career.collect_phase8_governance_evidence")
def collect_phase8_governance_evidence() -> int:
    async def run() -> int:
        from app.governance8 import collect_phase8_evidence

        async with SessionFactory() as session:
            organization_ids = list(
                (
                    await session.scalars(
                        select(Organization.id)
                    )
                ).all()
            )
            captured = 0

            for organization_id in organization_ids:
                captured += await collect_phase8_evidence(
                    session,
                    organization_id,
                )

            return captured

    return asyncio.run(run())

@celery.task(name="career.enforce_phase9_retention")
def enforce_phase9_retention() -> int:
    async def run() -> int:
        from app.phase9_services import enforce_retention_policy

        async with SessionFactory() as session:
            policies = list(
                (
                    await session.scalars(
                        select(RetentionPolicy).where(
                            RetentionPolicy.enabled.is_(True)
                        )
                    )
                ).all()
            )
            deleted = 0

            for policy in policies:
                try:
                    deleted += await enforce_retention_policy(session, policy)
                except Exception:
                    continue

            return deleted

    return asyncio.run(run())


@celery.task(name="career.collect_phase9_continuous_controls")
def collect_phase9_continuous_controls() -> int:
    async def run() -> int:
        from app.phase9_services import continuous_control_snapshot

        async with SessionFactory() as session:
            organization_ids = list(
                (
                    await session.scalars(
                        select(Organization.id)
                    )
                ).all()
            )
            captured = 0

            for organization_id in organization_ids:
                try:
                    await continuous_control_snapshot(session, organization_id)
                    captured += 1
                except Exception:
                    continue

            return captured

    return asyncio.run(run())

@celery.task(name="career.run_phase10_data_discovery")
def run_phase10_data_discovery() -> int:
    async def run() -> int:
        from app.phase10_services import run_data_discovery

        async with SessionFactory() as session:
            organization_ids = list(
                (await session.scalars(select(Organization.id))).all()
            )
            completed = 0

            for organization_id in organization_ids:
                try:
                    await run_data_discovery(session, organization_id)
                    completed += 1
                except Exception:
                    continue

            return completed

    return asyncio.run(run())


@celery.task(name="career.verify_phase10_audit_chains")
def verify_phase10_audit_chains() -> int:
    async def run() -> int:
        from app.phase10_services import verify_crypto_audit_chain

        async with SessionFactory() as session:
            organization_ids = list(
                (await session.scalars(select(Organization.id))).all()
            )
            valid = 0

            for organization_id in organization_ids:
                try:
                    result = await verify_crypto_audit_chain(
                        session,
                        organization_id,
                    )
                    if result["valid"]:
                        valid += 1
                except Exception:
                    continue

            return valid

    return asyncio.run(run())


@celery.task(name="career.cleanup_phase10_protocol_state")
def cleanup_phase10_protocol_state() -> dict[str, int]:
    async def run() -> dict[str, int]:
        from app.phase10_services import cleanup_expired_protocol_state

        async with SessionFactory() as session:
            return await cleanup_expired_protocol_state(session)

    return asyncio.run(run())



@celery.task(name="career.cleanup_phase12_runtime_events")
def cleanup_phase12_runtime_events() -> int:
    async def run() -> int:
        from app.phase12_services import purge_runtime_security_events

        async with SessionFactory() as session:
            return await purge_runtime_security_events(session)

    return asyncio.run(run())
@celery.task(name="career.create_phase13_trust_snapshots")
def create_phase13_trust_snapshots() -> int:
    async def run() -> int:
        from app.phase13_services import create_trust_continuity_snapshot

        async with SessionFactory() as session:
            organizations = list((await session.scalars(select(Organization))).all())
            created = 0

            for organization in organizations:
                try:
                    await create_trust_continuity_snapshot(
                        session,
                        organization_id=organization.id,
                        region_id=None,
                        snapshot_version="phase13-v1",
                        actor_user_id=organization.created_by_user_id,
                    )
                    created += 1
                except Exception:
                    continue

            return created

    return asyncio.run(run())


@celery.task(name="career.cleanup_phase13_trust_snapshots")
def cleanup_phase13_trust_snapshots() -> int:
    async def run() -> int:
        from app.phase13_services import purge_expired_trust_snapshots

        async with SessionFactory() as session:
            return await purge_expired_trust_snapshots(session)

    return asyncio.run(run())
