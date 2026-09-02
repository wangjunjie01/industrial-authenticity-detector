import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from industrial_authenticity.server import DetectorServer, Handler
from industrial_authenticity.research import ResearchManager
from industrial_authenticity.updates import UpdateManager


class LocalApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        manager = UpdateManager(Path(self.temp.name), fetch_json=lambda _: {})
        research = ResearchManager(
            api_key="",
            resolver=lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
            document_request=lambda url: {
                "url": url,
                "content_type": "text/html",
                "body": b"<title>Technical note</title><p>A 5 mm PP divider requires a documented load check before release.</p>",
            },
        )
        self.server = DetectorServer(("127.0.0.1", 0), Handler, manager, research)
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
        self.assertEqual(optimized["optimizer_version"], "iad-research-optimizer-0.4.0")
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

    def test_research_requires_consent_and_only_confirmed_cards_reach_optimizer(self):
        status, prepared = self.post("/api/research/prepare", {"text": "Choose a PP divider after checking the load."})
        self.assertEqual(status, 200)
        self.assertFalse(prepared["brave_search_available"])

        with self.assertRaises(HTTPError) as blocked:
            self.post(
                "/api/research/search",
                {"research_session_id": prepared["research_session_id"], "queries": [], "manual_urls": ["https://example.com/note"], "allow_network": False},
            )
        self.assertEqual(blocked.exception.code, 400)
        blocked.exception.close()

        status, researched = self.post(
            "/api/research/search",
            {"research_session_id": prepared["research_session_id"], "queries": [], "manual_urls": ["https://example.com/note"], "allow_network": True},
        )
        self.assertEqual(status, 200)
        self.assertTrue(researched["evidence_cards"])
        fact_id = researched["evidence_cards"][0]["fact_id"]

        status, optimized = self.post(
            "/api/optimize",
            {
                "text": "Choose the PP divider after checking the load.",
                "platform": "blog",
                "research_session_id": prepared["research_session_id"],
                "confirmed_source_fact_ids": [fact_id],
                "citation_mode": "body",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(optimized["fact_ledger"]["confirmed_source_facts"][0]["fact_id"], fact_id)


if __name__ == "__main__":
    unittest.main()
