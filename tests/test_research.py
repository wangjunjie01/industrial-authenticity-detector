import unittest

from industrial_authenticity.research import ResearchManager, _public_https_url


PUBLIC_RESOLVER = lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 443))]


class ResearchTests(unittest.TestCase):
    def manager(self, **kwargs):
        return ResearchManager(api_key="", resolver=PUBLIC_RESOLVER, **kwargs)

    def test_prepare_keeps_draft_local_and_returns_exact_outbound_preview(self):
        manager = self.manager()
        result = manager.prepare("PP divider load direction user@example.com")

        self.assertEqual(result["outbound_preview"], result["candidate_queries"])
        self.assertIn("email_address_detected", result["sensitive_information_warnings"])
        session = manager.sessions[result["research_session_id"]]
        self.assertFalse(hasattr(session, "text"))

    def test_search_requires_explicit_consent(self):
        manager = self.manager()
        prepared = manager.prepare("PP divider load check")
        with self.assertRaises(ValueError):
            manager.search(prepared["research_session_id"], [], [], False)

    def test_manual_source_produces_unconfirmed_traceable_cards(self):
        manager = self.manager(document_request=lambda url: {
            "url": url,
            "content_type": "text/html",
            "body": b"<title>PP Technical Data</title><p>A 5 mm PP divider requires a load check before release.</p>",
        })
        prepared = manager.prepare("PP divider load check")
        result = manager.search(
            prepared["research_session_id"], [], ["https://example.com/pp"], True
        )

        self.assertEqual(len(result["evidence_cards"]), 1)
        card = result["evidence_cards"][0]
        self.assertFalse(card["confirmed"])
        self.assertEqual(card["url"], "https://example.com/pp")
        self.assertTrue(card["content_fingerprint"])
        confirmed = manager.confirmed_facts(prepared["research_session_id"], [card["fact_id"]])
        self.assertTrue(confirmed[0]["confirmed"])

    def test_missing_brave_key_keeps_manual_fallback(self):
        manager = self.manager()
        prepared = manager.prepare("PP divider load check")
        result = manager.search(prepared["research_session_id"], ["PP load standard"], [], True)

        self.assertFalse(result["brave_search_used"])
        self.assertEqual(result["errors"][0]["type"], "brave_api_key_missing")
        self.assertTrue(result["offline_fallback_available"])

    def test_rejects_local_private_and_non_https_sources(self):
        private_resolver = lambda *_args, **_kwargs: [(None, None, None, None, ("127.0.0.1", 443))]
        for url, resolver in (
            ("http://example.com", PUBLIC_RESOLVER),
            ("file:///tmp/spec.pdf", PUBLIC_RESOLVER),
            ("https://localhost/spec", PUBLIC_RESOLVER),
            ("https://example.com/spec", private_resolver),
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    _public_https_url(url, resolver)

    def test_expired_or_unknown_fact_ids_are_rejected(self):
        now = [100.0]
        manager = ResearchManager(api_key="", resolver=PUBLIC_RESOLVER, clock=lambda: now[0])
        prepared = manager.prepare("PP divider load check")
        with self.assertRaises(ValueError):
            manager.confirmed_facts(prepared["research_session_id"], ["unknown"])
        now[0] += 1_801
        with self.assertRaises(ValueError):
            manager.search(prepared["research_session_id"], [], [], True)


if __name__ == "__main__":
    unittest.main()
