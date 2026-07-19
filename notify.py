from __future__ import annotations

import sys

from config import SettingsError, settings
from services import NotificationRunner, TelegramBotAPIClient
from storage import OpportunityRepository, StorageError


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _configure_console_encoding()
    try:
        settings.load()
        repository = OpportunityRepository(settings.database_path)
        repository.initialize()
        chat_id = repository.get_paired_chat_id() or settings.telegram_chat_id
        client = TelegramBotAPIClient(
            settings.telegram_token,
            api_base_url=settings.telegram_bot_api_base_url,
            request_timeout_seconds=settings.telegram_request_timeout_seconds,
        )
        result = NotificationRunner(repository, client, chat_id).run(
            minimum_score=settings.min_ai_score,
            batch_size=settings.telegram_notification_batch_size,
        )
    except (SettingsError, StorageError, ValueError) as exc:
        print(f"Notification configuration error: {exc}", file=sys.stderr)
        return 1

    print("========================================")
    print(f"Notifications claimed: {result.claimed}")
    print(f"Notifications sent: {result.sent}")
    print(f"Notifications failed: {result.failed}")
    print("========================================")
    return 0 if result.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
