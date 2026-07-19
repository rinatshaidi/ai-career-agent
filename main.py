from __future__ import annotations

import sys

from config import SettingsError, settings
from models import Opportunity
from providers.base import ProviderError
from providers.configured import configured_providers
from storage import OpportunityRepository, StorageError


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _format_salary(opportunity: Opportunity) -> str:
    currency = opportunity.currency or ""
    if opportunity.salary_from is not None and opportunity.salary_to is not None:
        return f"{opportunity.salary_from:,}-{opportunity.salary_to:,} {currency}".replace(",", " ")
    if opportunity.salary_from is not None:
        return f"from {opportunity.salary_from:,} {currency}".replace(",", " ")
    if opportunity.salary_to is not None:
        return f"up to {opportunity.salary_to:,} {currency}".replace(",", " ")
    return "N/A"


def main() -> int:
    _configure_console_encoding()
    try:
        settings.load()
    except SettingsError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    opportunities: list[Opportunity] = []
    provider_results: list[tuple[str, int]] = []
    for provider in configured_providers(settings):
        try:
            received = provider.fetch()
        except ProviderError as exc:
            print(f"Provider error ({provider.source}): {exc}", file=sys.stderr)
            continue
        opportunities.extend(received)
        provider_results.append((provider.source, len(received)))
    if not provider_results:
        return 1

    repository = OpportunityRepository(settings.database_path)
    try:
        repository.initialize()
        save_result = repository.add_many(opportunities)
        total_stored = repository.count()
    except (OSError, StorageError) as exc:
        print(f"Storage error: {exc}", file=sys.stderr)
        return 1

    print("========================================")
    for source, received_count in provider_results:
        print(f"{source} connection OK: {received_count}")
    print(f"Opportunities received: {len(opportunities)}")
    print(f"New opportunities saved: {save_result.inserted_count}")
    print(f"Duplicates skipped: {save_result.duplicate_count}")
    print(f"Total opportunities stored: {total_stored}")
    print("========================================")

    for opportunity in save_result.inserted:
        print("----------------------------------------")
        print(f"Title: {opportunity.title}")
        print(f"Company: {opportunity.company_name or 'N/A'}")
        print(f"Location: {opportunity.location or 'N/A'}")
        print(f"Remote type: {opportunity.remote_type.value}")
        print(f"Salary: {_format_salary(opportunity)}")
        published_at = opportunity.published_at.isoformat() if opportunity.published_at else "N/A"
        print(f"Published: {published_at}")
        print(f"URL: {opportunity.url}")
        print("----------------------------------------")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
