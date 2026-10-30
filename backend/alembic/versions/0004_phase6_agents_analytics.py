"""Phase 6 career agents, consent monitoring and recruiter analytics.

Revision ID: 0004_phase6
Revises: 0003_phase5
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_phase6"
down_revision = "0003_phase5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consent_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("consent_version", sa.String(100), nullable=False),
        sa.Column("source", sa.String(100), nullable=False, server_default="user"),
        sa.Column("evidence_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_consent_events_user_id", "consent_events", ["user_id"])
    op.create_index("ix_consent_events_purpose", "consent_events", ["purpose"])
    op.create_index("ix_consent_events_action", "consent_events", ["action"])
    op.create_index("ix_consent_events_occurred_at", "consent_events", ["occurred_at"])

    op.create_table(
        "career_monitor_policies",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("encrypted_preferences", sa.Text(), nullable=False),
        sa.Column(
            "minimum_match_score",
            sa.Float(),
            nullable=False,
            server_default="65",
        ),
        sa.Column("cadence", sa.String(50), nullable=False, server_default="daily"),
        sa.Column(
            "allow_ai_analysis",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "allow_notifications",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("consent_version", sa.String(100), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_career_monitor_policies_enabled",
        "career_monitor_policies",
        ["enabled"],
    )
    op.create_index(
        "ix_career_monitor_policies_last_scanned_at",
        "career_monitor_policies",
        ["last_scanned_at"],
    )

    op.create_table(
        "job_recommendations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.String(64),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("encrypted_analysis", sa.Text(), nullable=False),
        sa.Column("state", sa.String(50), nullable=False, server_default="new"),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "user_id",
            "job_id",
            name="uq_job_recommendation_user_job",
        ),
    )
    op.create_index(
        "ix_job_recommendations_user_id",
        "job_recommendations",
        ["user_id"],
    )
    op.create_index(
        "ix_job_recommendations_job_id",
        "job_recommendations",
        ["job_id"],
    )
    op.create_index(
        "ix_job_recommendations_score",
        "job_recommendations",
        ["score"],
    )
    op.create_index(
        "ix_job_recommendations_state",
        "job_recommendations",
        ["state"],
    )
    op.create_index(
        "ix_job_recommendations_evaluated_at",
        "job_recommendations",
        ["evaluated_at"],
    )

    op.create_table(
        "career_agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "job_id",
            sa.String(64),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("agent_type", sa.String(100), nullable=False),
        sa.Column("trigger", sa.String(100), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("encrypted_result", sa.Text(), nullable=False, server_default=""),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_career_agent_runs_user_id", "career_agent_runs", ["user_id"])
    op.create_index(
        "ix_career_agent_runs_organization_id",
        "career_agent_runs",
        ["organization_id"],
    )
    op.create_index("ix_career_agent_runs_job_id", "career_agent_runs", ["job_id"])
    op.create_index(
        "ix_career_agent_runs_agent_type",
        "career_agent_runs",
        ["agent_type"],
    )
    op.create_index("ix_career_agent_runs_status", "career_agent_runs", ["status"])
    op.create_index(
        "ix_career_agent_runs_started_at",
        "career_agent_runs",
        ["started_at"],
    )

    op.create_table(
        "analytics_daily",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("dimension_key", sa.String(300), nullable=False, server_default=""),
        sa.Column("value", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "dimensions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "day",
            "metric",
            "dimension_key",
            name="uq_analytics_daily_org_metric_dimension",
        ),
    )
    op.create_index(
        "ix_analytics_daily_organization_id",
        "analytics_daily",
        ["organization_id"],
    )
    op.create_index("ix_analytics_daily_day", "analytics_daily", ["day"])
    op.create_index("ix_analytics_daily_metric", "analytics_daily", ["metric"])


def downgrade() -> None:
    op.drop_table("analytics_daily")
    op.drop_table("career_agent_runs")
    op.drop_table("job_recommendations")
    op.drop_table("career_monitor_policies")
    op.drop_table("consent_events")
