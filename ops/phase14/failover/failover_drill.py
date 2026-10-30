#!/usr/bin/env python3
"""Safe-by-default staging failover exercise.

Temporarily points a region's Service selector at non-existent pods (no API
deletion, no HPA conflict). Verifies failed regional ingress and healthy global
traffic from the surviving region, then restores the original selector.
"""
import argparse
import json
import subprocess
import sys
import time
from urllib.request import Request, urlopen

def kube(context, namespace, *args):
    command = ["kubectl", "--context", context, "-n", namespace, *args]
    result = subprocess.run(command, text=True, capture_output=True, timeout=45)
    if result.returncode:
        raise RuntimeError(f"kubectl failed: {result.stderr.strip()}")
    return result.stdout

def selector_patch(selector):
    return json.dumps([{"op": "replace", "path": "/spec/selector", "value": selector}])

def probe(url: str, timeout: int = 5):
    req = Request(url.rstrip("/") + "/ready", headers={"User-Agent": "phase14-failover-drill"})
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"unhealthy response: {response.status}")
        body = json.load(response)
        return response.headers.get("X-Deployment-Region") or body.get("region")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kube-context", required=True)
    parser.add_argument("--namespace", default="career-ai-staging")
    parser.add_argument("--service", default="career-api")
    parser.add_argument("--global-url", required=True)
    parser.add_argument("--failed-region-url", required=True)
    parser.add_argument("--survivor-url", required=True)
    parser.add_argument("--survivor-region", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ack-impact", action="store_true")
    parser.add_argument("--allow-production", action="store_true")
    args = parser.parse_args()

    if args.timeout_seconds < 30 or args.timeout_seconds > 900:
        parser.error("timeout-seconds must be 30..900")
    if "staging" not in args.namespace and not args.allow_production:
        parser.error("non-staging namespace requires --allow-production")
    print(json.dumps({
        "mode": "EXECUTE" if args.execute else "DRY_RUN",
        "affected_context": args.kube_context,
        "affected_namespace": args.namespace,
        "service": args.service,
        "survivor_region": args.survivor_region,
        "global_url": args.global_url,
        "timeout_seconds": args.timeout_seconds,
    }, indent=2))
    if not args.execute:
        print("No resources changed. Use --execute --ack-impact for staging drill.")
        return 0
    if not args.ack_impact:
        parser.error("--ack-impact required for disruptive drill")
    region = probe(args.survivor_url)
    if region != args.survivor_region:
        raise RuntimeError(f"survivor identity mismatch: {region!r}")
    probe(args.failed_region_url)  # confirms region was healthy before fault
    service = json.loads(kube(args.kube_context, args.namespace,
                              "get", "service", args.service, "-o", "json"))
    original = service["spec"].get("selector")
    if not original:
        raise RuntimeError("Service must have a selector to restore")
    print(f"Isolating Service {args.service}", flush=True)
    attempted = False
    try:
        attempted = True  # ensure restoration even if API response is lost
        kube(args.kube_context, args.namespace, "patch", "service", args.service,
             "--type=json", "--patch", selector_patch(
                 {"phase14-drill-blocked": "do-not-match-any-pods"}
             ))
        deadline = time.monotonic() + args.timeout_seconds
        failed_seen = False
        consecutive = 0
        while time.monotonic() < deadline:
            try:
                probe(args.failed_region_url)
                consecutive = 0
                print("Waiting for failed region to stop accepting traffic", flush=True)
            except Exception:
                failed_seen = True
            if failed_seen:
                try:
                    current = probe(args.global_url)
                    consecutive = consecutive + 1 if current == args.survivor_region else 0
                    print(f"Global healthy region={current}, consecutive={consecutive}", flush=True)
                    if consecutive >= 3:
                        print("FAILOVER DRILL PASS", flush=True)
                        return 0
                except Exception as exc:
                    consecutive = 0
                    print(f"Waiting for global failover: {exc}", flush=True)
            time.sleep(5)
        print("FAILOVER DRILL FAIL: unsuccessful failover before deadline", file=sys.stderr)
        return 1
    finally:
        if attempted:
            print("Restoring original Service selector", flush=True)
            kube(args.kube_context, args.namespace, "patch", "service", args.service,
                 "--type=json", "--patch", selector_patch(original))

if __name__ == "__main__":
    raise SystemExit(main())
