"""Dependency-light unit tests for the actual Phase 14 live validation helpers."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from create_ci_env import write_env
from live_smoke import verify_database, verify_health, EXPECTED_TABLES


class EnvironmentPreparationTests(unittest.TestCase):
    def test_ci_creates_private_secrets_and_refuses_overwrite(self):
        source = Path(__file__).resolve().parents[3] / ".env.example"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.example").write_text(source.read_text())
            generated = write_env(root)
            text = generated.read_text()
            values = {
                line.split("=", 1)[0]: line.split("=", 1)[1]
                for line in text.splitlines()
                if line and not line.startswith("#") and "=" in line
            }
            self.assertGreaterEqual(len(values["JWT_SECRET"]), 32)
            self.assertGreaterEqual(len(values["OIDC_SESSION_SECRET"]), 32)
            self.assertNotEqual(values["JWT_SECRET"], values["OIDC_SESSION_SECRET"])
            self.assertEqual(values["PHASE14_ENABLED"], "false")
            self.assertEqual(values["SCHEDULER_ENABLED"], "false")
            keys = json.loads(values["LOCAL_MASTER_KEYS_JSON"])
            self.assertEqual(len(base64.b64decode(keys["ci-local-v1"])), 32)
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(generated.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                write_env(root)


class StackValidatorTests(unittest.TestCase):
    def test_database_verifier_checks_migration_vector_and_tables(self):
        expected_results = [
            "0012_phase14",
            "1",
            "\n".join(sorted(EXPECTED_TABLES)),
        ]
        with patch("live_smoke.postgres_scalar", side_effect=expected_results) as query:
            verify_database()
        self.assertEqual(query.call_count, 3)

    def test_wrong_migration_fails_closed(self):
        with patch("live_smoke.postgres_scalar", return_value="0011_phase13"):
            with self.assertRaisesRegex(AssertionError, "0012_phase14"):
                verify_database()

    def test_readiness_fails_when_agent_execution_is_enabled(self):
        def fetch_mock(url, *, deadline):
            if url.endswith("/health"):
                return 200, json.dumps({"status": "ok"}).encode()
            if url.endswith("/ready"):
                return 200, json.dumps({"status": "ready"}).encode()
            if url.endswith("/v1/phase14/readiness"):
                return 200, json.dumps({"phase": "14A+14B", "enabled": True}).encode()
            if "/assets/" in url:
                return 200, b"console.log('compiled vite bundle')"
            return 200, b'<title>Global Career Architecture AI</title><script type="module" src="/assets/index-aaa.js"></script>' 

        with patch("live_smoke.wait_for", side_effect=fetch_mock):
            with self.assertRaisesRegex(AssertionError, "disabled"):
                verify_health("http://127.0.0.1:8000", "http://127.0.0.1:5173", deadline=3)

    def test_healthy_stack_is_accepted(self):
        def fetch_mock(url, *, deadline):
            if url.endswith("/health"):
                return 200, b'{"status":"ok"}'
            if url.endswith("/ready"):
                return 200, b'{"status":"ready"}'
            if url.endswith("/v1/phase14/readiness"):
                return 200, b'{"phase":"14A+14B","enabled":false}'
            if "/assets/" in url:
                return 200, b"console.log('compiled vite bundle')"
            return 200, b'<title>Global Career Architecture AI</title><script type="module" src="/assets/index-aaa.js"></script>' 

        with patch("live_smoke.wait_for", side_effect=fetch_mock):
            verify_health("http://127.0.0.1:8000", "http://127.0.0.1:5173", deadline=3)


if __name__ == "__main__":
    unittest.main()
