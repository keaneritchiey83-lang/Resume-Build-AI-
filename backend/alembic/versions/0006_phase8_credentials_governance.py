"""Phase 8 credentials, learning, labor intelligence, portfolios and AI governance.

Revision ID: 0006_phase8
Revises: 0005_phase7
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_phase8"
down_revision = "0005_phase7"
branch_labels = None
depends_on = None


def _indices(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "verified_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_hash", sa.String(64), nullable=False),
        sa.Column("credential_id", sa.String(2000), nullable=False, server_default=""),
        sa.Column("credential_format", sa.String(100), nullable=False),
        sa.Column("credential_type", sa.String(300), nullable=False, server_default=""),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("issuer_name", sa.String(1000), nullable=False, server_default=""),
        sa.Column("issuer_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("subject_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("verification_level", sa.String(100), nullable=False, server_default="structural"),
        sa.Column("verification_method", sa.String(300), nullable=False, server_default=""),
        sa.Column("verification_status", sa.String(100), nullable=False, server_default="unverified"),
        sa.Column("skills", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "credential_hash", name="uq_verified_credential_user_hash"),
    )
    _indices("verified_credentials", ("user_id","credential_hash","credential_format","title","subject_hash","verification_level","verification_status","created_at"))

    op.create_table(
        "learning_provider_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("organization_id","provider","base_url",name="uq_learning_provider_org_provider_url"),
    )
    _indices("learning_provider_connections", ("organization_id","provider","enabled"))

    op.create_table(
        "learning_catalog_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", sa.String(36), sa.ForeignKey("learning_provider_connections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(1000), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("learning_type", sa.String(100), nullable=False, server_default="course"),
        sa.Column("skills", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("level", sa.String(100), nullable=False, server_default=""),
        sa.Column("language", sa.String(50), nullable=False, server_default=""),
        sa.Column("duration_hours", sa.Float(), nullable=True),
        sa.Column("credential_offered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("provenance_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("organization_id","provider","external_id",name="uq_learning_catalog_org_provider_external"),
    )
    _indices("learning_catalog_items", ("organization_id","connection_id","provider","title","learning_type","updated_at"))

    op.create_table(
        "labor_market_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("data_vintage", sa.String(100), nullable=False),
        sa.Column("country_code", sa.String(3), nullable=False),
        sa.Column("region_code", sa.String(100), nullable=False, server_default=""),
        sa.Column("occupation_code", sa.String(100), nullable=False),
        sa.Column("occupation_title", sa.String(1000), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("period", sa.String(50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(100), nullable=False, server_default=""),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("license", sa.String(500), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("source","country_code","region_code","occupation_code","metric","period",name="uq_labor_observation_series_period"),
    )
    _indices("labor_market_observations", ("source","data_vintage","country_code","region_code","occupation_code","occupation_title","metric","period"))

    op.create_table(
        "labor_trend_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("country_code", sa.String(3), nullable=False),
        sa.Column("region_code", sa.String(100), nullable=False, server_default=""),
        sa.Column("occupation_code", sa.String(100), nullable=False),
        sa.Column("occupation_title", sa.String(1000), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("method_version", sa.String(100), nullable=False),
        sa.Column("input_count", sa.Integer(), nullable=False),
        sa.Column("start_period", sa.String(50), nullable=False),
        sa.Column("end_period", sa.String(50), nullable=False),
        sa.Column("start_value", sa.Float(), nullable=False),
        sa.Column("end_value", sa.Float(), nullable=False),
        sa.Column("linear_slope", sa.Float(), nullable=False),
        sa.Column("annualized_change", sa.Float(), nullable=True),
        sa.Column("volatility", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("projected_next_value", sa.Float(), nullable=True),
        sa.Column("provenance_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    _indices("labor_trend_snapshots", ("source","country_code","region_code","occupation_code","metric","direction","created_at"))

    op.create_table(
        "career_portfolios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", name="uq_career_portfolio_user"),
    )
    _indices("career_portfolios", ("user_id",))

    op.create_table(
        "career_portfolio_shares",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portfolio_id", sa.String(36), sa.ForeignKey("career_portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("visibility_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
    )
    _indices("career_portfolio_shares", ("portfolio_id","token_hash","expires_at"))

    op.create_table(
        "ai_system_inventory",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_key", sa.String(200), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("owner", sa.String(500), nullable=False, server_default=""),
        sa.Column("intended_purpose", sa.Text(), nullable=False),
        sa.Column("operator_role", sa.String(50), nullable=False, server_default="deployer"),
        sa.Column("lifecycle_status", sa.String(50), nullable=False, server_default="development"),
        sa.Column("jurisdictions", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("model_names", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("data_categories", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("employment_use", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("education_use", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("profiles_natural_persons", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("materially_influences_decisions", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("human_oversight", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("eu_risk_class", sa.String(100), nullable=False, server_default="not_assessed"),
        sa.Column("eu_classification_basis", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("iso42001_in_scope", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("applicable_from", sa.Date(), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("organization_id","system_key","version",name="uq_ai_inventory_org_key_version"),
    )
    _indices("ai_system_inventory", ("organization_id","system_key","version","lifecycle_status","employment_use","eu_risk_class"))

    op.create_table(
        "ai_risk_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("inventory_id", sa.String(36), sa.ForeignKey("ai_system_inventory.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_version", sa.String(100), nullable=False),
        sa.Column("likelihood", sa.Integer(), nullable=False),
        sa.Column("impact", sa.Integer(), nullable=False),
        sa.Column("inherent_score", sa.Integer(), nullable=False),
        sa.Column("residual_score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(50), nullable=False),
        sa.Column("hazards_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("controls_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("approved_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("inventory_id","assessment_version",name="uq_ai_risk_inventory_version"),
    )
    _indices("ai_risk_assessments", ("inventory_id","risk_level","status","created_at"))

    op.create_table(
        "ai_incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inventory_id", sa.String(36), sa.ForeignKey("ai_system_inventory.id", ondelete="SET NULL"), nullable=True),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("serious_incident_candidate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("encrypted_details", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    _indices("ai_incidents", ("organization_id","inventory_id","severity","category","status","serious_incident_candidate","detected_at"))

    op.create_table(
        "governance_control_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inventory_id", sa.String(36), sa.ForeignKey("ai_system_inventory.id", ondelete="CASCADE"), nullable=True),
        sa.Column("framework", sa.String(100), nullable=False),
        sa.Column("control_ref", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("implementation_status", sa.String(50), nullable=False, server_default="not_started"),
        sa.Column("owner", sa.String(500), nullable=False, server_default=""),
        sa.Column("evidence_requirements", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("organization_id","framework","control_ref","inventory_id",name="uq_governance_control_mapping_scope"),
    )
    _indices("governance_control_mappings", ("organization_id","inventory_id","framework","control_ref","implementation_status"))


def downgrade() -> None:
    for table in (
        "governance_control_mappings",
        "ai_incidents",
        "ai_risk_assessments",
        "ai_system_inventory",
        "career_portfolio_shares",
        "career_portfolios",
        "labor_trend_snapshots",
        "labor_market_observations",
        "learning_catalog_items",
        "learning_provider_connections",
        "verified_credentials",
    ):
        op.drop_table(table)
