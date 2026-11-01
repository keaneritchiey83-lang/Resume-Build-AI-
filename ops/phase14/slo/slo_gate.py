#!/usr/bin/env python3
"""Live Prometheus SLO check; include in delivery gates and scheduled validation.

Needs career_phase14_http_requests_total and career_phase14_http_duration_seconds_bucket.
No metrics / telemetry are fabricated when requests fail.
"""
import argparse
import json
import math
import sys
from urllib.parse import urlencode
from urllib.request import urlopen

REQUESTS = 'sum(increase(career_phase14_http_requests_total{route!="/health",route!="/ready",route!="/metrics"}[30d]))'
FAILURES = 'sum(increase(career_phase14_http_requests_total{status=~"5..",route!="/health",route!="/ready",route!="/metrics"}[30d]))'
P95 = ('histogram_quantile(0.95, sum by (le) '
       '(rate(career_phase14_http_duration_seconds_bucket{route!="/health",route!="/ready",route!="/metrics"}[5m])))')

def query(server, promql):
    endpoint = server.rstrip("/") + "/api/v1/query?" + urlencode({"query": promql})
    with urlopen(endpoint, timeout=15) as response:
        obj = json.load(response)
    if obj.get("status") != "success" or obj["data"]["resultType"] != "vector":
        raise RuntimeError("Prometheus query unsuccessful")
    rows = obj["data"]["result"]
    if len(rows) != 1:
        raise RuntimeError("expected exactly one series; no data or unexpected cardinality")
    value = float(rows[0]["value"][1])
    if not math.isfinite(value):
        raise RuntimeError("non-finite Prometheus result")
    return value

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prometheus-url", required=True)
    parser.add_argument("--availability-target", type=float, default=0.999)
    parser.add_argument("--p95-max-seconds", type=float, default=1.0)
    parser.add_argument("--min-30d-requests", type=int, default=100)
    args = parser.parse_args()
    if not 0 < args.availability_target <= 1 or args.p95_max_seconds <= 0:
        parser.error("invalid SLO thresholds")
    total = query(args.prometheus_url, REQUESTS)
    failures = query(args.prometheus_url, FAILURES)
    p95 = query(args.prometheus_url, P95)
    availability = 1 - failures / total if total else 0
    ok = (total >= args.min_30d_requests and 0 <= failures <= total
          and availability >= args.availability_target and p95 <= args.p95_max_seconds)
    print(json.dumps({
        "period": "30d availability; 5m p95",
        "observed_requests": total, "observed_5xx": failures,
        "availability": availability, "p95_latency_seconds": p95,
        "result": "PASS" if ok else "FAIL"
    }, indent=2))
    return 0 if ok else 1

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SLO GATE ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
