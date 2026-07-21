from __future__ import annotations

import json
import unittest
import traceback

import httpx

from services import TelegramAPIError, TelegramBotAPIClient


class TelegramBotAPIClientTests(unittest.TestCase):
    def test_gets_updates_with_offset_and_allowed_types(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/botsecret-token/getUpdates")
            payload = json.loads(request.content)
            self.assertEqual(payload["offset"], 101)
            self.assertEqual(payload["allowed_updates"], ["message", "callback_query"])
            return httpx.Response(
                200,
                json={"ok": True, "result": [{"update_id": 101}]},
                request=request,
            )

        client = TelegramBotAPIClient(
            token="secret-token",
            transport=httpx.MockTransport(handler),
        )
        self.assertEqual(client.get_updates(offset=101, timeout=0), [{"update_id": 101}])

    def test_api_error_does_not_expose_token(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                json={"ok": False, "description": "Unauthorized"},
                request=request,
            )

        client = TelegramBotAPIClient(
            token="secret-token",
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(TelegramAPIError, "Unauthorized") as context:
            client.get_me()
        self.assertNotIn("secret-token", str(context.exception))
        rendered_traceback = "".join(
            traceback.format_exception(context.exception)
        )
        self.assertNotIn("secret-token", rendered_traceback)

    def test_sets_bot_commands(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/botsecret-token/setMyCommands")
            self.assertEqual(
                json.loads(request.content),
                {
                    "commands": [
                        {"command": "profile", "description": "View profile"},
                    ]
                },
            )
            return httpx.Response(200, json={"ok": True, "result": True}, request=request)

        client = TelegramBotAPIClient(
            token="secret-token",
            transport=httpx.MockTransport(handler),
        )
        client.set_my_commands([{"command": "profile", "description": "View profile"}])


if __name__ == "__main__":
    unittest.main()
