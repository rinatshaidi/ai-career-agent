from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from models import Opportunity, RemoteType
from providers.base import ProviderError
from providers.text import html_to_text


class JobicyError(ProviderError):
    """Base error raised by the official Jobicy API provider."""


class JobicyFeedError(JobicyError):
    """Raised when a Jobicy response cannot be normalized safely."""


def _published_at(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise JobicyFeedError(f"Invalid Jobicy publication date: {value!r}.") from exc
    if parsed.tzinfo is None:
        raise JobicyFeedError("Jobicy publication date must include a timezone.")
    return parsed


def _positive_amount(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        amount = int(float(str(value)))
    except (TypeError, ValueError) as exc:
        raise JobicyFeedError(f"Invalid Jobicy salary value: {value!r}.") from exc
    return amount if amount > 0 else None


def _string_list(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        values = value
    elif value in (None, ""):
        values = []
    else:
        values = [value]
    return tuple(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


def parse_jobicy_jobs(
    payload: object,
    *,
    limit: int | None = None,
    collected_at: datetime | None = None,
) -> list[Opportunity]:
    """Normalize the official Jobicy public API response."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than or equal to 1.")
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise JobicyFeedError("Jobicy response must contain a jobs array.")

    if collected_at is None:
        collected_at = datetime.now(timezone.utc)
    elif collected_at.tzinfo is None:
        raise ValueError("collected_at must include timezone information.")

    opportunities: list[Opportunity] = []
    for raw_job in payload["jobs"]:
        if not isinstance(raw_job, dict) or not raw_job.get("id"):
            continue

        title = str(raw_job.get("jobTitle") or "").strip()
        url = str(raw_job.get("url") or "").strip()
        if not title or not url:
            raise JobicyFeedError("Jobicy job is missing title or URL.")

        description = html_to_text(str(raw_job.get("jobDescription") or ""))
        details: list[str] = []
        industries = _string_list(raw_job.get("jobIndustry"))
        job_types = _string_list(raw_job.get("jobType"))
        job_level = str(raw_job.get("jobLevel") or "").strip()
        salary_period = str(raw_job.get("salaryPeriod") or "").strip()
        if industries:
            details.append(f"Industries: {', '.join(industries)}")
        if job_types:
            details.append(f"Job types: {', '.join(job_types)}")
        if job_level:
            details.append(f"Level: {job_level}")
        if salary_period:
            details.append(f"Salary period: {salary_period}")

        salary_from = _positive_amount(raw_job.get("salaryMin"))
        salary_to = _positive_amount(raw_job.get("salaryMax"))
        currency = str(raw_job.get("salaryCurrency") or "").strip() or None
        if salary_from is None and salary_to is None:
            currency = None
        elif currency is None:
            raise JobicyFeedError("Jobicy salary currency is missing.")

        opportunities.append(
            Opportunity(
                source="jobicy",
                external_id=str(raw_job["id"]),
                title=title,
                description="\n\n".join(part for part in (description, *details) if part),
                url=url,
                company_name=str(raw_job.get("companyName") or ""),
                location=str(raw_job.get("jobGeo") or ""),
                remote_type=RemoteType.REMOTE,
                salary_from=salary_from,
                salary_to=salary_to,
                currency=currency,
                published_at=_published_at(raw_job.get("pubDate")),
                collected_at=collected_at,
            )
        )
        if limit is not None and len(opportunities) >= limit:
            break

    return opportunities


@dataclass(slots=True)
class JobicyProvider:
    api_url: str
    user_agent: str
    tag: str
    limit: int
    timeout_seconds: int
    transport: httpx.BaseTransport | None = field(default=None, repr=False)

    source = "jobicy"
    # Jobicy asks clients to poll only a few times per day. Fast retries are disabled.
    retry_attempts = 1

    def fetch(self) -> list[Opportunity]:
        params = {"count": str(self.limit)}
        if self.tag:
            params["tag"] = self.tag
        try:
            with httpx.Client(
                headers={"Accept": "application/json", "User-Agent": self.user_agent},
                timeout=float(self.timeout_seconds),
                follow_redirects=True,
                transport=self.transport,
            ) as client:
                response = client.get(self.api_url, params=params)
                response.raise_for_status()
                payload: Any = response.json()
        except httpx.HTTPStatusError as exc:
            raise JobicyError(f"Jobicy API returned HTTP {exc.response.status_code}.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise JobicyError(f"Jobicy API request failed: {exc}") from exc

        if self.tag:
            applied_filters = payload.get("appliedFilters") if isinstance(payload, dict) else None
            applied_tag = applied_filters.get("tag") if isinstance(applied_filters, dict) else None
            if str(applied_tag or "").casefold() != self.tag.casefold():
                raise JobicyFeedError("Jobicy response did not confirm the requested tag filter.")
        return parse_jobicy_jobs(payload, limit=self.limit)
