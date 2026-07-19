from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class Difficulty(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AIAnalysis:
    suitable: bool
    score: int
    summary: str
    estimated_effort: str
    difficulty: Difficulty
    risks: tuple[str, ...]
    action_plan: tuple[str, ...]
    application_draft: str
    missing_information: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.suitable, bool):
            raise ValueError("suitable must be a boolean.")
        if isinstance(self.score, bool) or not isinstance(self.score, int):
            raise ValueError("score must be an integer.")
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100.")
        if not isinstance(self.difficulty, Difficulty):
            raise ValueError("difficulty must be a Difficulty value.")

        for field_name in ("summary", "estimated_effort", "application_draft"):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be a string.")
            normalized = value.strip()
            if not normalized:
                raise ValueError(f"{field_name} cannot be empty.")
            object.__setattr__(self, field_name, normalized)

        for field_name in ("risks", "action_plan", "missing_information"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not all(isinstance(item, str) for item in values):
                raise ValueError(f"{field_name} must be a tuple of strings.")
            normalized = tuple(item.strip() for item in values if item.strip())
            object.__setattr__(self, field_name, normalized)

        if not self.action_plan:
            raise ValueError("action_plan cannot be empty.")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "AIAnalysis":
        required = {
            "suitable",
            "score",
            "summary",
            "estimated_effort",
            "difficulty",
            "risks",
            "action_plan",
            "application_draft",
            "missing_information",
        }
        missing = required.difference(data)
        if missing:
            raise ValueError(f"AI analysis is missing fields: {', '.join(sorted(missing))}.")

        try:
            difficulty = Difficulty(data["difficulty"])
        except (TypeError, ValueError) as exc:
            raise ValueError("AI analysis contains an invalid difficulty.") from exc

        return cls(
            suitable=data["suitable"],
            score=data["score"],
            summary=data["summary"],
            estimated_effort=data["estimated_effort"],
            difficulty=difficulty,
            risks=cls._string_tuple(data["risks"], "risks"),
            action_plan=cls._string_tuple(data["action_plan"], "action_plan"),
            application_draft=data["application_draft"],
            missing_information=cls._string_tuple(
                data["missing_information"], "missing_information"
            ),
        )

    @staticmethod
    def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{field_name} must be an array of strings.")
        return tuple(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suitable": self.suitable,
            "score": self.score,
            "summary": self.summary,
            "estimated_effort": self.estimated_effort,
            "difficulty": self.difficulty.value,
            "risks": list(self.risks),
            "action_plan": list(self.action_plan),
            "application_draft": self.application_draft,
            "missing_information": list(self.missing_information),
        }
