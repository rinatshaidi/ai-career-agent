from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from models import AIAnalysis, CandidateProfile, Difficulty, Opportunity, RemoteType
from storage import OpportunityRepository, OpportunityStatus, StorageError


def make_opportunity(external_id: str = "42") -> Opportunity:
    return Opportunity(
        source="test_provider",
        external_id=external_id,
        title=f"Automation task {external_id}",
        description="Build a workflow.",
        url=f"https://example.com/opportunities/{external_id}",
        company_name="Example",
        location="Moscow",
        remote_type=RemoteType.REMOTE,
        salary_from=10_000,
        salary_to=15_000,
        currency="RUB",
        published_at=datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc),
        collected_at=datetime(2026, 7, 17, 13, 0, tzinfo=timezone.utc),
    )


def make_analysis(*, suitable: bool = True) -> AIAnalysis:
    return AIAnalysis(
        suitable=suitable,
        score=88 if suitable else 25,
        summary="Анализ завершён.",
        estimated_effort="2 дня",
        difficulty=Difficulty.MEDIUM,
        risks=("Не указан дедлайн.",),
        action_plan=("Уточнить требования.",),
        application_draft="Готов обсудить задачу.",
        missing_information=("Дедлайн.",),
    )


class OpportunityRepositoryTests(unittest.TestCase):
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

    def test_creates_database_and_round_trips_opportunity(self) -> None:
        opportunity = make_opportunity()
        result = self.repository.add_many([opportunity])

        self.assertTrue(self.database_path.exists())
        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.duplicate_count, 0)
        stored = self.repository.get_by_status(OpportunityStatus.NEW)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].opportunity, opportunity)
        self.assertEqual(stored[0].status, OpportunityStatus.NEW)

    def test_deduplicates_by_source_and_external_id(self) -> None:
        opportunity = make_opportunity()
        first = self.repository.add_many([opportunity])
        second = self.repository.add_many([opportunity])

        self.assertEqual(first.inserted_count, 1)
        self.assertEqual(second.inserted_count, 0)
        self.assertEqual(second.duplicate_count, 1)
        self.assertEqual(self.repository.count(), 1)

    def test_allows_same_external_id_from_another_source(self) -> None:
        first = make_opportunity()
        second = replace(first, source="another_provider")

        result = self.repository.add_many([first, second])
        self.assertEqual(result.inserted_count, 2)
        self.assertEqual(self.repository.count(), 2)

    def test_updates_and_filters_status(self) -> None:
        opportunity = make_opportunity()
        self.repository.add_many([opportunity])

        updated = self.repository.set_status(
            opportunity.source,
            opportunity.external_id,
            OpportunityStatus.FAILED,
            last_error="Temporary provider failure",
        )

        self.assertTrue(updated)
        self.assertEqual(self.repository.get_by_status(OpportunityStatus.NEW), [])
        failed = self.repository.get_by_status(OpportunityStatus.FAILED)
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].last_error, "Temporary provider failure")

    def test_returns_false_when_status_target_does_not_exist(self) -> None:
        self.assertFalse(
            self.repository.set_status("missing", "404", OpportunityStatus.ANALYZING)
        )

    def test_wraps_sqlite_connection_errors(self) -> None:
        repository = OpportunityRepository(self.test_data_root)
        with self.assertRaisesRegex(StorageError, "SQLite operation failed"):
            repository.initialize()

    def test_claims_and_saves_suitable_analysis(self) -> None:
        self.repository.add_many([make_opportunity()])
        claimed = self.repository.claim_for_analysis(limit=10)

        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0].status, OpportunityStatus.ANALYZING)
        self.repository.save_analysis(claimed[0].id, make_analysis(), model="test-model")

        analyzed = self.repository.get_by_status(OpportunityStatus.ANALYZED)
        self.assertEqual(len(analyzed), 1)
        stored_analysis = self.repository.get_analysis(claimed[0].id)
        self.assertIsNotNone(stored_analysis)
        self.assertEqual(stored_analysis.model, "test-model")
        self.assertEqual(stored_analysis.analysis.score, 88)

    def test_marks_unsuitable_analysis_as_rejected(self) -> None:
        self.repository.add_many([make_opportunity()])
        claimed = self.repository.claim_for_analysis(limit=1)
        self.repository.save_analysis(
            claimed[0].id,
            make_analysis(suitable=False),
            model="test-model",
        )
        self.assertEqual(len(self.repository.get_by_status(OpportunityStatus.REJECTED)), 1)

    def test_does_not_claim_same_opportunity_twice(self) -> None:
        self.repository.add_many([make_opportunity()])
        self.assertEqual(len(self.repository.claim_for_analysis(limit=1)), 1)
        self.assertEqual(self.repository.claim_for_analysis(limit=1), [])

    def test_recovers_interrupted_analysis_claims(self) -> None:
        self.repository.add_many([make_opportunity("first"), make_opportunity("second")])
        self.assertEqual(len(self.repository.claim_for_analysis(limit=2)), 2)

        recovered = self.repository.recover_interrupted_analyses()

        self.assertEqual(recovered, 2)
        restored = self.repository.get_by_status(OpportunityStatus.NEW)
        self.assertEqual(len(restored), 2)
        self.assertTrue(
            all("interrupted" in (opportunity.last_error or "") for opportunity in restored)
        )

    def test_saves_profile_session_and_confirmed_profile(self) -> None:
        profile = CandidateProfile(
            positioning="Automation specialist",
            skills=("n8n", "API"),
            preferred_tasks=("business automation",),
            avoid_tasks=("cold sales",),
            preferences=("remote",),
        )
        self.repository.save_profile_session(
            "123",
            step=2,
            draft={"positioning": profile.positioning, "skills": list(profile.skills)},
        )
        session = self.repository.get_profile_session("123")
        self.assertEqual(session.step, 2)
        self.repository.save_user_profile("123", profile)
        self.assertEqual(self.repository.get_user_profile("123"), profile)
        self.repository.delete_profile_session("123")
        self.assertIsNone(self.repository.get_profile_session("123"))

    def test_stores_paired_chat_id_without_source_configuration_changes(self) -> None:
        self.assertIsNone(self.repository.get_paired_chat_id())
        self.repository.set_paired_chat_id("123456")
        self.assertEqual(self.repository.get_paired_chat_id(), "123456")

    def test_stores_service_heartbeat(self) -> None:
        self.assertIsNone(self.repository.get_service_heartbeat("profile_bot"))
        self.repository.set_service_heartbeat("profile_bot")
        self.assertIsNotNone(self.repository.get_service_heartbeat("profile_bot"))

    def test_persists_source_schedule_and_collection_statistics(self) -> None:
        started_at = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(
            self.repository.source_is_due("remote_ok", 900, now=started_at)
        )

        run_id = self.repository.start_source_run("remote_ok", started_at=started_at)
        self.repository.finish_source_run(
            run_id,
            "remote_ok",
            status="completed",
            received_count=20,
            saved_count=4,
            duplicate_count=16,
            finished_at=started_at + timedelta(seconds=10),
        )

        state = self.repository.get_source_state("remote_ok")
        self.assertIsNotNone(state)
        self.assertEqual(state.last_status, "completed")
        self.assertEqual(state.last_received, 20)
        self.assertEqual(state.last_saved, 4)
        self.assertEqual(state.last_duplicates, 16)
        self.assertFalse(
            self.repository.source_is_due(
                "remote_ok",
                900,
                now=started_at + timedelta(seconds=899),
            )
        )
        self.assertTrue(
            self.repository.source_is_due(
                "remote_ok",
                900,
                now=started_at + timedelta(seconds=900),
            )
        )

        with self.repository._connect() as connection:
            stored_run = connection.execute(
                "SELECT * FROM source_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        self.assertEqual(stored_run["status"], "completed")
        self.assertEqual(stored_run["received_count"], 20)

    def test_recovers_interrupted_source_run(self) -> None:
        run_id = self.repository.start_source_run("we_work_remotely")

        recovered = self.repository.recover_interrupted_source_runs()

        self.assertEqual(recovered, 1)
        state = self.repository.get_source_state("we_work_remotely")
        self.assertEqual(state.last_status, "failed")
        self.assertIn("stopped", state.last_error)
        with self.repository._connect() as connection:
            stored_run = connection.execute(
                "SELECT status, last_error FROM source_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        self.assertEqual(stored_run["status"], "failed")
        self.assertIn("stopped", stored_run["last_error"])


if __name__ == "__main__":
    unittest.main()
