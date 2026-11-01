from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.governance import _case_result
from app.schemas import EvalCase


def main() -> int:
    path = Path(__file__).resolve().parents[2] / "governance" / "evals" / "default_cases.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = [
        _case_result(EvalCase.model_validate(case))
        for case in payload["cases"]
    ]
    failed = [item for item in results if not item["passed"]]

    for item in results:
        state = "PASS" if item["passed"] else "FAIL"
        print(f"{state} {item['case_id']}: {item['reason']}")

    if failed:
        print(f"Governance gate failed: {len(failed)} baseline case(s).")
        return 1

    print(f"Governance gate passed: {len(results)} baseline case(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
