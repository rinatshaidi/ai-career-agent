from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlparse


class RemoteType(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Opportunity:
    """Provider-independent representation of a work opportunity."""

    source: str
    external_id: str
    title: str
    description: str
    url: str
    company_name: str = ""
    location: str = ""
    remote_type: RemoteType = RemoteType.UNKNOWN
    salary_from: int | None = None
    salary_to: int | None = None
    currency: str | None = None
    published_at: datetime | None = None
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        for field_name in (
            "source",
            "external_id",
            "title",
            "description",
            "url",
            "company_name",
            "location",
        ):
            value = getattr(self, field_name)
            object.__setattr__(self, field_name, value.strip())

        if self.currency is not None:
            normalized_currency = self.currency.strip().upper()
            object.__setattr__(self, "currency", normalized_currency or None)

        required = {
            "source": self.source,
            "external_id": self.external_id,
            "title": self.title,
            "url": self.url,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Opportunity fields cannot be empty: {', '.join(missing)}.")

        parsed_url = urlparse(self.url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("Opportunity url must be an absolute HTTP(S) URL.")

        for field_name in ("salary_from", "salary_to"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} cannot be negative.")

        if (
            self.salary_from is not None
            and self.salary_to is not None
            and self.salary_from > self.salary_to
        ):
            raise ValueError("salary_from cannot be greater than salary_to.")

        if (self.salary_from is not None or self.salary_to is not None) and self.currency is None:
            raise ValueError("currency is required when salary is present.")

        if not isinstance(self.remote_type, RemoteType):
            raise ValueError("remote_type must be a RemoteType value.")

        for field_name in ("published_at", "collected_at"):
            value = getattr(self, field_name)
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{field_name} must include timezone information.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "external_id": self.external_id,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "company_name": self.company_name,
            "location": self.location,
            "remote_type": self.remote_type.value,
            "salary_from": self.salary_from,
            "salary_to": self.salary_to,
            "currency": self.currency,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "collected_at": self.collected_at.isoformat(),
        }
