from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from models import AIAnalysis, Difficulty, Opportunity, RemoteType
from services import NotificationRunner, TelegramAPIError, format_notification
from storage import OpportunityRepository, OpportunityStatus
from utils import RetryPolicy


class FakeTelegramClient:
    def __init__(self, *, error: str | None = None) -> None:
        self.error = error
        self.messages: list[tuple[str | int, str, object]] = []

    def send_message(self, chat_id, text, *, reply_markup=None) -> None:
        if self.error:
            raise TelegramAPIError(self.error)
        self.messages.append((chat_id, text, reply_markup))


def make_opportunity(external_id: str = "notification-1") -> Opportunity:
    return Opportunity(
        source="test",
        external_id=external_id,
        title="AI automation specialist",
        description="Build an n8n workflow and Telegram integration.",
        url=f"https://example.com/{external_id}",
        company_name="Example",
        location="Remote",
        remote_type=RemoteType.REMOTE,
        salary_from=100_000,
        salary_to=150_000,
        currency="RUB",
        collected_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
    )


def make_analysis(*, score: int = 85, suitable: bool = True) -> AIAnalysis:
    return AIAnalysis(
        suitable=suitable,
        score=score,
        summary="Задача соответствует профилю.",
        estimated_effort="2–3 дня",
        difficulty=Difficulty.MEDIUM,
        risks=("Нужно уточнить доступы.",),
        action_plan=("Уточнить требования.", "Подготовить workflow."),
        application_draft="Готов обсудить автоматизацию и предложить решение.",
        missing_information=(),
    )


class NotificationRunnerTests(unittest.TestCase):
    test_data_root = Path(__file__).resolve().parents[1] / "data"

    def setUp(self) -> None:
        self.test_data_root.mkdir(exist_ok=True)
        self.database_path = self.test_data_root / f"test-{uuid4().hex}.db"
        self.repository = OpportunityRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        for suffix in ("", "-shm", "-wal"):
            path = Path(f"{self.database_path}{suffix}")
            if path.exists():
                path.unlink()

    def save_analyzed(self, *, score: int = 85) -> int:
        self.repository.add_many([make_opportunity()])
        stored = self.repository.claim_for_analysis(limit=1)[0]
        self.repository.save_analysis(stored.id, make_analysis(score=score), model="test-model")
        return stored.id

    def test_sends_once_and_marks_opportunity_notified(self) -> None:
        opportunity_id = self.save_analyzed()
        client = FakeTelegramClient()
        runner = NotificationRunner(self.repository, client, "123")

        first = runner.run(minimum_score=70, batch_size=10)
        second = runner.run(minimum_score=70, batch_size=10)

        self.assertEqual((first.claimed, first.sent, first.failed), (1, 1, 0))
        self.assertEqual((second.claimed, second.sent, second.failed), (0, 0, 0))
        self.assertEqual(len(client.messages), 1)
        self.assertIn("Совпадение: 85%", client.messages[0][1])
        self.assertEqual(
            client.messages[0][2]["inline_keyboard"][0][0]["url"],
            "https://example.com/notification-1",
        )
        self.assertEqual(
            self.repository.get_opportunity(opportunity_id).status,
            OpportunityStatus.NOTIFIED,
        )

    def test_failed_delivery_can_be_retried(self) -> None:
        opportunity_id = self.save_analyzed()
        failed = NotificationRunner(
            self.repository,
            FakeTelegramClient(error="temporary failure"),
            "123",
            retry_policy=RetryPolicy(attempts=1, delay_seconds=0),
        ).run(minimum_score=70, batch_size=10)

        retried_client = FakeTelegramClient()
        retried = NotificationRunner(
            self.repository,
            retried_client,
            "123",
        ).run(minimum_score=70, batch_size=10)

        self.assertEqual((failed.claimed, failed.sent, failed.failed), (1, 0, 1))
        self.assertEqual((retried.claimed, retried.sent, retried.failed), (1, 1, 0))
        self.assertEqual(
            self.repository.get_opportunity(opportunity_id).status,
            OpportunityStatus.NOTIFIED,
        )

    def test_does_not_claim_analysis_below_threshold(self) -> None:
        self.save_analyzed(score=69)
        result = NotificationRunner(
            self.repository,
            FakeTelegramClient(),
            "123",
        ).run(minimum_score=70, batch_size=10)
        self.assertEqual((result.claimed, result.sent, result.failed), (0, 0, 0))

    def test_formatted_message_stays_within_telegram_limit(self) -> None:
        opportunity_id = self.save_analyzed()
        candidate = self.repository.claim_for_notification(minimum_score=70, limit=1)[0]
        message = format_notification(candidate)
        self.assertLessEqual(len(message), 4096)
        self.assertIn("AI automation specialist", message)
        self.repository.mark_notification_failed(opportunity_id, "test cleanup")


if __name__ == "__main__":
    unittest.main()
