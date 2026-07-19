from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from models import CandidateProfile, ProfileError
from services.telegram_client import TelegramClient
from storage import OpportunityRepository, ProfileSession


@dataclass(frozen=True, slots=True)
class ProfileQuestion:
    field: str
    prompt: str
    is_list: bool
    required: bool = True


QUESTIONS = (
    ProfileQuestion(
        "positioning",
        "1/5. Как вы описываете себя как специалиста?\n\nНапример: AI automation специалист с опытом в бизнесе.",
        False,
    ),
    ProfileQuestion(
        "skills",
        "2/5. Какие задачи вы умеете выполнять и какие инструменты используете?\n\nНапишите по одному пункту с новой строки.",
        True,
    ),
    ProfileQuestion(
        "preferred_tasks",
        "3/5. Какую работу и задачи вы хотите получать?\n\nНапишите по одному пункту с новой строки.",
        True,
    ),
    ProfileQuestion(
        "avoid_tasks",
        "4/5. Какую работу не нужно предлагать?\n\nНапишите список или слово «нет».",
        True,
        required=False,
    ),
    ProfileQuestion(
        "preferences",
        "5/5. Укажите важные условия: удалённость, график, языки, география, минимальная оплата.\n\nНапишите по одному условию с новой строки.",
        True,
        required=False,
    ),
)


