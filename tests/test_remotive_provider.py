from __future__ import annotations

import unittest
from datetime import datetime, timezone

import httpx

from models import RemoteType
from providers.base import OpportunityProvider
from providers.remotive import (
    RemotiveError,
    RemotiveFeedError,
    RemotiveProvider,
    parse_remotive_jobs,
)


COLLECTED_AT = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
SAMPLE_PAYLOAD = {
    "0-legal-notice": "Remotive API Legal Notice",
    "job-count": 2,
    "jobs": [
        {
            "id": 501,
            "url": "https://remotive.com/remote-jobs/software-dev/ai-automation-501",
            "title": "AI Automation Specialist",
            "company_name": "Automation Co",
            "category": "Software Development",
            "job_type": "contract",
            "publication_date": "2026-07-19T10:30:00",
            "candidate_required_location": "Worldwide",
            "salary": "$40,000 - $50,000",
            "description": "<p>Build <strong>business workflows</strong>.</p>",
        },
        {
            "id": 502,
            "url": "https://remotive.com/remote-jobs/project-management/automation-pm-502",
            "title": "Automation Project Manager",
            "company_name": "Project Co",
            "category": "Project Management",
            "job_type": "full_time",
            "publication_date": "2026-07-19T11:30:00Z",
            "candidate_required_location": "Europe",
            "salary": "",
            "description": "Coordinate automation projects.",
        },
    ],
}


class RemotiveParserTests(unittest.TestCase):
    def test_normalizes_official_json_response(self) -> None:
        opportunities = parse_remotive_jobs(SAMPLE_PAYLOAD, collected_at=COLLECTED_AT)

        self.assertEqual(len(opportunities), 2)
        first = opportunities[0]
        self.assertEqual(first.source, "remotive")
        self.assertEqual(first.external_id, "501")
        self.assertEqual(first.title, "AI Automation Specialist")
        self.assertEqual(first.company_name, "Automation Co")
        self.assertEqual(first.location, "Worldwide")
        self.assertEqual(first.remote_type, RemoteType.REMOTE)
        self.assertEqual(first.url, SAMPLE_PAYLOAD["jobs"][0]["url"])
        self.assertIn("Build business workflows.", first.description)
        self.assertIn("Category: Software Development", first.description)
        self.assertIn("Job type: contract", first.description)
        self.assertIn("Salary: $40,000 - $50,000", first.description)
        self.assertIsNone(first.salary_from)
        self.assertIsNone(first.salary_to)
        self.assertEqual(first.published_at.tzinfo, timezone.utc)
        self.assertEqual(first.collected_at, COLLECTED_AT)

    def test_respects_limit(self) -> None:
        opportunities = parse_remotive_jobs(SAMPLE_PAYLOAD, limit=1)
        self.assertEqual([item.external_id for item in opportunities], ["501"])

    def test_rejects_response_without_jobs_array(self) -> None:
        with self.assertRaisesRegex(RemotiveFeedError, "jobs array"):
            parse_remotive_jobs({"job-count": 0})

    def test_rejects_job_without_title(self) -> None:
        payload = {
            "jobs": [
                {
                    "id": 1,
                    "url": "https://remotive.com/remote-jobs/1",
                }
            ]
        }
        with self.assertRaisesRegex(RemotiveFeedError, "title or URL"):
            parse_remotive_jobs(payload)


class RemotiveHttpTests(unittest.TestCase):
    def test_implements_contract_and_fetches_once_with_limit(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            self.assertEqual(request.headers["User-Agent"], "JobMonitor/Test")
            self.assertEqual(request.headers["Accept"], "application/json")
            self.assertEqual(request.url.params["limit"], "100")
            return httpx.Response(200, json=SAMPLE_PAYLOAD, request=request)

        provider = RemotiveProvider(
            api_url="https://remotive.com/api/remote-jobs",
            user_agent="JobMonitor/Test",
            limit=100,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )

        self.assertIsInstance(provider, OpportunityProvider)
        self.assertEqual(provider.retry_attempts, 1)
        self.assertEqual(len(provider.fetch()), 2)
        self.assertEqual(len(requests), 1)

    def test_converts_http_status_to_provider_error(self) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(429, request=request)

        provider = RemotiveProvider(
            api_url="https://remotive.com/api/remote-jobs",
            user_agent="JobMonitor/Test",
            limit=100,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(RemotiveError, "HTTP 429"):
            provider.fetch()
        self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()
