from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from models import CandidateProfile, ProfileError, SearchTrack
from services.telegram_client import TelegramClient
from storage import OpportunityRepository, ProfileSession


BOT_COMMANDS = [
    {"command": "start", "description": "Открыть меню JobMonitor"},
    {"command": "profile", "description": "Посмотреть профиль поиска"},
    {"command": "directions", "description": "Посмотреть направления поиска"},
    {"command": "edit_profile", "description": "Изменить профиль поиска"},
]

PERSISTENT_MENU = {
    "keyboard": [[{"text": "Профиль"}, {"text": "Направления"}], [{"text": "Изменить профиль"}]],
    "resize_keyboard": True,
    "is_persistent": True,
}


@dataclass(frozen=True, slots=True)
class ProfileQuestion:
    field: str
    prompt: str
    required: bool


COMMON_QUESTIONS = (
    ProfileQuestion(
        "positioning",
        "1/3. Коротко опишите опыт, сильные стороны и работу, которая у вас получается лучше всего. Пишите свободно.",
        True,
    ),
    ProfileQuestion(
        "languages",
        "2/3. Какие рабочие языки должен учитывать агент? Этот вопрос можно пропустить.",
        False,
    ),
    ProfileQuestion(
        "stop_conditions",
        "3/3. Какие предложения точно не нужно показывать? Только жёсткие исключения; вопрос можно пропустить.",
        False,
    ),
)

TRACK_QUESTIONS = (
    ProfileQuestion("name", "Назовите это направление поиска. Например: операционное управление, AI-автоматизация или коммерческая недвижимость.", True),
    ProfileQuestion("target_description", "Какую работу вы хотите находить в этом направлении? Опишите своими словами.", True),
    ProfileQuestion("roles_and_signals", "Какие роли, фразы или слова в объявлении помогут агенту распознать подходящую возможность?", True),
    ProfileQuestion("skills_and_experience", "Опишите опыт, навыки, инструменты, отрасли и достижения, относящиеся к этому направлению.", True),
    ProfileQuestion("tasks_and_outcomes", "За какие задачи или результаты вы готовы отвечать в этом направлении?", True),
    ProfileQuestion("locations", "Какие города, страны, регионы и форматы работы подходят именно для этого направления?", True),
    ProfileQuestion("growth_opportunities", "Какие смежные роли или возможности роста тоже стоит показывать? Этот вопрос можно пропустить.", False),
)


