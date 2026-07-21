from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from models import Opportunity, RemoteType
from providers.base import ProviderError
from providers.text import html_to_text


class GreenhouseError(ProviderError):
    """Base error raised by a Greenhouse job board provider."""


class GreenhouseFeedError(GreenhouseError):
    """Raised when a Greenhouse response cannot be normalized safely."""


@dataclass(frozen=True, slots=True)
class GreenhouseBoard:
    token: str
    company_name: str


def parse_greenhouse_boards(value: str) -> tuple[GreenhouseBoard, ...]:
    """Parse `token|Company Name` entries separated by semicolons."""
    if not value.strip():
        return ()

    boards: list[GreenhouseBoard] = []
    seen: set[str] = set()
    for raw_entry in value.split(";"):
        token, separator, company_name = raw_entry.partition("|")
        token = token.strip().lower()
        company_name = company_name.strip()
        if not separator or not token or not company_name:
            raise ValueError(
                "GREENHOUSE_BOARDS entries must use token|Company Name separated by semicolons."
            )
        if not re.fullmatch(r"[a-z0-9_-]+", token):
            raise ValueError(
                "Greenhouse board token may contain only a-z, 0-9, underscore and hyphen."
            )
        if token in seen:
            raise ValueError(f"Duplicate Greenhouse board token: {token}.")
        seen.add(token)
        boards.append(GreenhouseBoard(token=token, company_name=company_name))
    return tuple(boards)


def _updated_at(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise GreenhouseFeedError(f"Invalid Greenhouse update date: {value!r}.") from exc
    if parsed.tzinfo is None:
        raise GreenhouseFeedError("Greenhouse update date must include a timezone.")
    return parsed


def _remote_type(title: str, location: str, description: str) -> RemoteType:
    combined = f"{title} {location} {description}".casefold()
    if "remote" in combined:
        return RemoteType.REMOTE
    if "hybrid" in combined:
        return RemoteType.HYBRID
    if any(value in combined for value in ("on-site", "onsite", "in office")):
        return RemoteType.ONSITE
    return RemoteType.UNKNOWN


def _names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(item.get("name") or "").strip()
        for item in value
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]


def parse_greenhouse_jobs(
    payload: object,
    *,
    board: GreenhouseBoard,
    limit: int | None = None,
    collected_at: datetime | None = None,
) -> list[Opportunity]:
    """Normalize a public Greenhouse Job Board API response."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than or equal to 1.")
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise GreenhouseFeedError("Greenhouse response must contain a jobs array.")

    if collected_at is None:
        collected_at = datetime.now(timezone.utc)
    elif collected_at.tzinfo is None:
        raise ValueError("collected_at must include timezone information.")

    source = f"greenhouse_{board.token}"
    opportunities: list[Opportunity] = []
    for raw_job in payload["jobs"]:
        if not isinstance(raw_job, dict) or raw_job.get("id") in (None, ""):
            continue

        title = str(raw_job.get("title") or "").strip()
        url = str(raw_job.get("absolute_url") or "").strip()
        if not title or not url:
            raise GreenhouseFeedError("Greenhouse job is missing title or absolute_url.")

        location_value = raw_job.get("location")
        location = (
            str(location_value.get("name") or "").strip()
            if isinstance(location_value, dict)
            else ""
        )
        description = html_to_text(str(raw_job.get("content") or ""))
        details: list[str] = []
        departments = _names(raw_job.get("departments"))
        offices = _names(raw_job.get("offices"))
        if departments:
            details.append(f"Departments: {', '.join(departments)}")
        if offices:
            details.append(f"Offices: {', '.join(offices)}")
        language = str(raw_job.get("language") or "").strip()
        if language:
            details.append(f"Language: {language}")
        full_description = "\n\n".join(part for part in (description, *details) if part)

        opportunities.append(
            Opportunity(
                source=source,
                external_id=str(raw_job["id"]),
                title=title,
                description=full_description,
                url=url,
                company_name=board.company_name,
                location=location,
                remote_type=_remote_type(title, location, full_description),
                published_at=_updated_at(raw_job.get("updated_at")),
                collected_at=collected_at,
            )
        )
        if limit is not None and len(opportunities) >= limit:
            break

    return opportunities


@dataclass(slots=True)
class GreenhouseProvider:
    api_base_url: str
    board: GreenhouseBoard
    user_agent: str
    limit: int
    timeout_seconds: int
    transport: httpx.BaseTransport | None = field(default=None, repr=False)
    source: str = field(init=False)

    def __post_init__(self) -> None:
        self.source = f"greenhouse_{self.board.token}"

    def fetch(self) -> list[Opportunity]:
        url = f"{self.api_base_url.rstrip('/')}/{self.board.token}/jobs"
        try:
            with httpx.Client(
                headers={"Accept": "application/json", "User-Agent": self.user_agent},
                timeout=float(self.timeout_seconds),
                follow_redirects=True,
                transport=self.transport,
            ) as client:
                response = client.get(url, params={"content": "true"})
                response.raise_for_status()
                payload: Any = response.json()
        except httpx.HTTPStatusError as exc:
            raise GreenhouseError(
                f"Greenhouse board {self.board.token} returned HTTP {exc.response.status_code}."
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise GreenhouseError(
                f"Greenhouse board {self.board.token} request failed: {exc}"
            ) from exc

        return parse_greenhouse_jobs(payload, board=self.board, limit=self.limit)
