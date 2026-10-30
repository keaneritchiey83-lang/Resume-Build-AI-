from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlparse


PROMPT_INJECTION_PATTERNS: list[tuple[str, int, str]] = [
    (r"\bignore (?:all|any|the|your|previous|prior) instructions?\b", 45, "instruction_override"),
    (r"\b(system|developer) (prompt|message|instructions?)\b", 30, "privileged_prompt_reference"),
    (r"\bdo not (?:tell|show|inform) (?:the )?user\b", 35, "concealment_request"),
    (r"\b(exfiltrate|leak|send|upload|transmit)\b.{0,80}\b(secret|token|password|credential|private)\b", 55, "data_exfiltration"),
    (r"\b(call|invoke|use|execute)\b.{0,50}\b(tool|function|shell|command|api)\b", 25, "tool_coercion"),
    (r"\boverride\b.{0,50}\b(policy|guardrail|safety|permission)\b", 40, "policy_override"),
    (r"\bfollow (?:these|my) instructions\b", 20, "embedded_instruction"),
    (r"\b(?:reveal|print|return)\b.{0,60}\b(system prompt|hidden instructions|api key|secret)\b", 45, "secret_or_prompt_request"),
]


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_object(value: Any) -> str:
    return sha256_text(canonical_json(value))


def scan_prompt_injection(content: str, block_threshold: int = 70) -> dict[str, Any]:
    lowered = content.lower()
    score = 0
    indicators: list[str] = []

    for pattern, weight, indicator in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE | re.DOTALL):
            score += weight
            indicators.append(indicator)

    if "<script" in lowered or "javascript:" in lowered:
        score += 20
        indicators.append("active_content_marker")

    score = min(100, score)

    if score >= block_threshold:
        decision = "block"
    elif score >= max(20, block_threshold // 2):
        decision = "review"
    else:
        decision = "allow"

    return {
        "score": score,
        "decision": decision,
        "indicators": sorted(set(indicators)),
        "content_digest": sha256_text(content),
    }


def validate_peer_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    keys = bundle.get("keys")

    if not isinstance(keys, list) or not keys:
        raise ValueError("Peer SPIFFE bundle must contain a non-empty keys array.")

    public_keys = []

    for item in keys:
        if not isinstance(item, dict):
            raise ValueError("Peer bundle keys must be objects.")

        if any(name in item for name in {"d", "p", "q", "dp", "dq", "qi"}):
            raise ValueError("Peer trust bundle must contain public keys only.")

        public_keys.append(
            {
                key: item.get(key)
                for key in ("kid", "kty", "use", "alg", "crv", "x", "y", "n", "e")
                if item.get(key) is not None
            }
        )

    return {
        "key_count": len(public_keys),
        "bundle_digest": digest_object(bundle),
        "key_ids": sorted(
            str(item.get("kid", ""))
            for item in public_keys
            if item.get("kid")
        ),
    }


def validate_https_allowlisted_url(value: str, allowed_hosts: set[str]) -> str:
    parsed = urlparse(value)

    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Endpoint must use HTTPS.")

    host = parsed.hostname.lower()

    if allowed_hosts and host not in allowed_hosts:
        raise ValueError("Endpoint host is not allowlisted.")

    if parsed.username or parsed.password:
        raise ValueError("Endpoint URLs may not contain credentials.")

    return host


def host_is_allowed(host: str, allowed_hosts: list[str]) -> bool:
    if not host:
        return True

    candidate = host.lower().strip().rstrip(".")

    for value in allowed_hosts:
        allowed = value.lower().strip().rstrip(".")

        if candidate == allowed or candidate.endswith("." + allowed):
            return True

    return False
