from __future__ import annotations

import unittest
from datetime import datetime, timezone

import httpx

from models import RemoteType
from providers.base import OpportunityProvider
from providers.weworkremotely import (
    WeWorkRemotelyError,
    WeWorkRemotelyFeedError,
    WeWorkRemotelyProvider,
    parse_weworkremotely_rss,
)


COLLECTED_AT = datetime(2026, 7, 18, 16, 0, tzinfo=timezone.utc)
SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Remote Jobs</title>
    <item>
      <title>Workflow Co: AI Automation Specialist</title>
      <region>Anywhere in the World</region>
      <category>Product</category>
      <type>Contract</type>
      <description><![CDATA[<p>Build <strong>n8n workflows</strong> for clients.</p>]]></description>
      <pubDate>Sat, 18 Jul 2026 12:00:00 +0000</pubDate>
      <link>https://weworkremotely.com/remote-jobs/workflow-co-ai-automation</link>
      <guid>https://weworkremotely.com/remote-jobs/workflow-co-ai-automation</guid>
    </item>
    <item>
      <title>Independent Automation Consultant</title>
      <region>Europe</region>
      <description>Integrate APIs.</description>
      <pubDate>Fri, 17 Jul 2026 12:00:00 +0000</pubDate>
      <link>https://weworkremotely.com/remote-jobs/automation-consultant</link>
      <guid>https://weworkremotely.com/remote-jobs/automation-consultant</guid>
    </item>
  </channel>
</rss>
"""


class WeWorkRemotelyParserTests(unittest.TestCase):
    def test_normalizes_official_rss_feed(self) -> None:
        opportunities = parse_weworkremotely_rss(SAMPLE_FEED, collected_at=COLLECTED_AT)

        self.assertEqual(len(opportunities), 2)
        first = opportunities[0]
        self.assertEqual(first.source, "we_work_remotely")
        self.assertEqual(first.title, "AI Automation Specialist")
        self.assertEqual(first.company_name, "Workflow Co")
        self.assertEqual(first.location, "Anywhere in the World")
        self.assertEqual(first.remote_type, RemoteType.REMOTE)
        self.assertIn("Build n8n workflows for clients.", first.description)
        self.assertIn("Category: Product; Contract", first.description)
        self.assertEqual(first.published_at.isoformat(), "2026-07-18T12:00:00+00:00")
        self.assertEqual(first.collected_at, COLLECTED_AT)
        self.assertEqual(opportunities[1].company_name, "")

    def test_respects_limit(self) -> None:
        opportunities = parse_weworkremotely_rss(SAMPLE_FEED, limit=1)
        self.assertEqual(len(opportunities), 1)

    def test_rejects_malformed_xml(self) -> None:
        with self.assertRaisesRegex(WeWorkRemotelyFeedError, "malformed"):
            parse_weworkremotely_rss("<rss><channel>")

    def test_rejects_item_without_guid(self) -> None:
        feed = SAMPLE_FEED.replace(
            "<guid>https://weworkremotely.com/remote-jobs/workflow-co-ai-automation</guid>",
            "",
            1,
        )
        with self.assertRaisesRegex(WeWorkRemotelyFeedError, "guid"):
            parse_weworkremotely_rss(feed)


class WeWorkRemotelyHttpTests(unittest.TestCase):
    def test_implements_provider_contract_and_fetches_feed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["User-Agent"], "JobMonitor/Test")
            return httpx.Response(200, text=SAMPLE_FEED, request=request)

        provider = WeWorkRemotelyProvider(
            feed_url="https://weworkremotely.com/remote-jobs.rss",
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

        provider = WeWorkRemotelyProvider(
            feed_url="https://weworkremotely.com/remote-jobs.rss",
            user_agent="JobMonitor/Test",
            limit=10,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(WeWorkRemotelyError, "HTTP 503"):
            provider.fetch()


if __name__ == "__main__":
    unittest.main()
