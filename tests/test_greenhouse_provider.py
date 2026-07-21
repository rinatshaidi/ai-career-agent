from __future__ import annotations

import unittest
from datetime import datetime, timezone

import httpx

from models import RemoteType
from providers.base import OpportunityProvider
from providers.greenhouse import (
    GreenhouseBoard,
    GreenhouseError,
    GreenhouseFeedError,
    GreenhouseProvider,
    parse_greenhouse_boards,
    parse_greenhouse_jobs,
)


BOARD = GreenhouseBoard(token="automationco", company_name="Automation Co")
COLLECTED_AT = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
SAMPLE_PAYLOAD = {
    "jobs": [
        {
            "id": 12345,
            "title": "AI Implementation Specialist",
            "updated_at": "2026-07-20T08:30:00-04:00",
            "location": {"name": "Remote"},
            "absolute_url": "https://job-boards.greenhouse.io/automationco/jobs/12345",
            "language": "en",
            "content": "<p>Build <strong>AI workflow automations</strong>.</p>",
            "departments": [{"id": 1, "name": "Professional Services"}],
            "offices": [{"id": 2, "name": "Remote - Worldwide"}],
        },
        {
            "id": 12346,
            "title": "Project Coordinator",
            "updated_at": "2026-07-20T13:00:00Z",
            "location": {"name": "Berlin - Hybrid"},
            "absolute_url": "https://job-boards.greenhouse.io/automationco/jobs/12346",
            "content": "Coordinate delivery projects.",
            "departments": [],
            "offices": [],
        },
    ],
    "meta": {"total": 2},
}


class GreenhouseBoardConfigTests(unittest.TestCase):
    def test_parses_multiple_named_boards(self) -> None:
        boards = parse_greenhouse_boards("karbon|Karbon;kalepa|Kalepa")
        self.assertEqual(
            boards,
            (
                GreenhouseBoard("karbon", "Karbon"),
                GreenhouseBoard("kalepa", "Kalepa"),
            ),
        )

    def test_rejects_duplicate_or_malformed_board(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            parse_greenhouse_boards("karbon|Karbon;karbon|Other")
        with self.assertRaisesRegex(ValueError, r"token\|Company Name"):
            parse_greenhouse_boards("karbon")


class GreenhouseParserTests(unittest.TestCase):
    def test_normalizes_public_job_board_response(self) -> None:
        opportunities = parse_greenhouse_jobs(
            SAMPLE_PAYLOAD,
            board=BOARD,
            collected_at=COLLECTED_AT,
        )

        self.assertEqual(len(opportunities), 2)
        first = opportunities[0]
        self.assertEqual(first.source, "greenhouse_automationco")
        self.assertEqual(first.external_id, "12345")
        self.assertEqual(first.company_name, "Automation Co")
        self.assertEqual(first.location, "Remote")
        self.assertEqual(first.remote_type, RemoteType.REMOTE)
        self.assertIn("Build AI workflow automations.", first.description)
        self.assertIn("Departments: Professional Services", first.description)
        self.assertIn("Offices: Remote - Worldwide", first.description)
        self.assertIn("Language: en", first.description)
        self.assertEqual(first.collected_at, COLLECTED_AT)
        self.assertIsNotNone(first.published_at)
        self.assertEqual(opportunities[1].remote_type, RemoteType.HYBRID)

    def test_respects_limit(self) -> None:
        opportunities = parse_greenhouse_jobs(SAMPLE_PAYLOAD, board=BOARD, limit=1)
        self.assertEqual([item.external_id for item in opportunities], ["12345"])

    def test_rejects_response_without_jobs_array(self) -> None:
        with self.assertRaisesRegex(GreenhouseFeedError, "jobs array"):
            parse_greenhouse_jobs({"meta": {"total": 0}}, board=BOARD)

    def test_rejects_job_without_absolute_url(self) -> None:
        payload = {"jobs": [{"id": 1, "title": "Missing URL"}]}
        with self.assertRaisesRegex(GreenhouseFeedError, "absolute_url"):
            parse_greenhouse_jobs(payload, board=BOARD)


class GreenhouseHttpTests(unittest.TestCase):
    def test_implements_contract_and_requests_full_content(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(
                str(request.url.copy_with(query=None)),
                "https://boards-api.greenhouse.io/v1/boards/automationco/jobs",
            )
            self.assertEqual(request.url.params["content"], "true")
            self.assertEqual(request.headers["User-Agent"], "JobMonitor/Test")
            return httpx.Response(200, json=SAMPLE_PAYLOAD, request=request)

        provider = GreenhouseProvider(
            api_base_url="https://boards-api.greenhouse.io/v1/boards",
            board=BOARD,
            user_agent="JobMonitor/Test",
            limit=50,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )

        self.assertIsInstance(provider, OpportunityProvider)
        self.assertEqual(provider.source, "greenhouse_automationco")
        self.assertEqual(len(provider.fetch()), 2)

    def test_converts_board_http_status_to_provider_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, request=request)

        provider = GreenhouseProvider(
            api_base_url="https://boards-api.greenhouse.io/v1/boards",
            board=BOARD,
            user_agent="JobMonitor/Test",
            limit=50,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(GreenhouseError, "automationco returned HTTP 404"):
            provider.fetch()


if __name__ == "__main__":
    unittest.main()
