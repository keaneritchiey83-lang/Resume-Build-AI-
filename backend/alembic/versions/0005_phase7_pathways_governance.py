"""Phase 7 pathways, salary intelligence and enterprise governance.

Revision ID: 0005_phase7
Revises: 0004_phase6
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_phase7"
down_revision = "0004_phase6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "salary_benchmarks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("data_vintage", sa.String(100), nullable=False),
        sa.Column("country_code", sa.String(3), nullable=False),
        sa.Column("region_code", sa.String(100), nullable=False, server_default=""),
        sa.Column("occupation_code", sa.String(100), nullable=False),
        sa.Column("occupation_title", sa.String(1000), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("wage_p10", sa.Float(), nullable=True),
        sa.Column("wage_p25", sa.Float(), nullable=True),
        sa.Column("wage_median", sa.Float(), nullable=True),
        sa.Column("wage_p75", sa.Float(), nullable=True),
        sa.Column("wage_p90", sa.Float(), nullable=True),
        sa.Column("annual_mean", sa.Float(), nullable=True),
        sa.Column("employment", sa.Float(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("license", sa.String(500), nullable=False, server_default=""),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "source",
            "data_vintage",
            "country_code",
            "region_code",
            "occupation_code",
            name="uq_salary_benchmark_source_vintage_geo_occ",
        ),
    )
    for column in (
        "source",
        "data_vintage",
        "country_code",
        "region_code",
        "occupation_code",
        "occupation_title",
    ):
        op.create_index(f"ix_salary_benchmarks_{column}", "salary_benchmarks", [column])

    op.create_table(
        "education_pathways",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("external_id", sa.String(1000), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("provider", sa.String(500), nullable=False, server_default=""),
        sa.Column("pathway_type", sa.String(100), nullable=False),
        sa.Column("country_code", sa.String(3), nullable=False, server_default=""),
        sa.Column("occupation_code", sa.String(100), nullable=False, server_default=""),
        sa.Column("skills", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("license", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(50), nullable=False, server_default="approved"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "source",
            "external_id",
            name="uq_education_pathway_source_external",
        ),
    )
    for column in ("source", "title", "pathway_type", "country_code", "occupation_code", "status"):
        op.create_index(f"ix_education_pathways_{column}", "education_pathways", [column])

    op.create_table(
        "mobility_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("from_country", sa.String(3), nullable=False),
        sa.Column("from_occupation_code", sa.String(100), nullable=False),
        sa.Column("from_title", sa.String(1000), nullable=False),
        sa.Column("to_country", sa.String(3), nullable=False),
        sa.Column("to_occupation_code", sa.String(100), nullable=False),
        sa.Column("to_title", sa.String(1000), nullable=False),
        sa.Column("common_taxonomy", sa.String(100), nullable=False, server_default="ISCO-08"),
        sa.Column("common_code", sa.String(100), nullable=False, server_default=""),
        sa.Column("skill_overlap", sa.Float(), nullable=False, server_default="0"),
        sa.Column("transition_effort", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "source",
            "from_country",
            "from_occupation_code",
            "to_country",
            "to_occupation_code",
            name="uq_mobility_mapping_route",
        ),
    )
    for column in (
        "source", "from_country", "from_occupation_code",
        "to_country", "to_occupation_code", "common_code"
    ):
        op.create_index(f"ix_mobility_mappings_{column}", "mobility_mappings", [column])

    op.create_table(
        "career_forecasts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_country", sa.String(3), nullable=False, server_default="USA"),
        sa.Column("method_version", sa.String(100), nullable=False),
        sa.Column("data_version", sa.String(200), nullable=False),
        sa.Column("encrypted_result", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_career_forecasts_user_id", "career_forecasts", ["user_id"])
    op.create_index("ix_career_forecasts_target_country", "career_forecasts", ["target_country"])
    op.create_index("ix_career_forecasts_created_at", "career_forecasts", ["created_at"])

    op.create_table(
        "learning_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_occupation_code", sa.String(100), nullable=False),
        sa.Column("target_occupation_title", sa.String(1000), nullable=False),
        sa.Column("encrypted_plan", sa.Text(), nullable=False),
        sa.Column("method_version", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_learning_plans_user_id", "learning_plans", ["user_id"])
    op.create_index("ix_learning_plans_target_occupation_code", "learning_plans", ["target_occupation_code"])
    op.create_index("ix_learning_plans_created_at", "learning_plans", ["created_at"])

    op.create_table(
        "governance_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("policy_key", sa.String(200), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("policy_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "policy_key",
            "version",
            name="uq_governance_policy_org_key_version",
        ),
    )
    op.create_index("ix_governance_policies_organization_id", "governance_policies", ["organization_id"])
    op.create_index("ix_governance_policies_policy_key", "governance_policies", ["policy_key"])
    op.create_index("ix_governance_policies_version", "governance_policies", ["version"])

    op.create_table(
        "model_eval_suites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("cases_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_model_eval_suites_organization_id", "model_eval_suites", ["organization_id"])
    op.create_index("ix_model_eval_suites_name", "model_eval_suites", ["name"])

    op.create_table(
        "model_eval_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "suite_id",
            sa.String(36),
            sa.ForeignKey("model_eval_suites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(300), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("results_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in ("suite_id", "model_name", "status", "started_at"):
        op.create_index(f"ix_model_eval_runs_{column}", "model_eval_runs", [column])

    op.create_table(
        "fairness_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("process_name", sa.String(200), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("reference_group", sa.String(200), nullable=False),
        sa.Column("minimum_group_size", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("results_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    for column in ("organization_id", "process_name", "metric", "requires_review", "created_at"):
        op.create_index(f"ix_fairness_snapshots_{column}", "fairness_snapshots", [column])

    op.create_table(
        "human_review_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("subject_type", sa.String(100), nullable=False),
        sa.Column("subject_id", sa.String(200), nullable=False, server_default=""),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column(
            "assigned_to_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("encrypted_context", sa.Text(), nullable=False, server_default=""),
        sa.Column("resolution", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in (
        "organization_id", "category", "severity", "subject_type",
        "subject_id", "status", "created_at"
    ):
        op.create_index(f"ix_human_review_items_{column}", "human_review_items", [column])

    op.create_table(
        "compliance_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("framework", sa.String(100), nullable=False),
        sa.Column("control_id", sa.String(100), nullable=False),
        sa.Column("evidence_type", sa.String(100), nullable=False),
        sa.Column("source", sa.String(300), nullable=False),
        sa.Column("artifact_hash", sa.String(64), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "framework",
            "control_id",
            "artifact_hash",
            name="uq_compliance_evidence_artifact",
        ),
    )
    for column in (
        "organization_id", "framework", "control_id", "artifact_hash", "captured_at"
    ):
        op.create_index(f"ix_compliance_evidence_{column}", "compliance_evidence", [column])


def downgrade() -> None:
    op.drop_table("compliance_evidence")
    op.drop_table("human_review_items")
    op.drop_table("fairness_snapshots")
    op.drop_table("model_eval_runs")
    op.drop_table("model_eval_suites")
    op.drop_table("governance_policies")
    op.drop_table("learning_plans")
    op.drop_table("career_forecasts")
    op.drop_table("mobility_mappings")
    op.drop_table("education_pathways")
    op.drop_table("salary_benchmarks")
