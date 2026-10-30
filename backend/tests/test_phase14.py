import json
import os
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from phase14 import (
    Authority, TrustRegistry, CapabilityError, ApprovalService, ApprovalRequired,
    MemoryVault, AgentOrchestrator, AgentStep, create_database
)
from phase14.storage import ApprovalRecord, EncryptedMemory

@pytest.fixture
def system(tmp_path):
    db = create_database(f"sqlite:///{tmp_path / 'phase14.db'}", create_tables=True)
    trust = TrustRegistry({
        ("tenant-a", "coordinator", "researcher"): {"profile.parse", "memory.read", "memory.write"},
        ("tenant-a", "coordinator", "mailer"): {"email.send"},
        ("tenant-a", "researcher", "advisor"): {"cover_letter.draft"},
    })
    authority = Authority(Ed25519PrivateKey.generate(), db, trust)
    approvals = ApprovalService(authority)
    memory = MemoryVault(authority, os.urandom(32))
    orchestrator = AgentOrchestrator(authority, approvals)
    return authority, approvals, memory, orchestrator

def root(authority, *, workflow="workflow-1", tenant="tenant-a"):
    return authority.issue(
        tenant=tenant, workflow=workflow, subject="coordinator", max_depth=2,
        caps=[{"action": a, "resource": r} for a, r in (
            ("profile.parse", "resume-1"), ("memory.write", "own"),
            ("memory.read", "own"), ("email.send", "application-1"),
            ("cover_letter.draft", "job-1")
        )]
    )

def test_tampering_and_scopes_rejected(system):
    auth, *_ = system
    token = root(auth)
    assert auth.verify(token, action="profile.parse", resource="resume-1").sub == "coordinator"
    with pytest.raises(CapabilityError):
        auth.verify(token, action="profile.parse", resource="resume-2")
    head, payload, sig = token.split(".")
    with pytest.raises(CapabilityError):
        auth.verify(head + "." + payload[:-1] + "A." + sig)
    with pytest.raises(CapabilityError):
        auth.verify("not-a-valid-token")

def test_trust_and_attenuation(system):
    auth, *_ = system
    token = root(auth)
    child = auth.delegate(token, recipient="researcher", caps=[
        {"action": "profile.parse", "resource": "resume-1"}
    ])
    assert auth.verify(child).sub == "researcher"
    with pytest.raises(CapabilityError):
        auth.delegate(token, recipient="advisor", caps=[
            {"action": "profile.parse", "resource": "resume-1"}
        ])
    with pytest.raises(CapabilityError):
        auth.delegate(token, recipient="researcher", caps=[
            {"action": "profile.parse", "resource": "resume-OTHER"}
        ])
    with pytest.raises(CapabilityError):
        auth.delegate(child, recipient="advisor", caps=[
            {"action": "profile.parse", "resource": "resume-1"}
        ])

def test_parent_revocation_cascades(system):
    auth, *_ = system
    token = root(auth)
    child = auth.delegate(token, recipient="researcher", caps=[
        {"action": "profile.parse", "resource": "resume-1"}
    ])
    auth.revoke(auth.verify(token).jti)
    with pytest.raises(CapabilityError):
        auth.verify(child)

def test_memory_encrypted_and_isolated(system):
    auth, _, vault, _ = system
    coordinator = root(auth)
    vault.put(coordinator, "assessment", {"private": "alice"})
    assert vault.get(coordinator, "assessment") == {"private": "alice"}
    other_workflow = root(auth, workflow="workflow-2")
    assert vault.get(other_workflow, "assessment") is None
    other_tenant = root(auth, tenant="tenant-b")
    assert vault.get(other_tenant, "assessment") is None
    researcher = auth.delegate(coordinator, recipient="researcher", caps=[
        {"action": "memory.write", "resource": "own"},
        {"action": "memory.read", "resource": "own"}
    ])
    assert vault.get(researcher, "assessment") is None
    vault.put(researcher, "assessment", {"private": "bob"})
    assert vault.get(coordinator, "assessment") == {"private": "alice"}
    with auth.sessions() as db:
        rows = db.query(EncryptedMemory).all()
        assert len(rows) == 2
        assert all(b"alice" not in row.cipherblob and b"bob" not in row.cipherblob for row in rows)

def test_human_checkpoint_exact_payload_and_one_time(system):
    auth, approvals, _, orch = system
    parent = root(auth)
    calls = []
    orch.register("mailer", "email.send", lambda ctx, payload: calls.append(payload) or {"id": "sent"})
    step = AgentStep("send-1", "mailer", "email.send", "application-1", {"subject": "Hi"})
    with pytest.raises(ApprovalRequired) as pending:
        orch.dispatch(parent, step)
    approval_id = pending.value.approval_id
    with pytest.raises(CapabilityError):
        approvals.review(approval_id, reviewer_id="coordinator", reviewer_tenant="tenant-a",
                         authenticated_roles=frozenset({"human_approver"}), approve=True)
    with pytest.raises(CapabilityError):
        approvals.review(approval_id, reviewer_id="reviewer-1", reviewer_tenant="tenant-a",
                         authenticated_roles=frozenset(), approve=True)
    approvals.review(approval_id, reviewer_id="reviewer-1", reviewer_tenant="tenant-a",
                     authenticated_roles=frozenset({"human_approver"}), approve=True)
    with pytest.raises(CapabilityError):
        approvals.consume(approval_id, parent, "mailer", "email.send",
                          "application-1", {"subject": "DIFFERENT"})
    assert orch.dispatch(parent, step, approval_id=approval_id)["status"] == "completed"
    assert len(calls) == 1
    assert orch.dispatch(parent, step, approval_id=approval_id)["status"] == "already_completed"
    assert len(calls) == 1
    with pytest.raises(CapabilityError):
        approvals.consume(approval_id, parent, "mailer", "email.send",
                          "application-1", {"subject": "Hi"})

