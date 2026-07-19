from __future__ import annotations

from typing import Protocol, runtime_checkable

from models import Opportunity


class ProviderError(RuntimeError):
    """Base error for recoverable external provider failures."""


@runtime_checkable
class OpportunityProvider(Protocol):
    """Contract implemented by every opportunity source."""

    source: str

    def fetch(self) -> list[Opportunity]:
        """Return the latest opportunities normalized to the domain model."""
        ...
