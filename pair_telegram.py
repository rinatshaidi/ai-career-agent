from __future__ import annotations

import sys
from typing import Any

from config import SettingsError, settings
from services import TelegramAPIError, TelegramBotAPIClient
from storage import OpportunityRepository, StorageError


def _private_start(update: dict[str, Any]) -> tuple[int, int] | None:
    update_id = update.get("update_id")
    message = update.get("message")
    if not isinstance(update_id, int) or not isinstance(message, dict):
        return None
    text = message.get("text")
    chat = message.get("chat")
    if not isinstance(text, str) or text.split(maxsplit=1)[0].lower() != "/start":
        return None
    if not isinstance(chat, dict) or chat.get("type") != "private":
        return None
    chat_id = chat.get("id")
    if not isinstance(chat_id, int):
        return None
    return update_id, chat_id


def main() -> int:
    try:
        settings.load()
        repository = OpportunityRepository(settings.database_path)
        repository.initialize()
        client = TelegramBotAPIClient(
            settings.telegram_token,
            settings.telegram_bot_api_base_url,
            settings.telegram_request_timeout_seconds,
        )
        updates = client.get_updates(offset=repository.get_bot_offset(), timeout=0)
        starts = [result for update in updates if (result := _private_start(update))]
        if not starts:
            print("No pending private /start command found.", file=sys.stderr)
            return 2
        update_id, chat_id = starts[-1]
        repository.set_paired_chat_id(chat_id)
        repository.set_bot_offset(update_id + 1)
    except (SettingsError, StorageError, TelegramAPIError, ValueError) as exc:
        print(f"Telegram pairing error: {exc}", file=sys.stderr)
        return 1

    print("Telegram private chat paired successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
