from __future__ import annotations

import unittest
from datetime import datetime, timezone

from models import Opportunity, RemoteType


def make_opportunity(**overrides: object) -> Opportunity:
    values: dict[str, object] = {
        "source": "test",
        "external_id": "42",
        "title": "Automation task",
        "description": "Build an automation.",
        "url": "https://example.com/opportunities/42",
        "remote_type": RemoteType.REMOTE,
        "collected_at": datetime(2026, 7, 17, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return Opportunity(**values)  # type: ignore[arg-type]


class OpportunityTests(unittest.TestCase):
    def test_trims_and_serializes_values(self) -> None:
        opportunity = make_opportunity(
            source=" test ",
            title=" Automation task ",
            currency=" rub ",
            salary_from=5_000,
        )
        self.assertEqual(opportunity.source, "test")
        self.assertEqual(opportunity.title, "Automation task")
        self.assertEqual(opportunity.currency, "RUB")
        self.assertEqual(opportunity.to_dict()["remote_type"], "remote")

    def test_rejects_invalid_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute"):
            make_opportunity(url="/opportunities/42")

    def test_rejects_inverted_salary_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "greater"):
            make_opportunity(salary_from=20_000, salary_to=10_000, currency="RUB")

    def test_requires_currency_for_salary(self) -> None:
        with self.assertRaisesRegex(ValueError, "currency"):
            make_opportunity(salary_from=5_000)

    def test_requires_timezone_aware_dates(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone"):
            make_opportunity(collected_at=datetime(2026, 7, 17))


if __name__ == "__main__":
    unittest.main()