def test_denial_and_fail_closed_receipt(system):
    auth, approvals, _, orch = system
    parent = root(auth)
    def broken(ctx, payload):
        raise RuntimeError("upstream service failed")
    orch.register("researcher", "profile.parse", broken)
    step = AgentStep("parse-2", "researcher", "profile.parse", "resume-1", {})
    with pytest.raises(RuntimeError):
        orch.dispatch(parent, step)
    with pytest.raises(CapabilityError, match="reconcile manually"):
        orch.dispatch(parent, step)

def test_multistep_plan_resume(system):
    auth, approvals, vault, orch = system
    parent = root(auth)
    def parse(ctx, payload):
        vault.put(ctx.token, "parsed", payload)
        return {"ok": True}
    orch.register("researcher", "profile.parse", parse)
    orch.register("mailer", "email.send", lambda ctx, payload: {"sent": True})
    steps = [
        AgentStep("parse-1", "researcher", "profile.parse", "resume-1",
                  {"resume_id": 123}, extras=(("memory.write", "own"),)),
        AgentStep("send-1", "mailer", "email.send", "application-1", {"subject": "Hello"})
    ]
    first = orch.run_plan(parent, steps)
    assert first["status"] == "pending_human_approval"
    assert first["steps"][0]["status"] == "completed"
    approvals.review(first["approval_id"], reviewer_id="human-1", reviewer_tenant="tenant-a",
                     authenticated_roles=frozenset({"human_approver"}), approve=True)
    second = orch.run_plan(parent, steps, approvals={"send-1": first["approval_id"]})
    assert second["status"] == "completed"
    assert second["steps"][0]["status"] == "already_completed"
    child = auth.delegate(parent, recipient="researcher", caps=[
        {"action": "memory.read", "resource": "own"}
    ])
    assert vault.get(child, "parsed") == {"resume_id": 123}

def test_rejected_approval_not_usable(system):
    auth, approvals, _, orch = system
    parent = root(auth)
    orch.register("mailer", "email.send", lambda ctx, payload: None)
    step = AgentStep("send-2", "mailer", "email.send", "application-1", {"subject": "Hello"})
    with pytest.raises(ApprovalRequired) as pending:
        orch.dispatch(parent, step)
    approvals.review(pending.value.approval_id, reviewer_id="human-1", reviewer_tenant="tenant-a",
                     authenticated_roles=frozenset({"human_approver"}), approve=False)
    with pytest.raises(CapabilityError):
        orch.dispatch(parent, step, approval_id=pending.value.approval_id)

def test_no_implicit_agent_trust(system):
    auth, approvals, vault, orch = system
    parent = root(auth, tenant="tenant-b")
    orch.register("researcher", "profile.parse", lambda ctx, payload: "unsafe")
    with pytest.raises(CapabilityError):
        orch.dispatch(parent, AgentStep(
            "parse-1", "researcher", "profile.parse", "resume-1", {}
        ))

def test_step_id_cannot_be_repurposed(system):
    auth, approvals, vault, orch = system
    parent = root(auth)
    orch.register("researcher", "profile.parse", lambda ctx, payload: True)
    orch.dispatch(parent, AgentStep("parse-1", "researcher", "profile.parse", "resume-1", {}))
    with pytest.raises(CapabilityError, match="different operation"):
        orch.dispatch(parent, AgentStep(
            "parse-1", "researcher", "profile.parse", "resume-1", {"changed": True}
        ))


def test_signed_token_rewrite_still_rejected_by_ledger(system):
    from phase14.security import _b64, _unb64, _json
    auth, *_ = system
    original = root(auth)
    head, body, _signature = original.split(".")
    claims = json.loads(_unb64(body))
    claims["caps"].append({"action": "payment.initiate", "resource": "anything"})
    signing_input = head + "." + _b64(_json(claims))
    rewritten = signing_input + "." + _b64(auth.signing_key.sign(signing_input.encode()))
    with pytest.raises(CapabilityError, match="revoked or not issued"):
        auth.verify(rewritten)


def test_approver_must_belong_to_request_tenant(system):
    auth, approvals, _, _ = system
    token = root(auth)
    approval_id = approvals.request(
        token, "mailer", "email.send", "application-1", {"subject": "Hello"}
    )
    with pytest.raises(CapabilityError, match="not authorized for this tenant"):
        approvals.review(
            approval_id, reviewer_id="external-human",
            reviewer_tenant="tenant-b",
            authenticated_roles=frozenset({"human_approver"}), approve=True
        )
