#!/usr/bin/env python3
"""CI cost and N-1 capacity gate. Inputs are user-supplied estimates, not live metrics."""
import argparse
import json
import math
from pathlib import Path

def evaluate(data: dict) -> tuple[bool, dict]:
    needed = math.ceil(
        float(data["peak_global_requests_per_second"]) /
        (float(data["healthy_requests_per_second_per_pod"]) *
         float(data["maximum_planned_pod_utilization"]))
    )
    budget = float(data["monthly_spend_usd_estimate"]) <= float(data["monthly_spend_usd_ceiling"])
    failover = (
        int(data["region_a_max_replicas"]) >= needed and
        int(data["region_b_max_replicas"]) >= needed
    )
    return budget and failover, {
        "estimated_monthly_spend_within_ceiling": budget,
        "required_pods_after_single_region_failure": needed,
        "region_a_can_handle_total_peak": int(data["region_a_max_replicas"]) >= needed,
        "region_b_can_handle_total_peak": int(data["region_b_max_replicas"]) >= needed,
        "gate": "PASS" if budget and failover else "FAIL"
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("budget_file", type=Path)
    args = parser.parse_args()
    passed, result = evaluate(json.loads(args.budget_file.read_text()))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if passed else 1)
