from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

import httpx

from models import CandidateProfile, Opportunity, RemoteType, SearchTrack
from services import OpenAIAnalyzer, OpenAIAnalyzerError


ANALYSIS_DATA = {
    "suitable": True,
    "score": 91,
    "summary": "Задача соответствует профилю.",
    "estimated_effort": "1-2 дня",
    "difficulty": "low",
    "risks": [],
    "action_plan": ["Уточнить доступы.", "Собрать workflow."],
    "application_draft": "Могу выполнить эту автоматизацию.",
    "missing_information": ["Срок выполнения."],
    "recommendation": "priority",
    "primary_track_id": "automation",
    "primary_track_name": "AI-автоматизация",
    "match_reasons": ["Совпадают задачи автоматизации и интеграции."],
    "required_actions": ["Приложить примеры проектов."],
    "employment_type": "проектная работа",
    "track_assessments": [
        {
            "track_id": "automation",
            "track_name": "AI-автоматизация",
            "score": 91,
            "reason": "Совпадают задачи и инструменты.",
        }
    ],
}


def make_opportunity() -> Opportunity:
    return Opportunity(
        source="test",
        external_id="42",
        title="Build an automation",
        description="Connect a form to Telegram.",
        url="https://example.com/42",
        remote_type=RemoteType.REMOTE,
        collected_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
    )


def make_profile() -> CandidateProfile:
    return CandidateProfile(
        positioning="AI automation specialist",
        skills=("workflow automation", "Telegram bots"),
        preferred_tasks=("build integrations",),
        avoid_tasks=("cold sales",),
        preferences=("remote",),
    )


class OpenAIAnalyzerTests(unittest.TestCase):
    def test_sends_responses_api_structured_output_request(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/v1/responses")
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            payload = json.loads(request.content)
            self.assertFalse(payload["store"])
            self.assertEqual(payload["model"], "test-model")
            self.assertEqual(payload["text"]["format"]["type"], "json_schema")
            self.assertTrue(payload["text"]["format"]["strict"])
            self.assertEqual(payload["reasoning"], {"effort": "low"})
            user_data = json.loads(payload["input"][1]["content"])
            self.assertEqual(user_data["opportunity"]["external_id"], "42")
            self.assertEqual(user_data["candidate_profile"]["skills"][0], "workflow automation")
            return httpx.Response(
                200,
                json={
                    "usage": {"input_tokens": 120, "output_tokens": 45, "total_tokens": 165},
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": json.dumps(ANALYSIS_DATA)}
                            ],
                        }
                    ]
                },
                request=request,
            )

        analyzer = OpenAIAnalyzer(
            api_key="test-key",
            model="test-model",
            transport=httpx.MockTransport(handler),
        )
        analysis = analyzer.analyze(make_opportunity(), make_profile())
        self.assertEqual(analysis.score, 91)
        self.assertEqual(analysis.recommendation.value, "priority")
        self.assertEqual(analysis.input_tokens, 120)
        self.assertEqual(analysis.output_tokens, 45)
        self.assertEqual(analysis.total_tokens, 165)
        self.assertEqual(analysis.primary_track_name, "AI-автоматизация")

    def test_converts_api_error_without_exposing_key(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429,
                json={"error": {"message": "Rate limit reached"}},
                request=request,
            )

        analyzer = OpenAIAnalyzer(
            api_key="secret-test-key",
            model="test-model",
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(OpenAIAnalyzerError, "Rate limit reached") as context:
            analyzer.analyze(make_opportunity(), make_profile())
        self.assertNotIn("secret-test-key", str(context.exception))

    def test_sends_user_search_tracks_without_losing_legacy_profile_fields(self) -> None:
        profile = CandidateProfile(
            positioning="AI Automation / Infrastructure & Business Projects",
            skills=("n8n", "project development"),
            preferred_tasks=("automation", "partnerships"),
            avoid_tasks=(),
            preferences=("worldwide",),
            search_tracks=(
                SearchTrack(
                    track_id="automation",
                    name="Automation",
                    target_description="AI automation work",
                    roles_and_signals=("business automation",),
                    skills_and_experience=("n8n",),
                    tasks_and_outcomes=(),
                    locations=("Remote",),
                ),
                SearchTrack(
                    track_id="infrastructure",
                    name="Infrastructure",
                    target_description="Infrastructure projects",
                    roles_and_signals=("infrastructure",),
                    skills_and_experience=("project development",),
                    tasks_and_outcomes=(),
                    locations=("Worldwide",),
                ),
            ),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            user_data = json.loads(payload["input"][1]["content"])
            tracks = user_data["candidate_profile"]["search_tracks"]
            self.assertEqual(len(tracks), 2)
            self.assertEqual(tracks[0]["name"], "Automation")
            self.assertIn("n8n", user_data["candidate_profile"]["skills"])
            return httpx.Response(
                200,
                json={
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": json.dumps(ANALYSIS_DATA)}
                            ],
                        }
                    ]
                },
                request=request,
            )

        analyzer = OpenAIAnalyzer(
            api_key="test-key",
            model="test-model",
            transport=httpx.MockTransport(handler),
        )
        analyzer.analyze(make_opportunity(), profile)

    def test_reports_model_refusal(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "refusal", "refusal": "Cannot comply"}],
                        }
                    ]
                },
                request=request,
            )

        analyzer = OpenAIAnalyzer(
            api_key="test-key",
            model="test-model",
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(OpenAIAnalyzerError, "refused"):
            analyzer.analyze(make_opportunity(), make_profile())

    def test_reports_incomplete_response_reason(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "incomplete",
                    "incomplete_details": {"reason": "max_output_tokens"},
                    "output": [],
                },
                request=request,
            )

        analyzer = OpenAIAnalyzer(
            api_key="test-key",
            model="test-model",
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(OpenAIAnalyzerError, "max_output_tokens"):
            analyzer.analyze(make_opportunity(), make_profile())


if __name__ == "__main__":
    unittest.main()
