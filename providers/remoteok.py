from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from models import Opportunity, RemoteType
from providers.base import ProviderError
from providers.text import html_to_text


class RemoteOKError(ProviderError):
    """Base error raised by the Remote OK provider."""


class RemoteOKFeedError(RemoteOKError):
    """Raised when the Remote OK response cannot be normalized safely."""


def _published_at(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise RemoteOKFeedError(f"Invalid Remote OK publication date: {value!r}.") from exc
    if parsed.tzinfo is None:
        raise RemoteOKFeedError("Remote OK publication date must include a timezone.")
    return parsed


def _positive_amount(value: object) -> int | None:
    try:
        amount = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise RemoteOKFeedError(f"Invalid Remote OK salary value: {value!r}.") from exc
    return amount if amount > 0 else None


def parse_remoteok_jobs(
    payload: object,
    *,
    limit: int | None = None,
    collected_at: datetime | None = None,
) -> list[Opportunity]:
    """Normalize the official Remote OK JSON feed."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than or equal to 1.")
    if not isinstance(payload, list):
        raise RemoteOKFeedError("Remote OK response must be a JSON array.")

    if collected_at is None:
        collected_at = datetime.now(timezone.utc)
    elif collected_at.tzinfo is None:
        raise ValueError("collected_at must include timezone information.")

    opportunities: list[Opportunity] = []
    for raw_job in payload:
        if not isinstance(raw_job, dict) or not raw_job.get("id"):
            continue

        title = str(raw_job.get("position") or "").strip()
        url = str(raw_job.get("url") or raw_job.get("apply_url") or "").strip()
        if not title or not url:
            raise RemoteOKFeedError("Remote OK job is missing position or URL.")

        tags_value = raw_job.get("tags")
        tags = [str(tag).strip() for tag in tags_value] if isinstance(tags_value, list) else []
        description = html_to_text(str(raw_job.get("description") or ""))
        if tags:
            description = f"{description}\n\nTags: {', '.join(tag for tag in tags if tag)}".strip()

        salary_from = _positive_amount(raw_job.get("salary_min"))
        salary_to = _positive_amount(raw_job.get("salary_max"))
        opportunities.append(
            Opportunity(
                source="remote_ok",
                external_id=str(raw_job["id"]),
                title=title,
                description=description,
                url=url,
                company_name=str(raw_job.get("company") or ""),
                location=str(raw_job.get("location") or ""),
                remote_type=RemoteType.REMOTE,
                salary_from=salary_from,
                salary_to=salary_to,
                currency="USD" if salary_from is not None or salary_to is not None else None,
                published_at=_published_at(raw_job.get("date")),
                collected_at=collected_at,
            )
        )
        if limit is not None and len(opportunities) >= limit:
            break

    return opportunities


@dataclass(slots=True)
class RemoteOKProvider:
    api_url: str
    user_agent: str
    limit: int
    timeout_seconds: int
    transport: httpx.BaseTransport | None = field(default=None, repr=False)

    source = "remote_ok"

    def fetch(self) -> list[Opportunity]:
        try:
            with httpx.Client(
                headers={"Accept": "application/json", "User-Agent": self.user_agent},
                timeout=float(self.timeout_seconds),
                follow_redirects=True,
                transport=self.transport,
            ) as client:
                response = client.get(self.api_url)
                response.raise_for_status()
                payload: Any = response.json()
        except httpx.HTTPStatusError as exc:
            raise RemoteOKError(f"Remote OK API returned HTTP {exc.response.status_code}.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RemoteOKError(f"Remote OK API request failed: {exc}") from exc

        return parse_remoteok_jobs(payload, limit=self.limit)
