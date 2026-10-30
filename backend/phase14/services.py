"""Durable approvals, isolated encrypted memory, and permission-checked agent dispatch."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import secrets
import time
from collections.abc import Callable, Sequence
from typing import Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from .security import Authority, CapabilityError, _json
from .storage import ApprovalRecord, EncryptedMemory, StepReceipt, TokenRecord

def digest(value: Any) -> str:
    return sha256(_json(value)).hexdigest()

class ApprovalRequired(Exception):
    def __init__(self, approval_id: str):
        self.approval_id = approval_id
        super().__init__(f"human approval required: {approval_id}")

class ApprovalService:
    def __init__(self, authority: Authority,
                 protected_actions: set[str] | None = None):
        self.authority = authority
        self.protected_actions = frozenset(protected_actions or {
            "job.submit", "email.send", "document.publish", "data.export",
            "account.modify", "payment.initiate"
        })

    def is_required(self, action: str) -> bool:
        return action in self.protected_actions

    def request(self, token: str, recipient: str, action: str, resource: str,
                payload: Any, *, ttl_seconds: int = 900) -> str:
        claim = self.authority.verify(token, action=action, resource=resource)
        if not 1 <= ttl_seconds <= 3600:
            raise ValueError("approval TTL out of range")
        if not self.authority.trust.allows(claim.tenant, claim.sub, recipient, action):
            raise CapabilityError("untrusted recipient")
        approval_id = secrets.token_hex(16)
        with self.authority.sessions.begin() as db:
            origin_token = db.get(TokenRecord, claim.jti)
            if origin_token is None:
                raise CapabilityError("grant origin unavailable")
            db.add(ApprovalRecord(
                id=approval_id, tenant=claim.tenant, workflow=claim.workflow,
                token_jti=claim.jti, requester_agent=claim.sub,
                recipient_agent=recipient, action=action, resource=resource,
                payload_digest=digest(payload),
                origin_user_id=origin_token.origin_user_id, expires_at=min(
                    int(time.time()) + ttl_seconds, claim.expires_at
                ), state="pending"
            ))
        return approval_id

    def review(self, approval_id: str, *, reviewer_id: str,
               reviewer_tenant: str,
               authenticated_roles: frozenset[str],
               approve: bool) -> None:
        """Only call with identity+roles established by the upstream auth layer."""
        if ("human_approver" not in authenticated_roles or not reviewer_id
                or not isinstance(reviewer_id, str)):
            raise CapabilityError("authenticated human approver role required")
        now = int(time.time())
        with self.authority.sessions.begin() as db:
            record = db.get(ApprovalRecord, approval_id)
            if record is None or record.expires_at <= now:
                raise CapabilityError("unknown or expired approval")
            if reviewer_tenant != record.tenant:
                raise CapabilityError("approver is not authorized for this tenant")
            if reviewer_id == record.requester_agent or (
                record.origin_user_id is not None and reviewer_id == record.origin_user_id
            ):
                raise CapabilityError("requester or initiating human cannot approve own action")
            updated = db.execute(
                update(ApprovalRecord).where(
                    ApprovalRecord.id == approval_id,
                    ApprovalRecord.state == "pending",
                    ApprovalRecord.expires_at > now
                ).values(
                    state="approved" if approve else "rejected",
                    reviewed_by=reviewer_id, reviewed_at=now
                )
            )
            if updated.rowcount != 1:
                raise CapabilityError("approval is no longer pending")

    def consume(self, approval_id: str, token: str, recipient: str,
                action: str, resource: str, payload: Any) -> None:
        claim = self.authority.verify(token, action=action, resource=resource)
        now = int(time.time())
        # Atomic compare-and-set; cannot consume once in two active regions
        # with a globally consistent transactional database.
        with self.authority.sessions.begin() as db:
            result = db.execute(
                update(ApprovalRecord).where(
                    ApprovalRecord.id == approval_id,
                    ApprovalRecord.tenant == claim.tenant,
                    ApprovalRecord.workflow == claim.workflow,
                    ApprovalRecord.token_jti == claim.jti,
                    ApprovalRecord.requester_agent == claim.sub,
                    ApprovalRecord.recipient_agent == recipient,
                    ApprovalRecord.action == action,
                    ApprovalRecord.resource == resource,
                    ApprovalRecord.payload_digest == digest(payload),
                    ApprovalRecord.state == "approved",
                    ApprovalRecord.expires_at > now
                ).values(state="consumed")
            )
            if result.rowcount != 1:
                raise CapabilityError("approval not granted, scope mismatch, or already used")

class MemoryVault:
    """Encrypted at rest, physically separated by tenant+agent+workflow."""
    def __init__(self, authority: Authority, master_key: bytes):
        if not isinstance(master_key, bytes) or len(master_key) < 32:
            raise ValueError("MEMORY_MASTER_KEY must be random and at least 32 bytes")
        self.authority = authority
        self.master_key = master_key

    def _derive(self, tenant: str, agent: str, workflow: str) -> bytes:
        identity = _json([tenant, agent, workflow])
        return HKDF(
            algorithm=hashes.SHA256(), length=32, salt=sha256(identity).digest(),
            info=b"global-career-ai/phase14/agent-memory/v1"
        ).derive(self.master_key)

    def put(self, token: str, key: str, value: Any):
        claim = self.authority.verify(token, action="memory.write", resource="own")
        if not isinstance(key, str) or not 0 < len(key) <= 256:
            raise ValueError("invalid memory key")
        clear = _json(value)
        if len(clear) > 64 * 1024:
            raise ValueError("memory entry exceeds 64 KiB")
        associated = _json([claim.tenant, claim.sub, claim.workflow, key])
        nonce = secrets.token_bytes(12)
        blob = nonce + AESGCM(self._derive(claim.tenant, claim.sub, claim.workflow)).encrypt(
            nonce, clear, associated
        )
        with self.authority.sessions.begin() as db:
            ident = (claim.tenant, claim.sub, claim.workflow, key)
            record = db.get(EncryptedMemory, ident)
            if record is None:
                db.add(EncryptedMemory(
                    tenant=claim.tenant, agent=claim.sub, workflow=claim.workflow,
                    key=key, cipherblob=blob, updated_at=int(time.time())
                ))
            else:
                record.cipherblob = blob
                record.updated_at = int(time.time())

    def get(self, token: str, key: str) -> Any | None:
        claim = self.authority.verify(token, action="memory.read", resource="own")
        if not isinstance(key, str) or not 0 < len(key) <= 256:
            raise ValueError("invalid memory key")
        with self.authority.sessions() as db:
            record = db.get(EncryptedMemory, (claim.tenant, claim.sub, claim.workflow, key))
            if record is None:
                return None
            blob = record.cipherblob
        associated = _json([claim.tenant, claim.sub, claim.workflow, key])
        plain = AESGCM(self._derive(claim.tenant, claim.sub, claim.workflow)).decrypt(
            blob[:12], blob[12:], associated
        )
        return json.loads(plain)

@dataclass(frozen=True)
class PolicyPermit:
    """Server-derived allow result; may mandate a human checkpoint."""
    requires_approval: bool = False

@dataclass(frozen=True)
class AgentStep:
    id: str
    recipient: str
    action: str
    resource: str
    payload: dict[str, Any]
    extras: tuple[tuple[str, str], ...] = ()

@dataclass(frozen=True)
class AgentContext:
    token: str
    step_id: str
    tenant: str
    workflow: str
    agent: str
    idempotency_key: str

class AgentOrchestrator:
    """Explicit multi-agent handoffs, bounded grants, resumable sequential plans.

    Handler execution is local injection: connect existing Phase 13 agent runtimes,
    job tools, audit logs and authentication in the application composition root.
    """
    def __init__(
        self,
        authority: Authority,
        approvals: ApprovalService,
        *,
        policy_enforcer: Callable[[Any, AgentStep], bool] | None = None,
        require_policy_enforcer: bool = False,
    ):
        """Pass a live, server-side Phase 13 permission-manifest decision callback.

        The callback must independently authorize the target agent, action,
        resource, all delegated extras, data category, destinations and call budget
        from trusted server-side metadata. It must return the singleton True only
        when every applicable policy allows the request. Errors deny access.
        In a Phase 13 integration, require_policy_enforcer MUST be True.
        """
        if require_policy_enforcer and not callable(policy_enforcer):
            raise ValueError("Phase 13 permission manifest enforcer is required")
        self.authority = authority
        self.approvals = approvals
        self.policy_enforcer = policy_enforcer
        self.require_policy_enforcer = require_policy_enforcer
        self.handlers: dict[tuple[str, str], Callable[[AgentContext, dict], Any]] = {}

    def register(self, recipient: str, action: str,
                 handler: Callable[[AgentContext, dict], Any]):
        if (recipient, action) in self.handlers:
            raise ValueError("duplicate handler")
        self.handlers[(recipient, action)] = handler

    def dispatch(self, parent_token: str, step: AgentStep,
                 *, approval_id: str | None = None) -> dict:
        grant = self.authority.verify(
            parent_token, action=step.action, resource=step.resource
        )
        if (not step.id or len(step.id) > 128 or
                not isinstance(step.payload, dict)):
            raise ValueError("invalid step")
        if not self.authority.trust.allows(
            grant.tenant, grant.sub, step.recipient, step.action
        ):
            raise CapabilityError("untrusted agent handoff")
        handler = self.handlers.get((step.recipient, step.action))
        if handler is None:
            raise CapabilityError("agent/action handler not registered")
        # Independently intersect Phase 14 capabilities with Phase 13's
        # default-deny permission manifests. Never use payload-supplied
        # metadata as the authority for data category, destination or budget.
        if self.require_policy_enforcer and self.policy_enforcer is None:
            raise CapabilityError("Phase 13 permission enforcer unavailable")
        policy_requires_approval = False
        if self.policy_enforcer is not None:
            try:
                decision = self.policy_enforcer(grant, step)
            except Exception as exc:
                raise CapabilityError("Phase 13 permission evaluation failed") from exc
            if isinstance(decision, PolicyPermit):
                policy_requires_approval = decision.requires_approval
            elif decision is not True:
                raise CapabilityError("Phase 13 permission manifest denied the action")
        caps = [{"action": step.action, "resource": step.resource}]
        caps.extend({"action": a, "resource": r} for a, r in step.extras)
        spec_hash = digest({
            "recipient": step.recipient, "action": step.action,
            "resource": step.resource, "payload": step.payload, "extras": step.extras
        })
        identity = (grant.tenant, grant.workflow, step.id)
        with self.authority.sessions() as db:
            receipt = db.get(StepReceipt, identity)
            if receipt is not None:
                if receipt.source_agent != grant.sub:
                    raise CapabilityError("step owned by another source agent")
                if receipt.spec_digest != spec_hash:
                    raise CapabilityError("step ID reused for a different operation")
                if receipt.state == "completed":
                    return {"status": "already_completed", "step_id": step.id}
                raise CapabilityError("step reserved but not completed: reconcile manually")
        if self.approvals.is_required(step.action) or policy_requires_approval:
            if approval_id is None:
                raise ApprovalRequired(self.approvals.request(
                    parent_token, step.recipient, step.action, step.resource, step.payload
                ))
            # Consumes approval before performing side effects; a crashed attempt
            # requires manual reconciliation rather than unsafe automatic replay.
            self.approvals.consume(
                approval_id, parent_token, step.recipient,
                step.action, step.resource, step.payload
            )
        child_token = self.authority.delegate(
            parent_token, recipient=step.recipient, caps=caps
        )
        # Durable reservation ensures one attempt per step across multiple regions.
        # External handlers MUST also honor idempotency_key for their own side effects.
        try:
            with self.authority.sessions.begin() as db:
                db.add(StepReceipt(
                    tenant=grant.tenant, workflow=grant.workflow,
                    step_id=step.id, source_agent=grant.sub,
                    spec_digest=spec_hash, state="reserved"
                ))
        except IntegrityError as exc:
            raise CapabilityError("step concurrently reserved in another region") from exc
        ctx = AgentContext(
            token=child_token, step_id=step.id, tenant=grant.tenant,
            workflow=grant.workflow, agent=step.recipient,
            idempotency_key=digest([grant.tenant, grant.workflow, step.id])
        )
        result = handler(ctx, step.payload)
        with self.authority.sessions.begin() as db:
            record = db.get(StepReceipt, identity)
            if record is None or record.state != "reserved":
                raise CapabilityError("execution receipt missing or corrupt")
            record.state = "completed"
        return {"status": "completed", "step_id": step.id, "result": result}

    def run_plan(self, parent_token: str, steps: Sequence[AgentStep],
                 *, approvals: dict[str, str] | None = None) -> dict:
        if not 1 <= len(steps) <= 50 or len({s.id for s in steps}) != len(steps):
            raise ValueError("plan needs 1-50 distinct steps")
        outcomes = []
        for step in steps:
            try:
                outcome = self.dispatch(
                    parent_token, step, approval_id=(approvals or {}).get(step.id)
                )
                outcomes.append(outcome)
            except ApprovalRequired as exc:
                return {
                    "status": "pending_human_approval",
                    "pending_step": step.id,
                    "approval_id": exc.approval_id,
                    "steps": outcomes
                }
        return {"status": "completed", "steps": outcomes}
