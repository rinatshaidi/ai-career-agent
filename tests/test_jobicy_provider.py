from __future__ import annotations

import unittest
from datetime import datetime, timezone

import httpx

from models import RemoteType
from providers.base import OpportunityProvider
from providers.jobicy import JobicyFeedError, JobicyProvider, parse_jobicy_jobs


COLLECTED_AT = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
SAMPLE_JOB = {
    "id": 146001,
    "url": "https://jobicy.com/jobs/146001-automation-specialist",
    "jobTitle": "Automation Specialist",
    "companyName": "Example",
    "jobIndustry": ["Software Engineering", "Product & Operations"],
    "jobType": ["Full-Time"],
    "jobGeo": "Europe, EMEA",
    "jobLevel": "Midweight",
    "jobDescription": "<p>Build <strong>AI workflows</strong> and API integrations.</p>",
    "pubDate": "2026-07-20T09:30:00+00:00",
    "salaryMin": 50000,
    "salaryMax": 70000,
    "salaryCurrency": "EUR",
    "salaryPeriod": "yearly",
}


def make_payload(*jobs: dict, tag: str = "automation") -> dict:
    return {
        "apiVersion": "2.2.14",
        "jobCount": len(jobs),
        "appliedFilters": {"count": 20, "tag": tag},
        "jobs": list(jobs),
    }


class JobicyParserTests(unittest.TestCase):
    def test_normalizes_official_response(self) -> None:
        opportunity = parse_jobicy_jobs(
            make_payload(SAMPLE_JOB),
            collected_at=COLLECTED_AT,
        )[0]

        self.assertEqual(opportunity.source, "jobicy")
        self.assertEqual(opportunity.external_id, "146001")
        self.assertEqual(opportunity.title, "Automation Specialist")
        self.assertEqual(opportunity.company_name, "Example")
        self.assertEqual(opportunity.location, "Europe, EMEA")
        self.assertEqual(opportunity.remote_type, RemoteType.REMOTE)
        self.assertEqual(opportunity.salary_from, 50000)
        self.assertEqual(opportunity.salary_to, 70000)
        self.assertEqual(opportunity.currency, "EUR")
        self.assertEqual(opportunity.published_at.isoformat(), "2026-07-20T09:30:00+00:00")
        self.assertEqual(opportunity.collected_at, COLLECTED_AT)
        self.assertIn("Build AI workflows and API integrations.", opportunity.description)
        self.assertIn("Industries: Software Engineering, Product & Operations", opportunity.description)
        self.assertIn("Job types: Full-Time", opportunity.description)
        self.assertIn("Level: Midweight", opportunity.description)
        self.assertIn("Salary period: yearly", opportunity.description)
        self.assertNotIn("<strong>", opportunity.description)

    def test_ignores_nonpositive_salary_and_currency(self) -> None:
        job = {
            **SAMPLE_JOB,
            "salaryMin": 0,
            "salaryMax": None,
            "salaryCurrency": "USD",
        }
        opportunity = parse_jobicy_jobs(make_payload(job))[0]
        self.assertIsNone(opportunity.salary_from)
        self.assertIsNone(opportunity.salary_to)
        self.assertIsNone(opportunity.currency)

    def test_accepts_string_values_for_list_fields(self) -> None:
        job = {**SAMPLE_JOB, "jobIndustry": "Automation", "jobType": "Contract"}
        opportunity = parse_jobicy_jobs(make_payload(job))[0]
        self.assertIn("Industries: Automation", opportunity.description)
        self.assertIn("Job types: Contract", opportunity.description)

    def test_rejects_malformed_response_and_invalid_values(self) -> None:
        with self.assertRaisesRegex(JobicyFeedError, "jobs array"):
            parse_jobicy_jobs({"jobs": {}})
        with self.assertRaisesRegex(JobicyFeedError, "missing title or URL"):
            parse_jobicy_jobs(make_payload({**SAMPLE_JOB, "jobTitle": ""}))
        with self.assertRaisesRegex(JobicyFeedError, "publication date"):
            parse_jobicy_jobs(make_payload({**SAMPLE_JOB, "pubDate": "invalid"}))
        with self.assertRaisesRegex(JobicyFeedError, "salary value"):
            parse_jobicy_jobs(make_payload({**SAMPLE_JOB, "salaryMin": "invalid"}))
        with self.assertRaisesRegex(JobicyFeedError, "currency"):
            parse_jobicy_jobs(make_payload({**SAMPLE_JOB, "salaryCurrency": ""}))
        with self.assertRaisesRegex(ValueError, "limit"):
            parse_jobicy_jobs(make_payload(SAMPLE_JOB), limit=0)
        with self.assertRaisesRegex(ValueError, "timezone"):
            parse_jobicy_jobs(
                make_payload(SAMPLE_JOB),
                collected_at=datetime(2026, 7, 20, 12, 0),
            )

    def test_skips_entries_without_id_and_honors_limit(self) -> None:
        second = {**SAMPLE_JOB, "id": 146002}
        opportunities = parse_jobicy_jobs(
            make_payload({**SAMPLE_JOB, "id": None}, SAMPLE_JOB, second),
            limit=1,
        )
        self.assertEqual([item.external_id for item in opportunities], ["146001"])


class JobicyHttpTests(unittest.TestCase):
    def test_fetches_one_filtered_request(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            self.assertEqual(request.headers["User-Agent"], "JobMonitor/Test")
            self.assertEqual(request.headers["Accept"], "application/json")
            self.assertEqual(request.url.params["count"], "20")
            self.assertEqual(request.url.params["tag"], "automation")
            return httpx.Response(200, json=make_payload(SAMPLE_JOB), request=request)

        provider = JobicyProvider(
            api_url="https://jobicy.com/api/v2/remote-jobs",
            user_agent="JobMonitor/Test",
            tag="automation",
            limit=20,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )

        opportunities = provider.fetch()

        self.assertIsInstance(provider, OpportunityProvider)
        self.assertEqual(provider.retry_attempts, 1)
        self.assertEqual(len(requests), 1)
        self.assertEqual([item.external_id for item in opportunities], ["146001"])

    def test_rejects_response_when_filter_is_not_confirmed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = make_payload(SAMPLE_JOB)
            payload["appliedFilters"] = {"count": 20}
            return httpx.Response(200, json=payload, request=request)

        provider = JobicyProvider(
            api_url="https://jobicy.com/api/v2/remote-jobs",
            user_agent="JobMonitor/Test",
            tag="automation",
            limit=20,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaisesRegex(JobicyFeedError, "requested tag filter"):
            provider.fetch()

    def test_wraps_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, request=request)

        provider = JobicyProvider(
            api_url="https://jobicy.com/api/v2/remote-jobs",
            user_agent="JobMonitor/Test",
            tag="automation",
            limit=20,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaisesRegex(Exception, "HTTP 429"):
            provider.fetch()


if __name__ == "__main__":
    unittest.main()
