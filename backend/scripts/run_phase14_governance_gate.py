"""Phase 14 gating for the merged Phase 13 application."""
from pathlib import Path
import subprocess
import sys
from run_phase13_governance_gate import verify_application_version

verify_application_version(14)

backend = Path(__file__).resolve().parents[1]
root = backend.parent

checks = {
    "backend/app/main.py": ("phase14_router", "metrics_middleware"),
    "backend/app/phase14_runtime.py": ("phase13_enforce", "require_policy_enforcer=True", "approved_by_user_id"),
    "backend/app/phase14_api.py": ("Depends(current_user)", "require_org_role", "approvals/{approval_id}/review"),
    "backend/alembic/versions/0012_phase14_agents_operations.py": ("down_revision = \"0011_phase13\"",),
    "backend/Dockerfile": ("COPY phase14 ./phase14",),
    "k8s/base/kustomization.yaml": ("newTag: phase14",),
    "ops/phase14/slo/slo_gate.py": ("career_phase14_http_requests_total",),
    ".github/workflows/phase14-security.yml": ("test_phase14_integration_contract.py",),
}
for path, needles in checks.items():
    content = (root / path).read_text()
    for needle in needles:
        if needle not in content:
            raise SystemExit(f"FAIL {path} missing {needle}")
for command, working_directory in (
    ([sys.executable, "-m", "compileall", "-q", "app", "phase14", "alembic", "scripts", "tests"], backend),
    ([sys.executable, "-m", "pytest", "-q", "tests/test_phase14.py", "tests/test_phase14_integration_contract.py"], backend),
    ([sys.executable, "scripts/run_phase13_governance_gate.py"], backend),
):
    print("+", " ".join(command), flush=True)
    result = subprocess.run(command, cwd=working_directory)
    if result.returncode:
        raise SystemExit(result.returncode)
print("Phase 14 governance gate PASS")
