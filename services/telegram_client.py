from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

import httpx


class TelegramAPIError(RuntimeError):
    """Raised when Telegram Bot API cannot complete a request."""


@runtime_checkable
class TelegramClient(Protocol):
    def get_updates(self, *, offset: int | None, timeout: int) -> list[dict[str, Any]]: ...

    def send_message(
        self,
        chat_id: str | int,
        text: str,
        *,
        reply_markup: Mapping[str, Any] | None = None,
    ) -> None: ...

    def answer_callback_query(self, callback_query_id: str) -> None: ...

    def set_my_commands(self, commands: list[dict[str, str]]) -> None: ...


@dataclass(slots=True)
class TelegramBotAPIClient:
    token: str
    api_base_url: str = "https://api.telegram.org"
    request_timeout_seconds: int = 30
    transport: httpx.BaseTransport | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.token = self.token.strip()
        self.api_base_url = self.api_base_url.rstrip("/")
        if not self.token:
            raise ValueError("Telegram bot token cannot be empty.")
        if self.request_timeout_seconds < 1:
            raise ValueError("Telegram request timeout must be positive.")

    def get_me(self) -> dict[str, Any]:
        result = self._call("getMe", {})
        if not isinstance(result, dict):
            raise TelegramAPIError("Telegram getMe returned an invalid result.")
        return result

    def get_webhook_info(self) -> dict[str, Any]:
        result = self._call("getWebhookInfo", {})
        if not isinstance(result, dict):
            raise TelegramAPIError("Telegram getWebhookInfo returned an invalid result.")
        return result

    def get_updates(self, *, offset: int | None, timeout: int) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        result = self._call("getUpdates", payload, timeout=max(timeout + 10, self.request_timeout_seconds))
        if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
            raise TelegramAPIError("Telegram getUpdates returned an invalid result.")
        return result

    def send_message(
        self,
        chat_id: str | int,
        text: str,
        *,
        reply_markup: Mapping[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = dict(reply_markup)
        self._call("sendMessage", payload)

    def answer_callback_query(self, callback_query_id: str) -> None:
        self._call("answerCallbackQuery", {"callback_query_id": callback_query_id})

    def set_my_commands(self, commands: list[dict[str, str]]) -> None:
        if not commands or not all(
            isinstance(command.get("command"), str)
            and isinstance(command.get("description"), str)
            for command in commands
        ):
            raise ValueError("Telegram commands must contain command and description strings.")
        self._call("setMyCommands", {"commands": commands})

    def _call(
        self,
        method: str,
        payload: Mapping[str, Any],
        *,
        timeout: int | None = None,
    ) -> Any:
        url = f"{self.api_base_url}/bot{self.token}/{method}"
        try:
            with httpx.Client(
                timeout=float(timeout or self.request_timeout_seconds),
                transport=self.transport,
            ) as client:
                response = client.post(url, json=dict(payload))
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            description = self._description(exc.response)
            raise TelegramAPIError(
                f"Telegram method {method} returned HTTP {exc.response.status_code}: {description}"
            ) from None
        except httpx.HTTPError as exc:
            raise TelegramAPIError(f"Telegram method {method} request failed.") from None

        try:
            data = response.json()
        except ValueError as exc:
            raise TelegramAPIError(f"Telegram method {method} returned non-JSON data.") from exc
        if not isinstance(data, dict) or data.get("ok") is not True:
            description = data.get("description", "request failed") if isinstance(data, dict) else "request failed"
            raise TelegramAPIError(f"Telegram method {method} failed: {description}")
        return data.get("result")

    @staticmethod
    def _description(response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return "request failed"
        if isinstance(data, dict) and isinstance(data.get("description"), str):
            return data["description"]
        return "request failed"
