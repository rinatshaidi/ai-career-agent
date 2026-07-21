from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import httpx

from models import Opportunity, RemoteType
from providers.base import ProviderError
from providers.text import html_to_text


class TrudvsemError(ProviderError):
    """Base error raised by the official Rabota Rossii API provider."""


class TrudvsemFeedError(TrudvsemError):
    """Raised when the Rabota Rossii response cannot be normalized safely."""


_REMOTE_PHRASES = (
    "дистанционная работа",
    "дистанционный формат",
    "полностью дистанционно",
    "удаленная работа",
    "удалённая работа",
    "удаленный формат работы",
    "удалённый формат работы",
    "работа удаленно",
    "работа удалённо",
    "работа из дома",
    "fully remote",
    "remote work",
)
_HYBRID_PHRASES = (
    "гибридная работа",
    "гибридный формат",
    "частично дистанционно",
    "частично удаленно",
    "частично удалённо",
)


def parse_search_queries(value: str) -> tuple[str, ...]:
    """Parse a semicolon-delimited list while preserving query phrases."""
    return tuple(dict.fromkeys(part.strip() for part in value.split(";") if part.strip()))


def parse_region_codes(value: str) -> tuple[str, ...]:
    """Parse optional numeric Rabota Rossii region codes."""
    regions = tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))
    invalid = [region for region in regions if not region.isdigit()]
    if invalid:
        raise ValueError("TRUDVSEM_REGION_CODES must contain comma-separated numeric codes.")
    return regions


