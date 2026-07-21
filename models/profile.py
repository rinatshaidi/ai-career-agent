from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class ProfileError(ValueError):
    """Raised when a candidate profile is missing or invalid."""


def _string_tuple(value: Any, field_name: str, *, required: bool = False) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        raise ProfileError(f"Profile {field_name} must be an array of strings.")
    return tuple(item.strip() for item in value if item.strip())


@dataclass(frozen=True, slots=True)
class SearchTrack:
    """A user-created, independently enabled search direction."""

    track_id: str
    name: str
    target_description: str
    roles_and_signals: tuple[str, ...]
    skills_and_experience: tuple[str, ...]
    tasks_and_outcomes: tuple[str, ...]
    locations: tuple[str, ...]
    work_formats: tuple[str, ...] = ()
    growth_opportunities: tuple[str, ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        for field_name in ("track_id", "name", "target_description"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ProfileError(f"Search track {field_name} cannot be empty.")
            object.__setattr__(self, field_name, value.strip())
        if not isinstance(self.enabled, bool):
            raise ProfileError("Search track enabled must be a boolean.")
        for field_name in (
            "roles_and_signals",
            "skills_and_experience",
            "tasks_and_outcomes",
            "locations",
            "work_formats",
            "growth_opportunities",
        ):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not all(isinstance(item, str) for item in values):
                raise ProfileError(f"Search track {field_name} must be a tuple of strings.")
            object.__setattr__(
                self,
                field_name,
                tuple(item.strip() for item in values if item.strip()),
            )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SearchTrack":
        return cls(
            track_id=cls._required_string(data, "track_id"),
            name=cls._required_string(data, "name"),
            target_description=cls._required_string(data, "target_description"),
            roles_and_signals=_string_tuple(data.get("roles_and_signals"), "roles_and_signals"),
            skills_and_experience=_string_tuple(
                data.get("skills_and_experience"), "skills_and_experience"
            ),
            tasks_and_outcomes=_string_tuple(
                data.get("tasks_and_outcomes"), "tasks_and_outcomes"
            ),
            locations=_string_tuple(data.get("locations"), "locations"),
            work_formats=_string_tuple(data.get("work_formats"), "work_formats"),
            growth_opportunities=_string_tuple(
                data.get("growth_opportunities"), "growth_opportunities"
            ),
            enabled=data.get("enabled", True),
        )

    @staticmethod
    def _required_string(data: Mapping[str, Any], field_name: str) -> str:
        value = data.get(field_name)
        if not isinstance(value, str):
            raise ProfileError(f"Search track {field_name} must be a string.")
        return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "name": self.name,
            "target_description": self.target_description,
            "roles_and_signals": list(self.roles_and_signals),
            "skills_and_experience": list(self.skills_and_experience),
            "tasks_and_outcomes": list(self.tasks_and_outcomes),
            "locations": list(self.locations),
            "work_formats": list(self.work_formats),
            "growth_opportunities": list(self.growth_opportunities),
            "enabled": self.enabled,
        }


@dataclass(frozen=True, slots=True)
class CandidateProfile:
    """One person with common context and one or more user-created search tracks."""

    positioning: str
    skills: tuple[str, ...]
    preferred_tasks: tuple[str, ...]
    avoid_tasks: tuple[str, ...]
    preferences: tuple[str, ...]
    common_preferences: tuple[str, ...] = ()
    search_tracks: tuple[SearchTrack, ...] = ()

    def __post_init__(self) -> None:
        positioning = self.positioning.strip()
        if not positioning:
            raise ProfileError("Profile positioning cannot be empty.")
        object.__setattr__(self, "positioning", positioning)

        for field_name in (
            "skills",
            "preferred_tasks",
            "avoid_tasks",
            "preferences",
            "common_preferences",
        ):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not all(isinstance(item, str) for item in values):
                raise ProfileError(f"Profile {field_name} must be a tuple of strings.")
            object.__setattr__(
                self,
                field_name,
                tuple(item.strip() for item in values if item.strip()),
            )

        if not isinstance(self.search_tracks, tuple) or not all(
            isinstance(track, SearchTrack) for track in self.search_tracks
        ):
            raise ProfileError("Profile search_tracks must be a tuple of SearchTrack values.")
        track_ids = tuple(track.track_id for track in self.search_tracks)
        if len(set(track_ids)) != len(track_ids):
            raise ProfileError("Profile search track identifiers must be unique.")

        # Pre-Block 9 profiles have no tracks and remain readable.
        if not self.search_tracks:
            if not self.skills:
                raise ProfileError("Profile skills cannot be empty.")
            if not self.preferred_tasks:
                raise ProfileError("Profile preferred_tasks cannot be empty.")

    @property
    def active_search_tracks(self) -> tuple[SearchTrack, ...]:
        return tuple(track for track in self.search_tracks if track.enabled)

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
        raw_tracks = data.get("search_tracks", [])
        if not isinstance(raw_tracks, list) or not all(isinstance(item, Mapping) for item in raw_tracks):
            raise ProfileError("Profile search_tracks must be an array of objects.")
        tracks = tuple(SearchTrack.from_mapping(item) for item in raw_tracks)
        positioning = data.get("positioning")
        if not isinstance(positioning, str):
            if tracks:
                positioning = " / ".join(track.name for track in tracks)
            else:
                raise ProfileError("Profile positioning must be a string.")
        return cls(
            positioning=positioning,
            skills=_string_tuple(data.get("skills"), "skills"),
            preferred_tasks=_string_tuple(data.get("preferred_tasks"), "preferred_tasks"),
            avoid_tasks=_string_tuple(data.get("avoid_tasks"), "avoid_tasks"),
            preferences=_string_tuple(data.get("preferences"), "preferences"),
            common_preferences=_string_tuple(
                data.get("common_preferences"), "common_preferences"
            ),
            search_tracks=tracks,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "positioning": self.positioning,
            "skills": list(self.skills),
            "preferred_tasks": list(self.preferred_tasks),
            "avoid_tasks": list(self.avoid_tasks),
            "preferences": list(self.preferences),
            "common_preferences": list(self.common_preferences),
            "search_tracks": [track.to_dict() for track in self.search_tracks],
        }
