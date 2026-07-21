from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"

_STRING_SETTINGS = {
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_MODEL": "openai_model",
    "TELEGRAM_TOKEN": "telegram_token",
    "TELEGRAM_CHAT_ID": "telegram_chat_id",
}

_OPTIONAL_STRING_SETTINGS = {
    "HABR_RSS_URL": ("habr_rss_url", "https://career.habr.com/vacancies/rss"),
    "HABR_USER_AGENT": ("habr_user_agent", "JobMonitor/0.8"),
    "REMOTEOK_API_URL": ("remoteok_api_url", "https://remoteok.com/api"),
    "REMOTEOK_USER_AGENT": ("remoteok_user_agent", "JobMonitor/0.8"),
    "WWR_RSS_URL": ("wwr_rss_url", "https://weworkremotely.com/remote-jobs.rss"),
    "WWR_USER_AGENT": ("wwr_user_agent", "JobMonitor/0.8"),
    "REMOTIVE_API_URL": ("remotive_api_url", "https://remotive.com/api/remote-jobs"),
    "REMOTIVE_USER_AGENT": ("remotive_user_agent", "JobMonitor/0.8"),
    "GREENHOUSE_API_BASE_URL": (
        "greenhouse_api_base_url",
        "https://boards-api.greenhouse.io/v1/boards",
    ),
    "GREENHOUSE_USER_AGENT": ("greenhouse_user_agent", "JobMonitor/0.8"),
    "GREENHOUSE_BOARDS": ("greenhouse_boards", ""),
    "TRUDVSEM_API_URL": (
        "trudvsem_api_url",
        "https://opendata.trudvsem.ru/api/v1/vacancies",
    ),
    "TRUDVSEM_USER_AGENT": ("trudvsem_user_agent", "JobMonitor/0.8"),
    "TRUDVSEM_SEARCH_QUERIES": (
        "trudvsem_search_queries",
        "автоматизация бизнеса;n8n;OpenAI;Telegram бот;искусственный интеллект;интеграция API",
    ),
    "TRUDVSEM_REGION_CODES": ("trudvsem_region_codes", ""),
    "JOBICY_API_URL": ("jobicy_api_url", "https://jobicy.com/api/v2/remote-jobs"),
    "JOBICY_USER_AGENT": ("jobicy_user_agent", "JobMonitor/0.8"),
    "JOBICY_TAG": ("jobicy_tag", "automation"),
    "OPENAI_API_BASE_URL": ("openai_api_base_url", "https://api.openai.com/v1"),
    "TELEGRAM_BOT_API_BASE_URL": ("telegram_bot_api_base_url", "https://api.telegram.org"),
    "LOG_LEVEL": ("log_level", "INFO"),
}

_OPTIONAL_PATH_SETTINGS = {
    "DATABASE_PATH": ("database_path", PROJECT_ROOT / "data" / "jobmonitor.db"),
    "LOG_FILE": ("log_file", PROJECT_ROOT / "logs" / "jobmonitor.log"),
}

_INTEGER_SETTINGS = {
    "CHECK_INTERVAL_SECONDS": ("check_interval_seconds", 1, None),
    "MIN_AI_SCORE": ("min_ai_score", 0, 100),
}

