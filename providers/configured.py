from __future__ import annotations

from typing import Any

from providers.base import OpportunityProvider
from providers.habr import HabrCareerProvider
from providers.remoteok import RemoteOKProvider
from providers.weworkremotely import WeWorkRemotelyProvider


def configured_providers(settings: Any) -> tuple[OpportunityProvider, ...]:
    """Build all production providers from validated application settings."""
    providers: list[OpportunityProvider] = []
    if settings.habr_enabled:
        providers.append(
            HabrCareerProvider(
                feed_url=settings.habr_rss_url,
                user_agent=settings.habr_user_agent,
                limit=settings.habr_vacancy_limit,
                timeout_seconds=settings.http_timeout_seconds,
            )
        )
    if settings.remoteok_enabled:
        providers.append(
            RemoteOKProvider(
                api_url=settings.remoteok_api_url,
                user_agent=settings.remoteok_user_agent,
                limit=settings.remoteok_vacancy_limit,
                timeout_seconds=settings.http_timeout_seconds,
            )
        )
    if settings.wwr_enabled:
        providers.append(
            WeWorkRemotelyProvider(
                feed_url=settings.wwr_rss_url,
                user_agent=settings.wwr_user_agent,
                limit=settings.wwr_vacancy_limit,
                timeout_seconds=settings.http_timeout_seconds,
            )
        )
    return tuple(providers)


def configured_provider_intervals(settings: Any) -> dict[str, int]:
    """Return polling intervals for enabled production providers."""
    intervals: dict[str, int] = {}
    if settings.habr_enabled:
        intervals[HabrCareerProvider.source] = settings.habr_poll_interval_seconds
    if settings.remoteok_enabled:
        intervals[RemoteOKProvider.source] = settings.remoteok_poll_interval_seconds
    if settings.wwr_enabled:
        intervals[WeWorkRemotelyProvider.source] = settings.wwr_poll_interval_seconds
    return intervals
