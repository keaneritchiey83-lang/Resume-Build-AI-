"""Failover is never executed during CI without protected staging credentials."""
import subprocess
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]

class FailoverSafetyTests(unittest.TestCase):
    def test_dry_run_has_no_kubectl_requirement(self):
        proc = subprocess.run([
            sys.executable, "ops/phase14/failover/failover_drill.py",
            "--kube-context", "staging",
            "--namespace", "career-ai-staging",
            "--global-url", "https://global.invalid",
            "--failed-region-url", "https://failed.invalid",
            "--survivor-url", "https://survivor.invalid",
            "--survivor-region", "staging-survivor",
        ], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("DRY_RUN", proc.stdout)
        self.assertIn("No resources changed", proc.stdout)

    def test_nondryrun_requires_explicit_impact_ack(self):
        proc = subprocess.run([
            sys.executable, "ops/phase14/failover/failover_drill.py",
            "--kube-context", "staging",
            "--namespace", "career-ai-staging",
            "--global-url", "https://global.invalid",
            "--failed-region-url", "https://failed.invalid",
            "--survivor-url", "https://survivor.invalid",
            "--survivor-region", "staging-survivor",
            "--execute",
        ], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--ack-impact", proc.stderr)


if __name__ == "__main__":
    unittest.main()