def _published_at(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TrudvsemFeedError(f"Invalid Rabota Rossii publication date: {value!r}.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _positive_integer(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(float(str(value).replace(" ", "").replace(",", ".")))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _currency(value: object) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if "руб" in text or text in {"rur", "rub"}:
        return "RUB"
    if "дол" in text or text == "usd":
        return "USD"
    if "евро" in text or text == "eur":
        return "EUR"
    normalized = "".join(character for character in text.upper() if character.isalpha())
    return normalized[:8] or None


def _locations(raw_job: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    region = raw_job.get("region")
    if isinstance(region, dict) and str(region.get("name") or "").strip():
        values.append(str(region["name"]).strip())

    addresses = raw_job.get("addresses")
    if isinstance(addresses, dict):
        address_items = addresses.get("address")
        if isinstance(address_items, list):
            for address in address_items:
                if isinstance(address, dict):
                    location = str(address.get("location") or "").strip()
                    if location:
                        values.append(location)
    return tuple(dict.fromkeys(values))


def _remote_type(raw_job: dict[str, Any], description: str, locations: tuple[str, ...]) -> RemoteType:
    schedule = str(raw_job.get("schedule") or "")
    haystack = f"{schedule}\n{description}".casefold()
    if any(phrase in haystack for phrase in _HYBRID_PHRASES):
        return RemoteType.HYBRID
    if any(phrase in haystack for phrase in _REMOTE_PHRASES):
        return RemoteType.REMOTE
    if locations:
        return RemoteType.ONSITE
    return RemoteType.UNKNOWN


def _description(raw_job: dict[str, Any]) -> str:
    parts: list[str] = []
    for label, key in (
        ("Обязанности", "duty"),
        ("Требования", "requirements"),
        ("Квалификация", "qualification"),
        ("График", "schedule"),
    ):
        value = html_to_text(str(raw_job.get(key) or ""))
        if value:
            parts.append(f"{label}: {value}")

    skills = raw_job.get("skills")
    if isinstance(skills, list):
        skill_names = [
            str(skill.get("skill_name") or skill.get("name") or "").strip()
            for skill in skills
            if isinstance(skill, dict)
        ]
        skill_names = list(dict.fromkeys(value for value in skill_names if value))
        if skill_names:
            parts.append(f"Навыки: {', '.join(skill_names)}")
    return "\n\n".join(parts)


def parse_trudvsem_jobs(
    payload: object,
    *,
    limit: int | None = None,
    collected_at: datetime | None = None,
) -> list[Opportunity]:
    """Normalize an official Rabota Rossii open-data API response."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than or equal to 1.")
    if not isinstance(payload, dict) or str(payload.get("status")) != "200":
        raise TrudvsemFeedError("Rabota Rossii response has an unsuccessful status.")
    results = payload.get("results")
    if not isinstance(results, dict):
        raise TrudvsemFeedError("Rabota Rossii response must contain a results object.")
    vacancies = results.get("vacancies", [])
    if not isinstance(vacancies, list):
        raise TrudvsemFeedError("Rabota Rossii vacancies must be an array when present.")

    if collected_at is None:
        collected_at = datetime.now(timezone.utc)
    elif collected_at.tzinfo is None:
        raise ValueError("collected_at must include timezone information.")

    opportunities: list[Opportunity] = []
    for wrapper in vacancies:
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("vacancy"), dict):
            continue
        raw_job = wrapper["vacancy"]
        external_id = str(raw_job.get("id") or "").strip()
        if not external_id:
            continue
        title = str(raw_job.get("job-name") or "").strip()
        url = str(raw_job.get("vac_url") or "").strip()
        if not title or not url:
            raise TrudvsemFeedError("Rabota Rossii vacancy is missing title or URL.")

        company = raw_job.get("company")
        company_name = (
            str(company.get("name") or "").strip() if isinstance(company, dict) else ""
        )
        locations = _locations(raw_job)
        description = _description(raw_job)
        salary_from = _positive_integer(raw_job.get("salary_min"))
        salary_to = _positive_integer(raw_job.get("salary_max"))
        currency = _currency(raw_job.get("currency")) if salary_from or salary_to else None

        opportunities.append(
            Opportunity(
                source="rabota_rossii",
                external_id=external_id,
                title=title,
                description=description,
                url=url,
                company_name=company_name,
                location="; ".join(locations),
                remote_type=_remote_type(raw_job, description, locations),
                salary_from=salary_from,
                salary_to=salary_to,
                currency=currency,
                published_at=_published_at(
                    raw_job.get("date_modify") or raw_job.get("creation-date")
                ),
                collected_at=collected_at,
            )
        )
        if limit is not None and len(opportunities) >= limit:
            break
    return opportunities


@dataclass(slots=True)
class TrudvsemProvider:
    api_url: str
    user_agent: str
    search_queries: tuple[str, ...]
    region_codes: tuple[str, ...]
    per_query_limit: int
    limit: int
    initial_lookback_days: int
    timeout_seconds: int
    transport: httpx.BaseTransport | None = field(default=None, repr=False)
    now: Callable[[], datetime] = field(
        default=lambda: datetime.now(timezone.utc), repr=False
    )

    source = "rabota_rossii"

    def fetch(self) -> list[Opportunity]:
        return self.fetch_since(None)

    def fetch_since(self, last_success_at: datetime | None) -> list[Opportunity]:
        if not self.search_queries:
            raise TrudvsemError("TRUDVSEM_SEARCH_QUERIES must contain at least one query.")

        current = self.now()
        if current.tzinfo is None:
            raise TrudvsemError("Provider clock must include timezone information.")
        since = (
            last_success_at.astimezone(timezone.utc) - timedelta(minutes=5)
            if last_success_at is not None
            else current.astimezone(timezone.utc) - timedelta(days=self.initial_lookback_days)
        )
        modified_from = since.isoformat(timespec="seconds")
        regions: tuple[str | None, ...] = self.region_codes or (None,)
        collected: dict[str, Opportunity] = {}

        try:
            with httpx.Client(
                headers={"Accept": "application/json", "User-Agent": self.user_agent},
                timeout=float(self.timeout_seconds),
                follow_redirects=True,
                transport=self.transport,
            ) as client:
                for query in self.search_queries:
                    for region in regions:
                        endpoint = self.api_url.rstrip("/")
                        if region is not None:
                            endpoint = f"{endpoint}/region/{region}"
                        response = client.get(
                            endpoint,
                            params={
                                "text": query,
                                "limit": str(self.per_query_limit),
                                "offset": "1",
                                "modifiedFrom": modified_from,
                            },
                        )
                        response.raise_for_status()
                        payload: Any = response.json()
                        for opportunity in parse_trudvsem_jobs(payload):
                            collected[opportunity.external_id] = opportunity
        except httpx.HTTPStatusError as exc:
            raise TrudvsemError(
                f"Rabota Rossii API returned HTTP {exc.response.status_code}."
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise TrudvsemError(f"Rabota Rossii API request failed: {exc}") from exc

        return sorted(
            collected.values(),
            key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[: self.limit]
