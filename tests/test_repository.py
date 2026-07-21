from __future__ import annotations

import unittest
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from models import (
    AIAnalysis,
    CandidateProfile,
    Difficulty,
    Opportunity,
    RemoteType,
    SearchTrack,
)
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

    def test_migrates_existing_opportunity_to_identity_and_source_tables(self) -> None:
        legacy_path = self.test_data_root / f"legacy-{uuid4().hex}.db"
        opportunity = make_opportunity("legacy")
        try:
            connection = sqlite3.connect(legacy_path)
            try:
                connection.execute(
                    """
                    CREATE TABLE opportunities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT NOT NULL,
                        external_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        url TEXT NOT NULL,
                        company_name TEXT NOT NULL DEFAULT '',
                        location TEXT NOT NULL DEFAULT '',
                        remote_type TEXT NOT NULL,
                        salary_from INTEGER,
                        salary_to INTEGER,
                        currency TEXT,
                        published_at TEXT,
                        collected_at TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'new',
                        last_error TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE (source, external_id)
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO opportunities (
                        source, external_id, title, description, url,
                        company_name, location, remote_type, salary_from,
                        salary_to, currency, published_at, collected_at,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
                    """,
                    (
                        opportunity.source,
                        opportunity.external_id,
                        opportunity.title,
                        opportunity.description,
                        opportunity.url,
                        opportunity.company_name,
                        opportunity.location,
                        opportunity.remote_type.value,
                        opportunity.salary_from,
                        opportunity.salary_to,
                        opportunity.currency,
                        opportunity.published_at.isoformat(),
                        opportunity.collected_at.isoformat(),
                        opportunity.collected_at.isoformat(),
                        opportunity.collected_at.isoformat(),
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            repository = OpportunityRepository(legacy_path)
            repository.initialize()
            repository.initialize()

            stored = repository.get_by_status(OpportunityStatus.NEW)
            self.assertEqual(len(stored), 1)
            sources = repository.get_opportunity_sources(stored[0].id)
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0].source, opportunity.source)
            with repository._connect() as connection:
                identity = connection.execute(
                    "SELECT canonical_url, content_fingerprint FROM opportunities"
                ).fetchone()
            self.assertTrue(identity["canonical_url"])
            self.assertEqual(len(identity["content_fingerprint"]), 64)
        finally:
            for suffix in ("", "-shm", "-wal"):
                path = Path(f"{legacy_path}{suffix}")
                if path.exists():
                    path.unlink()

    def test_deduplicates_by_source_and_external_id(self) -> None:
        opportunity = make_opportunity()
        first = self.repository.add_many([opportunity])
        second = self.repository.add_many([opportunity])

        self.assertEqual(first.inserted_count, 1)
        self.assertEqual(second.inserted_count, 0)
        self.assertEqual(second.duplicate_count, 1)
        self.assertEqual(self.repository.count(), 1)

    def test_merges_same_opportunity_from_another_source_and_keeps_provenance(self) -> None:
        first = make_opportunity()
        second = replace(
            first,
            source="another_provider",
            url="https://www.example.com/opportunities/42/?utm_source=aggregator",
        )

        result = self.repository.add_many([first, second])
        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.merged_count, 1)
        self.assertEqual(self.repository.count(), 1)
        stored = self.repository.get_by_status(OpportunityStatus.NEW)[0]
        sources = self.repository.get_opportunity_sources(stored.id)
        self.assertEqual([item.source for item in sources], ["test_provider", "another_provider"])

    def test_merges_exact_content_from_different_urls(self) -> None:
        first = make_opportunity("first")
        second = replace(
            first,
            source="another_provider",
            external_id="second",
            url="https://another.example/jobs/second",
        )

        result = self.repository.add_many([first, second])

        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.merged_count, 1)
        self.assertEqual(len(self.repository.get_opportunity_sources(1)), 2)

    def test_does_not_merge_when_url_and_content_are_different(self) -> None:
        first = make_opportunity("first")
        second = replace(
            first,
            source="another_provider",
            external_id="second",
            title="Different role",
            description="Different work.",
            url="https://another.example/jobs/second",
        )

        result = self.repository.add_many([first, second])

        self.assertEqual(result.inserted_count, 2)
        self.assertEqual(result.duplicate_count, 0)

    def test_defers_only_new_records_when_queue_capacity_is_reached(self) -> None:
        first = make_opportunity("first")
        duplicate = replace(first, source="another_provider", external_id="duplicate")
        second = make_opportunity("second")

        result = self.repository.add_many([first, duplicate, second], max_new=1)

        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.merged_count, 1)
        self.assertEqual(result.deferred_count, 1)
        self.assertEqual(self.repository.count_pending_analysis(), 1)

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
        analysis = replace(
            make_analysis(),
            input_tokens=120,
            output_tokens=45,
            total_tokens=165,
        )
        self.repository.save_analysis(claimed[0].id, analysis, model="test-model")

        analyzed = self.repository.get_by_status(OpportunityStatus.ANALYZED)
        self.assertEqual(len(analyzed), 1)
        stored_analysis = self.repository.get_analysis(claimed[0].id)
        self.assertIsNotNone(stored_analysis)
        self.assertEqual(stored_analysis.model, "test-model")
        self.assertEqual(stored_analysis.analysis.score, 88)
        self.assertEqual(stored_analysis.analysis.total_tokens, 165)

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

    def test_saves_multiple_user_search_tracks_without_losing_common_preferences(self) -> None:
        profile = CandidateProfile(
            positioning="AI Automation / Infrastructure & Business Projects",
            skills=("n8n", "project coordination"),
            preferred_tasks=("automation", "project development"),
            avoid_tasks=("cold sales",),
            preferences=("remote",),
            common_preferences=("Geography: worldwide", "Work format: remote"),
            search_tracks=(
                SearchTrack(
                    track_id="automation",
                    name="Automation",
                    target_description="Automation projects",
                    roles_and_signals=("workflow",),
                    skills_and_experience=("n8n", "API"),
                    tasks_and_outcomes=("automation",),
                    locations=("Remote",),
                ),
                SearchTrack(
                    track_id="infrastructure",
                    name="Infrastructure",
                    target_description="Infrastructure projects",
                    roles_and_signals=("infrastructure",),
                    skills_and_experience=("project development",),
                    tasks_and_outcomes=("partnerships",),
                    locations=("Worldwide",),
                ),
            ),
        )

        self.repository.save_user_profile("123", profile)

        restored = self.repository.get_user_profile("123")
        self.assertEqual(restored, profile)

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
        self.assertEqual(state.last_deferred, 0)
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
