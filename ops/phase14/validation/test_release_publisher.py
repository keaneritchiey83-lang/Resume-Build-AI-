"""Dependency-free regression checks for the controlled GitHub release importer."""
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('publish', ROOT / 'scripts' / 'publish_to_github.py')
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


class PublishSafetyTests(unittest.TestCase):
    def archive(self, files):
        buf = io.BytesIO()
        with ZipFile(buf, 'w') as z:
            for name, text in files.items():
                z.writestr('global-career-ai-phase14/' + name, text)
        buf.seek(0)
        return ZipFile(buf)

    def valid_files(self):
        return {name: 'public source' for name in publisher.REQUIRED}

    def test_accepts_complete_source(self):
        with self.archive(self.valid_files()) as z:
            self.assertEqual(len(publisher.checked_entries(z)), len(publisher.REQUIRED))

    def test_refuses_missing_source(self):
        files = self.valid_files()
        del files['frontend/package.json']
        with self.archive(files) as z:
            with self.assertRaisesRegex(ValueError, 'missing required'):
                publisher.checked_entries(z)

    def test_refuses_sensitive_env(self):
        files = self.valid_files()
        files['.env.production'] = 'DO_NOT_LEAK=secret'
        with self.archive(files) as z:
            with self.assertRaisesRegex(ValueError, 'Environment configuration'):
                publisher.checked_entries(z)

    def test_refuses_private_key_block(self):
        files = self.valid_files()
        files['docs/secret.md'] = '-----BEGIN ' + 'PRIVATE KEY-----\nFake\n-----END PRIVATE KEY-----'
        with self.archive(files) as z:
            with self.assertRaisesRegex(ValueError, 'Private-key material'):
                publisher.checked_entries(z)

    def test_refuses_zip_slip(self):
        files = self.valid_files()
        files['docs/../../escape.txt'] = 'danger'
        with self.archive(files) as z:
            with self.assertRaisesRegex(ValueError, 'Unsafe ZIP entry'):
                publisher.checked_entries(z)


if __name__ == '__main__':
    unittest.main()
