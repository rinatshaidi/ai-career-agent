from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class Difficulty(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class RecommendationCategory(str, Enum):
    PRIORITY = "priority"
    REVIEW = "review"
    ARCHIVE = "archive"


@dataclass(frozen=True, slots=True)
class TrackAssessment:
    track_id: str
    track_name: str
    score: int
    reason: str

    def __post_init__(self) -> None:
        for field_name in ("track_id", "track_name", "reason"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} cannot be empty.")
            object.__setattr__(self, field_name, value.strip())
        if isinstance(self.score, bool) or not isinstance(self.score, int) or not 0 <= self.score <= 100:
            raise ValueError("track assessment score must be between 0 and 100.")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "TrackAssessment":
        return cls(
            track_id=data.get("track_id"),
            track_name=data.get("track_name"),
            score=data.get("score"),
            reason=data.get("reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "track_name": self.track_name,
            "score": self.score,
            "reason": self.reason,
        }


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
    recommendation: RecommendationCategory | None = None
    primary_track_id: str | None = None
    primary_track_name: str | None = None
    match_reasons: tuple[str, ...] = ()
    required_actions: tuple[str, ...] = ()
    employment_type: str = "не указана"
    track_assessments: tuple[TrackAssessment, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.suitable, bool):
            raise ValueError("suitable must be a boolean.")
        if isinstance(self.score, bool) or not isinstance(self.score, int):
            raise ValueError("score must be an integer.")
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100.")
        if not isinstance(self.difficulty, Difficulty):
            raise ValueError("difficulty must be a Difficulty value.")
        if self.recommendation is not None:
            if not isinstance(self.recommendation, RecommendationCategory):
                raise ValueError("recommendation must be a RecommendationCategory value.")
            expected_suitable = self.recommendation is not RecommendationCategory.ARCHIVE
            if self.suitable != expected_suitable:
                raise ValueError("suitable must agree with recommendation.")

        for field_name in ("summary", "estimated_effort", "application_draft", "employment_type"):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be a string.")
            normalized = value.strip()
            if not normalized:
                raise ValueError(f"{field_name} cannot be empty.")
            object.__setattr__(self, field_name, normalized)

        for field_name in (
            "risks",
            "action_plan",
            "missing_information",
            "match_reasons",
            "required_actions",
        ):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not all(isinstance(item, str) for item in values):
                raise ValueError(f"{field_name} must be a tuple of strings.")
            normalized = tuple(item.strip() for item in values if item.strip())
            object.__setattr__(self, field_name, normalized)

        if not self.action_plan:
            raise ValueError("action_plan cannot be empty.")
        for field_name in ("primary_track_id", "primary_track_name"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{field_name} must be a non-empty string or None.")
            if isinstance(value, str):
                object.__setattr__(self, field_name, value.strip())
        if not isinstance(self.track_assessments, tuple) or not all(
            isinstance(item, TrackAssessment) for item in self.track_assessments
        ):
            raise ValueError("track_assessments must be a tuple of TrackAssessment values.")
        for field_name in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer.")

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

        recommendation_raw = data.get("recommendation")
        try:
            recommendation = (
                RecommendationCategory(recommendation_raw)
                if recommendation_raw is not None
                else None
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("AI analysis contains an invalid recommendation.") from exc
        raw_assessments = data.get("track_assessments", [])
        if not isinstance(raw_assessments, list) or not all(isinstance(item, Mapping) for item in raw_assessments):
            raise ValueError("track_assessments must be an array of objects.")
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
            recommendation=recommendation,
            primary_track_id=data.get("primary_track_id"),
            primary_track_name=data.get("primary_track_name"),
            match_reasons=cls._string_tuple(data.get("match_reasons", []), "match_reasons"),
            required_actions=cls._string_tuple(data.get("required_actions", []), "required_actions"),
            employment_type=data.get("employment_type", "не указана"),
            track_assessments=tuple(TrackAssessment.from_mapping(item) for item in raw_assessments),
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
            "recommendation": self.recommendation.value if self.recommendation else None,
            "primary_track_id": self.primary_track_id,
            "primary_track_name": self.primary_track_name,
            "match_reasons": list(self.match_reasons),
            "required_actions": list(self.required_actions),
            "employment_type": self.employment_type,
            "track_assessments": [item.to_dict() for item in self.track_assessments],
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }
