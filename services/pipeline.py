from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable, Mapping

from providers.base import OpportunityProvider, ProviderError
from services.ai_service import AIAnalyzer
from services.analysis_runner import AnalysisRunner
from services.notification_runner import NotificationRunner
from services.telegram_client import TelegramClient
from storage import OpportunityRepository
from utils import RetryPolicy, retry_call


logger = logging.getLogger("jobmonitor.pipeline")


@dataclass(frozen=True, slots=True)
class PipelineResult:
    sources_succeeded: int = 0
    sources_failed: int = 0
    sources_skipped: int = 0
    opportunities_received: int = 0
    opportunities_saved: int = 0
    duplicates_skipped: int = 0
    opportunities_merged: int = 0
    opportunities_deferred: int = 0
    sources_queue_limited: int = 0
    analyses_suitable: int = 0
    analyses_rejected: int = 0
    analyses_failed: int = 0
    notifications_sent: int = 0
    notifications_failed: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(slots=True)
class JobMonitorPipeline:
    repository: OpportunityRepository
    providers: Iterable[OpportunityProvider]
    analyzer: AIAnalyzer
    telegram_client: TelegramClient
    chat_id: str | int
    ai_batch_size: int
    notification_batch_size: int
    minimum_score: int
    retry_policy: RetryPolicy
    provider_intervals: Mapping[str, int] = field(default_factory=dict)
    max_pending_ai_queue: int = 50
    initial_source_import_limit: int = 20
    sleep: Callable[[float], None] = time.sleep

    def run_cycle(self) -> PipelineResult:
        recovered_analyses = self.repository.recover_interrupted_analyses()
        if recovered_analyses:
            logger.warning(
                "Recovered %s interrupted opportunity analysis claim(s).",
                recovered_analyses,
            )
        recovered = self.repository.recover_interrupted_system_runs()
        if recovered:
            logger.warning("Recovered %s interrupted system run(s).", recovered)
        recovered_sources = self.repository.recover_interrupted_source_runs()
        if recovered_sources:
            logger.warning("Recovered %s interrupted source run(s).", recovered_sources)
        run_id = self.repository.start_system_run()
        logger.info("Cycle started run_id=%s", run_id)
        try:
            result = self._execute()
        except Exception as exc:
            self.repository.finish_system_run(
                run_id,
                status="failed",
                summary={},
                last_error=str(exc),
            )
            logger.exception("Cycle failed run_id=%s", run_id)
            raise

        self.repository.finish_system_run(
            run_id,
            status="completed",
            summary=result.to_dict(),
        )
        logger.info("Cycle completed run_id=%s summary=%s", run_id, result.to_dict())
        return result

    def _execute(self) -> PipelineResult:
        counters = PipelineResult()
        for provider in self.providers:
            interval_seconds = self.provider_intervals.get(provider.source)
            if interval_seconds is not None and not self.repository.source_is_due(
                provider.source,
                interval_seconds,
            ):
                logger.info(
                    "Provider skipped source=%s interval_seconds=%s",
                    provider.source,
                    interval_seconds,
                )
                counters = _add(counters, sources_skipped=1)
                continue

            pending_count = self.repository.count_pending_analysis()
            if pending_count >= self.max_pending_ai_queue:
                logger.info(
                    "Provider deferred source=%s pending_ai=%s queue_limit=%s",
                    provider.source,
                    pending_count,
                    self.max_pending_ai_queue,
                )
                counters = _add(
                    counters,
                    sources_skipped=1,
                    sources_queue_limited=1,
                )
                continue

            source_state = self.repository.get_source_state(provider.source)
            initial_run = source_state is None
            source_run_id = self.repository.start_source_run(provider.source)
            provider_retry_policy = RetryPolicy(
                attempts=getattr(provider, "retry_attempts", self.retry_policy.attempts),
                delay_seconds=self.retry_policy.delay_seconds,
            )
            try:
                fetch_since = getattr(provider, "fetch_since", None)
                fetch_operation = (
                    lambda: fetch_since(
                        source_state.last_success_at if source_state is not None else None
                    )
                ) if callable(fetch_since) else provider.fetch
                fetched_opportunities = retry_call(
                    fetch_operation,
                    exceptions=(ProviderError,),
                    policy=provider_retry_policy,
                    sleep=self.sleep,
                    on_retry=lambda exc, attempt, total, source=provider.source: logger.warning(
                        "Provider retry %s/%s source=%s: %s",
                        attempt,
                        total,
                        source,
                        exc,
                    ),
                )
            except ProviderError as exc:
                self.repository.finish_source_run(
                    source_run_id,
                    provider.source,
                    status="failed",
                    last_error=str(exc),
                )
                logger.error("Provider failed source=%s: %s", provider.source, exc)
                counters = _add(counters, sources_failed=1)
                continue

            try:
                opportunities = list(fetched_opportunities)
                initial_deferred = 0
                if initial_run and len(opportunities) > self.initial_source_import_limit:
                    initial_deferred = len(opportunities) - self.initial_source_import_limit
                    opportunities = opportunities[: self.initial_source_import_limit]

                available_slots = self.max_pending_ai_queue - pending_count
                saved = self.repository.add_many(
                    opportunities,
                    max_new=available_slots,
                )
                deferred_count = initial_deferred + saved.deferred_count
            except Exception as exc:
                self.repository.finish_source_run(
                    source_run_id,
                    provider.source,
                    status="failed",
                    received_count=len(fetched_opportunities),
                    last_error=str(exc),
                )
                raise
            self.repository.finish_source_run(
                source_run_id,
                provider.source,
                status="completed",
                received_count=len(fetched_opportunities),
                saved_count=saved.inserted_count,
                duplicate_count=saved.duplicate_count,
                deferred_count=deferred_count,
            )
            counters = _add(
                counters,
                sources_succeeded=1,
                opportunities_received=len(fetched_opportunities),
                opportunities_saved=saved.inserted_count,
                duplicates_skipped=saved.duplicate_count,
                opportunities_merged=saved.merged_count,
                opportunities_deferred=deferred_count,
            )
            logger.info(
                "Provider completed source=%s received=%s saved=%s duplicates=%s merged=%s deferred=%s",
                provider.source,
                len(fetched_opportunities),
                saved.inserted_count,
                saved.duplicate_count,
                saved.merged_count,
                deferred_count,
            )

        profile = self.repository.get_user_profile(self.chat_id)
        if profile is None:
            logger.warning("AI analysis skipped because the Telegram profile is not configured.")
        else:
            analyses = AnalysisRunner(
                self.repository,
                self.analyzer,
                profile,
                retry_policy=self.retry_policy,
                sleep=self.sleep,
            ).run(batch_size=self.ai_batch_size)
            counters = _add(
                counters,
                analyses_suitable=analyses.analyzed,
                analyses_rejected=analyses.rejected,
                analyses_failed=analyses.failed,
            )

        notifications = NotificationRunner(
            self.repository,
            self.telegram_client,
            self.chat_id,
            retry_policy=self.retry_policy,
            sleep=self.sleep,
        ).run(
            minimum_score=self.minimum_score,
            batch_size=self.notification_batch_size,
        )
        return _add(
            counters,
            notifications_sent=notifications.sent,
            notifications_failed=notifications.failed,
        )


def _add(result: PipelineResult, **increments: int) -> PipelineResult:
    values = result.to_dict()
    for field_name, increment in increments.items():
        values[field_name] += increment
    return PipelineResult(**values)
