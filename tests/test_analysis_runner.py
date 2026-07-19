from __future__ import annotations

import unittest
from pathlib import Path
from uuid import uuid4

from models import AIAnalysis, CandidateProfile, Difficulty
from services import AIAnalyzerError, AnalysisRunner
from storage import OpportunityRepository, OpportunityStatus
from tests.test_repository import make_opportunity
from utils import RetryPolicy


def analysis(suitable: bool) -> AIAnalysis:
    return AIAnalysis(
        suitable=suitable,
        score=90 if suitable else 20,
        summary="Результат анализа.",
        estimated_effort="1 день",
        difficulty=Difficulty.LOW,
        risks=(),
        action_plan=("Проверить требования.",),
        application_draft="Готов обсудить задачу.",
        missing_information=(),
    )


class FakeAnalyzer:
    model = "fake-model"

    def analyze(self, opportunity, profile):
        if opportunity.external_id == "failed":
            raise AIAnalyzerError("Temporary failure")
        return analysis(opportunity.external_id == "suitable")


class AnalysisRunnerTests(unittest.TestCase):
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

    def test_runner_continues_after_one_analysis_failure(self) -> None:
        self.repository.add_many(
            [
                make_opportunity("suitable"),
                make_opportunity("rejected"),
                make_opportunity("failed"),
            ]
        )
        profile = CandidateProfile(
            positioning="Automation specialist",
            skills=("automation",),
            preferred_tasks=("integrations",),
            avoid_tasks=(),
            preferences=(),
        )

        result = AnalysisRunner(
            self.repository,
            FakeAnalyzer(),
            profile,
            retry_policy=RetryPolicy(attempts=1, delay_seconds=0),
        ).run(batch_size=10)

        self.assertEqual(result.claimed, 3)
        self.assertEqual(result.analyzed, 1)
        self.assertEqual(result.rejected, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(len(self.repository.get_by_status(OpportunityStatus.ANALYZED)), 1)
        self.assertEqual(len(self.repository.get_by_status(OpportunityStatus.REJECTED)), 1)
        failed = self.repository.get_by_status(OpportunityStatus.FAILED)
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].last_error, "Temporary failure")


if __name__ == "__main__":
    unittest.main()