class TelegramProfileBot:
    def __init__(
        self,
        repository: OpportunityRepository,
        client: TelegramClient,
        *,
        allowed_chat_id: str | int,
    ) -> None:
        self.repository = repository
        self.client = client
        self.allowed_chat_id = str(allowed_chat_id).strip()
        if not self.allowed_chat_id:
            raise ValueError("allowed_chat_id cannot be empty.")

    def handle_update(self, update: dict[str, Any]) -> None:
        callback = update.get("callback_query")
        if isinstance(callback, dict):
            self._handle_callback(callback)
            return

        message = update.get("message")
        if not isinstance(message, dict):
            return
        chat = message.get("chat")
        if not isinstance(chat, dict) or str(chat.get("id", "")) != self.allowed_chat_id:
            return
        text = message.get("text")
        if not isinstance(text, str):
            self.client.send_message(self.allowed_chat_id, "Пожалуйста, отправьте ответ текстом.")
            return
        self._handle_message(text.strip())

    def _handle_message(self, text: str) -> None:
        command = text.split(maxsplit=1)[0].lower()
        if command == "/start":
            self._send_menu()
            return
        if command == "/profile":
            self._send_profile()
            return
        if command in {"/edit_profile", "/skills"}:
            self._start_questionnaire()
            return

        session = self.repository.get_profile_session(self.allowed_chat_id)
        if session is None:
            self.client.send_message(
                self.allowed_chat_id,
                "Используйте /start, чтобы открыть меню JobMonitor.",
            )
            return
        self._accept_answer(session, text)

    def _handle_callback(self, callback: dict[str, Any]) -> None:
        message = callback.get("message")
        chat = message.get("chat") if isinstance(message, dict) else None
        if not isinstance(chat, dict) or str(chat.get("id", "")) != self.allowed_chat_id:
            return
        callback_id = callback.get("id")
        if isinstance(callback_id, str):
            self.client.answer_callback_query(callback_id)
        data = callback.get("data")
        if data in {"profile:start", "profile:edit"}:
            self._start_questionnaire()
        elif data == "profile:view":
            self._send_profile()
        elif data == "profile:confirm":
            self._confirm_profile()
        elif data == "profile:cancel":
            self.repository.delete_profile_session(self.allowed_chat_id)
            self.client.send_message(self.allowed_chat_id, "Заполнение профиля отменено.")
            self._send_menu()

    def _send_menu(self) -> None:
        profile = self.repository.get_user_profile(self.allowed_chat_id)
        if profile is None:
            text = "JobMonitor готов к настройке. Сначала заполните профиль поиска."
            buttons = [[{"text": "Заполнить профиль", "callback_data": "profile:start"}]]
        else:
            text = "Профиль настроен. Его можно посмотреть или изменить."
            buttons = [
                [{"text": "Посмотреть профиль", "callback_data": "profile:view"}],
                [{"text": "Изменить профиль", "callback_data": "profile:edit"}],
            ]
        self.client.send_message(
            self.allowed_chat_id,
            text,
            reply_markup={"inline_keyboard": buttons},
        )

    def _start_questionnaire(self) -> None:
        self.repository.save_profile_session(self.allowed_chat_id, step=0, draft={})
        self.client.send_message(self.allowed_chat_id, QUESTIONS[0].prompt)

    def _accept_answer(self, session: ProfileSession, text: str) -> None:
        if session.step >= len(QUESTIONS):
            self.client.send_message(
                self.allowed_chat_id,
                "Проверьте профиль и нажмите «Сохранить профиль».",
            )
            return
        question = QUESTIONS[session.step]
        value: str | list[str]
        if question.is_list:
            value = self._parse_list(text)
            if not value and question.required:
                self.client.send_message(
                    self.allowed_chat_id,
                    "Нужен хотя бы один пункт. Напишите ответ ещё раз.",
                )
                return
        else:
            value = text.strip()
            if not value:
                self.client.send_message(self.allowed_chat_id, "Ответ не может быть пустым.")
                return

        draft = dict(session.draft)
        draft[question.field] = value
        next_step = session.step + 1
        self.repository.save_profile_session(
            self.allowed_chat_id,
            step=next_step,
            draft=draft,
        )
        if next_step < len(QUESTIONS):
            self.client.send_message(self.allowed_chat_id, QUESTIONS[next_step].prompt)
            return
        self._send_draft(draft)

    def _send_draft(self, draft: dict[str, Any]) -> None:
        try:
            profile = CandidateProfile.from_mapping(draft)
        except ProfileError as exc:
            self.client.send_message(self.allowed_chat_id, f"Профиль заполнен некорректно: {exc}")
            return
        self.client.send_message(
            self.allowed_chat_id,
            "Проверьте профиль:\n\n" + self._format_profile(profile),
            reply_markup={
                "inline_keyboard": [
                    [{"text": "Сохранить профиль", "callback_data": "profile:confirm"}],
                    [{"text": "Заполнить заново", "callback_data": "profile:edit"}],
                    [{"text": "Отмена", "callback_data": "profile:cancel"}],
                ]
            },
        )

    def _confirm_profile(self) -> None:
        session = self.repository.get_profile_session(self.allowed_chat_id)
        if session is None or session.step < len(QUESTIONS):
            self.client.send_message(self.allowed_chat_id, "Нет готового профиля для сохранения.")
            return
        try:
            profile = CandidateProfile.from_mapping(session.draft)
        except ProfileError as exc:
            self.client.send_message(self.allowed_chat_id, f"Профиль заполнен некорректно: {exc}")
            return
        self.repository.save_user_profile(self.allowed_chat_id, profile)
        self.repository.delete_profile_session(self.allowed_chat_id)
        self.client.send_message(
            self.allowed_chat_id,
            "Профиль сохранён. JobMonitor может использовать его для AI-анализа.",
        )
        self._send_menu()

    def _send_profile(self) -> None:
        profile = self.repository.get_user_profile(self.allowed_chat_id)
        if profile is None:
            self.client.send_message(
                self.allowed_chat_id,
                "Профиль ещё не заполнен.",
                reply_markup={
                    "inline_keyboard": [
                        [{"text": "Заполнить профиль", "callback_data": "profile:start"}]
                    ]
                },
            )
            return
        self.client.send_message(
            self.allowed_chat_id,
            self._format_profile(profile),
            reply_markup={
                "inline_keyboard": [
                    [{"text": "Изменить профиль", "callback_data": "profile:edit"}]
                ]
            },
        )

    @staticmethod
    def _parse_list(text: str) -> list[str]:
        if text.strip().casefold() in {"нет", "none", "-"}:
            return []
        parts = re.split(r"[\n,;]+", text)
        return [
            re.sub(r"^\s*(?:[-•]+|\d+[.)])\s*", "", part).strip()
            for part in parts
            if part.strip()
        ]

    @staticmethod
    def _format_profile(profile: CandidateProfile) -> str:
        def section(title: str, values: tuple[str, ...]) -> str:
            content = "\n".join(f"- {value}" for value in values) if values else "- не указано"
            return f"{title}:\n{content}"

        return "\n\n".join(
            (
                f"Позиционирование:\n{profile.positioning}",
                section("Навыки и задачи", profile.skills),
                section("Желаемые задачи", profile.preferred_tasks),
                section("Не предлагать", profile.avoid_tasks),
                section("Условия", profile.preferences),
            )
        )


class ProfileBotRunner:
    def __init__(
        self,
        repository: OpportunityRepository,
        client: TelegramClient,
        handler: TelegramProfileBot,
    ) -> None:
        self.repository = repository
        self.client = client
        self.handler = handler

    def run_once(self, *, timeout: int) -> int:
        updates = self.client.get_updates(
            offset=self.repository.get_bot_offset(),
            timeout=timeout,
        )
        for update in updates:
            update_id = update.get("update_id")
            if not isinstance(update_id, int):
                continue
            self.handler.handle_update(update)
            self.repository.set_bot_offset(update_id + 1)
        self.repository.set_service_heartbeat("profile_bot")
        return len(updates)
