from __future__ import annotations

import argparse
import sys

from config import SettingsError, settings
from services import (
    ProfileBotRunner,
    BOT_COMMANDS,
    TelegramAPIError,
    TelegramBotAPIClient,
    TelegramProfileBot,
)
from storage import OpportunityRepository, StorageError


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the JobMonitor Telegram profile bot.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Request one batch of updates and exit.",
    )
    return parser.parse_args()


def main() -> int:
    _configure_console_encoding()
    args = _arguments()
    try:
        settings.load()
        repository = OpportunityRepository(settings.database_path)
        repository.initialize()
        client = TelegramBotAPIClient(
            token=settings.telegram_token,
            api_base_url=settings.telegram_bot_api_base_url,
            request_timeout_seconds=settings.telegram_request_timeout_seconds,
        )
        client.get_me()
        webhook = client.get_webhook_info()
        if webhook.get("url"):
            raise TelegramAPIError(
                "This bot already has a webhook. JobMonitor will not replace it automatically."
            )
        client.set_my_commands(BOT_COMMANDS)
        handler = TelegramProfileBot(
            repository,
            client,
            allowed_chat_id=repository.get_paired_chat_id() or settings.telegram_chat_id,
        )
        runner = ProfileBotRunner(repository, client, handler)
        print("JobMonitor Telegram profile bot is running.")
        if args.once:
            runner.run_once(timeout=0)
            return 0
        while True:
            runner.run_once(timeout=settings.telegram_poll_timeout_seconds)
    except KeyboardInterrupt:
        print("JobMonitor Telegram profile bot stopped.")
        return 0
    except (SettingsError, StorageError, TelegramAPIError, ValueError) as exc:
        print(f"Telegram profile bot error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
