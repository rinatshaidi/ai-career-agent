from __future__ import annotations

from providers.jobicy import JobicyProvider


def main() -> None:
    provider = JobicyProvider(
        api_url="https://jobicy.com/api/v2/remote-jobs",
        user_agent="JobMonitor/0.8 smoke-check",
        tag="automation",
        limit=3,
        timeout_seconds=20,
    )
    opportunities = provider.fetch()
    print(f"count={len(opportunities)}")
    print(f"normalized={str(all(item.source == 'jobicy' for item in opportunities)).lower()}")


if __name__ == "__main__":
    main()
