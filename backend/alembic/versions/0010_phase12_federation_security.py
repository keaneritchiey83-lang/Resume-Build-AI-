
"""Phase 12 federation, HSM signing, confidential inference, and runtime security.

Revision ID: 0010_phase12
Revises: 0009_phase11
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_phase12"
down_revision = "0009_phase11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "federation_trust_anchors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(500), nullable=False, server_default=""),
        sa.Column("jwks", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("metadata_policy", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approved_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "entity_id", name="uq_federation_anchor_org_entity"),
    )
    op.create_index("ix_federation_anchor_org", "federation_trust_anchors", ["organization_id"])

    op.create_table(
        "federation_entities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False, server_default="federation_entity"),
        sa.Column("parent_entity_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("jwks", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("metadata_policy", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("trust_marks", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("self_statement_jwt", sa.Text(), nullable=False, server_default=""),
        sa.Column("subordinate_statement_jwt", sa.Text(), nullable=False, server_default=""),
        sa.Column("trust_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("validation_details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "entity_id", name="uq_federation_entity_org_entity"),
    )
    op.create_index("ix_federation_entity_org", "federation_entities", ["organization_id"])
    op.create_index("ix_federation_entity_status", "federation_entities", ["trust_status"])

    op.create_table(
        "wallet_attestation_trust_anchors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("root_certificate_pem", sa.Text(), nullable=False),
        sa.Column("allowed_subjects", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_wallet_attestation_anchor_org_name"),
    )

    op.create_table(
        "wallet_attestation_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trust_anchor_id", sa.String(36), sa.ForeignKey("wallet_attestation_trust_anchors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False, server_default=""),
        sa.Column("issuer", sa.Text(), nullable=False, server_default=""),
        sa.Column("attestation_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("claims_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("verification_status", sa.String(50), nullable=False, server_default="verified"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "credential_negotiation_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("purpose", sa.String(300), nullable=False, server_default=""),
        sa.Column("accepted_formats", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("accepted_credential_types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("required_claims", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("accepted_proof_algorithms", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("required_trust_frameworks", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("require_wallet_attestation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("require_hardware_backed_key", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("minimum_assurance_level", sa.String(100), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_credential_policy_org_name"),
    )

    op.create_table(
        "credential_negotiation_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_id", sa.String(36), sa.ForeignKey("credential_negotiation_policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("negotiated_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "hsm_signing_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issuer_profile_id", sa.String(36), sa.ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_name", sa.String(300), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("key_reference", sa.Text(), nullable=False),
        sa.Column("algorithm", sa.String(100), nullable=False, server_default="ES256"),
        sa.Column("public_jwk", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approval_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approved_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("issuer_profile_id", "key_name", name="uq_hsm_key_issuer_name"),
    )
    op.create_index("ix_hsm_signing_keys_issuer", "hsm_signing_keys", ["issuer_profile_id"])

    op.create_table(
        "confidential_inference_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("allowed_measurements", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("allowed_data_categories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("require_attestation", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fail_closed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_confidential_inference_policy_org_name"),
    )

    op.create_table(
        "confidential_inference_attestations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("policy_id", sa.String(36), sa.ForeignKey("confidential_inference_policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("measurement", sa.Text(), nullable=False),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "workload_identity_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("spiffe_id_pattern", sa.String(1000), nullable=False),
        sa.Column("namespace", sa.String(300), nullable=False, server_default=""),
        sa.Column("service_account", sa.String(300), nullable=False, server_default=""),
        sa.Column("allowed_peer_patterns", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_workload_identity_policy_org_name"),
    )

    op.create_table(
        "runtime_security_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("rule", sa.String(500), nullable=False),
        sa.Column("workload", sa.String(500), nullable=False, server_default=""),
        sa.Column("namespace", sa.String(300), nullable=False, server_default=""),
        sa.Column("event_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "containment_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("minimum_severity", sa.String(50), nullable=False, server_default="critical"),
        sa.Column("rule_patterns", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("actions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("auto_execute_reversible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_containment_policy_org_name"),
    )

    op.create_table(
        "incident_containment_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("runtime_security_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_id", sa.String(36), sa.ForeignKey("containment_policies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("reversible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("requires_human_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approved_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table in [
        "incident_containment_actions",
        "containment_policies",
        "runtime_security_events",
        "workload_identity_policies",
        "confidential_inference_attestations",
        "confidential_inference_policies",
        "hsm_signing_keys",
        "credential_negotiation_decisions",
        "credential_negotiation_policies",
        "wallet_attestation_evidence",
        "wallet_attestation_trust_anchors",
        "federation_entities",
        "federation_trust_anchors",
    ]:
        op.drop_table(table)
