from __future__ import annotations

import unittest
from pathlib import Path
from uuid import uuid4

from services import ProfileBotRunner, TelegramProfileBot
from storage import OpportunityRepository


class FakeTelegramClient:
    def __init__(self) -> None:
        self.messages = []
        self.answered_callbacks = []
        self.updates = []
        self.requested_offset = None

    def get_updates(self, *, offset, timeout):
        self.requested_offset = offset
        return list(self.updates)

    def send_message(self, chat_id, text, *, reply_markup=None):
        self.messages.append((str(chat_id), text, reply_markup))

    def answer_callback_query(self, callback_query_id):
        self.answered_callbacks.append(callback_query_id)


def message(update_id: int, chat_id: str, text: str) -> dict:
    return {
        "update_id": update_id,
        "message": {"chat": {"id": int(chat_id)}, "text": text},
    }


def callback(update_id: int, chat_id: str, data: str) -> dict:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"callback-{update_id}",
            "data": data,
            "message": {"chat": {"id": int(chat_id)}},
        },
    }


class TelegramProfileBotTests(unittest.TestCase):
    chat_id = "12345"
    test_data_root = Path(__file__).resolve().parents[1] / "data"

    def setUp(self) -> None:
        self.test_data_root.mkdir(exist_ok=True)
        self.database_path = self.test_data_root / f"test-{uuid4().hex}.db"
        self.repository = OpportunityRepository(self.database_path)
        self.repository.initialize()
        self.client = FakeTelegramClient()
        self.bot = TelegramProfileBot(
            self.repository,
            self.client,
            allowed_chat_id=self.chat_id,
        )

    def tearDown(self) -> None:
        for suffix in ("", "-shm", "-wal"):
            path = Path(f"{self.database_path}{suffix}")
            if path.exists():
                path.unlink()

    def test_completes_and_saves_profile_questionnaire(self) -> None:
        updates = [
            message(1, self.chat_id, "/start"),
            callback(2, self.chat_id, "profile:start"),
            message(3, self.chat_id, "AI automation специалист"),
            message(4, self.chat_id, "n8n\nAPI integrations\nTelegram bots"),
            message(5, self.chat_id, "Автоматизация бизнеса\nНебольшие проекты"),
            message(6, self.chat_id, "Холодные продажи"),
            message(7, self.chat_id, "Удалённо\nОт 10 000 рублей"),
            callback(8, self.chat_id, "profile:confirm"),
        ]
        for update in updates:
            self.bot.handle_update(update)

        profile = self.repository.get_user_profile(self.chat_id)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.positioning, "AI automation специалист")
        self.assertEqual(profile.skills[0], "n8n")
        self.assertIn("Удалённо", profile.preferences)
        self.assertIsNone(self.repository.get_profile_session(self.chat_id))
        self.assertIn("Профиль сохранён", "\n".join(item[1] for item in self.client.messages))

    def test_ignores_another_chat(self) -> None:
        self.bot.handle_update(message(1, "99999", "/start"))
        self.assertEqual(self.client.messages, [])
        self.assertIsNone(self.repository.get_profile_session("99999"))

    def test_runner_persists_update_offset(self) -> None:
        self.client.updates = [message(10, self.chat_id, "/start")]
        runner = ProfileBotRunner(self.repository, self.client, self.bot)
        self.assertEqual(runner.run_once(timeout=0), 1)
        self.assertEqual(self.repository.get_bot_offset(), 11)


if __name__ == "__main__":
    unittest.main()
