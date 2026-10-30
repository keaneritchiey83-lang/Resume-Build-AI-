"""Offline regressions for the Phase 15–17 deployment recovery controls."""
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit
import tempfile

from create_ci_env import write_env

ROOT = Path(__file__).resolve().parents[3]


class Phase1517DeploymentTests(unittest.TestCase):
    def test_ci_db_password_is_generated_and_consistent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".env.example").write_text((ROOT / ".env.example").read_text())
            settings = dict(line.split("=", 1) for line in write_env(root).read_text().splitlines()
                            if line and not line.startswith("#") and "=" in line)
            self.assertGreaterEqual(len(settings["POSTGRES_PASSWORD"]), 24)
            self.assertEqual(urlsplit(settings["DATABASE_URL"]).password,
                             settings["POSTGRES_PASSWORD"])
            self.assertEqual(urlsplit(settings["DATABASE_URL"]).hostname, "postgres")

    def test_compose_uses_configured_database_secret(self):
        compose = (ROOT / "docker-compose.yml").read_text()
        self.assertIn("POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?", compose)
        self.assertNotIn("POSTGRES_PASSWORD: career", compose)

    def test_ci_live_smoke_requires_explicit_approval_and_proxy(self):
        workflow = (ROOT / ".github/workflows/phase14-live-validation.yml").read_text()
        smoke = (ROOT / "ops/phase15_17/integration_smoke.py").read_text()
        self.assertIn("integration_smoke.py --ack-isolated-stack", workflow)
        self.assertIn("http://127.0.0.1:5173", workflow)
        self.assertIn("--ack-isolated-stack", smoke)
        for check in ("CSRF", "Cross-organization", "automatic_failover_enabled", "resume_html"):
            self.assertIn(check, smoke)

    def test_career_studio_exposes_all_phases_without_mutating_failover(self):
        ui = (ROOT / "frontend/src/App.tsx").read_text()
        self.assertIn("/v1/phase15/resume/evidence-map", ui)
        self.assertIn("/v1/phase16/interview/plan", ui)
        self.assertIn("/v1/phase17/operations/plan", ui)
        self.assertIn("canManageOperations", ui)
        self.assertIn("Export HTML / print PDF", ui)
        self.assertNotIn("/phase17/operations/execute", ui)


if __name__ == "__main__":
    unittest.main()
