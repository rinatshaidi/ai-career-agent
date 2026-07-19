from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class ProfileError(ValueError):
    """Raised when a candidate profile is missing or invalid."""


@dataclass(frozen=True, slots=True)
class CandidateProfile:
    positioning: str
    skills: tuple[str, ...]
    preferred_tasks: tuple[str, ...]
    avoid_tasks: tuple[str, ...]
    preferences: tuple[str, ...]

    def __post_init__(self) -> None:
        positioning = self.positioning.strip()
        if not positioning:
            raise ProfileError("Profile positioning cannot be empty.")
        object.__setattr__(self, "positioning", positioning)

        for field_name in ("skills", "preferred_tasks", "avoid_tasks", "preferences"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not all(isinstance(item, str) for item in values):
                raise ProfileError(f"Profile {field_name} must be a tuple of strings.")
            normalized = tuple(item.strip() for item in values if item.strip())
            object.__setattr__(self, field_name, normalized)

        if not self.skills:
            raise ProfileError("Profile skills cannot be empty.")
        if not self.preferred_tasks:
            raise ProfileError("Profile preferred_tasks cannot be empty.")

    @classmethod
    def from_file(cls, path: str | Path) -> "CandidateProfile":
        profile_path = Path(path)
        try:
            raw_data = json.loads(profile_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ProfileError(f"Candidate profile not found: {profile_path}.") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ProfileError(f"Cannot read candidate profile {profile_path}: {exc}") from exc
        if not isinstance(raw_data, dict):
            raise ProfileError("Candidate profile must contain a JSON object.")
        return cls.from_mapping(raw_data)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "CandidateProfile":
        return cls(
            positioning=cls._required_string(data, "positioning"),
            skills=cls._string_tuple(data, "skills"),
            preferred_tasks=cls._string_tuple(data, "preferred_tasks"),
            avoid_tasks=cls._string_tuple(data, "avoid_tasks", required=False),
            preferences=cls._string_tuple(data, "preferences", required=False),
        )

    @staticmethod
    def _required_string(data: Mapping[str, Any], field_name: str) -> str:
        value = data.get(field_name)
        if not isinstance(value, str):
            raise ProfileError(f"Profile {field_name} must be a string.")
        return value

    @staticmethod
    def _string_tuple(
        data: Mapping[str, Any],
        field_name: str,
        *,
        required: bool = True,
    ) -> tuple[str, ...]:
        value = data.get(field_name)
        if value is None and not required:
            return ()
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ProfileError(f"Profile {field_name} must be an array of strings.")
        return tuple(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "positioning": self.positioning,
            "skills": list(self.skills),
            "preferred_tasks": list(self.preferred_tasks),
            "avoid_tasks": list(self.avoid_tasks),
            "preferences": list(self.preferences),
        }
