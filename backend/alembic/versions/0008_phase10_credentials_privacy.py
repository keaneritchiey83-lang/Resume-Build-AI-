"""Phase 10 OpenID credentials and privacy engineering.

Revision ID: 0008_phase10
Revises: 0007_phase9
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_phase10"
down_revision = "0007_phase9"
branch_labels = None
depends_on = None


def _indices(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def upgrade() -> None:
    op.create_table(
        "credential_issuer_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("issuer_identifier", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("approval_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("signing_alg", sa.String(50), nullable=False, server_default="ES256"),
        sa.Column("public_jwk", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("encrypted_private_key", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approved_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("slug", name="uq_credential_issuer_slug"),
        sa.UniqueConstraint("issuer_identifier", name="uq_credential_issuer_identifier"),
    )
    _indices("credential_issuer_profiles", ("organization_id", "slug", "approval_status"))

    op.create_table(
        "credential_configurations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer_profile_id", sa.String(36), sa.ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("configuration_id", sa.String(300), nullable=False),
        sa.Column("credential_format", sa.String(100), nullable=False),
        sa.Column("credential_type", sa.String(500), nullable=False),
        sa.Column("vct", sa.Text(), nullable=False, server_default=""),
        sa.Column("scope", sa.String(300), nullable=False, server_default=""),
        sa.Column("claim_names", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("selective_claims", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("display_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("require_holder_binding", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("issuer_profile_id", "configuration_id", name="uq_credential_configuration_issuer_id"),
    )
    _indices("credential_configurations", ("issuer_profile_id", "configuration_id", "credential_format", "active"))

    op.create_table(
        "credential_wallet_clients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(500), nullable=False, unique=True),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("redirect_uris", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    _indices("credential_wallet_clients", ("client_id", "approved"))

    op.create_table(
        "credential_issuance_offers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer_profile_id", sa.String(36), sa.ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_configuration_id", sa.String(36), sa.ForeignKey("credential_configurations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pre_authorized_code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("transaction_code_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("transaction_code_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    _indices("credential_issuance_offers", ("issuer_profile_id", "user_id", "credential_configuration_id", "pre_authorized_code_hash", "expires_at"))

    op.create_table(
        "credential_authorization_codes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer_profile_id", sa.String(36), sa.ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(500), nullable=False),
        sa.Column("credential_configuration_id", sa.String(36), sa.ForeignKey("credential_configurations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("code_challenge", sa.String(200), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    _indices("credential_authorization_codes", ("issuer_profile_id", "user_id", "client_id", "credential_configuration_id", "code_hash", "expires_at"))

    op.create_table(
        "credential_access_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer_profile_id", sa.String(36), sa.ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_configuration_id", sa.String(36), sa.ForeignKey("credential_configurations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("holder_jwk", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("nonce_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    _indices("credential_access_tokens", ("issuer_profile_id", "user_id", "credential_configuration_id", "token_hash", "expires_at"))

    op.create_table(
        "issued_credential_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer_profile_id", sa.String(36), sa.ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_configuration_id", sa.String(36), sa.ForeignKey("credential_configurations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_format", sa.String(100), nullable=False),
        sa.Column("jti", sa.String(100), nullable=False, unique=True),
        sa.Column("credential_hash", sa.String(64), nullable=False),
        sa.Column("encrypted_credential", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    _indices("issued_credential_records", ("issuer_profile_id", "user_id", "credential_configuration_id", "credential_format", "jti", "credential_hash", "status", "issued_at"))

    op.create_table(
        "credential_verifier_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("client_id", sa.Text(), nullable=False),
        sa.Column("response_uri", sa.Text(), nullable=False),
        sa.Column("approval_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("vp_formats_supported", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approved_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("slug", name="uq_credential_verifier_slug"),
        sa.UniqueConstraint("client_id", name="uq_credential_verifier_client"),
    )
    _indices("credential_verifier_profiles", ("organization_id", "slug", "approval_status"))

    op.create_table(
        "credential_trust_anchors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issuer_identifier", sa.Text(), nullable=False),
        sa.Column("public_jwk", sa.JSON(), nullable=False),
        sa.Column("allowed_formats", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("organization_id", "issuer_identifier", name="uq_credential_trust_anchor_org_issuer"),
    )
    _indices("credential_trust_anchors", ("organization_id", "active"))

    op.create_table(
        "presentation_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("verifier_profile_id", sa.String(36), sa.ForeignKey("credential_verifier_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("nonce", sa.String(200), nullable=False),
        sa.Column("state", sa.String(200), nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("dcql_query", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    _indices("presentation_requests", ("verifier_profile_id", "state_hash", "status", "expires_at"))

    op.create_table(
        "presentation_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("presentation_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("holder_identifier", sa.Text(), nullable=False, server_default=""),
        sa.Column("verification_status", sa.String(50), nullable=False, server_default="received"),
        sa.Column("issuer_identifiers", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("encrypted_result", sa.Text(), nullable=False),
        sa.Column("raw_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    _indices("presentation_submissions", ("request_id", "verification_status", "raw_hash"))

    op.create_table(
        "consent_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("purpose", sa.String(200), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("lawful_basis", sa.String(200), nullable=False, server_default="consent"),
        sa.Column("processing_purposes", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("data_categories", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("receipt_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("previous_receipt_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    _indices("consent_receipts", ("user_id", "organization_id", "purpose", "action", "receipt_hash", "occurred_at"))

    op.create_table(
        "data_classification_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_key", sa.String(200), nullable=False),
        sa.Column("field_pattern", sa.String(500), nullable=False),
        sa.Column("classification", sa.String(100), nullable=False),
        sa.Column("sensitivity", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("organization_id", "rule_key", name="uq_data_classification_rule_org_key"),
    )
    _indices("data_classification_rules", ("organization_id", "rule_key", "classification", "sensitivity", "enabled"))

    op.create_table(
        "data_discovery_scans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("scope", sa.String(200), nullable=False, server_default="application_schema"),
        sa.Column("finding_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    _indices("data_discovery_scans", ("organization_id", "status", "started_at"))

    op.create_table(
        "data_discovery_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scan_id", sa.String(36), sa.ForeignKey("data_discovery_scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_name", sa.String(300), nullable=False),
        sa.Column("field_name", sa.String(300), nullable=False),
        sa.Column("classification", sa.String(100), nullable=False),
        sa.Column("sensitivity", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
    )
    _indices("data_discovery_findings", ("scan_id", "table_name", "field_name", "classification", "sensitivity"))

    op.create_table(
        "deletion_workflows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dsar_id", sa.String(36), sa.ForeignKey("data_subject_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="planned"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("legal_hold_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("steps_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    _indices("deletion_workflows", ("user_id", "dsar_id", "status"))

    op.create_table(
        "privacy_analytics_budgets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("epsilon_limit", sa.Float(), nullable=False, server_default="2.0"),
        sa.Column("epsilon_used", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("organization_id", "day", name="uq_privacy_analytics_budget_org_day"),
    )
    _indices("privacy_analytics_budgets", ("organization_id", "day"))

    op.create_table(
        "privacy_analytics_releases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("epsilon", sa.Float(), nullable=False),
        sa.Column("minimum_group_size", sa.Integer(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("noisy_value", sa.Float(), nullable=True),
        sa.Column("suppressed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    _indices("privacy_analytics_releases", ("organization_id", "metric", "day", "query_hash"))

    op.create_table(
        "cryptographic_audit_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(200), nullable=False),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("subject_type", sa.String(200), nullable=False, server_default=""),
        sa.Column("subject_id", sa.String(200), nullable=False, server_default=""),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("entry_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("signature", sa.Text(), nullable=False, server_default=""),
        sa.Column("signing_key_id", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("organization_id", "sequence", name="uq_crypto_audit_org_sequence"),
    )
    _indices("cryptographic_audit_entries", ("organization_id", "sequence", "event_type", "entry_hash", "created_at"))


def downgrade() -> None:
    for table in (
        "cryptographic_audit_entries",
        "privacy_analytics_releases",
        "privacy_analytics_budgets",
        "deletion_workflows",
        "data_discovery_findings",
        "data_discovery_scans",
        "data_classification_rules",
        "consent_receipts",
        "presentation_submissions",
        "presentation_requests",
        "credential_trust_anchors",
        "credential_verifier_profiles",
        "issued_credential_records",
        "credential_access_tokens",
        "credential_authorization_codes",
        "credential_issuance_offers",
        "credential_wallet_clients",
        "credential_configurations",
        "credential_issuer_profiles",
    ):
        op.drop_table(table)
