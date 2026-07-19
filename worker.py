from __future__ import annotations

import argparse
import signal
import sys

from config import SettingsError, settings
from providers.configured import configured_provider_intervals, configured_providers
from services import (
    IntervalScheduler,
    JobMonitorPipeline,
    OpenAIAnalyzer,
    TelegramBotAPIClient,
)
from storage import OpportunityRepository, StorageError
from utils import RetryPolicy, configure_logging


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the automated JobMonitor pipeline.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute one complete cycle and exit.",
    )
    return parser.parse_args()


def main() -> int:
    _configure_console_encoding()
    args = _arguments()
    try:
        settings.load()
        logger = configure_logging(
            settings.log_file,
            level=settings.log_level,
            max_bytes=settings.log_max_bytes,
            backup_count=settings.log_backup_count,
        )
        repository = OpportunityRepository(settings.database_path)
        repository.initialize()
        chat_id = repository.get_paired_chat_id() or settings.telegram_chat_id
        retry_policy = RetryPolicy(
            attempts=settings.retry_attempts,
            delay_seconds=settings.retry_delay_seconds,
        )
        pipeline = JobMonitorPipeline(
            repository=repository,
            providers=configured_providers(settings),
            analyzer=OpenAIAnalyzer(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                base_url=settings.openai_api_base_url,
                timeout_seconds=settings.openai_timeout_seconds,
                max_output_tokens=settings.openai_max_output_tokens,
            ),
            telegram_client=TelegramBotAPIClient(
                settings.telegram_token,
                api_base_url=settings.telegram_bot_api_base_url,
                request_timeout_seconds=settings.telegram_request_timeout_seconds,
            ),
            chat_id=chat_id,
            ai_batch_size=settings.ai_batch_size,
            notification_batch_size=settings.telegram_notification_batch_size,
            minimum_score=settings.min_ai_score,
            retry_policy=retry_policy,
            provider_intervals=configured_provider_intervals(settings),
        )
        def run_pipeline_cycle():
            repository.set_service_heartbeat("worker")
            try:
                return pipeline.run_cycle()
            finally:
                repository.set_service_heartbeat("worker")

        scheduler = IntervalScheduler(
            run_pipeline_cycle,
            interval_seconds=settings.check_interval_seconds,
        )
    except (SettingsError, StorageError, ValueError) as exc:
        print(f"Worker configuration error: {exc}", file=sys.stderr)
        return 1

    def request_stop(signum: int, _frame: object) -> None:
        logger.info("Stop requested signal=%s", signum)
        scheduler.stop()

    for signal_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signal_name):
            signal.signal(getattr(signal, signal_name), request_stop)

    if args.once:
        try:
            result = scheduler.run_once()
        except Exception as exc:
            logger.error("One-shot worker cycle failed: %s", exc)
            return 2
        logger.info("One-shot worker cycle completed summary=%s", result.to_dict())
        return 0

    scheduler.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
