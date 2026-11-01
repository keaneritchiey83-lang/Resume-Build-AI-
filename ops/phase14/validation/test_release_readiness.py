"""Release regression coverage: governance versions, local exposure, CI controls."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'backend/scripts/run_phase13_governance_gate.py'
spec = importlib.util.spec_from_file_location('phase13_gate_for_test', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class VersionGateTests(unittest.TestCase):
    def write_project(self, root, version, declared):
        (root / 'backend/app').mkdir(parents=True)
        (root / 'backend/app/main.py').write_text(f'APP_VERSION = "{version}"\n')
        (root / 'backend/pyproject.toml').write_text(
            f'[project]\nname = "global-career-architecture-ai"\nversion = "{declared}"\n')

    def test_phase13_and_14_accept_newer_matching_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_project(root, '0.17.0', '0.17.0')
            with patch.object(module, 'ROOT', root):
                module.verify_application_version(13)
                module.verify_application_version(14)

    def test_phase14_rejects_old_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_project(root, '0.13.9', '0.13.9')
            with patch.object(module, 'ROOT', root):
                with self.assertRaisesRegex(SystemExit, 'older'):
                    module.verify_application_version(14)

    def test_rejects_mismatched_package_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_project(root, '0.17.0', '0.16.0')
            with patch.object(module, 'ROOT', root):
                with self.assertRaisesRegex(SystemExit, 'differs'):
                    module.verify_application_version(14)


class ReleaseSecurityTests(unittest.TestCase):
    def test_static_control_review(self):
        result = subprocess.run([sys.executable, 'ops/phase15_17/security_review.py'],
                                cwd=ROOT, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_release_workflow_is_non_disruptive(self):
        workflow = (ROOT / '.github/workflows/phase15-17-release-readiness.yml').read_text()
        self.assertIn('workflow_dispatch:', workflow)
        self.assertIn('run_release_checks.py', workflow)
        self.assertIn('upload-artifact@v4', workflow)
        self.assertNotIn('--execute --ack-impact', workflow)


if __name__ == '__main__':
    unittest.main()
