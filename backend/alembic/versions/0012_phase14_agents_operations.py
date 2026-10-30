"""Phase 14 multi-agent capabilities, checkpoint ledger, memory and receipts.

Revision ID: 0012_phase14
Revises: 0011_phase13
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_phase14"
down_revision = "0011_phase13"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "phase14_tokens",
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("parent_jti", sa.String(64), sa.ForeignKey("phase14_tokens.jti")),
        sa.Column("tenant", sa.String(128), nullable=False),
        sa.Column("workflow", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(128), nullable=False),
        sa.Column("issued_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("origin_user_id", sa.String(128)),
    )
    for column in ("parent_jti", "tenant", "workflow", "expires_at"):
        op.create_index("ix_phase14_tokens_"+column, "phase14_tokens", [column])
    op.create_table(
        "phase14_approvals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant", sa.String(128), nullable=False),
        sa.Column("workflow", sa.String(128), nullable=False),
        sa.Column("token_jti", sa.String(64), sa.ForeignKey("phase14_tokens.jti"), nullable=False),
        sa.Column("requester_agent", sa.String(128), nullable=False),
        sa.Column("recipient_agent", sa.String(128), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource", sa.String(256), nullable=False),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("origin_user_id", sa.String(128)),
        sa.Column("reviewed_at", sa.Integer()),
        sa.CheckConstraint("state IN ('pending', 'approved', 'rejected', 'consumed')", name="valid_phase14_approval_state"),
    )
    for column in ("tenant", "workflow"):
        op.create_index("ix_phase14_approvals_"+column, "phase14_approvals", [column])
    op.create_table(
        "phase14_agent_memory",
        sa.Column("tenant", sa.String(128), nullable=False),
        sa.Column("agent", sa.String(128), nullable=False),
        sa.Column("workflow", sa.String(128), nullable=False),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("cipherblob", sa.LargeBinary(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("tenant", "agent", "workflow", "key"),
    )
    op.create_table(
        "phase14_step_receipts",
        sa.Column("tenant", sa.String(128), nullable=False),
        sa.Column("workflow", sa.String(128), nullable=False),
        sa.Column("step_id", sa.String(128), nullable=False),
        sa.Column("source_agent", sa.String(128), nullable=False),
        sa.Column("spec_digest", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="reserved"),
        sa.PrimaryKeyConstraint("tenant", "workflow", "step_id"),
        sa.CheckConstraint("state IN ('reserved', 'completed')", name="valid_phase14_step_receipt_state"),
    )

def downgrade():
    # Destructive! Production downgrade requires an explicit data retention decision.
    op.drop_table("phase14_step_receipts")
    op.drop_table("phase14_agent_memory")
    op.drop_index("ix_phase14_approvals_workflow", table_name="phase14_approvals")
    op.drop_index("ix_phase14_approvals_tenant", table_name="phase14_approvals")
    op.drop_table("phase14_approvals")
    for column in ("expires_at", "workflow", "tenant", "parent_jti"):
        op.drop_index("ix_phase14_tokens_"+column, table_name="phase14_tokens")
    op.drop_table("phase14_tokens")
