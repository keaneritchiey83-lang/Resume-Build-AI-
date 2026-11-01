"""Phase 9 portable career records, privacy operations, lineage and red teaming.

Revision ID: 0007_phase9
Revises: 0006_phase8
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_phase9"
down_revision = "0006_phase8"
branch_labels = None
depends_on = None


def _indices(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "candidate_wallets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("holder_did", sa.Text(), nullable=False),
        sa.Column("did_method", sa.String(100), nullable=False),
        sa.Column("wallet_type", sa.String(100), nullable=False, server_default="external"),
        sa.Column("presentation_endpoint", sa.Text(), nullable=False, server_default=""),
        sa.Column("issuance_endpoint", sa.Text(), nullable=False, server_default=""),
        sa.Column("verification_status", sa.String(100), nullable=False, server_default="registered"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "holder_did", name="uq_candidate_wallet_user_did"),
    )
    _indices("candidate_wallets", ("user_id", "did_method", "verification_status"))

    op.create_table(
        "skills_passports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("wallet_id", sa.String(36), sa.ForeignKey("candidate_wallets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", name="uq_skills_passport_user"),
    )
    _indices("skills_passports", ("user_id", "wallet_id", "payload_hash"))

    op.create_table(
        "privacy_impact_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("system_or_process", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("risk_level", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("processing_purposes", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("data_categories", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("data_subjects", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("jurisdictions", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("lawful_bases", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("recipients", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("retention_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("international_transfers", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("automated_decision_support", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("high_risk_processing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("mitigations", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    _indices("privacy_impact_assessments", ("organization_id", "system_or_process", "status", "risk_level", "review_due_at", "created_at"))

    op.create_table(
        "data_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_key", sa.String(200), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("asset_type", sa.String(100), nullable=False),
        sa.Column("data_categories", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("contains_personal_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("contains_sensitive_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("system_owner", sa.String(500), nullable=False, server_default=""),
        sa.Column("retention_class", sa.String(100), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("organization_id", "asset_key", name="uq_data_asset_org_key"),
    )
    _indices("data_assets", ("organization_id", "asset_key", "asset_type", "retention_class"))

    op.create_table(
        "data_lineage_edges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("upstream_asset_id", sa.String(36), sa.ForeignKey("data_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("downstream_asset_id", sa.String(36), sa.ForeignKey("data_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transformation", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("purpose_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint(
            "organization_id", "upstream_asset_id", "downstream_asset_id", "purpose_hash",
            name="uq_data_lineage_edge",
        ),
    )
    _indices("data_lineage_edges", ("organization_id", "upstream_asset_id", "downstream_asset_id"))

    op.create_table(
        "retention_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_type", sa.String(100), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_deleted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("organization_id", "record_type", name="uq_retention_policy_org_type"),
    )
    _indices("retention_policies", ("organization_id", "record_type", "enabled"))

    op.create_table(
        "data_subject_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="received"),
        sa.Column("identity_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("encrypted_details", sa.Text(), nullable=False, server_default=""),
        sa.Column("encrypted_result", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    _indices("data_subject_requests", ("user_id", "request_type", "status", "submitted_at", "due_at"))

    op.create_table(
        "red_team_campaigns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inventory_id", sa.String(36), sa.ForeignKey("ai_system_inventory.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(50), nullable=False, server_default="planned"),
        sa.Column("total_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("encrypted_findings", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    _indices("red_team_campaigns", ("organization_id", "inventory_id", "status", "created_at"))

    op.create_table(
        "continuous_control_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("overall_status", sa.String(50), nullable=False),
        sa.Column("checks_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("open_findings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    _indices("continuous_control_snapshots", ("organization_id", "overall_status", "generated_at"))


def downgrade() -> None:
    for table in (
        "continuous_control_snapshots",
        "red_team_campaigns",
        "data_subject_requests",
        "retention_policies",
        "data_lineage_edges",
        "data_assets",
        "privacy_impact_assessments",
        "skills_passports",
        "candidate_wallets",
    ):
        op.drop_table(table)
