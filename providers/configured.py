from __future__ import annotations

from typing import Any

from providers.base import OpportunityProvider
from providers.greenhouse import GreenhouseProvider, parse_greenhouse_boards
from providers.habr import HabrCareerProvider
from providers.jobicy import JobicyProvider
from providers.remotive import RemotiveProvider
from providers.remoteok import RemoteOKProvider
from providers.trudvsem import TrudvsemProvider, parse_region_codes, parse_search_queries
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
    if settings.remotive_enabled:
        providers.append(
            RemotiveProvider(
                api_url=settings.remotive_api_url,
                user_agent=settings.remotive_user_agent,
                limit=settings.remotive_vacancy_limit,
                timeout_seconds=settings.http_timeout_seconds,
            )
        )
    if settings.greenhouse_enabled:
        boards = parse_greenhouse_boards(settings.greenhouse_boards)
        if not boards:
            raise ValueError("GREENHOUSE_BOARDS must contain at least one board when enabled.")
        providers.extend(
            GreenhouseProvider(
                api_base_url=settings.greenhouse_api_base_url,
                board=board,
                user_agent=settings.greenhouse_user_agent,
                limit=settings.greenhouse_vacancy_limit,
                timeout_seconds=settings.http_timeout_seconds,
            )
            for board in boards
        )
    if settings.trudvsem_enabled:
        queries = parse_search_queries(settings.trudvsem_search_queries)
        if not queries:
            raise ValueError(
                "TRUDVSEM_SEARCH_QUERIES must contain at least one query when enabled."
            )
        providers.append(
            TrudvsemProvider(
                api_url=settings.trudvsem_api_url,
                user_agent=settings.trudvsem_user_agent,
                search_queries=queries,
                region_codes=parse_region_codes(settings.trudvsem_region_codes),
                per_query_limit=settings.trudvsem_per_query_limit,
                limit=settings.trudvsem_vacancy_limit,
                initial_lookback_days=settings.trudvsem_initial_lookback_days,
                timeout_seconds=settings.http_timeout_seconds,
            )
        )
    if settings.jobicy_enabled:
        providers.append(
            JobicyProvider(
                api_url=settings.jobicy_api_url,
                user_agent=settings.jobicy_user_agent,
                tag=settings.jobicy_tag,
                limit=settings.jobicy_vacancy_limit,
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
    if settings.remotive_enabled:
        intervals[RemotiveProvider.source] = settings.remotive_poll_interval_seconds
    if settings.greenhouse_enabled:
        boards = parse_greenhouse_boards(settings.greenhouse_boards)
        if not boards:
            raise ValueError("GREENHOUSE_BOARDS must contain at least one board when enabled.")
        for board in boards:
            intervals[f"greenhouse_{board.token}"] = settings.greenhouse_poll_interval_seconds
    if settings.trudvsem_enabled:
        intervals[TrudvsemProvider.source] = settings.trudvsem_poll_interval_seconds
    if settings.jobicy_enabled:
        intervals[JobicyProvider.source] = settings.jobicy_poll_interval_seconds
    return intervals
