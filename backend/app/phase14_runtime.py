"""Phase 14 security composition rooted in the real Phase 13 database and manifests.

Only trusted administrators mint root capability tokens. Operations fail closed when
Phase 14 configuration, database availability or Phase 13 policy is unavailable.
"""
from __future__ import annotations

import base64
import json
from functools import lru_cache
from hashlib import sha256
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.models import AgentPermissionManifest
from phase14 import (
    AgentOrchestrator, AgentStep, Authority, ApprovalService, MemoryVault,
    TrustRegistry, create_database, CapabilityError, PolicyPermit,
)


def _manifest_allows(manifest: AgentPermissionManifest | None, actions: set[str]) -> bool:
    return bool(
        manifest is not None
        and manifest.active
        and manifest.approved_by_user_id
        and not actions.intersection(manifest.denied_actions or [])
        and actions.issubset(set(manifest.allowed_actions or []))
    )


def _active_manifest(db, organization_id: str, agent_name: str):
    return db.scalar(
        select(AgentPermissionManifest)
        .where(
            AgentPermissionManifest.organization_id == organization_id,
            AgentPermissionManifest.agent_name == agent_name,
            AgentPermissionManifest.active.is_(True),
            AgentPermissionManifest.approved_by_user_id.is_not(None),
        )
        .order_by(AgentPermissionManifest.created_at.desc())
        .limit(1)
    )


class Phase14Runtime:
    def __init__(self):
        if not settings.phase14_enabled:
            raise RuntimeError("Phase 14 disabled")
        key_text = settings.phase14_token_signing_key_pem_b64.get_secret_value()
        memory_text = settings.phase14_memory_master_key_b64.get_secret_value()
        if not key_text or not memory_text:
            raise RuntimeError("Phase 14 signing and memory keys required")
        signing_key_pem = base64.b64decode(key_text, validate=True)
        memory_key = base64.b64decode(memory_text, validate=True)
        edges_raw = json.loads(settings.phase14_agent_trust_edges_json.get_secret_value())
        if not isinstance(edges_raw, list):
            raise ValueError("Phase 14 trust edges must be a list")
        trust_map: dict[tuple[str, str, str], set[str]] = {}
        for item in edges_raw:
            if not isinstance(item, dict) or set(item) != {"organization_id", "source", "target", "actions"}:
                raise ValueError("invalid explicit trust edge")
            org, source, target = (item[k] for k in ("organization_id", "source", "target"))
            actions = item["actions"]
            if not all(isinstance(v, str) and 0 < len(v) <= 128 for v in (org, source, target)):
                raise ValueError("invalid trust edge identity")
            if (not isinstance(actions, list) or not actions or
                not all(isinstance(v, str) and 0 < len(v) <= 128 and "*" not in v for v in actions)):
                raise ValueError("invalid trust edge actions")
            trust_map.setdefault((org, source, target), set()).update(actions)
        # Phase 13 async engine URL cannot be used with the sync SQLAlchemy
        # transactions required for Phase 14 atomic approvals and receipts.
        db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if not db_url.startswith("postgresql+psycopg://"):
            raise RuntimeError("Phase 14 requires a PostgreSQL psycopg transactional ledger")
        self.sessions = create_database(db_url)
        self.authority = Authority.from_pem(
            signing_key_pem, self.sessions, TrustRegistry(trust_map)
        )
        self.approvals = ApprovalService(self.authority)
        self.memory = MemoryVault(self.authority, memory_key)
        self.orchestrator = AgentOrchestrator(
            self.authority, self.approvals,
            policy_enforcer=self.phase13_enforce,
            require_policy_enforcer=True,
        )
        # The one registered example has no side effects and returns digests
        # only. External agent handlers must be explicitly registered in code.
        self.orchestrator.register("audit-agent", "audit.digest", self._audit_digest)

    @staticmethod
    def _audit_digest(context, payload: dict) -> dict:
        from phase14.services import digest
        return {"payload_sha256": digest(payload), "step_id": context.step_id}

    def phase13_enforce(self, grant: Any, step: AgentStep) -> bool | PolicyPermit:
        """Server-authorized policy: checks both agents and every delegated action.

        No payload-specified destination/data class/call budget is authoritative.
        The only registered handler is local and makes zero outbound requests.
        """
        actions = {step.action} | {action for action, _resource in step.extras}
        if step.recipient != "audit-agent" or step.action != "audit.digest" or step.extras:
            return False
        with self.sessions() as db:
            source = _active_manifest(db, grant.tenant, grant.sub)
            recipient = _active_manifest(db, grant.tenant, step.recipient)
            if not _manifest_allows(source, actions) or not _manifest_allows(recipient, actions):
                return False
            for manifest in (source, recipient):
                if manifest.max_external_calls < 0:
                    return False
            return PolicyPermit(
                requires_approval=any(
                    step.action in (manifest.require_human_approval_actions or [])
                    for manifest in (source, recipient)
                )
            )


@lru_cache(maxsize=1)
def get_phase14_runtime() -> Phase14Runtime:
    return Phase14Runtime()


def assert_agent_permissions(db, organization_id: str, agent_name: str, actions: set[str]) -> None:
    manifest = _active_manifest(db, organization_id, agent_name)
    if not _manifest_allows(manifest, actions):
        raise CapabilityError("active approved Phase 13 permission manifest required")
    # Memory routes have no human-review receipt parameter; fail closed where
    # Phase 13 explicitly requires one rather than silently bypassing review.
    if any(action.startswith("memory.") for action in actions) and (
        set(manifest.require_human_approval_actions or []) & actions
    ):
        raise CapabilityError("this memory operation requires a separate human checkpoint")
