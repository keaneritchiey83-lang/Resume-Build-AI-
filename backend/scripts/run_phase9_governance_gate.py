from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    governance = ROOT / "governance" / "phase9"

    for name in (
        "portable_identity_profile.json",
        "privacy_security_profile.json",
        "continuous_controls.json",
    ):
        require((governance / name).exists(), f"Missing Phase 9 artifact: {name}")

    identity = json.loads(
        (governance / "portable_identity_profile.json").read_text(encoding="utf-8")
    )
    privacy = json.loads(
        (governance / "privacy_security_profile.json").read_text(encoding="utf-8")
    )

    require(
        identity["trust_boundaries"]["candidate_private_keys"]
        == "never stored by the platform",
        "Candidate wallet private-key custody boundary is missing.",
    )
    require(
        privacy["retention"]["legal_hold_blocks_deletion"] is True,
        "Legal-hold retention boundary is missing.",
    )
    require(
        privacy["dsar"]["default_due_days"] == 30,
        "Phase 9 DSAR default deadline changed unexpectedly.",
    )
    require(
        "prompt_injection" in privacy["red_teaming"]["manual_required"],
        "Prompt-injection red-team case must remain a manual/system-execution test.",
    )

    policy = (ROOT / "governance" / "policies" / "career.rego").read_text()

    for action in (
        "wallet.private_key.store",
        "portable_record.claim_as_verified",
        "dsar.complete",
        "retention.delete",
        "ai.release",
    ):
        require(action in policy, f"Policy gate missing action: {action}")

    migration = (
        ROOT
        / "backend"
        / "alembic"
        / "versions"
        / "0007_phase9_portability_privacy.py"
    )
    require(migration.exists(), "Phase 9 migration is missing.")

    api = (ROOT / "backend" / "app" / "phase9_api.py").read_text()
    require("/v1/portable-career-record" in api, "Portable career record endpoint missing.")
    require("/v1/privacy/requests" in api, "DSAR endpoint missing.")

    print("Phase 9 governance gate: PASS")


if __name__ == "__main__":
    main()
