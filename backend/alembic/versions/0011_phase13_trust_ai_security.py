"""Phase 13 multi-region trust continuity and AI security gateway.

Revision ID: 0011_phase13
Revises: 0010_phase12
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_phase13"
down_revision = "0010_phase12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deployment_regions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("region_key", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(300), nullable=False),
        sa.Column("cloud_provider", sa.String(100), nullable=False),
        sa.Column("jurisdiction", sa.String(100), nullable=False, server_default=""),
        sa.Column("spiffe_trust_domain", sa.String(500), nullable=False),
        sa.Column("federation_entity_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "region_key", name="uq_deployment_region_org_key"),
    )
    op.create_index("ix_deployment_regions_org", "deployment_regions", ["organization_id"])
    op.create_index("ix_deployment_regions_key", "deployment_regions", ["region_key"])

    op.create_table(
        "region_trust_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_region_id", sa.String(36), sa.ForeignKey("deployment_regions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("peer_region_id", sa.String(36), sa.ForeignKey("deployment_regions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("peer_bundle_endpoint", sa.Text(), nullable=False, server_default=""),
        sa.Column("peer_bundle_digest", sa.String(64), nullable=False),
        sa.Column("peer_bundle_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("federation_anchor_entity_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("verification_details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("approved_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "organization_id",
            "source_region_id",
            "peer_region_id",
            name="uq_region_trust_link_org_pair",
        ),
    )
    op.create_index("ix_region_trust_links_org", "region_trust_links", ["organization_id"])

    op.create_table(
        "cross_cloud_workload_bindings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("spiffe_id", sa.String(1000), nullable=False),
        sa.Column("aws_role_arn", sa.Text(), nullable=False, server_default=""),
        sa.Column("azure_client_id", sa.String(300), nullable=False, server_default=""),
        sa.Column("azure_tenant_id", sa.String(300), nullable=False, server_default=""),
        sa.Column("audience", sa.String(1000), nullable=False, server_default=""),
        sa.Column("allowed_regions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_cross_cloud_binding_org_name"),
    )
    op.create_index("ix_cross_cloud_binding_org", "cross_cloud_workload_bindings", ["organization_id"])
    op.create_index("ix_cross_cloud_binding_spiffe", "cross_cloud_workload_bindings", ["spiffe_id"])

    op.create_table(
        "transparency_log_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("log_name", sa.String(200), nullable=False, server_default="career-trust"),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(100), nullable=False),
        sa.Column("subject_id", sa.String(500), nullable=False, server_default=""),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("previous_entry_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("entry_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("external_log_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("external_log_entry_id", sa.String(500), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "log_name", "sequence", name="uq_transparency_log_sequence"
        ),
    )
    op.create_index("ix_transparency_org_log", "transparency_log_entries", ["organization_id", "log_name"])
    op.create_index("ix_transparency_entry_hash", "transparency_log_entries", ["entry_hash"])

    op.create_table(
        "trust_continuity_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("region_id", sa.String(36), sa.ForeignKey("deployment_regions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("snapshot_version", sa.String(100), nullable=False),
        sa.Column("snapshot_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("encrypted_snapshot", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False, server_default=""),
        sa.Column("signing_key_id", sa.String(300), nullable=False, server_default=""),
        sa.Column("status", sa.String(50), nullable=False, server_default="sealed"),
        sa.Column("transparency_entry_id", sa.String(36), sa.ForeignKey("transparency_log_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_for_restore_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trust_snapshot_org", "trust_continuity_snapshots", ["organization_id"])
    op.create_index("ix_trust_snapshot_digest", "trust_continuity_snapshots", ["snapshot_digest"])

    op.create_table(
        "model_gateway_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("allowed_models", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("allowed_tasks", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("allowed_data_categories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tools_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("require_signed_release", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("require_confidential_rag", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("block_injection_score", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("max_input_chars", sa.Integer(), nullable=False, server_default="50000"),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False, server_default="4000"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_model_gateway_policy_org_name"),
    )

    op.create_table(
        "model_releases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("release_name", sa.String(300), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(300), nullable=False),
        sa.Column("model_snapshot", sa.String(300), nullable=False, server_default=""),
        sa.Column("prompt_version", sa.String(200), nullable=False),
        sa.Column("eval_run_id", sa.String(36), sa.ForeignKey("model_eval_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("signature", sa.Text(), nullable=False, server_default=""),
        sa.Column("signing_key_id", sa.String(300), nullable=False, server_default=""),
        sa.Column("release_status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("transparency_entry_id", sa.String(36), sa.ForeignKey("transparency_log_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "release_name", "version", name="uq_model_release_org_name_version"
        ),
    )
    op.create_index("ix_model_release_org", "model_releases", ["organization_id"])
    op.create_index("ix_model_release_model", "model_releases", ["model_name"])

    op.create_table(
        "agent_permission_manifests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.String(300), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("allowed_actions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("denied_actions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("allowed_data_categories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("allowed_destination_hosts", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("max_external_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("require_human_approval_actions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("manifest_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("approved_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "agent_name", "version", name="uq_agent_manifest_org_name_version"
        ),
    )

    op.create_table(
        "agent_action_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("manifest_id", sa.String(36), sa.ForeignKey("agent_permission_manifests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_name", sa.String(300), nullable=False),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("destination_host", sa.String(500), nullable=False, server_default=""),
        sa.Column("data_categories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("requires_human_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_action_decisions_org", "agent_action_decisions", ["organization_id"])

    op.create_table(
        "prompt_injection_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("source_id", sa.String(500), nullable=False, server_default=""),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("indicators", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_prompt_injection_org", "prompt_injection_events", ["organization_id"])
    op.create_index("ix_prompt_injection_digest", "prompt_injection_events", ["content_digest"])

    op.create_table(
        "confidential_rag_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query_digest", sa.String(64), nullable=False),
        sa.Column("document_digests", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("blocked_document_digests", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("model_release_id", sa.String(36), sa.ForeignKey("model_releases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_confidential_rag_org", "confidential_rag_audits", ["organization_id"])


def downgrade() -> None:
    op.drop_table("confidential_rag_audits")
    op.drop_table("prompt_injection_events")
    op.drop_table("agent_action_decisions")
    op.drop_table("agent_permission_manifests")
    op.drop_table("model_releases")
    op.drop_table("model_gateway_policies")
    op.drop_table("trust_continuity_snapshots")
    op.drop_table("transparency_log_entries")
    op.drop_table("cross_cloud_workload_bindings")
    op.drop_table("region_trust_links")
    op.drop_table("deployment_regions")