_OPTIONAL_INTEGER_SETTINGS = {
    "HABR_VACANCY_LIMIT": ("habr_vacancy_limit", 20, 1, 100),
    "REMOTEOK_VACANCY_LIMIT": ("remoteok_vacancy_limit", 20, 1, 100),
    "WWR_VACANCY_LIMIT": ("wwr_vacancy_limit", 20, 1, 100),
    "REMOTIVE_VACANCY_LIMIT": ("remotive_vacancy_limit", 100, 1, 100),
    "GREENHOUSE_VACANCY_LIMIT": ("greenhouse_vacancy_limit", 20, 1, 100),
    "TRUDVSEM_PER_QUERY_LIMIT": ("trudvsem_per_query_limit", 10, 1, 100),
    "TRUDVSEM_VACANCY_LIMIT": ("trudvsem_vacancy_limit", 20, 1, 100),
    "TRUDVSEM_INITIAL_LOOKBACK_DAYS": (
        "trudvsem_initial_lookback_days",
        14,
        1,
        90,
    ),
    "JOBICY_VACANCY_LIMIT": ("jobicy_vacancy_limit", 20, 1, 100),
    "HABR_POLL_INTERVAL_SECONDS": ("habr_poll_interval_seconds", 300, 60, None),
    "REMOTEOK_POLL_INTERVAL_SECONDS": ("remoteok_poll_interval_seconds", 900, 60, None),
    "WWR_POLL_INTERVAL_SECONDS": ("wwr_poll_interval_seconds", 900, 60, None),
    "REMOTIVE_POLL_INTERVAL_SECONDS": (
        "remotive_poll_interval_seconds",
        21_600,
        21_600,
        None,
    ),
    "GREENHOUSE_POLL_INTERVAL_SECONDS": (
        "greenhouse_poll_interval_seconds",
        3_600,
        900,
        None,
    ),
    "TRUDVSEM_POLL_INTERVAL_SECONDS": (
        "trudvsem_poll_interval_seconds",
        3_600,
        3_600,
        None,
    ),
    "JOBICY_POLL_INTERVAL_SECONDS": (
        "jobicy_poll_interval_seconds",
        21_600,
        21_600,
        None,
    ),
    "HTTP_TIMEOUT_SECONDS": ("http_timeout_seconds", 20, 1, 120),
    "OPENAI_TIMEOUT_SECONDS": ("openai_timeout_seconds", 60, 1, 300),
    "OPENAI_MAX_OUTPUT_TOKENS": ("openai_max_output_tokens", 4000, 100, 10000),
    "AI_BATCH_SIZE": ("ai_batch_size", 5, 1, 100),
    "MAX_PENDING_AI_QUEUE": ("max_pending_ai_queue", 50, 1, 10_000),
    "SOURCE_INITIAL_IMPORT_LIMIT": ("source_initial_import_limit", 20, 1, 100),
    "TELEGRAM_REQUEST_TIMEOUT_SECONDS": ("telegram_request_timeout_seconds", 30, 1, 120),
    "TELEGRAM_POLL_TIMEOUT_SECONDS": ("telegram_poll_timeout_seconds", 25, 1, 50),
    "TELEGRAM_NOTIFICATION_BATCH_SIZE": ("telegram_notification_batch_size", 10, 1, 100),
    "RETRY_ATTEMPTS": ("retry_attempts", 3, 1, 10),
    "RETRY_DELAY_SECONDS": ("retry_delay_seconds", 5, 0, 300),
    "LOG_MAX_BYTES": ("log_max_bytes", 5_000_000, 1_000, 100_000_000),
    "LOG_BACKUP_COUNT": ("log_backup_count", 5, 1, 20),
}

_OPTIONAL_BOOLEAN_SETTINGS = {
    "HABR_ENABLED": ("habr_enabled", True),
    "REMOTEOK_ENABLED": ("remoteok_enabled", True),
    "WWR_ENABLED": ("wwr_enabled", True),
    "REMOTIVE_ENABLED": ("remotive_enabled", True),
    "GREENHOUSE_ENABLED": ("greenhouse_enabled", False),
    "TRUDVSEM_ENABLED": ("trudvsem_enabled", False),
    "JOBICY_ENABLED": ("jobicy_enabled", False),
}

_KNOWN_FIELDS = {
    *tuple(_STRING_SETTINGS.values()),
    *(field_name for field_name, _ in _OPTIONAL_STRING_SETTINGS.values()),
    *(field_name for field_name, _ in _OPTIONAL_PATH_SETTINGS.values()),
    *(field_name for field_name, _, _ in _INTEGER_SETTINGS.values()),
    *(field_name for field_name, _, _, _ in _OPTIONAL_INTEGER_SETTINGS.values()),
    *(field_name for field_name, _ in _OPTIONAL_BOOLEAN_SETTINGS.values()),
}


