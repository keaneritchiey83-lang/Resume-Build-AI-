
from __future__ import annotations

from app.phase12_services import (
    ASSURANCE_LEVELS,
    REVERSIBLE_AUTO_ACTIONS,
    _sanitize_runtime_details,
    canonical_digest,
)


def test_runtime_details_redact_common_secrets() -> None:
    cleaned = _sanitize_runtime_details(
        {
            "token": "secret",
            "nested": {
                "authorization": "Bearer abc",
                "safe": "value",
            },
        }
    )

    assert cleaned["token"] == "[REDACTED]"
    assert cleaned["nested"]["authorization"] == "[REDACTED]"
    assert cleaned["nested"]["safe"] == "value"


def test_runtime_event_digest_is_stable() -> None:
    left = canonical_digest({"b": 2, "a": 1})
    right = canonical_digest({"a": 1, "b": 2})
    assert left == right


def test_auto_containment_is_bounded_to_reversible_actions() -> None:
    assert REVERSIBLE_AUTO_ACTIONS == {
        "disable_provider_integrations",
        "pause_career_agents",
    }
    assert "request_network_quarantine" not in REVERSIBLE_AUTO_ACTIONS


def test_assurance_order() -> None:
    assert ASSURANCE_LEVELS["high"] > ASSURANCE_LEVELS["substantial"]
    assert ASSURANCE_LEVELS["substantial"] > ASSURANCE_LEVELS["low"]
