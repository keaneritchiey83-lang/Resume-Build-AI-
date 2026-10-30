from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, Integer, LargeBinary, String,
    UniqueConstraint, create_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

class Base(DeclarativeBase):
    pass

class TokenRecord(Base):
    __tablename__ = "phase14_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_jti: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("phase14_tokens.jti"), nullable=True, index=True
    )
    tenant: Mapped[str] = mapped_column(String(128), index=True)
    workflow: Mapped[str] = mapped_column(String(128), index=True)
    subject: Mapped[str] = mapped_column(String(128))
    issued_at: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    origin_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

class ApprovalRecord(Base):
    __tablename__ = "phase14_approvals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant: Mapped[str] = mapped_column(String(128), index=True)
    workflow: Mapped[str] = mapped_column(String(128), index=True)
    token_jti: Mapped[str] = mapped_column(String(64), ForeignKey("phase14_tokens.jti"))
    requester_agent: Mapped[str] = mapped_column(String(128))
    recipient_agent: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128))
    resource: Mapped[str] = mapped_column(String(256))
    payload_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    origin_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (CheckConstraint(
        "state IN ('pending', 'approved', 'rejected', 'consumed')",
        name="valid_phase14_approval_state"
    ),)

class EncryptedMemory(Base):
    __tablename__ = "phase14_agent_memory"
    tenant: Mapped[str] = mapped_column(String(128), primary_key=True)
    agent: Mapped[str] = mapped_column(String(128), primary_key=True)
    workflow: Mapped[str] = mapped_column(String(128), primary_key=True)
    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    cipherblob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer)

class StepReceipt(Base):
    __tablename__ = "phase14_step_receipts"
    tenant: Mapped[str] = mapped_column(String(128), primary_key=True)
    workflow: Mapped[str] = mapped_column(String(128), primary_key=True)
    step_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_agent: Mapped[str] = mapped_column(String(128), nullable=False)
    spec_digest: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), default="reserved")
    __table_args__ = (CheckConstraint(
        "state IN ('reserved', 'completed')", name="valid_phase14_step_receipt_state"
    ),)

def create_database(database_url: str, *, create_tables: bool = False):
    """create_tables=True is ONLY for local tests/demo. Use an approved SQL migration in prod."""
    kwargs = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool
        if ":memory:" in database_url:
            kwargs.update(connect_args={"check_same_thread": False}, poolclass=StaticPool)
    engine = create_engine(database_url, **kwargs)
    if create_tables:
        Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