class TelegramProfileBot:
    """Telegram questionnaire for a free-text profile with multiple search tracks."""

    def __init__(self, repository: OpportunityRepository, client: TelegramClient, *, allowed_chat_id: str | int) -> None:
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
        normalized = text.casefold()
        if command == "/start":
            self._send_menu()
            return
        if command == "/profile" or normalized == "профиль":
            self._send_profile()
            return
        if command == "/directions" or normalized == "направления":
            self._send_directions()
            return
        if command in {"/edit_profile", "/skills"} or normalized == "изменить профиль":
            self._start_questionnaire()
            return
        session = self.repository.get_profile_session(self.allowed_chat_id)
        if session is None:
            self.client.send_message(self.allowed_chat_id, "Используйте /start, чтобы открыть меню JobMonitor.")
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
        elif data == "profile:directions":
            self._send_directions()
        elif data == "profile:add_track":
            self._add_search_track()
        elif data == "profile:finish_tracks":
            self._send_draft()
        elif data == "profile:confirm":
            self._confirm_profile()
        elif data == "profile:cancel":
            self.repository.delete_profile_session(self.allowed_chat_id)
            self.client.send_message(self.allowed_chat_id, "Заполнение профиля отменено.")
            self._send_menu()
        elif data == "profile:skip":
            session = self.repository.get_profile_session(self.allowed_chat_id)
            if session is not None:
                self._accept_answer(session, "skip")

    def _send_menu(self) -> None:
        profile = self.repository.get_user_profile(self.allowed_chat_id)
        text = (
            "JobMonitor готов к настройке. Нажмите «Изменить профиль» в нижнем меню, чтобы заполнить анкету."
            if profile is None
            else "Профиль сохранён. В любой момент можно посмотреть направления или заполнить профиль заново."
        )
        self.client.send_message(self.allowed_chat_id, text, reply_markup=PERSISTENT_MENU)

    def _start_questionnaire(self) -> None:
        draft = {"phase": "common", "step": 0, "common": {}, "tracks": [], "current_track": {}}
        self.repository.save_profile_session(self.allowed_chat_id, step=0, draft=draft)
        self._send_current_question(draft)

    def _add_search_track(self) -> None:
        session = self.repository.get_profile_session(self.allowed_chat_id)
        if session is None:
            self._start_questionnaire()
            return
        draft = self._copy_draft(session.draft)
        draft["phase"] = "track"
        draft["step"] = 0
        draft["current_track"] = {}
        self.repository.save_profile_session(self.allowed_chat_id, step=0, draft=draft)
        self._send_current_question(draft)

    def _send_current_question(self, draft: dict[str, Any]) -> None:
        phase = draft.get("phase")
        questions = COMMON_QUESTIONS if phase == "common" else TRACK_QUESTIONS
        step = draft.get("step", 0)
        if not isinstance(step, int) or step >= len(questions):
            self._send_track_choice()
            return
        question = questions[step]
        prefix = f"Общий профиль {step + 1}/{len(COMMON_QUESTIONS)}" if phase == "common" else f"Направление поиска {step + 1}/{len(TRACK_QUESTIONS)}"
        markup: dict[str, Any] | None = None
        if not question.required:
            markup = {"inline_keyboard": [[{"text": "Пропустить", "callback_data": "profile:skip"}]]}
        self.client.send_message(self.allowed_chat_id, f"{prefix}. {question.prompt}", reply_markup=markup)

    def _accept_answer(self, session: ProfileSession, text: str) -> None:
        draft = self._copy_draft(session.draft)
        phase = draft.get("phase")
        questions = COMMON_QUESTIONS if phase == "common" else TRACK_QUESTIONS
        step = draft.get("step", 0)
        if not isinstance(step, int) or step >= len(questions):
            self._send_track_choice()
            return
        question = questions[step]
        value = self._parse_list(text)
        if question.required and not value:
            self.client.send_message(self.allowed_chat_id, "Это обязательное поле. Напишите ответ своими словами.")
            return
        target = draft["common"] if phase == "common" else draft["current_track"]
        target[question.field] = value
        draft["step"] = step + 1
        if draft["step"] < len(questions):
            self.repository.save_profile_session(self.allowed_chat_id, step=draft["step"], draft=draft)
            self._send_current_question(draft)
            return
        if phase == "common":
            draft["phase"] = "track"
            draft["step"] = 0
            draft["current_track"] = {}
            self.repository.save_profile_session(self.allowed_chat_id, step=0, draft=draft)
            self._send_current_question(draft)
            return
        draft["tracks"].append(draft["current_track"])
        draft["current_track"] = {}
        draft["phase"] = "choice"
        draft["step"] = 0
        self.repository.save_profile_session(self.allowed_chat_id, step=0, draft=draft)
        self._send_track_choice()

    def _send_track_choice(self) -> None:
        session = self.repository.get_profile_session(self.allowed_chat_id)
        if session is None:
            return
        tracks = session.draft.get("tracks", [])
        count = len(tracks) if isinstance(tracks, list) else 0
        self.client.send_message(
            self.allowed_chat_id,
            f"Направлений в черновике: {count}. Добавьте ещё одно направление или завершите профиль.",
            reply_markup={"inline_keyboard": [
                [{"text": "+ Добавить направление", "callback_data": "profile:add_track"}],
                [{"text": "Завершить профиль", "callback_data": "profile:finish_tracks"}],
            ]},
        )

    def _send_draft(self) -> None:
        session = self.repository.get_profile_session(self.allowed_chat_id)
        if session is None:
            return
        try:
            profile = self._profile_from_draft(session.draft)
        except ProfileError as exc:
            self.client.send_message(self.allowed_chat_id, f"Черновик профиля заполнен некорректно: {exc}")
            return
        self.client.send_message(
            self.allowed_chat_id,
            "Проверьте профиль:\n\n" + self._format_profile(profile),
            reply_markup={"inline_keyboard": [
                [{"text": "Сохранить профиль", "callback_data": "profile:confirm"}],
                [{"text": "Заполнить заново", "callback_data": "profile:edit"}],
                [{"text": "Отмена", "callback_data": "profile:cancel"}],
            ]},
        )

    def _confirm_profile(self) -> None:
        session = self.repository.get_profile_session(self.allowed_chat_id)
        if session is None:
            self.client.send_message(self.allowed_chat_id, "Нет готового профиля для сохранения.")
            return
        try:
            profile = self._profile_from_draft(session.draft)
        except ProfileError as exc:
            self.client.send_message(self.allowed_chat_id, f"Черновик профиля заполнен некорректно: {exc}")
            return
        self.repository.save_user_profile(self.allowed_chat_id, profile)
        self.repository.delete_profile_session(self.allowed_chat_id)
        self.client.send_message(self.allowed_chat_id, "Профиль сохранён. Агент будет учитывать каждое включённое направление при оценке возможностей.")
        self._send_menu()

    def _send_profile(self) -> None:
        profile = self.repository.get_user_profile(self.allowed_chat_id)
        if profile is None:
            self.client.send_message(self.allowed_chat_id, "Профиль ещё не заполнен.", reply_markup={"inline_keyboard": [[{"text": "Заполнить профиль", "callback_data": "profile:start"}]]})
            return
        self.client.send_message(self.allowed_chat_id, self._format_profile(profile), reply_markup={"inline_keyboard": [[{"text": "Изменить профиль", "callback_data": "profile:edit"}]]})

    def _send_directions(self) -> None:
        profile = self.repository.get_user_profile(self.allowed_chat_id)
        if profile is None or not profile.search_tracks:
            self.client.send_message(self.allowed_chat_id, "Направления ещё не сохранены. Заполните профиль, чтобы добавить первое.", reply_markup={"inline_keyboard": [[{"text": "Заполнить профиль", "callback_data": "profile:start"}]]})
            return
        lines = ["Направления поиска:"]
        for index, track in enumerate(profile.search_tracks, start=1):
            status = "включено" if track.enabled else "выключено"
            lines.append(f"{index}. {track.name} ({status})")
        self.client.send_message(self.allowed_chat_id, "\n".join(lines), reply_markup={"inline_keyboard": [[{"text": "Изменить профиль", "callback_data": "profile:edit"}]]})

    @staticmethod
    def _copy_draft(draft: dict[str, Any]) -> dict[str, Any]:
        common = draft.get("common", {})
        tracks = draft.get("tracks", [])
        current_track = draft.get("current_track", {})
        return {
            "phase": draft.get("phase", "common"),
            "step": draft.get("step", 0),
            "common": {key: list(value) for key, value in common.items()} if isinstance(common, dict) else {},
            "tracks": [{key: list(value) for key, value in item.items()} for item in tracks if isinstance(item, dict)],
            "current_track": {key: list(value) for key, value in current_track.items()} if isinstance(current_track, dict) else {},
        }

    @staticmethod
    def _parse_list(text: str) -> list[str]:
        if text.strip().casefold() in {"no", "none", "-", "skip"}:
            return []
        return [
            re.sub(r"^\s*(?:[-*]+|\d+[.)])\s*", "", part).strip()
            for part in re.split(r"[\n,;]+", text)
            if part.strip()
        ]

    @staticmethod
    def _profile_from_draft(draft: dict[str, Any]) -> CandidateProfile:
        common = draft.get("common")
        raw_tracks = draft.get("tracks")
        if not isinstance(common, dict) or not isinstance(raw_tracks, list) or not raw_tracks:
            raise ProfileError("Нужно заполнить хотя бы одно направление поиска.")
        positioning = " ".join(common.get("positioning", [])).strip()
        if not positioning:
            raise ProfileError("Нужно описать опыт.")
        tracks = tuple(
            SearchTrack(
                track_id=f"track-{uuid4().hex}",
                name=" ".join(item.get("name", [])).strip(),
                target_description=" ".join(item.get("target_description", [])).strip(),
                roles_and_signals=tuple(item.get("roles_and_signals", [])),
                skills_and_experience=tuple(item.get("skills_and_experience", [])),
                tasks_and_outcomes=tuple(item.get("tasks_and_outcomes", [])),
                locations=tuple(item.get("locations", [])),
                growth_opportunities=tuple(item.get("growth_opportunities", [])),
            )
            for item in raw_tracks
            if isinstance(item, dict)
        )
        if not tracks:
            raise ProfileError("Нужно заполнить хотя бы одно направление поиска.")
        skills = tuple(value for track in tracks for value in track.skills_and_experience)
        tasks = tuple(value for track in tracks for value in track.tasks_and_outcomes)
        languages = tuple(common.get("languages", []))
        exclusions = tuple(common.get("stop_conditions", []))
        return CandidateProfile(
            positioning=positioning,
            skills=skills,
            preferred_tasks=tasks,
            avoid_tasks=exclusions,
            preferences=languages,
            common_preferences=languages,
            search_tracks=tracks,
        )

    @staticmethod
    def _format_profile(profile: CandidateProfile) -> str:
        lines = [f"Краткое описание опыта:\n{profile.positioning}", "", "Направления поиска:"]
        for track in profile.search_tracks:
            lines.extend((
                f"- {track.name}",
                f"  Ищу: {track.target_description}",
                f"  Города/страны/форматы: {', '.join(track.locations) or 'не указано'}",
            ))
        if profile.common_preferences:
            lines.extend(("", "Языки: " + ", ".join(profile.common_preferences)))
        if profile.avoid_tasks:
            lines.extend(("", "Не показывать: " + ", ".join(profile.avoid_tasks)))
        return "\n".join(lines)


class ProfileBotRunner:
    def __init__(self, repository: OpportunityRepository, client: TelegramClient, handler: TelegramProfileBot) -> None:
        self.repository = repository
        self.client = client
        self.handler = handler

    def run_once(self, *, timeout: int) -> int:
        updates = self.client.get_updates(offset=self.repository.get_bot_offset(), timeout=timeout)
        for update in updates:
            update_id = update.get("update_id")
            if not isinstance(update_id, int):
                continue
            self.handler.handle_update(update)
            self.repository.set_bot_offset(update_id + 1)
        self.repository.set_service_heartbeat("profile_bot")
        return len(updates)
