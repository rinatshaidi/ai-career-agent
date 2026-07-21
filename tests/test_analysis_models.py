from __future__ import annotations

import unittest
from pathlib import Path

from models import (
    AIAnalysis,
    CandidateProfile,
    Difficulty,
    ProfileError,
    RecommendationCategory,
    SearchTrack,
    TrackAssessment,
)


VALID_ANALYSIS = {
    "suitable": True,
    "score": 86,
    "summary": "Подходит по основным навыкам.",
    "estimated_effort": "2-3 дня",
    "difficulty": "medium",
    "risks": ["Не указан срок."],
    "action_plan": ["Уточнить требования.", "Подготовить прототип."],
    "application_draft": "Готов обсудить задачу.",
    "missing_information": ["Точный бюджет."],
}


class AIAnalysisTests(unittest.TestCase):
    def test_builds_validated_analysis_from_mapping(self) -> None:
        analysis = AIAnalysis.from_mapping(VALID_ANALYSIS)
        self.assertTrue(analysis.suitable)
        self.assertEqual(analysis.score, 86)
        self.assertEqual(analysis.difficulty, Difficulty.MEDIUM)
        self.assertEqual(analysis.to_dict()["action_plan"], VALID_ANALYSIS["action_plan"])

    def test_rejects_score_outside_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 0 and 100"):
            AIAnalysis.from_mapping({**VALID_ANALYSIS, "score": 101})

    def test_rejects_missing_fields(self) -> None:
        invalid = dict(VALID_ANALYSIS)
        invalid.pop("summary")
        with self.assertRaisesRegex(ValueError, "missing fields"):
            AIAnalysis.from_mapping(invalid)

    def test_validates_track_aware_recommendation(self) -> None:
        analysis = AIAnalysis.from_mapping(
            {
                **VALID_ANALYSIS,
                "recommendation": "review",
                "primary_track_id": "automation",
                "primary_track_name": "AI-автоматизация",
                "match_reasons": ["Совпадают задачи автоматизации."],
                "required_actions": [],
                "employment_type": "частичная занятость",
                "track_assessments": [
                    {
                        "track_id": "automation",
                        "track_name": "AI-автоматизация",
                        "score": 64,
                        "reason": "Есть смысловая близость.",
                    }
                ],
            }
        )

        self.assertEqual(analysis.recommendation, RecommendationCategory.REVIEW)
        self.assertEqual(
            analysis.track_assessments,
            (
                TrackAssessment(
                    track_id="automation",
                    track_name="AI-автоматизация",
                    score=64,
                    reason="Есть смысловая близость.",
                ),
            ),
        )


class CandidateProfileTests(unittest.TestCase):
    def test_reads_example_profile(self) -> None:
        path = Path(__file__).resolve().parents[1] / "profiles" / "user_profile.example.json"
        profile = CandidateProfile.from_file(path)
        self.assertTrue(profile.skills)
        self.assertTrue(profile.preferred_tasks)

    def test_rejects_profile_without_skills(self) -> None:
        with self.assertRaisesRegex(ProfileError, "skills"):
            CandidateProfile.from_mapping(
                {"positioning": "Automation", "skills": [], "preferred_tasks": ["Bots"]}
            )

    def test_accepts_user_created_search_track_when_legacy_fields_are_empty(self) -> None:
        profile = CandidateProfile(
            positioning="AI Automation",
            skills=(),
            preferred_tasks=(),
            avoid_tasks=(),
            preferences=(),
            search_tracks=(
                SearchTrack(
                    track_id="automation",
                    name="Automation work",
                    target_description="Automate business processes",
                    roles_and_signals=("business automation",),
                    skills_and_experience=(),
                    tasks_and_outcomes=(),
                    locations=(),
                ),
            ),
        )

        self.assertEqual(profile.active_search_tracks[0].name, "Automation work")


if __name__ == "__main__":
    unittest.main()
