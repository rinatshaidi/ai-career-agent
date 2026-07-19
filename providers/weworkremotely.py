from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx

from models import Opportunity, RemoteType
from providers.base import ProviderError
from providers.text import html_to_text


class WeWorkRemotelyError(ProviderError):
    """Base error raised by the We Work Remotely provider."""


class WeWorkRemotelyFeedError(WeWorkRemotelyError):
    """Raised when the public RSS feed cannot be normalized safely."""


def _required_text(item: ElementTree.Element, tag: str) -> str:
    value = item.findtext(tag, default="").strip()
    if not value:
        raise WeWorkRemotelyFeedError(f"We Work Remotely item is missing required field: {tag}.")
    return value


def _published_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise WeWorkRemotelyFeedError(
            f"Invalid We Work Remotely publication date: {value!r}."
        ) from exc
    if parsed.tzinfo is None:
        raise WeWorkRemotelyFeedError(
            "We Work Remotely publication date must include a timezone."
        )
    return parsed


def _title_and_company(raw_title: str) -> tuple[str, str]:
    company, separator, title = raw_title.partition(":")
    if separator and company.strip() and title.strip():
        return title.strip(), company.strip()
    return raw_title.strip(), ""


def parse_weworkremotely_rss(
    xml_text: str,
    *,
    limit: int | None = None,
    collected_at: datetime | None = None,
) -> list[Opportunity]:
    """Normalize the official We Work Remotely public RSS feed."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than or equal to 1.")
    if collected_at is None:
        collected_at = datetime.now(timezone.utc)
    elif collected_at.tzinfo is None:
        raise ValueError("collected_at must include timezone information.")

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise WeWorkRemotelyFeedError("We Work Remotely returned malformed RSS XML.") from exc
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise WeWorkRemotelyFeedError("We Work Remotely response is not an RSS 2.0 feed.")

    opportunities: list[Opportunity] = []
    for item in channel.findall("item"):
        title, company = _title_and_company(_required_text(item, "title"))
        description = html_to_text(item.findtext("description", default=""))
        metadata = [
            value
            for value in (
                item.findtext("category", default="").strip(),
                item.findtext("type", default="").strip(),
            )
            if value
        ]
        if metadata:
            description = f"{description}\n\nCategory: {'; '.join(metadata)}".strip()
        opportunities.append(
            Opportunity(
                source="we_work_remotely",
                external_id=_required_text(item, "guid"),
                title=title,
                description=description,
                url=_required_text(item, "link"),
                company_name=company,
                location=item.findtext("region", default="").strip(),
                remote_type=RemoteType.REMOTE,
                published_at=_published_at(item.findtext("pubDate", default="").strip()),
                collected_at=collected_at,
            )
        )
        if limit is not None and len(opportunities) >= limit:
            break

    return opportunities


@dataclass(slots=True)
class WeWorkRemotelyProvider:
    feed_url: str
    user_agent: str
    limit: int
    timeout_seconds: int
    transport: httpx.BaseTransport | None = field(default=None, repr=False)

    source = "we_work_remotely"

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
            raise WeWorkRemotelyError(
                f"We Work Remotely RSS returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise WeWorkRemotelyError(f"We Work Remotely RSS request failed: {exc}") from exc

        return parse_weworkremotely_rss(response.text, limit=self.limit)
