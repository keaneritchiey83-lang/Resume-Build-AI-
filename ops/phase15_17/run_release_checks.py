#!/usr/bin/env python3
"""Execute offline-safe release preflight and write auditable JSON evidence.

The report deliberately records blocked/unexecuted checks as BLOCKED, never PASS.
GitHub Actions, live Compose and cloud failover are separate external gates.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def execute(name: str, command: list[str], *, cwd: Path = ROOT, timeout: int = 120):
    try:
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return {'gate': name, 'status': 'PASS' if result.returncode == 0 else 'FAIL',
                'exit_code': result.returncode, 'command': command,
                'output_tail': (result.stdout + result.stderr)[-2500:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'gate': name, 'status': 'BLOCKED', 'reason': str(exc), 'command': command}


def blocked(name: str, why: str):
    return {'gate': name, 'status': 'BLOCKED', 'reason': why}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', default='reports/phase15-17-local-release-evidence.json')
    ap.add_argument('--light', action='store_true',
                    help='Run standard-library checks only (for clean CI checkout).')
    args = ap.parse_args()
    python = sys.executable
    gates = [
        execute('Python source compilation', [python, '-m', 'compileall', '-q', 'backend/app',
                 'backend/phase14', 'backend/alembic', 'backend/tests', 'ops', 'scripts']),
        execute('Phase 14/15-17 deployment regression tests',
                [python, '-m', 'unittest', 'discover', '-s', 'ops/phase14/validation', '-p', 'test_*.py', '-v']),
    ]
    if args.light:
        gates.extend([
            blocked('Phase 15-17 targeted backend tests', 'Full backend dependencies are tested in ci.yml'),
            blocked('Phase 13/14 governance execution', 'Backend governance suite is tested in ci.yml'),
        ])
    else:
        gates.extend([
        execute('Phase 15-17 targeted backend tests',
                [python, '-m', 'pytest', '-q', 'tests/test_phase15_17.py',
                 'tests/test_phase15_17_b.py', 'tests/test_phase14.py', 'tests/test_phase13.py'],
                cwd=ROOT / 'backend'),
        execute('Phase 13 governance gate', [python, 'scripts/run_phase13_governance_gate.py'],
                cwd=ROOT / 'backend'),
        execute('Phase 14 governance gate', [python, 'scripts/run_phase14_governance_gate.py'],
                cwd=ROOT / 'backend'),
        ])
    gates.append(execute('Static deployment-security controls', [python, 'ops/phase15_17/security_review.py']))
    gates.append(execute('Controlled failover dry-run (zero cluster changes)',
                         [python, 'ops/phase14/failover/failover_drill.py', '--kube-context',
                          'staging', '--namespace', 'career-ai-staging', '--global-url',
                          'https://global.invalid', '--failed-region-url',
                          'https://failed.invalid', '--survivor-url', 'https://survivor.invalid',
                          '--survivor-region', 'staging-survivor']))
    if shutil.which('docker'):
        gates.append(execute('Docker Compose availability', ['docker', 'compose', 'version']))
    else:
        gates.append(blocked('Docker Compose live deployment', 'Docker CLI is unavailable on this host'))
    if (ROOT / 'frontend/node_modules').is_dir():
        gates.append(execute('Frontend production build', ['npm', 'run', 'build'], cwd=ROOT / 'frontend'))
        gates.append(execute('Frontend bundle validation', ['npm', 'run', 'test:build'], cwd=ROOT / 'frontend'))
    else:
        gates.append(blocked('Frontend production build',
                             'No frontend/node_modules; install dependencies on a connected runner'))
    gates.extend([
        blocked('Live PostgreSQL migration and authenticated Compose integration',
                'Requires running disposable PostgreSQL/Docker Compose infrastructure'),
        blocked('GitHub Actions hosted pipeline',
                'Must run on a repository containing this project; local execution is not a hosted CI run'),
        blocked('Approved staging regional failover',
                'Requires a protected GitHub staging environment and authorized regional infrastructure'),
        blocked('Independent manual security approval',
                'Static configuration review is not a full security review'),
    ])
    report = {'project': 'Global Career Architecture AI',
              'phase': '15-17 B-track', 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'LOCAL preflight; not a completed CI pipeline or production certification',
              'gates': gates}
    counts = {s: sum(g['status'] == s for g in gates) for s in ('PASS', 'FAIL', 'BLOCKED')}
    report['counts'] = counts
    report['production_ready'] = counts['FAIL'] == 0 and counts['BLOCKED'] == 0
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'RELEASE PREFLIGHT: {counts}; production_ready={report["production_ready"]}')
    print(f'Report: {output}')
    return 1 if counts['FAIL'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
