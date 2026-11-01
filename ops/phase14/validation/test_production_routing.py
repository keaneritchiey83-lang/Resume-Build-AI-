"""Static deployment-contract checks that work without Docker or npm."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]

class ProductionRoutingTests(unittest.TestCase):
    def test_same_origin_default(self):
        api = (ROOT / "frontend/src/api.ts").read_text()
        self.assertIn('import.meta.env.VITE_API_URL ?? ""', api)
        self.assertNotIn('"http://localhost:8000"', api)

    def test_nginx_proxy_and_health(self):
        config = (ROOT / "frontend/nginx.conf").read_text()
        for expected in ('location ^~ /v1/', 'proxy_pass http://api:8000;',
                         'location = /healthz', 'location = /ready'):
            self.assertIn(expected, config)

    def test_compose_build_uses_same_origin(self):
        compose = (ROOT / "docker-compose.yml").read_text()
        self.assertIn('VITE_API_URL: ""', compose)

if __name__ == "__main__":
    unittest.main()
