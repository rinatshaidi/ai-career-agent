from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from models import Opportunity, RemoteType
from providers.base import ProviderError
from providers.text import html_to_text


class RemotiveError(ProviderError):
    """Base error raised by the Remotive provider."""


class RemotiveFeedError(RemotiveError):
    """Raised when the Remotive response cannot be normalized safely."""


def _published_at(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise RemotiveFeedError(f"Invalid Remotive publication date: {value!r}.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_remotive_jobs(
    payload: object,
    *,
    limit: int | None = None,
    collected_at: datetime | None = None,
) -> list[Opportunity]:
    """Normalize the official Remotive public API response."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than or equal to 1.")
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise RemotiveFeedError("Remotive response must contain a jobs array.")

    if collected_at is None:
        collected_at = datetime.now(timezone.utc)
    elif collected_at.tzinfo is None:
        raise ValueError("collected_at must include timezone information.")

    opportunities: list[Opportunity] = []
    for raw_job in payload["jobs"]:
        if not isinstance(raw_job, dict) or not raw_job.get("id"):
            continue

        title = str(raw_job.get("title") or "").strip()
        url = str(raw_job.get("url") or "").strip()
        if not title or not url:
            raise RemotiveFeedError("Remotive job is missing title or URL.")

        description_parts = [html_to_text(str(raw_job.get("description") or ""))]
        details = (
            ("Category", raw_job.get("category")),
            ("Job type", raw_job.get("job_type")),
            ("Salary", raw_job.get("salary")),
        )
        description_parts.extend(
            f"{label}: {str(value).strip()}"
            for label, value in details
            if str(value or "").strip()
        )

        opportunities.append(
            Opportunity(
                source="remotive",
                external_id=str(raw_job["id"]),
                title=title,
                description="\n\n".join(part for part in description_parts if part),
                url=url,
                company_name=str(raw_job.get("company_name") or ""),
                location=str(raw_job.get("candidate_required_location") or ""),
                remote_type=RemoteType.REMOTE,
                published_at=_published_at(raw_job.get("publication_date")),
                collected_at=collected_at,
            )
        )
        if limit is not None and len(opportunities) >= limit:
            break

    return opportunities


@dataclass(slots=True)
class RemotiveProvider:
    api_url: str
    user_agent: str
    limit: int
    timeout_seconds: int
    transport: httpx.BaseTransport | None = field(default=None, repr=False)

    source = "remotive"
    # Remotive advises at most four API requests per day. Fast retries are disabled.
    retry_attempts = 1

    def fetch(self) -> list[Opportunity]:
        try:
            with httpx.Client(
                headers={"Accept": "application/json", "User-Agent": self.user_agent},
                timeout=float(self.timeout_seconds),
                follow_redirects=True,
                transport=self.transport,
            ) as client:
                response = client.get(self.api_url, params={"limit": str(self.limit)})
                response.raise_for_status()
                payload: Any = response.json()
        except httpx.HTTPStatusError as exc:
            raise RemotiveError(f"Remotive API returned HTTP {exc.response.status_code}.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RemotiveError(f"Remotive API request failed: {exc}") from exc

        return parse_remotive_jobs(payload, limit=self.limit)
