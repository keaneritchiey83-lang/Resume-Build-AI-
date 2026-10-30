#!/usr/bin/env python3
"""Staging-only, manually authorized failover drill with verified rollback.

No resource changes without --execute and --ack-impact, an approved change ID,
an exact staging namespace, and an expected Kubernetes control plane URL.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

STAGING_NAMESPACE = "career-ai-staging"


def kube(context: str, namespace: str, *args: str) -> str:
    result = subprocess.run(["kubectl", "--context", context, "-n", namespace, *args],
                            text=True, capture_output=True, timeout=45)
    if result.returncode:
        raise RuntimeError("kubectl failed: " + result.stderr.strip())
    return result.stdout


def verify_cluster(context: str, expected_server: str) -> None:
    parsed = urlsplit(expected_server)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.fragment or parsed.query or parsed.path not in ("", "/")):
        raise RuntimeError("Approved Kubernetes API server must be an HTTPS origin")
    cmd = ["kubectl", "--context", context, "config", "view", "--minify", "-o", "json"]
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=45)
    if result.returncode:
        raise RuntimeError("Cannot verify kubeconfig context: " + result.stderr.strip())
    entries = json.loads(result.stdout).get("clusters", [])
    if len(entries) != 1:
        raise RuntimeError("Expected exactly one staging cluster")
    actual = entries[0].get("cluster", {}).get("server", "")
    if actual.rstrip("/") != expected_server.rstrip("/"):
        raise RuntimeError("Cluster API server does not match approved staging endpoint")


def selector_patch(selector: dict[str, str]) -> str:
    return json.dumps([{"op": "replace", "path": "/spec/selector", "value": selector}])


def service_selector(context: str, namespace: str, service: str) -> dict[str, str]:
    data = json.loads(kube(context, namespace, "get", "service", service, "-o", "json"))
    selector = data["spec"].get("selector")
    if not isinstance(selector, dict) or not selector:
        raise RuntimeError("Service selector not suitable for reversible failover drill")
    return selector


def probe(url: str, timeout: int = 5) -> str | None:
    req = Request(url.rstrip("/") + "/ready", headers={"User-Agent": "phase14-failover-drill"})
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError("Unhealthy regional HTTP response")
        body = json.load(response)
        return response.headers.get("X-Deployment-Region") or body.get("region")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kube-context", required=True)
    parser.add_argument("--namespace", default=STAGING_NAMESPACE)
    parser.add_argument("--service", default="career-api")
    parser.add_argument("--global-url", required=True)
    parser.add_argument("--failed-region-url", required=True)
    parser.add_argument("--survivor-url", required=True)
    parser.add_argument("--survivor-region", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--expected-cluster-server", default="")
    parser.add_argument("--approval-id", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ack-impact", action="store_true")
    args = parser.parse_args()
    if not 30 <= args.timeout_seconds <= 900:
        parser.error("Timeout must be between 30 and 900 seconds")
    if args.namespace != STAGING_NAMESPACE:
        parser.error("Only the exact career-ai-staging namespace is permitted")
    print(json.dumps({"mode": "EXECUTE" if args.execute else "DRY_RUN",
                      "context": args.kube_context, "namespace": args.namespace,
                      "service": args.service, "timeout_seconds": args.timeout_seconds}))
    if not args.execute:
        print("DRY_RUN ONLY: no Kubernetes resources changed")
        return 0
    if not args.ack_impact or not args.approval_id.strip() or not args.expected_cluster_server:
        parser.error("Execution requires --ack-impact, --approval-id and --expected-cluster-server")
    verify_cluster(args.kube_context, args.expected_cluster_server)
    if probe(args.survivor_url) != args.survivor_region:
        raise RuntimeError("Survivor region identity does not match approved input")
    probe(args.failed_region_url)
    original = service_selector(args.kube_context, args.namespace, args.service)
    recovered = False
    rollback_verified = False
    attempted = False
    try:
        attempted = True
        kube(args.kube_context, args.namespace, "patch", "service", args.service,
             "--type=json", "--patch",
             selector_patch({"phase14-drill-blocked": "do-not-match-any-pods"}))
        deadline = time.monotonic() + args.timeout_seconds
        failed_seen = False
        consecutive = 0
        while time.monotonic() < deadline:
            try:
                probe(args.failed_region_url)
                consecutive = 0
            except Exception:
                failed_seen = True
            if failed_seen:
                try:
                    current = probe(args.global_url)
                    consecutive = consecutive + 1 if current == args.survivor_region else 0
                    if consecutive >= 3:
                        recovered = True
                        break
                except Exception:
                    consecutive = 0
            time.sleep(5)
    finally:
        if attempted:
            kube(args.kube_context, args.namespace, "patch", "service", args.service,
                 "--type=json", "--patch", selector_patch(original))
            rollback_verified = service_selector(args.kube_context, args.namespace, args.service) == original
    if not rollback_verified:
        raise RuntimeError("Original Service selector was not verified after rollback")
    if not recovered:
        print("FAILOVER DRILL FAIL: no verified recovery before timeout", file=sys.stderr)
        return 1
    print("FAILOVER DRILL PASS: recovery observed and original Service selector restored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
