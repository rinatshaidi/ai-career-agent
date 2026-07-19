from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from config import Settings, SettingsError
from providers.configured import configured_provider_intervals, configured_providers


REQUIRED_ENV = {
    "OPENAI_API_KEY": "test-key",
    "OPENAI_MODEL": "test-model",
    "TELEGRAM_TOKEN": "123456789:" + "test_token_value_for_unit_tests",
    "TELEGRAM_CHAT_ID": "123456789",
    "CHECK_INTERVAL_SECONDS": "300",
    "MIN_AI_SCORE": "70",
}


class SettingsTests(unittest.TestCase):
    def test_habr_settings_have_production_defaults(self) -> None:
        with patch.dict("os.environ", REQUIRED_ENV, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                loaded = Settings().load()

        self.assertEqual(loaded.habr_rss_url, "https://career.habr.com/vacancies/rss")
        self.assertEqual(loaded.habr_user_agent, "JobMonitor/0.3")
        self.assertEqual(loaded.habr_vacancy_limit, 20)
        self.assertTrue(loaded.habr_enabled)
        self.assertEqual(loaded.habr_poll_interval_seconds, 300)
        self.assertEqual(loaded.remoteok_api_url, "https://remoteok.com/api")
        self.assertEqual(loaded.remoteok_user_agent, "JobMonitor/0.3")
        self.assertEqual(loaded.remoteok_vacancy_limit, 20)
        self.assertTrue(loaded.remoteok_enabled)
        self.assertEqual(loaded.remoteok_poll_interval_seconds, 900)
        self.assertEqual(loaded.wwr_rss_url, "https://weworkremotely.com/remote-jobs.rss")
        self.assertEqual(loaded.wwr_user_agent, "JobMonitor/0.3")
        self.assertEqual(loaded.wwr_vacancy_limit, 20)
        self.assertTrue(loaded.wwr_enabled)
        self.assertEqual(loaded.wwr_poll_interval_seconds, 900)
        self.assertEqual(loaded.http_timeout_seconds, 20)
        self.assertEqual(loaded.openai_api_base_url, "https://api.openai.com/v1")
        self.assertEqual(loaded.openai_timeout_seconds, 60)
        self.assertEqual(loaded.openai_max_output_tokens, 4000)
        self.assertEqual(loaded.ai_batch_size, 5)
        self.assertEqual(loaded.database_path, Path(__file__).resolve().parents[1] / "data" / "jobmonitor.db")
        self.assertEqual(loaded.telegram_bot_api_base_url, "https://api.telegram.org")
        self.assertEqual(loaded.telegram_request_timeout_seconds, 30)
        self.assertEqual(loaded.telegram_poll_timeout_seconds, 25)
        self.assertEqual(loaded.telegram_notification_batch_size, 10)
        self.assertEqual(loaded.retry_attempts, 3)
        self.assertEqual(loaded.retry_delay_seconds, 5)
        self.assertEqual(loaded.log_level, "INFO")
        self.assertEqual(loaded.log_backup_count, 5)

    def test_relative_database_path_is_resolved_from_project_root(self) -> None:
        env = {**REQUIRED_ENV, "DATABASE_PATH": "runtime/test.db"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                loaded = Settings().load()

        self.assertEqual(loaded.database_path, Path(__file__).resolve().parents[1] / "runtime" / "test.db")

    def test_habr_limit_is_validated(self) -> None:
        env = {**REQUIRED_ENV, "HABR_VACANCY_LIMIT": "0"}

        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                with self.assertRaisesRegex(SettingsError, "HABR_VACANCY_LIMIT"):
                    Settings().load()

    def test_telegram_token_format_is_validated_before_network_access(self) -> None:
        env = {**REQUIRED_ENV, "TELEGRAM_TOKEN": "not-a-token"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                with self.assertRaisesRegex(SettingsError, "TELEGRAM_TOKEN"):
                    Settings().load()

    def test_disabled_source_is_not_constructed_or_scheduled(self) -> None:
        env = {**REQUIRED_ENV, "REMOTEOK_ENABLED": "false"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                loaded = Settings().load()

        self.assertEqual(
            [provider.source for provider in configured_providers(loaded)],
            ["habr_career", "we_work_remotely"],
        )
        self.assertEqual(
            configured_provider_intervals(loaded),
            {"habr_career": 300, "we_work_remotely": 900},
        )

    def test_source_enable_flag_is_validated(self) -> None:
        env = {**REQUIRED_ENV, "WWR_ENABLED": "sometimes"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                with self.assertRaisesRegex(SettingsError, "WWR_ENABLED"):
                    Settings().load()

    def test_source_interval_is_validated(self) -> None:
        env = {**REQUIRED_ENV, "REMOTEOK_POLL_INTERVAL_SECONDS": "30"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                with self.assertRaisesRegex(SettingsError, "REMOTEOK_POLL_INTERVAL_SECONDS"):
                    Settings().load()


if __name__ == "__main__":
    unittest.main()
