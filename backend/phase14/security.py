"""Ed25519 signed, audience-bound and ledger-backed capability tokens.

All issuance methods must be called ONLY by trusted server-side orchestration code.
The agent should never receive a signing key or uncontrolled issue/delegate route.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import base64
import json
import secrets
import time
from typing import Mapping
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from .storage import TokenRecord

class CapabilityError(PermissionError):
    pass

def _fail(msg):
    raise CapabilityError(msg)

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

def _unb64(value: str) -> bytes:
    if not value or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in value):
        _fail("invalid token encoding")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc:
        raise CapabilityError("invalid token encoding") from exc

def _json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")

def _unique_pairs(pairs):
    o = {}
    for k, v in pairs:
        if k in o:
            _fail("duplicate JSON field")
        o[k] = v
    return o

def _parse(raw):
    try:
        return json.loads(raw, object_pairs_hook=_unique_pairs)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise CapabilityError("malformed token JSON") from exc

def _validate_caps(caps):
    if not isinstance(caps, list) or not caps or len(caps) > 64:
        _fail("capabilities must be non-empty and bounded")
    normalized = []
    for cap in caps:
        if (not isinstance(cap, dict) or set(cap) != {"action", "resource"}
                or not all(isinstance(cap[k], str) and 0 < len(cap[k]) <= 256 for k in ("action", "resource"))
                or "*" in cap["action"] or "*" in cap["resource"]):
            _fail("each capability must name an exact action and resource")
        normalized.append({"action": cap["action"], "resource": cap["resource"]})
    if len({_json(c) for c in normalized}) != len(normalized):
        _fail("duplicate capability")
    return normalized

@dataclass(frozen=True)
class Claims:
    tenant: str
    workflow: str
    sub: str
    audience: str
    jti: str
    issued_at: int
    expires_at: int
    caps: tuple[tuple[str, str], ...]
    depth: int
    max_depth: int
    parent_jti: str | None

    def allows(self, action: str, resource: str) -> bool:
        return (action, resource) in self.caps

class TrustRegistry:
    """Explicit directed edges; no implicit agent-to-agent trust."""
    def __init__(self, allowed: Mapping[tuple[str, str, str], set[str]] | None = None):
        self.allowed = {k: frozenset(v) for k, v in (allowed or {}).items()}

    def allows(self, tenant: str, source: str, destination: str, action: str) -> bool:
        return action in self.allowed.get((tenant, source, destination), frozenset())

class Authority:
    def __init__(self, private_key: Ed25519PrivateKey,
                 session_factory: sessionmaker,
                 trust: TrustRegistry,
                 *, kid: str = "phase14-primary", issuer: str = "global-career-ai",
                 audience: str = "global-career-ai-orchestrator",
                 verify_keys: dict[str, Ed25519PublicKey] | None = None):
        self.signing_key = private_key
        self.sessions = session_factory
        self.trust = trust
        self.kid = kid
        self.issuer = issuer
        self.audience = audience
        self.verify_keys = dict(verify_keys or {})
        self.verify_keys[kid] = private_key.public_key()

    @classmethod
    def from_pem(cls, pem: bytes, session_factory, trust, **kwargs):
        key = serialization.load_pem_private_key(pem, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("expected Ed25519 signing key")
        return cls(key, session_factory, trust, **kwargs)

    def _mint(self, payload: dict, *, origin_user_id: str | None = None):
        header = {"typ": "cap+jwt", "alg": "EdDSA", "kid": self.kid}
        content = _b64(_json(header)) + "." + _b64(_json(payload))
        signature = _b64(self.signing_key.sign(content.encode("ascii")))
        token = content + "." + signature
        with self.sessions.begin() as db:
            db.add(TokenRecord(
                jti=payload["jti"], token_digest=sha256(token.encode("ascii")).hexdigest(),
                parent_jti=payload["parent_jti"],
                tenant=payload["tenant"], workflow=payload["workflow"],
                subject=payload["sub"], issued_at=payload["iat"],
                expires_at=payload["exp"], revoked=False,
                origin_user_id=origin_user_id
            ))
        return token

    def issue(self, *, tenant: str, workflow: str, subject: str,
              caps: list[dict], ttl_seconds: int = 300, max_depth: int = 2,
              origin_user_id: str | None = None) -> str:
        """Root grants: platform-only entry point after upstream authentication/authorization."""
        if not all(isinstance(x, str) and 0 < len(x) <= 128 for x in (tenant, workflow, subject)):
            _fail("tenant, workflow and subject required")
        if origin_user_id is not None and (
            not isinstance(origin_user_id, str) or not 0 < len(origin_user_id) <= 128
        ):
            _fail("invalid authenticated origin identity")
        if not 1 <= ttl_seconds <= 3600 or not 0 <= max_depth <= 4:
            _fail("out-of-range lifetime or delegation depth")
        now = int(time.time())
        return self._mint({
            "iss": self.issuer, "aud": self.audience, "sub": subject,
            "tenant": tenant, "workflow": workflow, "caps": _validate_caps(caps),
            "iat": now, "nbf": now, "exp": now + ttl_seconds,
            "jti": secrets.token_hex(16), "depth": 0, "max_depth": max_depth,
            "parent_jti": None
        }, origin_user_id=origin_user_id)

    def verify(self, token: str, *, action: str | None = None, resource: str | None = None) -> Claims:
        if not isinstance(token, str) or len(token) > 16384:
            _fail("invalid token length")
        parts = token.split(".")
        if len(parts) != 3:
            _fail("invalid token structure")
        header = _parse(_unb64(parts[0]))
        if not isinstance(header, dict) or set(header) != {"typ", "alg", "kid"}:
            _fail("invalid token header")
        if header["typ"] != "cap+jwt" or header["alg"] != "EdDSA":
            _fail("unsupported algorithm")
        public_key = self.verify_keys.get(header["kid"])
        if public_key is None:
            _fail("unknown signing key")
        try:
            public_key.verify(_unb64(parts[2]), (parts[0] + "." + parts[1]).encode("ascii"))
        except Exception as exc:
            raise CapabilityError("invalid token signature") from exc
        payload = _parse(_unb64(parts[1]))
        required = {"iss", "aud", "sub", "tenant", "workflow", "caps", "iat", "nbf",
                    "exp", "jti", "depth", "max_depth", "parent_jti"}
        if not isinstance(payload, dict) or set(payload) != required:
            _fail("invalid token claims")
        if payload["iss"] != self.issuer or payload["aud"] != self.audience:
            _fail("wrong issuer or audience")
        if not all(isinstance(payload[k], str) and 0 < len(payload[k]) <= 128
                   for k in ("sub", "tenant", "workflow", "jti")):
            _fail("invalid identity claims")
        if not all(type(payload[k]) is int for k in ("iat", "nbf", "exp", "depth", "max_depth")):
            _fail("invalid numeric claims")
        now = int(time.time())
        if (payload["nbf"] > now + 5 or payload["iat"] > now + 5 or
                payload["exp"] <= now or payload["exp"] - payload["iat"] > 3600 or
                not 0 <= payload["depth"] <= payload["max_depth"] <= 4):
            _fail("expired or invalid grant")
        caps = _validate_caps(payload["caps"])
        if (action is None) != (resource is None):
            _fail("action and resource must be supplied together")
        if action is not None and {"action": action, "resource": resource} not in caps:
            _fail("capability not granted")
        # A globally transactional ledger is required for revocation and approval consumption.
        with self.sessions() as db:
            rec = db.get(TokenRecord, payload["jti"])
            if (rec is None or rec.revoked
                    or rec.token_digest != sha256(token.encode("ascii")).hexdigest()
                    or rec.tenant != payload["tenant"]
                    or rec.workflow != payload["workflow"] or rec.subject != payload["sub"]
                    or rec.issued_at != payload["iat"] or rec.expires_at != payload["exp"]
                    or rec.parent_jti != payload["parent_jti"]):
                _fail("token revoked or not issued by platform")
            parent_id = rec.parent_jti
            seen = {rec.jti}
            while parent_id is not None:
                if parent_id in seen:
                    _fail("token lineage cycle")
                seen.add(parent_id)
                parent = db.get(TokenRecord, parent_id)
                if parent is None or parent.revoked or parent.expires_at <= now:
                    _fail("parent grant revoked or expired")
                if parent.tenant != rec.tenant or parent.workflow != rec.workflow:
                    _fail("token lineage identity mismatch")
                parent_id = parent.parent_jti
        return Claims(
            tenant=payload["tenant"], workflow=payload["workflow"], sub=payload["sub"],
            audience=payload["aud"], jti=payload["jti"], issued_at=payload["iat"],
            expires_at=payload["exp"], caps=tuple((c["action"], c["resource"]) for c in caps),
            depth=payload["depth"], max_depth=payload["max_depth"], parent_jti=payload["parent_jti"]
        )

    def delegate(self, parent_token: str, *, recipient: str,
                 caps: list[dict], ttl_seconds: int = 180) -> str:
        parent = self.verify(parent_token)
        requested = _validate_caps(caps)
        if not isinstance(recipient, str) or not 0 < len(recipient) <= 128:
            _fail("recipient required")
        if parent.depth >= parent.max_depth:
            _fail("delegation depth exceeded")
        for c in requested:
            if not parent.allows(c["action"], c["resource"]):
                _fail("delegation cannot amplify privileges")
            if not self.trust.allows(parent.tenant, parent.sub, recipient, c["action"]):
                _fail("agent trust edge not allowed")
        if not 1 <= ttl_seconds <= 3600:
            _fail("invalid child lifetime")
        now = int(time.time())
        expiration = min(now + ttl_seconds, parent.expires_at)
        if expiration <= now:
            _fail("parent expired")
        with self.sessions() as db:
            parent_record = db.get(TokenRecord, parent.jti)
            if parent_record is None:
                _fail("parent grant unavailable")
            origin_user_id = parent_record.origin_user_id
        return self._mint({
            "iss": self.issuer, "aud": self.audience, "sub": recipient,
            "tenant": parent.tenant, "workflow": parent.workflow,
            "caps": requested, "iat": now, "nbf": now, "exp": expiration,
            "jti": secrets.token_hex(16), "depth": parent.depth + 1,
            "max_depth": parent.max_depth, "parent_jti": parent.jti
        }, origin_user_id=origin_user_id)

    def revoke(self, jti: str) -> None:
        """Revokes a token and, transitively, its descendants at verification time."""
        with self.sessions.begin() as db:
            record = db.get(TokenRecord, jti)
            if record is None:
                _fail("unknown grant")
            record.revoked = True
