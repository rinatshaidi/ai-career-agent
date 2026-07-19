from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from config import Settings, SettingsError
from storage import OpportunityRepository, StorageError


def heartbeat_is_fresh(
    repository: OpportunityRepository,
    service_name: str,
    *,
    maximum_age_seconds: int,
    now: datetime | None = None,
) -> bool:
    heartbeat = repository.get_service_heartbeat(service_name)
    if heartbeat is None:
        return False
    current = now or datetime.now(timezone.utc)
    if heartbeat.tzinfo is None:
        return False
    age = (current - heartbeat.astimezone(timezone.utc)).total_seconds()
    return 0 <= age <= maximum_age_seconds


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check JobMonitor service health.")
    parser.add_argument("service", choices=("worker", "profile_bot"))
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    try:
        settings = Settings().load()
        repository = OpportunityRepository(settings.database_path)
        repository.initialize()
        if args.service == "worker":
            maximum_age = max(settings.check_interval_seconds * 2 + 300, 600)
        else:
            maximum_age = max(settings.telegram_poll_timeout_seconds * 4 + 60, 180)
        healthy = heartbeat_is_fresh(
            repository,
            args.service,
            maximum_age_seconds=maximum_age,
        )
    except (SettingsError, StorageError, ValueError):
        return 1
    if healthy:
        print("healthy")
        return 0
    print("unhealthy", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
