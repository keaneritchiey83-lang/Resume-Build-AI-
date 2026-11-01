"""Offline production-release guard regression tests. No cloud operations."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"


class ProductionReleaseGuardTests(unittest.TestCase):
    def test_deploy_inputs_bound_to_checked_out_source(self):
        text = (WORKFLOWS / "deploy-kubernetes.yml").read_text()
        self.assertNotIn("phase10", text)
        self.assertEqual(text.count("environment: production-"), 2)
        self.assertEqual(text.count("IMAGE_TAG: ${{ inputs.image_tag }}"), 2)
        self.assertEqual(text.count('[[ "$IMAGE_TAG" =~ ^[a-f0-9]{40}$ ]]'), 2)
        self.assertEqual(text.count('[[ "$IMAGE_TAG" == "$GITHUB_SHA" ]]'), 2)
        self.assertEqual(text.count('grep -q "newTag: phase14"'), 2)
        self.assertEqual(text.count('grep -q "career-api:phase14"'), 2)
        self.assertNotIn("newTag: ${{ inputs.image_tag }}", text)

    def test_image_placeholders_match_actual_manifests(self):
        migration = (ROOT / "k8s/jobs/migrate.yaml").read_text()
        self.assertIn("image: career-api:phase14", migration)
        with tempfile.TemporaryDirectory() as tmp:
            for cloud in ("eks", "aks"):
                with self.subTest(cloud=cloud):
                    orig = (ROOT / "k8s/overlays" / cloud / "kustomization.yaml").read_text()
                    self.assertEqual(orig.count("newTag: phase14"), 2)
                    local = Path(tmp) / (cloud + ".yaml")
                    local.write_text(orig)
                    check = subprocess.run(["sed", "-i",
                        "s|newTag: phase14|newTag: " + "a" * 40 + "|g", str(local)],
                        capture_output=True, text=True)
                    self.assertEqual(check.returncode, 0, check.stderr)
                    self.assertEqual(local.read_text().count("newTag: " + "a" * 40), 2)

    def test_signing_requires_fixed_environment_and_security_reference(self):
        text = (WORKFLOWS / "phase13-release-transparency.yml").read_text()
        self.assertIn("environment: production-signing", text)
        self.assertNotIn("inputs.environment", text)
        self.assertIn("GCAI_RELEASE_APPROVED_SHA", text)
        self.assertIn("GCAI_SECURITY_APPROVAL_ID", text)
        self.assertIn("[a-f0-9]{64}", text)
        self.assertIn('"$GITHUB_SHA"', text)


if __name__ == "__main__":
    unittest.main()
