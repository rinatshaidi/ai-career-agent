from __future__ import annotations

import unittest
from datetime import datetime, timezone

import httpx

from models import RemoteType
from providers.base import OpportunityProvider
from providers.trudvsem import (
    TrudvsemFeedError,
    TrudvsemProvider,
    parse_region_codes,
    parse_search_queries,
    parse_trudvsem_jobs,
)


COLLECTED_AT = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
SAMPLE_VACANCY = {
    "id": "vacancy-501",
    "job-name": "Специалист по автоматизации бизнеса",
    "vac_url": "https://trudvsem.ru/vacancy/card/501",
    "duty": "Проектировать процессы и интеграции.",
    "requirements": "Опыт с API и Telegram-ботами.",
    "qualification": "Уверенная работа с no-code инструментами.",
    "schedule": "Гибкий график, дистанционная работа",
    "skills": [{"skill_name": "API"}, {"skill_name": "Автоматизация"}],
    "company": {
        "name": "Компания",
        "email": "private@example.test",
    },
    "region": {"region_code": "77", "name": "г. Москва"},
    "addresses": {"address": [{"location": "Москва, ул. Примерная"}]},
    "salary_min": "80000",
    "salary_max": 120000,
    "currency": "«руб.»",
    "date_modify": "2026-07-19T10:30:00+0300",
    "contact_person": "Не сохранять",
    "contact_list": [{"contact_type": "Телефон", "contact_value": "+70000000000"}],
}


def make_payload(*vacancies: dict) -> dict:
    return {
        "status": "200",
        "meta": {"total": len(vacancies), "limit": 10},
        "results": {"vacancies": [{"vacancy": vacancy} for vacancy in vacancies]},
    }


class TrudvsemParserTests(unittest.TestCase):
    def test_normalizes_official_response_without_contact_data(self) -> None:
        opportunities = parse_trudvsem_jobs(
            make_payload(SAMPLE_VACANCY),
            collected_at=COLLECTED_AT,
        )

        self.assertEqual(len(opportunities), 1)
        opportunity = opportunities[0]
        self.assertEqual(opportunity.source, "rabota_rossii")
        self.assertEqual(opportunity.external_id, "vacancy-501")
        self.assertEqual(opportunity.title, "Специалист по автоматизации бизнеса")
        self.assertEqual(opportunity.company_name, "Компания")
        self.assertEqual(opportunity.remote_type, RemoteType.REMOTE)
        self.assertEqual(opportunity.salary_from, 80000)
        self.assertEqual(opportunity.salary_to, 120000)
        self.assertEqual(opportunity.currency, "RUB")
        self.assertEqual(opportunity.published_at.isoformat(), "2026-07-19T10:30:00+03:00")
        self.assertIn("г. Москва", opportunity.location)
        self.assertIn("Москва, ул. Примерная", opportunity.location)
        self.assertIn("Обязанности:", opportunity.description)
        self.assertIn("Навыки: API, Автоматизация", opportunity.description)
        self.assertNotIn("private@example.test", opportunity.description)
        self.assertNotIn("+70000000000", opportunity.description)
        self.assertNotIn("Не сохранять", opportunity.description)

    def test_distinguishes_hybrid_onsite_and_unknown(self) -> None:
        hybrid = {
            **SAMPLE_VACANCY,
            "id": "hybrid",
            "schedule": "Гибридный формат работы",
        }
        onsite = {
            **SAMPLE_VACANCY,
            "id": "onsite",
            "schedule": "Полный рабочий день",
        }
        unknown = {
            **SAMPLE_VACANCY,
            "id": "unknown",
            "schedule": "Полный рабочий день",
            "region": {},
            "addresses": {},
        }

        opportunities = parse_trudvsem_jobs(make_payload(hybrid, onsite, unknown))

        self.assertEqual(opportunities[0].remote_type, RemoteType.HYBRID)
        self.assertEqual(opportunities[1].remote_type, RemoteType.ONSITE)
        self.assertEqual(opportunities[2].remote_type, RemoteType.UNKNOWN)

    def test_does_not_treat_unrelated_word_with_remote_stem_as_remote(self) -> None:
        vacancy = {
            **SAMPLE_VACANCY,
            "id": "not-remote",
            "duty": "Контроль удаленной строительной площадки.",
            "schedule": "Полный рабочий день",
        }
        opportunity = parse_trudvsem_jobs(make_payload(vacancy))[0]
        self.assertEqual(opportunity.remote_type, RemoteType.ONSITE)

    def test_rejects_unsuccessful_or_malformed_response(self) -> None:
        with self.assertRaisesRegex(TrudvsemFeedError, "unsuccessful status"):
            parse_trudvsem_jobs({"status": "500", "results": {"vacancies": []}})
        with self.assertRaisesRegex(TrudvsemFeedError, "results object"):
            parse_trudvsem_jobs({"status": "200", "results": []})
        with self.assertRaisesRegex(TrudvsemFeedError, "must be an array"):
            parse_trudvsem_jobs({"status": "200", "results": {"vacancies": {}}})

    def test_accepts_official_empty_results_object(self) -> None:
        payload = {"status": "200", "meta": {"total": 0}, "results": {}}
        self.assertEqual(parse_trudvsem_jobs(payload), [])

    def test_parses_configuration_lists(self) -> None:
        self.assertEqual(
            parse_search_queries("n8n; Telegram бот ;n8n"),
            ("n8n", "Telegram бот"),
        )
        self.assertEqual(parse_region_codes("77, 78,77"), ("77", "78"))
        with self.assertRaisesRegex(ValueError, "numeric codes"):
            parse_region_codes("77,moscow")


