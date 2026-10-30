"""Dependency-light Phase 14 security tests and verified repository integration hooks."""
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from phase14 import (
    Authority, TrustRegistry, ApprovalService, AgentOrchestrator, AgentStep,
    ApprovalRequired, CapabilityError, PolicyPermit, create_database,
)


def test_phase13_policy_can_force_human_checkpoint(tmp_path):
    sessions = create_database(f"sqlite:///{tmp_path / 'checkpoint.db'}", create_tables=True)
    authority = Authority(
        Ed25519PrivateKey.generate(), sessions,
        TrustRegistry({("org", "coordinator", "agent"): {"audit.digest"}})
    )
    token = authority.issue(tenant="org", workflow="w", subject="coordinator",
                            caps=[{"action": "audit.digest", "resource": "case"}])
    approvals = ApprovalService(authority, protected_actions=set())
    agent = AgentOrchestrator(
        authority, approvals, require_policy_enforcer=True,
        policy_enforcer=lambda claims, step: PolicyPermit(requires_approval=True)
    )
    calls = []
    agent.register("agent", "audit.digest", lambda context, payload: calls.append(payload) or True)
    step = AgentStep("s1", "agent", "audit.digest", "case", {"name": "private"})
    with pytest.raises(ApprovalRequired) as pending:
        agent.dispatch(token, step)
    assert not calls
    approvals.review(
        pending.value.approval_id, reviewer_id="human-id", reviewer_tenant="org",
        authenticated_roles=frozenset({"human_approver"}), approve=True
    )
    assert agent.dispatch(token, step, approval_id=pending.value.approval_id)["status"] == "completed"
    assert len(calls) == 1


def test_runtime_fails_closed_when_manifest_unavailable(tmp_path):
    sessions = create_database(f"sqlite:///{tmp_path / 'denied.db'}", create_tables=True)
    authority = Authority(Ed25519PrivateKey.generate(), sessions,
                          TrustRegistry({("org", "a", "b"): {"audit.digest"}}))
    token = authority.issue(tenant="org", workflow="w", subject="a",
                            caps=[{"action": "audit.digest", "resource": "case"}])
    orchestrator = AgentOrchestrator(
        authority, ApprovalService(authority),
        policy_enforcer=lambda claims, step: (_ for _ in ()).throw(RuntimeError("unavailable")),
        require_policy_enforcer=True
    )
    orchestrator.register("b", "audit.digest", lambda *_: True)
    with pytest.raises(CapabilityError, match="evaluation failed"):
        orchestrator.dispatch(token, AgentStep("s1", "b", "audit.digest", "case", {}))


def test_phase14_included_in_phase13_backend_entrypoint():
    repo = Path(__file__).resolve().parents[2]
    main = (repo / "backend/app/main.py").read_text()
    dockerfile = (repo / "backend/Dockerfile").read_text()
    api = (repo / "backend/app/phase14_api.py").read_text()
    assert "app.include_router(phase14_router)" in main
    assert "COPY phase14 ./phase14" in dockerfile
    assert "Depends(current_user)" in api
    assert "require_org_role(" in api
    assert "assert_agent_permissions" in (repo / "backend/app/phase14_runtime.py").read_text()
    assert "phase14_enabled: bool = False" in (repo / "backend/app/config.py").read_text()


def test_migration_extends_existing_phase13_head():
    repo = Path(__file__).resolve().parents[2]
    migration = (repo / "backend/alembic/versions/0012_phase14_agents_operations.py").read_text()
    assert 'revision = "0012_phase14"' in migration
    assert 'down_revision = "0011_phase13"' in migration
    assert "phase14_step_receipts" in migration
    assert "phase14_agent_memory" in migration
    assert "phase14_approvals" in migration

def test_initiating_human_cannot_approve_their_own_delegated_agent_action(tmp_path):
    sessions = create_database(f"sqlite:///{tmp_path / 'separation.db'}", create_tables=True)
    authority = Authority(
        Ed25519PrivateKey.generate(), sessions,
        TrustRegistry({("org", "coordinator", "mailer"): {"email.send"}})
    )
    token = authority.issue(
        tenant="org", workflow="w", subject="coordinator",
        origin_user_id="human-initiator",
        caps=[{"action": "email.send", "resource": "application"}]
    )
    approvals = ApprovalService(authority)
    approval_id = approvals.request(
        token, "mailer", "email.send", "application", {"subject": "Example"}
    )
    with pytest.raises(CapabilityError, match="initiating human"):
        approvals.review(
            approval_id, reviewer_id="human-initiator",
            reviewer_tenant="org", authenticated_roles=frozenset({"human_approver"}),
            approve=True
        )
    approvals.review(
        approval_id, reviewer_id="different-human",
        reviewer_tenant="org", authenticated_roles=frozenset({"human_approver"}),
        approve=True
    )
