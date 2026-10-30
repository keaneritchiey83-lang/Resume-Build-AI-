#!/usr/bin/env python3
"""Live, disposable Phase 15–17 web/API integration smoke test.

Runs *against a real deployed stack*. It creates two synthetic CI users and
checks authenticated routing, CSRF, organization boundaries, XSS escaping,
practice feedback, and default-deny failover. Do not run against production:
users are persisted in the database and this tool does not delete them.
"""
from __future__ import annotations

import argparse
from http.cookiejar import CookieJar
import json
import secrets
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener


class Client:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def request(self, method: str, route: str, body: dict | None = None, *, csrf: bool = True):
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if csrf and method.upper() not in {"GET", "HEAD"}:
            token = next((cookie.value for cookie in self.cookies if cookie.name == "career_csrf"), "")
            if token:
                headers["X-CSRF-Token"] = token
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base + route, data=data, headers=headers, method=method)
        try:
            response = self.opener.open(req, timeout=20)
        except HTTPError as exc:
            response = exc
        with response:
            raw = response.read(1_000_000)
            try:
                payload = json.loads(raw) if raw else None
            except ValueError:
                payload = raw.decode("utf-8", "replace")
            return response.status, payload


def expect(status: int, desired: int, context: str):
    if status != desired:
        raise AssertionError(f"{context}: expected HTTP {desired}, received {status}")


def run(base: str) -> None:
    # This is a *temporary CI environment only*, never production.
    owner, outsider = Client(base), Client(base)
    st, _ = owner.request("POST", "/v1/phase15/resume/draft", {})
    expect(st, 401, "Anonymous access to protected resume endpoint")
    suffix = secrets.token_hex(9)
    password = secrets.token_urlsafe(30)
    for client, email in ((owner, f"career-owner-{suffix}@example.invalid"),
                          (outsider, f"career-outsider-{suffix}@example.invalid")):
        credentials = {"email": email, "password": password, "mfa_code": ""}
        status, _ = client.request("POST", "/v1/auth/register", credentials)
        expect(status, 200, "Disposable account registration")
        status, _ = client.request("POST", "/v1/auth/login", credentials)
        expect(status, 200, "Disposable account login")
        status, me = client.request("GET", "/v1/auth/me")
        expect(status, 200, "Authenticated session")
        assert me["email"] == email

    status, organizations = owner.request("GET", "/v1/organizations")
    expect(status, 200, "Organization enumeration")
    assert organizations and organizations[0]["role"] in ("owner", "admin")
    org = organizations[0]["id"]
    draft_payload = {
        "organization_id": org,
        "candidate_name": "<script>alert(1)</script>",
        "target_role": "Aerospace Maintenance Supervisor",
        "summary": "Supervised documented inspections and maintenance coordination.",
        "requirements": ["aircraft inspection planning", "cloud security architecture"],
        "evidence": [{"id": "real_record_1", "description": "Performed aircraft inspection planning during annual maintenance."}],
        "template": "federal",
    }
    status, _ = owner.request("POST", "/v1/phase15/resume/draft", draft_payload, csrf=False)
    expect(status, 403, "Missing CSRF token must fail")
    status, resume = owner.request("POST", "/v1/phase15/resume/draft", draft_payload)
    expect(status, 200, "Authorized resume drafting")
    assert "&lt;script&gt;" in resume["resume_html"]
    assert "<script>" not in resume["resume_html"]
    assert "GAP: supply authentic evidence" in resume["resume_text"]
    assert resume["evidence_map"]["total_requirements"] == 2

    status, _ = outsider.request("POST", "/v1/phase15/resume/draft", draft_payload)
    expect(status, 403, "Cross-organization resume drafting must fail")

    interview_payload = {
        "organization_id": org,
        "question": "Describe a time you coordinated maintenance priorities.",
        "answer": "During inspection I was responsible for coordinating two shops. I verified the work was completed.",
        "competency": "production coordination",
    }
    status, feedback = owner.request("POST", "/v1/phase16/interview/simulate", interview_payload)
    expect(status, 200, "Authorized practice interview")
    assert 0 <= feedback["practice_score"] <= feedback["practice_max"]
    assert feedback["fact_checked"] is False and feedback["hiring_prediction"] is None

    status, plan = owner.request("POST", "/v1/phase17/operations/plan", {
        "organization_id": org,
        "regions": [{"region_id": "ci-east", "reported_health": "healthy"},
                    {"region_id": "ci-west", "reported_health": "unknown"}],
        "desired_primary": "ci-west", "attestations": [],
    })
    expect(status, 200, "Authorized operations dry-run")
    assert plan["automatic_failover_enabled"] is False
    assert plan["deployment_executed"] is False and plan["failover_executed"] is False
    assert plan["blockers"] and plan["missing_checks"]

    status, _ = outsider.request("POST", "/v1/phase17/operations/plan", {
        "organization_id": org,
        "regions": [{"region_id": "ci-east", "reported_health": "healthy"}],
        "attestations": [],
    })
    expect(status, 403, "Cross-organization operations access must fail")

    status, _ = owner.request("POST", "/v1/auth/logout", {})
    expect(status, 200, "Logout")
    status, _ = owner.request("GET", "/v1/auth/me")
    expect(status, 401, "Logout invalidates browser access")
    print("PASS: live web proxy, register/login/logout, organization isolation, CSRF,"
          " resume XSS/gap handling, interview feedback, and failover default-deny")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--ack-isolated-stack", action="store_true",
                        help="Explicitly confirm disposable stack (CI users are stored).")
    args = parser.parse_args()
    if not args.ack_isolated_stack:
        parser.error("Use --ack-isolated-stack after confirming the endpoint is disposable CI/staging.")
    try:
        run(args.base_url)
    except (AssertionError, OSError, URLError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: Phase 15–17 live smoke: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