class TrudvsemHttpTests(unittest.TestCase):
    def test_fetches_incrementally_and_deduplicates_queries(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            self.assertEqual(request.headers["User-Agent"], "JobMonitor/Test")
            self.assertEqual(request.headers["Accept"], "application/json")
            self.assertEqual(request.url.params["limit"], "10")
            self.assertEqual(request.url.params["offset"], "1")
            self.assertEqual(
                request.url.params["modifiedFrom"],
                "2026-07-20T09:55:00+00:00",
            )
            return httpx.Response(200, json=make_payload(SAMPLE_VACANCY), request=request)

        provider = TrudvsemProvider(
            api_url="https://opendata.trudvsem.ru/api/v1/vacancies",
            user_agent="JobMonitor/Test",
            search_queries=("автоматизация", "n8n"),
            region_codes=(),
            per_query_limit=10,
            limit=20,
            initial_lookback_days=14,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
        )

        opportunities = provider.fetch_since(
            datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
        )

        self.assertIsInstance(provider, OpportunityProvider)
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(opportunities), 1)

    def test_uses_region_endpoint_and_initial_lookback(self) -> None:
        request_seen: httpx.Request | None = None

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_seen
            request_seen = request
            return httpx.Response(200, json=make_payload(), request=request)

        provider = TrudvsemProvider(
            api_url="https://opendata.trudvsem.ru/api/v1/vacancies",
            user_agent="JobMonitor/Test",
            search_queries=("OpenAI",),
            region_codes=("77",),
            per_query_limit=10,
            limit=20,
            initial_lookback_days=14,
            timeout_seconds=5,
            transport=httpx.MockTransport(handler),
            now=lambda: datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(provider.fetch(), [])
        self.assertIsNotNone(request_seen)
        self.assertTrue(str(request_seen.url).startswith(
            "https://opendata.trudvsem.ru/api/v1/vacancies/region/77?"
        ))
        self.assertEqual(
            request_seen.url.params["modifiedFrom"],
            "2026-07-06T12:00:00+00:00",
        )


if __name__ == "__main__":
    unittest.main()
