"""Local startup contract tests; never invoke Docker or live network."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from create_ci_env import write_env

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "start_local.py"
spec = importlib.util.spec_from_file_location("start_local", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LocalLauncherTests(unittest.TestCase):
    def test_local_env_has_unique_keys_and_agent_execution_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / ".env.example").write_text((ROOT / ".env.example").read_text())
            config = write_env(directory, mode="local")
            values = dict(line.split("=", 1) for line in config.read_text().splitlines()
                          if line and not line.startswith("#") and "=" in line)
            self.assertEqual(values["DEPLOYMENT_ENVIRONMENT"], "local")
            self.assertEqual(values["PHASE14_ENABLED"], "false")
            self.assertEqual(values["ADMIN_EMAILS"], "")
            self.assertEqual(values["LOCAL_CURRENT_KEY_ID"], "local-v1")
            self.assertIn("local-v1", json.loads(values["LOCAL_MASTER_KEYS_JSON"]))

    def test_missing_docker_emits_install_guidance(self):
        with patch.object(module.subprocess, "run", side_effect=FileNotFoundError):
            failures = module.preflight()
        self.assertEqual(len(failures), 3)
        self.assertIn("Install Docker", failures[0])

    def test_existing_bad_config_does_not_get_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / ".env").write_text("PHASE14_ENABLED=true\\n")
            with patch.object(module, "ROOT", folder):
                with self.assertRaisesRegex(RuntimeError, "refuses PHASE14_ENABLED"):
                    module.verify_local_config()
            self.assertEqual((folder / ".env").read_text(), "PHASE14_ENABLED=true\\n")


if __name__ == "__main__":
    unittest.main()
