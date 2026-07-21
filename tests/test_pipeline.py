from __future__ import annotations

import unittest
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from models import CandidateProfile
from providers.base import ProviderError
from services import JobMonitorPipeline
from storage import OpportunityRepository, OpportunityStatus
from tests.test_repository import make_analysis, make_opportunity
from utils import RetryPolicy


class SuccessfulProvider:
    source = "successful"

    def __init__(self) -> None:
        self.calls = 0

    def fetch(self):
        self.calls += 1
        return [make_opportunity("pipeline")]


class FailingProvider:
    source = "failing"

    def __init__(self) -> None:
        self.calls = 0

    def fetch(self):
        self.calls += 1
        raise ProviderError("source unavailable")


class NonRetryingProvider(FailingProvider):
    source = "non_retrying"
    retry_attempts = 1


class BulkProvider:
    source = "bulk"

    def __init__(self, count: int) -> None:
        self.count = count
        self.calls = 0

    def fetch(self):
        self.calls += 1
        return [make_opportunity(f"bulk-{index}") for index in range(self.count)]


class IncrementalProvider:
    source = "incremental"

    def __init__(self) -> None:
        self.since_values: list[datetime | None] = []

    def fetch(self):
        raise AssertionError("Pipeline should prefer fetch_since when it is available.")

    def fetch_since(self, last_success_at):
        self.since_values.append(last_success_at)
        return []


class FakeAnalyzer:
    model = "test-model"

    def analyze(self, opportunity, profile):
        return make_analysis(suitable=True)


class FakeTelegramClient:
    def __init__(self) -> None:
        self.messages = []

    def send_message(self, chat_id, text, *, reply_markup=None) -> None:
        self.messages.append((chat_id, text, reply_markup))


