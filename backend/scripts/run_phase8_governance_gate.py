from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    governance = ROOT / "governance" / "phase8"
    required = [
        governance / "eu_ai_act_crosswalk.json",
        governance / "iso42001_crosswalk.json",
        governance / "ai_inventory_template.json",
        governance / "credential_trust_profiles.json",
    ]

    for path in required:
        require(path.exists(), f"Missing Phase 8 governance artifact: {path}")

    eu = json.loads((governance / "eu_ai_act_crosswalk.json").read_text())
    iso = json.loads((governance / "iso42001_crosswalk.json").read_text())
    trust = json.loads((governance / "credential_trust_profiles.json").read_text())

    require(
        eu["high_risk_timeline"]["annex_iii_standalone"] == "2027-12-02",
        "EU AI Act Annex III application date is stale.",
    )
    require(
        any(
            item["ref"] == "Article 14"
            for item in eu["controls"]
        ),
        "EU AI Act human-oversight control is missing.",
    )
    require(
        "does not reproduce" in iso["copyright_notice"].lower(),
        "ISO 42001 crosswalk must preserve the copyright boundary.",
    )
    require(
        trust["open_badges_3"]["never_promote_structural_to_verified"] is True,
        "Credential trust boundary is missing.",
    )

    policy = (ROOT / "governance" / "policies" / "career.rego").read_text()

    for action in (
        "credential.claim_as_verified",
        "portfolio.share_contact",
        "ai.employment.release",
    ):
        require(action in policy, f"Policy gate missing action: {action}")

    migration = (
        ROOT
        / "backend"
        / "alembic"
        / "versions"
        / "0006_phase8_credentials_governance.py"
    )
    require(migration.exists(), "Phase 8 migration is missing.")

    print("Phase 8 governance gate: PASS")


if __name__ == "__main__":
    main()
