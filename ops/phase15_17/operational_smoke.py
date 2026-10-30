#!/usr/bin/env python3
"""Local loopback HTTP tests of Phase 15–17 services, NOT the full application."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.phase15_17_b_services import resume_draft, interview_simulation, operations_plan  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def respond(self, status: int, payload: dict):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            self.respond(200, {"status": "ok", "scope": "local-test-harness"})
        else:
            self.respond(404, {"detail": "unknown endpoint"})

    def do_POST(self):
        if self.path not in ("/resume/draft", "/interview/simulate", "/regions/plan"):
            self.respond(404, {"detail": "unknown endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length < 32768:
                self.respond(413, {"detail": "test request size exceeded"})
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Expected object")
            if self.path == "/resume/draft":
                result = resume_draft(**payload)
            elif self.path == "/interview/simulate":
                result = interview_simulation(**payload)
            else:
                result = operations_plan(**payload)
            self.respond(200, result)
        except (TypeError, ValueError, KeyError):
            self.respond(400, {"detail": "invalid synthetic input"})


def request(base: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(base + path, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as response:
        return response.code, json.load(response)


def main() -> int:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    endpoint = f"http://127.0.0.1:{httpd.server_port}"
    results = []
    try:
        code, data = request(endpoint, "/health")
        results.append({"name": "health", "passed": code == 200 and data.get("status") == "ok"})
        code, data = request(endpoint, "/resume/draft", {
            "candidate_name": "Example Candidate",
            "target_role": "Security Analyst",
            "summary": "Review <script>alert(1)</script>",
            "requirements": ["network incident response and analysis"],
            "evidence": [{"id": "ev1", "description": "Led network incident response and analysis"}],
            "template": "technical",
        })
        results.append({"name": "resume_html_escaped", "passed": code == 200
                        and "<script>" not in data.get("resume_html", "")
                        and "&lt;script&gt;" in data.get("resume_html", "")})
        code, data = request(endpoint, "/interview/simulate", {
            "question": "Describe an incident",
            "answer": "During an incident I coordinated a verified response and outcome.",
            "competency": "Incident response",
        })
        results.append({"name": "interview_not_certification", "passed": code == 200
                        and 0 <= data.get("practice_score", -1) <= 30
                        and data.get("fact_checked") is False})
        code, data = request(endpoint, "/regions/plan", {
            "regions": [{"region_id": "test-a", "reported_health": "healthy"}],
            "attestations": [],
            "desired_primary": "test-a",
        })
        results.append({"name": "region_plan_read_only", "passed": code == 200
                        and data.get("mode") == "read_only_dry_run"
                        and data.get("failover_executed") is False})
        code, _ = request(endpoint, "/missing")
        results.append({"name": "unknown_route_404", "passed": code == 404})
    finally:
        httpd.shutdown()
        httpd.server_close()
        worker.join(timeout=3)
    report = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "ephemeral loopback HTTP service test; NOT the authenticated FastAPI/Docker application",
        "results": results, "full_application_running": False,
        "database_tested": False, "staging_failover_tested": False,
    }
    path = ROOT / "reports/phase15-17-operational-smoke.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if all(test["passed"] for test in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
