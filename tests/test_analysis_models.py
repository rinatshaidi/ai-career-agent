from __future__ import annotations

import unittest
from pathlib import Path

from models import AIAnalysis, CandidateProfile, Difficulty, ProfileError


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


if __name__ == "__main__":
    unittest.main()
