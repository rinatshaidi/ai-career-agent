from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx

from models import Opportunity, RemoteType
from providers.base import ProviderError


_TITLE_PATTERN = re.compile(
    r"^\u0422\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f\s+\u00ab(?P<title>.+?)\u00bb(?:\s+\(.+\))?$"
)
_LOCATION_PATTERN = re.compile(
    r"(?P<location>[^.!?]{2,80}?)\s+\((?:"
    r"\u0420\u043e\u0441\u0441\u0438\u044f|\u0411\u0435\u043b\u0430\u0440\u0443\u0441\u044c|"
    r"\u041a\u0430\u0437\u0430\u0445\u0441\u0442\u0430\u043d|\u0410\u0440\u043c\u0435\u043d\u0438\u044f|"
    r"\u0413\u0440\u0443\u0437\u0438\u044f|\u0423\u0437\u0431\u0435\u043a\u0438\u0441\u0442\u0430\u043d|"
    r"\u0421\u0435\u0440\u0431\u0438\u044f)\)\."
)
_SALARY_RANGE_PATTERN = re.compile(
    r"\u043e\u0442\s+(?P<from>\d[\d\s\u00a0]*)\s*(?P<currency_from>[\u20bd$\u20ac])?\s+"
    r"\u0434\u043e\s+(?P<to>\d[\d\s\u00a0]*)\s*(?P<currency_to>[\u20bd$\u20ac])",
    re.IGNORECASE,
)
_SALARY_FROM_PATTERN = re.compile(
    r"\u043e\u0442\s+(?P<from>\d[\d\s\u00a0]*)\s*(?P<currency>[\u20bd$\u20ac])",
    re.IGNORECASE,
)
_SALARY_TO_PATTERN = re.compile(
    r"\u0434\u043e\s+(?P<to>\d[\d\s\u00a0]*)\s*(?P<currency>[\u20bd$\u20ac])",
    re.IGNORECASE,
)
_CURRENCY_CODES = {"\u20bd": "RUB", "$": "USD", "\u20ac": "EUR"}


class HabrCareerError(ProviderError):
    """Base error raised by the Habr Career provider."""


class HabrCareerFeedError(HabrCareerError):
    """Raised when the RSS response cannot be normalized safely."""


def _required_text(item: ElementTree.Element, tag: str) -> str:
    value = item.findtext(tag, default="").strip()
    if not value:
        raise HabrCareerFeedError(f"Habr Career RSS item is missing required field: {tag}.")
    return value


def _published_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        published_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise HabrCareerFeedError(f"Invalid Habr Career publication date: {value!r}.") from exc
    if published_at.tzinfo is None:
        raise HabrCareerFeedError("Habr Career publication date must include a timezone.")
    return published_at


def _normalize_title(raw_title: str) -> str:
    match = _TITLE_PATTERN.fullmatch(raw_title)
    return match.group("title").strip() if match else raw_title.strip()


def _normalize_location(description: str) -> str:
    match = _LOCATION_PATTERN.search(description)
    return match.group("location").strip() if match else ""


def _normalize_remote_type(description: str) -> RemoteType:
    lowered = description.casefold()
    if "\u043c\u043e\u0436\u043d\u043e \u0443\u0434\u0430\u043b\u0451\u043d\u043d\u043e" in lowered or "\u043c\u043e\u0436\u043d\u043e \u0443\u0434\u0430\u043b\u0435\u043d\u043d\u043e" in lowered:
        return RemoteType.REMOTE
    if "\u0433\u0438\u0431\u0440\u0438\u0434" in lowered:
        return RemoteType.HYBRID
    if "\u0442\u043e\u043b\u044c\u043a\u043e \u043e\u0444\u0438\u0441" in lowered or "\u0440\u0430\u0431\u043e\u0442\u0430 \u0432 \u043e\u0444\u0438\u0441\u0435" in lowered:
        return RemoteType.ONSITE
    return RemoteType.UNKNOWN


def _amount(value: str) -> int:
    return int(re.sub(r"\D", "", value))


def _normalize_salary(text: str) -> tuple[int | None, int | None, str | None]:
    range_match = _SALARY_RANGE_PATTERN.search(text)
    if range_match:
        currency_symbol = range_match.group("currency_to") or range_match.group("currency_from")
        return (
            _amount(range_match.group("from")),
            _amount(range_match.group("to")),
            _CURRENCY_CODES[currency_symbol],
        )

    from_match = _SALARY_FROM_PATTERN.search(text)
    if from_match:
        return _amount(from_match.group("from")), None, _CURRENCY_CODES[from_match.group("currency")]

    to_match = _SALARY_TO_PATTERN.search(text)
    if to_match:
        return None, _amount(to_match.group("to")), _CURRENCY_CODES[to_match.group("currency")]

    return None, None, None


def parse_vacancies_rss(
    xml_text: str,
    *,
    limit: int | None = None,
    collected_at: datetime | None = None,
) -> list[Opportunity]:
    """Parse the official Habr Career RSS into normalized opportunities."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than or equal to 1.")

    if collected_at is None:
        collected_at = datetime.now(timezone.utc)
    elif collected_at.tzinfo is None:
        raise ValueError("collected_at must include timezone information.")

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise HabrCareerFeedError("Habr Career returned malformed RSS XML.") from exc

    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise HabrCareerFeedError("Habr Career response is not an RSS 2.0 feed.")

    opportunities: list[Opportunity] = []
    for item in channel.findall("item"):
        raw_title = _required_text(item, "title")
        description = item.findtext("description", default="").strip()
        salary_from, salary_to, currency = _normalize_salary(f"{raw_title} {description}")
        opportunities.append(
            Opportunity(
                source="habr_career",
                external_id=_required_text(item, "guid"),
                title=_normalize_title(raw_title),
                description=description,
                url=_required_text(item, "link"),
                company_name=item.findtext("author", default="").strip(),
                location=_normalize_location(description),
                remote_type=_normalize_remote_type(description),
                salary_from=salary_from,
                salary_to=salary_to,
                currency=currency,
                published_at=_published_at(item.findtext("pubDate", default="").strip()),
                collected_at=collected_at,
            )
        )
        if limit is not None and len(opportunities) >= limit:
            break

    return opportunities


@dataclass(slots=True)
class HabrCareerProvider:
    feed_url: str
    user_agent: str
    limit: int
    timeout_seconds: int
    transport: httpx.BaseTransport | None = field(default=None, repr=False)

    source = "habr_career"

    def fetch(self) -> list[Opportunity]:
        headers = {
            "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8",
            "User-Agent": self.user_agent,
        }
        try:
            with httpx.Client(
                headers=headers,
                timeout=float(self.timeout_seconds),
                follow_redirects=True,
                transport=self.transport,
            ) as client:
                response = client.get(self.feed_url)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HabrCareerError(
                f"Habr Career RSS returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise HabrCareerError(f"Habr Career RSS request failed: {exc}") from exc

        return parse_vacancies_rss(response.text, limit=self.limit)