class PipelineTests(unittest.TestCase):
    test_data_root = Path(__file__).resolve().parents[1] / "data"

    def setUp(self) -> None:
        self.test_data_root.mkdir(exist_ok=True)
        self.database_path = self.test_data_root / f"test-{uuid4().hex}.db"
        self.repository = OpportunityRepository(self.database_path)
        self.repository.initialize()
        self.repository.save_user_profile(
            "123",
            CandidateProfile(
                positioning="AI automation specialist",
                skills=("n8n", "Telegram bots"),
                preferred_tasks=("automation",),
                avoid_tasks=(),
                preferences=("remote",),
            ),
        )

    def tearDown(self) -> None:
        for suffix in ("", "-shm", "-wal"):
            path = Path(f"{self.database_path}{suffix}")
            if path.exists():
                path.unlink()

    def test_source_failure_does_not_stop_remaining_pipeline(self) -> None:
        failing = FailingProvider()
        telegram = FakeTelegramClient()
        pipeline = JobMonitorPipeline(
            repository=self.repository,
            providers=(failing, SuccessfulProvider()),
            analyzer=FakeAnalyzer(),
            telegram_client=telegram,
            chat_id="123",
            ai_batch_size=5,
            notification_batch_size=5,
            minimum_score=70,
            retry_policy=RetryPolicy(attempts=2, delay_seconds=0),
            sleep=lambda _seconds: None,
        )

        result = pipeline.run_cycle()

        self.assertEqual(failing.calls, 2)
        self.assertEqual(result.sources_failed, 1)
        self.assertEqual(result.sources_succeeded, 1)
        self.assertEqual(result.opportunities_saved, 1)
        self.assertEqual(result.analyses_suitable, 1)
        self.assertEqual(result.notifications_sent, 1)
        self.assertEqual(len(telegram.messages), 1)
        self.assertEqual(
            len(self.repository.get_by_status(OpportunityStatus.NOTIFIED)),
            1,
        )
        latest = self.repository.get_latest_system_run()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.status, "completed")
        self.assertEqual(latest.summary["sources_failed"], 1)

    def test_recovers_interrupted_run_before_next_cycle(self) -> None:
        interrupted_id = self.repository.start_system_run()
        pipeline = JobMonitorPipeline(
            repository=self.repository,
            providers=(),
            analyzer=FakeAnalyzer(),
            telegram_client=FakeTelegramClient(),
            chat_id="123",
            ai_batch_size=5,
            notification_batch_size=5,
            minimum_score=70,
            retry_policy=RetryPolicy(attempts=1, delay_seconds=0),
            sleep=lambda _seconds: None,
        )

        pipeline.run_cycle()

        with self.repository._connect() as connection:
            interrupted = connection.execute(
                "SELECT status, last_error FROM system_runs WHERE id = ?",
                (interrupted_id,),
            ).fetchone()
        self.assertEqual(interrupted["status"], "failed")
        self.assertIn("stopped", interrupted["last_error"])

    def test_recovers_and_reprocesses_interrupted_analysis_claim(self) -> None:
        self.repository.add_many([make_opportunity("interrupted-analysis")])
        self.assertEqual(len(self.repository.claim_for_analysis(limit=1)), 1)
        pipeline = JobMonitorPipeline(
            repository=self.repository,
            providers=(),
            analyzer=FakeAnalyzer(),
            telegram_client=FakeTelegramClient(),
            chat_id="123",
            ai_batch_size=5,
            notification_batch_size=5,
            minimum_score=70,
            retry_policy=RetryPolicy(attempts=1, delay_seconds=0),
            sleep=lambda _seconds: None,
        )

        result = pipeline.run_cycle()

        self.assertEqual(result.analyses_suitable, 1)
        self.assertEqual(result.notifications_sent, 1)
        self.assertEqual(
            len(self.repository.get_by_status(OpportunityStatus.NOTIFIED)),
            1,
        )

    def test_skips_provider_until_its_persistent_interval_expires(self) -> None:
        provider = SuccessfulProvider()
        pipeline = JobMonitorPipeline(
            repository=self.repository,
            providers=(provider,),
            analyzer=FakeAnalyzer(),
            telegram_client=FakeTelegramClient(),
            chat_id="123",
            ai_batch_size=5,
            notification_batch_size=5,
            minimum_score=70,
            retry_policy=RetryPolicy(attempts=1, delay_seconds=0),
            provider_intervals={"successful": 3600},
            sleep=lambda _seconds: None,
        )

        first = pipeline.run_cycle()
        second = pipeline.run_cycle()

        self.assertEqual(provider.calls, 1)
        self.assertEqual(first.sources_succeeded, 1)
        self.assertEqual(first.sources_skipped, 0)
        self.assertEqual(second.sources_succeeded, 0)
        self.assertEqual(second.sources_skipped, 1)
        state = self.repository.get_source_state("successful")
        self.assertIsNotNone(state)
        self.assertEqual(state.last_status, "completed")

    def test_provider_can_disable_fast_retries(self) -> None:
        provider = NonRetryingProvider()
        pipeline = JobMonitorPipeline(
            repository=self.repository,
            providers=(provider,),
            analyzer=FakeAnalyzer(),
            telegram_client=FakeTelegramClient(),
            chat_id="123",
            ai_batch_size=5,
            notification_batch_size=5,
            minimum_score=70,
            retry_policy=RetryPolicy(attempts=3, delay_seconds=0),
            provider_intervals={"non_retrying": 21_600},
            sleep=lambda _seconds: None,
        )

        first = pipeline.run_cycle()
        second = pipeline.run_cycle()

        self.assertEqual(provider.calls, 1)
        self.assertEqual(first.sources_failed, 1)
        self.assertEqual(second.sources_skipped, 1)

    def test_initial_source_import_is_limited(self) -> None:
        provider = BulkProvider(5)
        pipeline = JobMonitorPipeline(
            repository=self.repository,
            providers=(provider,),
            analyzer=FakeAnalyzer(),
            telegram_client=FakeTelegramClient(),
            chat_id="123",
            ai_batch_size=5,
            notification_batch_size=5,
            minimum_score=70,
            retry_policy=RetryPolicy(attempts=1, delay_seconds=0),
            max_pending_ai_queue=50,
            initial_source_import_limit=2,
            sleep=lambda _seconds: None,
        )

        result = pipeline.run_cycle()

        self.assertEqual(provider.calls, 1)
        self.assertEqual(result.opportunities_received, 5)
        self.assertEqual(result.opportunities_saved, 2)
        self.assertEqual(result.opportunities_deferred, 3)
        state = self.repository.get_source_state("bulk")
        self.assertEqual(state.last_deferred, 3)

    def test_full_ai_queue_defers_provider_without_consuming_schedule(self) -> None:
        self.repository.add_many(
            [make_opportunity(f"queued-{index}") for index in range(3)]
        )
        provider = BulkProvider(2)
        pipeline = JobMonitorPipeline(
            repository=self.repository,
            providers=(provider,),
            analyzer=FakeAnalyzer(),
            telegram_client=FakeTelegramClient(),
            chat_id="123",
            ai_batch_size=1,
            notification_batch_size=1,
            minimum_score=70,
            retry_policy=RetryPolicy(attempts=1, delay_seconds=0),
            max_pending_ai_queue=3,
            initial_source_import_limit=2,
            sleep=lambda _seconds: None,
        )

        result = pipeline.run_cycle()

        self.assertEqual(provider.calls, 0)
        self.assertEqual(result.sources_queue_limited, 1)
        self.assertEqual(result.sources_skipped, 1)
        self.assertIsNone(self.repository.get_source_state("bulk"))
        self.assertEqual(self.repository.count_pending_analysis(), 2)

    def test_passes_last_success_time_to_incremental_provider(self) -> None:
        provider = IncrementalProvider()
        pipeline = JobMonitorPipeline(
            repository=self.repository,
            providers=(provider,),
            analyzer=FakeAnalyzer(),
            telegram_client=FakeTelegramClient(),
            chat_id="123",
            ai_batch_size=5,
            notification_batch_size=5,
            minimum_score=70,
            retry_policy=RetryPolicy(attempts=1, delay_seconds=0),
            sleep=lambda _seconds: None,
        )

        pipeline.run_cycle()
        first_state = self.repository.get_source_state("incremental")
        pipeline.run_cycle()

        self.assertEqual(provider.since_values[0], None)
        self.assertEqual(provider.since_values[1], first_state.last_success_at)


if __name__ == "__main__":
    unittest.main()
