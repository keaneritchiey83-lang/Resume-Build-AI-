"""Phase 11 identity interoperability and security hardening.

Revision ID: 0009_phase11
Revises: 0008_phase10
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_phase11"
down_revision = "0008_phase10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "passkey_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_id_b64", sa.String(2000), nullable=False, unique=True),
        sa.Column("public_key_b64", sa.Text(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("device_type", sa.String(100), nullable=False, server_default=""),
        sa.Column("backed_up", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("transports", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("nickname", sa.String(300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_passkey_credentials_user_id", "passkey_credentials", ["user_id"])

    op.create_table(
        "webauthn_challenges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("challenge_b64", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_webauthn_challenges_user_id", "webauthn_challenges", ["user_id"])
    op.create_index("ix_webauthn_challenges_expires_at", "webauthn_challenges", ["expires_at"])

    op.create_table(
        "did_trust_registry_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("did", sa.Text(), nullable=False),
        sa.Column("did_document", sa.JSON(), nullable=False),
        sa.Column("trust_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(200), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "did", name="uq_did_trust_org_did"),
    )

    op.create_table(
        "bitstring_status_lists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer_profile_id", sa.String(36), sa.ForeignKey("credential_issuer_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(100), nullable=False, server_default="revocation"),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("capacity_bits", sa.Integer(), nullable=False, server_default="131072"),
        sa.Column("next_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bitstring_b64", sa.Text(), nullable=False),
        sa.Column("status_list_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer_profile_id", "purpose", "sequence", name="uq_status_list_issuer_purpose_sequence"),
    )

    op.create_table(
        "credential_status_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issued_credential_id", sa.String(36), sa.ForeignKey("issued_credential_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status_list_id", sa.String(36), sa.ForeignKey("bitstring_status_lists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(100), nullable=False),
        sa.Column("status_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issued_credential_id", "purpose", name="uq_credential_status_purpose"),
        sa.UniqueConstraint("status_list_id", "status_index", name="uq_status_list_index"),
    )

    op.create_table(
        "wallet_key_attestations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("holder_did", sa.Text(), nullable=False, server_default=""),
        sa.Column("key_id", sa.Text(), nullable=False),
        sa.Column("public_jwk", sa.JSON(), nullable=False),
        sa.Column("attestation_format", sa.String(100), nullable=False, server_default=""),
        sa.Column("hardware_backed_claim", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verification_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("encrypted_attestation", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "crypto_inventory_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component", sa.String(300), nullable=False),
        sa.Column("usage", sa.String(300), nullable=False),
        sa.Column("current_algorithm", sa.String(200), nullable=False),
        sa.Column("quantum_risk", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("target_standard", sa.String(200), nullable=False, server_default=""),
        sa.Column("migration_status", sa.String(50), nullable=False, server_default="inventory"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "component", "usage", name="uq_crypto_inventory_component_usage"),
    )

    op.create_table(
        "confidential_workload_attestations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workload_name", sa.String(300), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("measurement", sa.Text(), nullable=False, server_default=""),
        sa.Column("verification_status", sa.String(50), nullable=False, server_default="unverified"),
        sa.Column("evidence_digest", sa.String(64), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("attested_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "security_test_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("test_type", sa.String(100), nullable=False),
        sa.Column("tool", sa.String(200), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="scheduled"),
        sa.Column("findings_summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("report_digest", sa.String(64), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    for table in [
        "security_test_runs",
        "confidential_workload_attestations",
        "crypto_inventory_items",
        "wallet_key_attestations",
        "credential_status_assignments",
        "bitstring_status_lists",
        "did_trust_registry_entries",
        "webauthn_challenges",
        "passkey_credentials",
    ]:
        op.drop_table(table)
