from __future__ import annotations

from providers.trudvsem import TrudvsemProvider


def main() -> None:
    provider = TrudvsemProvider(
        api_url="https://opendata.trudvsem.ru/api/v1/vacancies",
        user_agent="JobMonitor/0.8 smoke-check",
        search_queries=("автоматизация бизнеса",),
        region_codes=(),
        per_query_limit=3,
        limit=3,
        initial_lookback_days=30,
        timeout_seconds=20,
    )
    opportunities = provider.fetch()
    normalized = all(item.source == "rabota_rossii" for item in opportunities)
    print(f"count={len(opportunities)}")
    print(f"normalized={str(normalized).lower()}")


if __name__ == "__main__":
    main()