class SettingsError(Exception):
    pass


class Settings:
    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def load(self) -> "Settings":
        self._load_dotenv_file()

        values: dict[str, Any] = {}
        issues: list[str] = []

        for env_name, field_name in _STRING_SETTINGS.items():
            raw_value = os.getenv(env_name, "").strip()
            if not raw_value:
                issues.append(f"{env_name} is required and cannot be empty.")
                continue
            if env_name == "TELEGRAM_TOKEN" and not re.fullmatch(
                r"\d+:[A-Za-z0-9_-]{20,}", raw_value
            ):
                issues.append("TELEGRAM_TOKEN has an invalid bot token format.")
                continue
            if env_name == "TELEGRAM_CHAT_ID" and not re.fullmatch(r"-?\d+", raw_value):
                issues.append("TELEGRAM_CHAT_ID must be a numeric Telegram chat ID.")
                continue
            values[field_name] = raw_value

        for env_name, (field_name, default) in _OPTIONAL_STRING_SETTINGS.items():
            values[field_name] = os.getenv(env_name, default).strip() or default

        for env_name, (field_name, default) in _OPTIONAL_PATH_SETTINGS.items():
            raw_value = os.getenv(env_name, "").strip()
            path = Path(raw_value) if raw_value else default
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            values[field_name] = path.resolve()

        for env_name, (field_name, minimum, maximum) in _INTEGER_SETTINGS.items():
            raw_value = os.getenv(env_name, "").strip()
            if not raw_value:
                issues.append(f"{env_name} is required and cannot be empty.")
                continue

            try:
                parsed_value = int(raw_value)
            except ValueError:
                issues.append(f"{env_name} must be an integer.")
                continue

            if parsed_value < minimum:
                issues.append(f"{env_name} must be greater than or equal to {minimum}.")
                continue

            if maximum is not None and parsed_value > maximum:
                issues.append(f"{env_name} must be less than or equal to {maximum}.")
                continue

            values[field_name] = parsed_value

        for env_name, (field_name, default, minimum, maximum) in _OPTIONAL_INTEGER_SETTINGS.items():
            raw_value = os.getenv(env_name, str(default)).strip()

            try:
                parsed_value = int(raw_value)
            except ValueError:
                issues.append(f"{env_name} must be an integer.")
                continue

            if parsed_value < minimum:
                issues.append(f"{env_name} must be greater than or equal to {minimum}.")
                continue

            if maximum is not None and parsed_value > maximum:
                issues.append(f"{env_name} must be less than or equal to {maximum}.")
                continue

            values[field_name] = parsed_value

        for env_name, (field_name, default) in _OPTIONAL_BOOLEAN_SETTINGS.items():
            raw_value = os.getenv(env_name, str(default)).strip().lower()
            if raw_value in {"1", "true", "yes", "on"}:
                values[field_name] = True
            elif raw_value in {"0", "false", "no", "off"}:
                values[field_name] = False
            else:
                issues.append(
                    f"{env_name} must be one of: true, false, 1, 0, yes, no, on, off."
                )

        if issues:
            details = list(issues)
            if not ENV_FILE.exists():
                details.insert(
                    0,
                    f".env file not found at {ENV_FILE}. Copy .env.example to .env and fill in the required values.",
                )
            raise SettingsError("Configuration validation failed: " + " ".join(details))

        self._values = values
        return self

    def _load_dotenv_file(self) -> None:
        try:
            from dotenv import load_dotenv
        except ModuleNotFoundError as exc:
            raise SettingsError(
                "Required dependency 'python-dotenv' is not installed. Install dependencies from requirements.txt."
            ) from exc

        load_dotenv(dotenv_path=ENV_FILE, override=False)

    def __getattr__(self, name: str) -> Any:
        if name in _KNOWN_FIELDS:
            if name not in self._values:
                raise SettingsError("Settings have not been loaded yet. Call settings.load() before using them.")
            return self._values[name]
        raise AttributeError(f"{type(self).__name__!s} object has no attribute {name!r}")


settings = Settings()
