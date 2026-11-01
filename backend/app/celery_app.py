from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings
from app.telemetry import configure_celery_telemetry


broker_url = settings.celery_broker_url or settings.redis_url
result_backend = settings.celery_result_backend or settings.redis_url

celery = Celery(
    "global_career_ai",
    broker=broker_url,
    backend=result_backend,
    include=["app.tasks"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    result_expires=3600,
    timezone="UTC",
    beat_schedule={
        "scan-job-monitors": {
            "task": "career.scan_job_monitors",
            "schedule": max(60, settings.agent_monitor_interval_minutes * 60),
        },
        "aggregate-recruiter-analytics": {
            "task": "career.aggregate_recruiter_analytics",
            "schedule": crontab(hour=2, minute=15),
        },
        "collect-phase7-compliance-evidence": {
            "task": "career.collect_phase7_compliance_evidence",
            "schedule": crontab(hour=3, minute=30),
        },
        "sync-phase8-learning-catalogs": {
            "task": "career.sync_phase8_learning_catalogs",
            "schedule": max(3600, settings.phase8_learning_sync_hours * 3600),
        },
        "collect-phase8-governance-evidence": {
            "task": "career.collect_phase8_governance_evidence",
            "schedule": max(3600, settings.phase8_evidence_interval_hours * 3600),
        },
        "enforce-phase9-retention": {
            "task": "career.enforce_phase9_retention",
            "schedule": max(3600, settings.phase9_retention_interval_hours * 3600),
        },
        "collect-phase9-continuous-controls": {
            "task": "career.collect_phase9_continuous_controls",
            "schedule": max(
                3600,
                settings.phase9_continuous_control_interval_hours * 3600,
            ),
        },
        "run-phase10-data-discovery": {
            "task": "career.run_phase10_data_discovery",
            "schedule": max(3600, settings.phase10_privacy_scan_hours * 3600),
        },
        "verify-phase10-audit-chains": {
            "task": "career.verify_phase10_audit_chains",
            "schedule": max(3600, settings.phase10_audit_verify_hours * 3600),
        },
        "cleanup-phase10-protocol-state": {
            "task": "career.cleanup_phase10_protocol_state",
            "schedule": max(900, settings.phase10_protocol_cleanup_hours * 3600),
        },
        "cleanup-phase12-runtime-events": {
            "task": "career.cleanup_phase12_runtime_events",
            "schedule": crontab(hour=4, minute=10),
        },
        "create-phase13-trust-snapshots": {
            "task": "career.create_phase13_trust_snapshots",
            "schedule": max(3600, settings.phase13_trust_snapshot_hours * 3600),
        },
        "cleanup-phase13-trust-snapshots": {
            "task": "career.cleanup_phase13_trust_snapshots",
            "schedule": crontab(hour=4, minute=40),
        },
    },
)

configure_celery_telemetry()

