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
        self.assertEqual(loaded.habr_user_agent, "JobMonitor/0.8")
        self.assertEqual(loaded.habr_vacancy_limit, 20)
        self.assertTrue(loaded.habr_enabled)
        self.assertEqual(loaded.habr_poll_interval_seconds, 300)
        self.assertEqual(loaded.remoteok_api_url, "https://remoteok.com/api")
        self.assertEqual(loaded.remoteok_user_agent, "JobMonitor/0.8")
        self.assertEqual(loaded.remoteok_vacancy_limit, 20)
        self.assertTrue(loaded.remoteok_enabled)
        self.assertEqual(loaded.remoteok_poll_interval_seconds, 900)
        self.assertEqual(loaded.wwr_rss_url, "https://weworkremotely.com/remote-jobs.rss")
        self.assertEqual(loaded.wwr_user_agent, "JobMonitor/0.8")
        self.assertEqual(loaded.wwr_vacancy_limit, 20)
        self.assertTrue(loaded.wwr_enabled)
        self.assertEqual(loaded.wwr_poll_interval_seconds, 900)
        self.assertEqual(loaded.remotive_api_url, "https://remotive.com/api/remote-jobs")
        self.assertEqual(loaded.remotive_user_agent, "JobMonitor/0.8")
        self.assertEqual(loaded.remotive_vacancy_limit, 100)
        self.assertTrue(loaded.remotive_enabled)
        self.assertEqual(loaded.remotive_poll_interval_seconds, 21_600)
        self.assertEqual(
            loaded.greenhouse_api_base_url,
            "https://boards-api.greenhouse.io/v1/boards",
        )
        self.assertEqual(loaded.greenhouse_user_agent, "JobMonitor/0.8")
        self.assertEqual(loaded.greenhouse_boards, "")
        self.assertEqual(loaded.greenhouse_vacancy_limit, 20)
        self.assertFalse(loaded.greenhouse_enabled)
        self.assertEqual(loaded.greenhouse_poll_interval_seconds, 3_600)
        self.assertEqual(
            loaded.trudvsem_api_url,
            "https://opendata.trudvsem.ru/api/v1/vacancies",
        )
        self.assertEqual(loaded.trudvsem_user_agent, "JobMonitor/0.8")
        self.assertIn("автоматизация бизнеса", loaded.trudvsem_search_queries)
        self.assertEqual(loaded.trudvsem_region_codes, "")
        self.assertEqual(loaded.trudvsem_per_query_limit, 10)
        self.assertEqual(loaded.trudvsem_vacancy_limit, 20)
        self.assertEqual(loaded.trudvsem_initial_lookback_days, 14)
        self.assertFalse(loaded.trudvsem_enabled)
        self.assertEqual(loaded.trudvsem_poll_interval_seconds, 3_600)
        self.assertEqual(loaded.jobicy_api_url, "https://jobicy.com/api/v2/remote-jobs")
        self.assertEqual(loaded.jobicy_user_agent, "JobMonitor/0.8")
        self.assertEqual(loaded.jobicy_tag, "automation")
        self.assertEqual(loaded.jobicy_vacancy_limit, 20)
        self.assertFalse(loaded.jobicy_enabled)
        self.assertEqual(loaded.jobicy_poll_interval_seconds, 21_600)
        self.assertEqual(loaded.http_timeout_seconds, 20)
        self.assertEqual(loaded.openai_api_base_url, "https://api.openai.com/v1")
        self.assertEqual(loaded.openai_timeout_seconds, 60)
        self.assertEqual(loaded.openai_max_output_tokens, 4000)
        self.assertEqual(loaded.ai_batch_size, 5)
        self.assertEqual(loaded.max_pending_ai_queue, 50)
        self.assertEqual(loaded.source_initial_import_limit, 20)
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
            ["habr_career", "we_work_remotely", "remotive"],
        )
        self.assertEqual(
            configured_provider_intervals(loaded),
            {"habr_career": 300, "we_work_remotely": 900, "remotive": 21_600},
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

    def test_remotive_interval_cannot_exceed_official_request_frequency(self) -> None:
        env = {**REQUIRED_ENV, "REMOTIVE_POLL_INTERVAL_SECONDS": "21599"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                with self.assertRaisesRegex(SettingsError, "REMOTIVE_POLL_INTERVAL_SECONDS"):
                    Settings().load()

    def test_constructs_each_greenhouse_board_as_independent_source(self) -> None:
        env = {
            **REQUIRED_ENV,
            "GREENHOUSE_ENABLED": "true",
            "GREENHOUSE_BOARDS": "karbon|Karbon;kalepa|Kalepa",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                loaded = Settings().load()

        sources = [provider.source for provider in configured_providers(loaded)]
        self.assertEqual(sources[-2:], ["greenhouse_karbon", "greenhouse_kalepa"])
        self.assertEqual(
            configured_provider_intervals(loaded)["greenhouse_karbon"],
            3_600,
        )
        self.assertEqual(
            configured_provider_intervals(loaded)["greenhouse_kalepa"],
            3_600,
        )

    def test_greenhouse_requires_named_boards_when_enabled(self) -> None:
        env = {**REQUIRED_ENV, "GREENHOUSE_ENABLED": "true"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                loaded = Settings().load()
        with self.assertRaisesRegex(ValueError, "GREENHOUSE_BOARDS"):
            configured_providers(loaded)

    def test_greenhouse_interval_has_conservative_minimum(self) -> None:
        env = {**REQUIRED_ENV, "GREENHOUSE_POLL_INTERVAL_SECONDS": "899"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                with self.assertRaisesRegex(SettingsError, "GREENHOUSE_POLL_INTERVAL_SECONDS"):
                    Settings().load()

    def test_constructs_rabota_rossii_only_when_enabled(self) -> None:
        env = {
            **REQUIRED_ENV,
            "TRUDVSEM_ENABLED": "true",
            "TRUDVSEM_SEARCH_QUERIES": "автоматизация;n8n",
            "TRUDVSEM_REGION_CODES": "77,78",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                loaded = Settings().load()

        providers = configured_providers(loaded)
        self.assertEqual(providers[-1].source, "rabota_rossii")
        self.assertEqual(providers[-1].search_queries, ("автоматизация", "n8n"))
        self.assertEqual(providers[-1].region_codes, ("77", "78"))
        self.assertEqual(
            configured_provider_intervals(loaded)["rabota_rossii"],
            3_600,
        )

    def test_rabota_rossii_requires_queries_when_enabled(self) -> None:
        env = {
            **REQUIRED_ENV,
            "TRUDVSEM_ENABLED": "true",
            "TRUDVSEM_SEARCH_QUERIES": "; ;",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                loaded = Settings().load()
        with self.assertRaisesRegex(ValueError, "TRUDVSEM_SEARCH_QUERIES"):
            configured_providers(loaded)

    def test_rabota_rossii_interval_has_conservative_minimum(self) -> None:
        env = {**REQUIRED_ENV, "TRUDVSEM_POLL_INTERVAL_SECONDS": "3599"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                with self.assertRaisesRegex(SettingsError, "TRUDVSEM_POLL_INTERVAL_SECONDS"):
                    Settings().load()

    def test_constructs_jobicy_only_when_enabled(self) -> None:
        env = {**REQUIRED_ENV, "JOBICY_ENABLED": "true"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                loaded = Settings().load()

        providers = configured_providers(loaded)
        self.assertEqual(providers[-1].source, "jobicy")
        self.assertEqual(providers[-1].tag, "automation")
        self.assertEqual(
            configured_provider_intervals(loaded)["jobicy"],
            21_600,
        )

    def test_jobicy_interval_has_conservative_minimum(self) -> None:
        env = {**REQUIRED_ENV, "JOBICY_POLL_INTERVAL_SECONDS": "21599"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(Settings, "_load_dotenv_file", return_value=None):
                with self.assertRaisesRegex(SettingsError, "JOBICY_POLL_INTERVAL_SECONDS"):
                    Settings().load()

if __name__ == "__main__":
    unittest.main()
