from __future__ import annotations

import unittest
from pathlib import Path
from uuid import uuid4

from services import ProfileBotRunner, TelegramProfileBot
from storage import OpportunityRepository


class FakeTelegramClient:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, dict | None]] = []
        self.answered_callbacks: list[str] = []
        self.updates: list[dict] = []
        self.requested_offset = None

    def get_updates(self, *, offset, timeout):
        self.requested_offset = offset
        return list(self.updates)

    def send_message(self, chat_id, text, *, reply_markup=None):
        self.messages.append((str(chat_id), text, reply_markup))

    def answer_callback_query(self, callback_query_id):
        self.answered_callbacks.append(callback_query_id)


def message(update_id: int, chat_id: str, text: str) -> dict:
    return {"update_id": update_id, "message": {"chat": {"id": int(chat_id)}, "text": text}}


def callback(update_id: int, chat_id: str, data: str) -> dict:
    return {
        "update_id": update_id,
        "callback_query": {"id": f"callback-{update_id}", "data": data, "message": {"chat": {"id": int(chat_id)}}},
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
        self.bot = TelegramProfileBot(self.repository, self.client, allowed_chat_id=self.chat_id)

    def tearDown(self) -> None:
        for suffix in ("", "-shm", "-wal"):
            path = Path(f"{self.database_path}{suffix}")
            if path.exists():
                path.unlink()

    def test_completes_and_saves_two_free_text_search_tracks(self) -> None:
        self.bot.handle_update(callback(1, self.chat_id, "profile:start"))
        answers = [
            "Business automation and project delivery",
            "Russian and English",
            "Cold sales",
            "Automation consulting",
            "Automation projects for small businesses",
            "automation specialist; integration engineer",
            "n8n; APIs; Telegram bots",
            "design workflows; automate reporting",
            "Remote; Russia; international market",
            "junior AI roles",
        ]
        for update_id, answer in enumerate(answers, start=2):
            self.bot.handle_update(message(update_id, self.chat_id, answer))
        self.bot.handle_update(callback(20, self.chat_id, "profile:add_track"))
        second_track = [
            "Infrastructure projects",
            "Commercial development projects",
            "project development; partnerships",
            "business development; negotiations",
            "launch projects; coordinate partners",
            "Moscow; Russia; relocation",
            "investment projects",
        ]
        for update_id, answer in enumerate(second_track, start=21):
            self.bot.handle_update(message(update_id, self.chat_id, answer))
        self.bot.handle_update(callback(30, self.chat_id, "profile:finish_tracks"))
        self.bot.handle_update(callback(31, self.chat_id, "profile:confirm"))

        profile = self.repository.get_user_profile(self.chat_id)
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(len(profile.search_tracks), 2)
        self.assertEqual(profile.search_tracks[0].name, "Automation consulting")
        self.assertIn("n8n", profile.search_tracks[0].skills_and_experience)
        self.assertEqual(profile.search_tracks[1].locations[0], "Moscow")
        self.assertIsNone(self.repository.get_profile_session(self.chat_id))

    def test_required_answer_cannot_be_skipped(self) -> None:
        self.bot.handle_update(callback(1, self.chat_id, "profile:start"))
        self.bot.handle_update(callback(2, self.chat_id, "profile:skip"))
        session = self.repository.get_profile_session(self.chat_id)
        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session.draft["step"], 0)
        self.assertIn("обязательное", self.client.messages[-1][1])

    def test_ignores_another_chat(self) -> None:
        self.bot.handle_update(message(1, "99999", "/start"))
        self.assertEqual(self.client.messages, [])

    def test_menu_has_profile_and_directions(self) -> None:
        self.bot.handle_update(message(1, self.chat_id, "/start"))
        markup = self.client.messages[-1][2]
        self.assertIsNotNone(markup)
        assert markup is not None
        self.assertTrue(markup["is_persistent"])
        self.assertEqual(markup["keyboard"][0][0]["text"], "Профиль")
        self.assertEqual(markup["keyboard"][0][1]["text"], "Направления")

    def test_persistent_keyboard_opens_editor(self) -> None:
        self.bot.handle_update(message(1, self.chat_id, "Изменить профиль"))
        self.assertIsNotNone(self.repository.get_profile_session(self.chat_id))
        self.assertIn("Общий профиль", self.client.messages[-1][1])

    def test_runner_persists_update_offset(self) -> None:
        self.client.updates = [message(10, self.chat_id, "/start")]
        runner = ProfileBotRunner(self.repository, self.client, self.bot)
        self.assertEqual(runner.run_once(timeout=0), 1)
        self.assertEqual(self.repository.get_bot_offset(), 11)


if __name__ == "__main__":
    unittest.main()
