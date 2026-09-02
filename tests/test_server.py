import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from industrial_authenticity.server import DetectorServer, Handler
from industrial_authenticity.updates import UpdateManager


class LocalApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        manager = UpdateManager(Path(self.temp.name), fetch_json=lambda _: {})
        self.server = DetectorServer(("127.0.0.1", 0), Handler, manager)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.opener = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def post(self, path, payload, origin="http://127.0.0.1"):
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Origin": origin},
            method="POST",
        )
        with self.opener.open(request, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_analyze_remains_compatible_and_optimize_is_available(self):
        source = "Check the load before release."
        status, analysis = self.post("/api/analyze", {"text": source, "platform": "linkedin"})
        self.assertEqual(status, 200)
        self.assertIn("writing_style_risk", analysis)
        self.assertIn("model_detection", analysis)

        status, optimized = self.post(
            "/api/optimize",
            {"text": "Furthermore, check the load before release.", "platform": "linkedin", "verified_facts": {}, "confirmed_verified": False},
        )
        self.assertEqual(status, 200)
        self.assertEqual(optimized["optimizer_version"], "iad-safe-optimizer-0.3.0")
        self.assertFalse(optimized["score_changes"]["model_detection"]["used_for_selection"])
        for path in Path(self.temp.name).rglob("*"):
            if path.is_file():
                self.assertNotIn(source, path.read_text(encoding="utf-8", errors="ignore"))

    def test_optimize_rejects_untrusted_origin_and_oversized_text(self):
        with self.assertRaises(HTTPError) as blocked:
            self.post("/api/optimize", {"text": "Safe local draft."}, origin="https://example.com")
        self.assertEqual(blocked.exception.code, 403)
        blocked.exception.close()

        with self.assertRaises(HTTPError) as oversized:
            self.post("/api/optimize", {"text": "x" * 50_001})
        self.assertEqual(oversized.exception.code, 400)
        oversized.exception.close()


if __name__ == "__main__":
    unittest.main()
