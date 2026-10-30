from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime

from app.webhook_pipeline import (
    linkedin_challenge_response,
    normalize_application_event,
    verify_indeed_signature,
    verify_linkedin_signature,
    verify_ziprecruiter_signature,
)


def test_linkedin_signature_matches_raw_body() -> None:
    body = b'{"jobApplicationId":"urn:li:jobApplication:123"}'
    secret = "linkedin-secret"
    expected = hmac.new(
        secret.encode(),
        b"hmacsha256=" + body,
        hashlib.sha256,
    ).hexdigest()

    assert verify_linkedin_signature(body, expected, secret)
    assert not verify_linkedin_signature(body + b" ", expected, secret)


def test_linkedin_challenge_response() -> None:
    expected = hmac.new(
        b"client-secret",
        b"challenge-code",
        hashlib.sha256,
    ).hexdigest()

    assert (
        linkedin_challenge_response("challenge-code", "client-secret")
        == expected
    )


def test_indeed_signature_matches_raw_body() -> None:
    body = b'{"id":"indeed-application-1"}'
    secret = "indeed-secret"
    expected = base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha1).digest()
    ).decode()

    assert verify_indeed_signature(body, expected, secret)
    assert not verify_indeed_signature(body, "bad", secret)


def test_ziprecruiter_signature_and_replay_window() -> None:
    body = b'{"zr_application_id":"abc","job_id":"job-1"}'
    secret = "zip-secret"
    timestamp = "2026-09-14T20:00:00Z"
    expected = base64.b64encode(
        hmac.new(
            secret.encode("ascii"),
            timestamp.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).digest()
    ).decode("ascii")

    assert verify_ziprecruiter_signature(
        body,
        expected,
        timestamp,
        "v1; sha256",
        secret,
        now=datetime(2026, 9, 14, 20, 0, 5, tzinfo=UTC),
        replay_window_seconds=15,
    )

    assert not verify_ziprecruiter_signature(
        body,
        expected,
        timestamp,
        "v1; sha256",
        secret,
        now=datetime(2026, 9, 14, 20, 1, 0, tzinfo=UTC),
        replay_window_seconds=15,
    )


def test_linkedin_normalization_drops_voluntary_identification() -> None:
    payload = {
        "jobApplicationId": "urn:li:jobApplication:123",
        "jobApplicant": "urn:li:person:456",
        "externalJobId": "job-1",
        "questionResponses": {
            "contactInformationQuestionResponses": {
                "firstNameAnswer": {"value": "A"},
                "lastNameAnswer": {"value": "Candidate"},
                "emailAnswer": {"value": "candidate@example.com"},
            },
            "voluntarySelfIdentificationQuestionResponses": {
                "raceAnswer": "OPT_OUT",
                "genderAnswer": "OPT_OUT",
                "disabilityAnswer": "OPT_OUT",
            },
        },
    }

    normalized = normalize_application_event(
        "linkedin",
        payload,
        {},
    )

    serialized = str(normalized)
    assert "voluntarySelfIdentificationQuestionResponses" not in serialized
    assert normalized["application"]["source_attribution"] == "LinkedIn Apply"


def test_ziprecruiter_rdb_requires_explicit_enablement() -> None:
    payload = {
        "source": "ZipRecruiter RDB",
        "zr_application_id": "application-1",
        "email": "candidate@example.com",
        "name": "Candidate",
    }

    try:
        normalize_application_event("ziprecruiter", payload, {})
    except PermissionError:
        pass
    else:
        raise AssertionError("RDB ingestion must require explicit opt-in.")
