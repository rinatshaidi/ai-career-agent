from __future__ import annotations

import unittest
from datetime import datetime, timezone

import httpx

from models import Opportunity, RemoteType
from providers.base import OpportunityProvider
from providers.habr import (
    HabrCareerError,
    HabrCareerFeedError,
    HabrCareerProvider,
    parse_vacancies_rss,
)


COLLECTED_AT = datetime(2026, 7, 17, 16, 0, tzinfo=timezone.utc)
SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Vacancies</title>
    <item>
      <title>\u0422\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f \u00abAI Automation Engineer\u00bb (\u043e\u0442 300 000 \u0434\u043e 350 000 \u20bd)</title>
      <description>Example Company. \u041c\u043e\u0441\u043a\u0432\u0430 (\u0420\u043e\u0441\u0441\u0438\u044f). \u041c\u043e\u0436\u043d\u043e \u0443\u0434\u0430\u043b\u0451\u043d\u043d\u043e.</description>
      <author>Example Company</author>
      <pubDate>Fri, 17 Jul 2026 18:10:47 +0300</pubDate>
      <link>https://career.habr.com/vacancies/1000000001</link>
      <guid>1000000001</guid>
    </item>
    <item>
      <title>\u0422\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f \u00abProject Manager\u00bb</title>
      <description>Second Company. \u0421\u0430\u043d\u043a\u0442-\u041f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433 (\u0420\u043e\u0441\u0441\u0438\u044f). \u0413\u0438\u0431\u0440\u0438\u0434\u043d\u044b\u0439 \u0444\u043e\u0440\u043c\u0430\u0442.</description>
      <author>Second Company</author>
      <pubDate>Thu, 16 Jul 2026 10:00:00 +0300</pubDate>
      <link>https://career.habr.com/vacancies/1000000002</link>
      <guid>1000000002</guid>
    </item>
  </channel>
</rss>
"""


class HabrCareerParserTests(unittest.TestCase):
    def test_normalizes_official_rss_to_opportunities(self) -> None:
        opportunities = parse_vacancies_rss(SAMPLE_FEED, collected_at=COLLECTED_AT)

        self.assertEqual(len(opportunities), 2)
        first = opportunities[0]
        self.assertIsInstance(first, Opportunity)
        self.assertEqual(first.source, "habr_career")
        self.assertEqual(first.external_id, "1000000001")
        self.assertEqual(first.title, "AI Automation Engineer")
        self.assertEqual(first.company_name, "Example Company")
        self.assertEqual(first.location, "\u041c\u043e\u0441\u043a\u0432\u0430")
        self.assertEqual(first.remote_type, RemoteType.REMOTE)
        self.assertEqual(first.salary_from, 300_000)
        self.assertEqual(first.salary_to, 350_000)
        self.assertEqual(first.currency, "RUB")
        self.assertEqual(first.published_at.isoformat(), "2026-07-17T18:10:47+03:00")
        self.assertEqual(first.collected_at, COLLECTED_AT)

        self.assertEqual(opportunities[1].location, "\u0421\u0430\u043d\u043a\u0442-\u041f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433")
        self.assertEqual(opportunities[1].remote_type, RemoteType.HYBRID)

    def test_respects_limit(self) -> None:
        opportunities = parse_vacancies_rss(SAMPLE_FEED, limit=1)
        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].external_id, "1000000001")

    def test_rejects_non_positive_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "limit"):
            parse_vacancies_rss(SAMPLE_FEED, limit=0)

    def test_rejects_malformed_xml(self) -> None:
        with self.assertRaisesRegex(HabrCareerFeedError, "malformed"):
            parse_vacancies_rss("<rss><channel>")

    def test_rejects_item_without_guid(self) -> None:
        feed = SAMPLE_FEED.replace("<guid>1000000001</guid>", "", 1)
        with self.assertRaisesRegex(HabrCareerFeedError, "guid"):
            parse_vacancies_rss(feed)


class HabrCareerHttpTests(unittest.TestCase):
    def test_implements_provider_contract_and_fetches_feed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["User-Agent"], "JobMonitor/Test")
            self.assertIn("application/rss+xml", request.headers["Accept"])
            return httpx.Response(200, text=SAMPLE_FEED, request=request)

        provider = HabrCareerProvider(
            feed_url="https://career.habr.com/vacancies/rss",
            user_agent="JobMonitor/Test",
            limit=10,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )
        self.assertIsInstance(provider, OpportunityProvider)
        self.assertEqual(len(provider.fetch()), 2)

    def test_converts_http_status_to_provider_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="Unavailable", request=request)

        provider = HabrCareerProvider(
            feed_url="https://career.habr.com/vacancies/rss",
            user_agent="JobMonitor/Test",
            limit=10,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(HabrCareerError, "HTTP 503"):
            provider.fetch()


if __name__ == "__main__":
    unittest.main()
