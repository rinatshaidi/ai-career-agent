from __future__ import annotations

import unittest
from datetime import datetime, timezone

import httpx

from models import RemoteType
from providers.base import OpportunityProvider
from providers.remoteok import (
    RemoteOKError,
    RemoteOKFeedError,
    RemoteOKProvider,
    parse_remoteok_jobs,
)


COLLECTED_AT = datetime(2026, 7, 18, 16, 0, tzinfo=timezone.utc)
SAMPLE_PAYLOAD = [
    {"last_updated": 1, "legal": "Link back to Remote OK."},
    {
        "id": "123",
        "date": "2026-07-18T12:30:00+00:00",
        "company": "Automation Co",
        "position": "AI Automation Specialist",
        "tags": ["n8n", "api", "automation"],
        "description": "<p>Build <strong>business workflows</strong>.</p>",
        "location": "Worldwide",
        "salary_min": 70000,
        "salary_max": 90000,
        "url": "https://remoteok.com/remote-jobs/123",
    },
    {
        "id": "124",
        "date": "2026-07-18T13:30:00Z",
        "company": "Bot Co",
        "position": "Telegram Bot Builder",
        "description": "Integrate a bot.",
        "location": "Europe",
        "salary_min": 0,
        "salary_max": 0,
        "apply_url": "https://remoteok.com/remote-jobs/124",
    },
]


class RemoteOKParserTests(unittest.TestCase):
    def test_normalizes_official_json_feed(self) -> None:
        opportunities = parse_remoteok_jobs(SAMPLE_PAYLOAD, collected_at=COLLECTED_AT)

        self.assertEqual(len(opportunities), 2)
        first = opportunities[0]
        self.assertEqual(first.source, "remote_ok")
        self.assertEqual(first.external_id, "123")
        self.assertEqual(first.title, "AI Automation Specialist")
        self.assertEqual(first.company_name, "Automation Co")
        self.assertEqual(first.location, "Worldwide")
        self.assertEqual(first.remote_type, RemoteType.REMOTE)
        self.assertEqual(first.salary_from, 70000)
        self.assertEqual(first.salary_to, 90000)
        self.assertEqual(first.currency, "USD")
        self.assertIn("Build business workflows.", first.description)
        self.assertIn("Tags: n8n, api, automation", first.description)
        self.assertEqual(first.collected_at, COLLECTED_AT)
        self.assertIsNone(opportunities[1].currency)

    def test_skips_legal_metadata_and_respects_limit(self) -> None:
        opportunities = parse_remoteok_jobs(SAMPLE_PAYLOAD, limit=1)
        self.assertEqual([item.external_id for item in opportunities], ["123"])

    def test_rejects_non_array_response(self) -> None:
        with self.assertRaisesRegex(RemoteOKFeedError, "JSON array"):
            parse_remoteok_jobs({"jobs": []})

    def test_rejects_job_without_position(self) -> None:
        payload = [{"id": "1", "url": "https://remoteok.com/remote-jobs/1"}]
        with self.assertRaisesRegex(RemoteOKFeedError, "position or URL"):
            parse_remoteok_jobs(payload)


class RemoteOKHttpTests(unittest.TestCase):
    def test_implements_provider_contract_and_fetches_feed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["User-Agent"], "JobMonitor/Test")
            self.assertEqual(request.headers["Accept"], "application/json")
            return httpx.Response(200, json=SAMPLE_PAYLOAD, request=request)

        provider = RemoteOKProvider(
            api_url="https://remoteok.com/api",
            user_agent="JobMonitor/Test",
            limit=10,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )
        self.assertIsInstance(provider, OpportunityProvider)
        self.assertEqual(len(provider.fetch()), 2)

    def test_converts_http_status_to_provider_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, request=request)

        provider = RemoteOKProvider(
            api_url="https://remoteok.com/api",
            user_agent="JobMonitor/Test",
            limit=10,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(RemoteOKError, "HTTP 503"):
            provider.fetch()


if __name__ == "__main__":
    unittest.main()
