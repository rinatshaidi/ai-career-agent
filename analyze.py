from __future__ import annotations

import sys

from config import SettingsError, settings
from models import ProfileError
from services import AnalysisRunner, OpenAIAnalyzer
from storage import OpportunityRepository, StorageError


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _configure_console_encoding()
    try:
        settings.load()
        repository = OpportunityRepository(settings.database_path)
        repository.initialize()
        profile_chat_id = repository.get_paired_chat_id() or settings.telegram_chat_id
        profile = repository.get_user_profile(profile_chat_id)
        if profile is None:
            raise ProfileError(
                "Telegram profile is not configured. Start the profile bot and use /start."
            )
        analyzer = OpenAIAnalyzer(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_api_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
            max_output_tokens=settings.openai_max_output_tokens,
        )
        result = AnalysisRunner(repository, analyzer, profile).run(
            batch_size=settings.ai_batch_size
        )
    except (SettingsError, ProfileError, StorageError, ValueError) as exc:
        print(f"Analysis configuration error: {exc}", file=sys.stderr)
        return 1

    print("========================================")
    print(f"Opportunities claimed: {result.claimed}")
    print(f"Suitable analyses saved: {result.analyzed}")
    print(f"Rejected opportunities saved: {result.rejected}")
    print(f"Failed analyses: {result.failed}")
    print("========================================")
    return 0 if result.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
