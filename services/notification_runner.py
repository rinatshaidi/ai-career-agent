from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from models import AIAnalysis, Opportunity
from services.telegram_client import TelegramAPIError, TelegramClient
from storage import NotificationCandidate, OpportunityRepository
from utils import RetryPolicy, retry_call


TELEGRAM_MESSAGE_LIMIT = 4096
logger = logging.getLogger("jobmonitor.notifications")


@dataclass(frozen=True, slots=True)
class NotificationRunResult:
    claimed: int
    sent: int
    failed: int


@dataclass(slots=True)
class NotificationRunner:
    repository: OpportunityRepository
    client: TelegramClient
    chat_id: str | int
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False)

    def run(self, *, minimum_score: int, batch_size: int) -> NotificationRunResult:
        candidates = self.repository.claim_for_notification(
            minimum_score=minimum_score,
            limit=batch_size,
        )
        sent = 0
        failed = 0
        for candidate in candidates:
            try:
                retry_call(
                    lambda: self.client.send_message(
                        self.chat_id,
                        format_notification(candidate),
                        reply_markup={
                            "inline_keyboard": [
                                [
                                    {
                                        "text": "Открыть вакансию",
                                        "url": candidate.opportunity.opportunity.url,
                                    }
                                ]
                            ]
                        },
                    ),
                    exceptions=(TelegramAPIError,),
                    policy=self.retry_policy,
                    sleep=self.sleep,
                    on_retry=lambda exc, attempt, total: logger.warning(
                        "Telegram retry %s/%s for opportunity_id=%s: %s",
                        attempt,
                        total,
                        candidate.opportunity.id,
                        exc,
                    ),
                )
            except TelegramAPIError as exc:
                self.repository.mark_notification_failed(
                    candidate.opportunity.id,
                    str(exc),
                )
                failed += 1
                logger.error(
                    "Telegram delivery failed for opportunity_id=%s: %s",
                    candidate.opportunity.id,
                    exc,
                )
                continue

            self.repository.mark_notification_sent(candidate.opportunity.id)
            sent += 1
            logger.info(
                "Telegram notification sent for opportunity_id=%s",
                candidate.opportunity.id,
            )

        return NotificationRunResult(claimed=len(candidates), sent=sent, failed=failed)


def format_notification(candidate: NotificationCandidate) -> str:
    opportunity = candidate.opportunity.opportunity
    analysis = candidate.analysis.analysis
    parts = [
        "🔥 Подходящая возможность",
        opportunity.title,
        _details(opportunity, analysis),
        f"Почему подходит:\n{analysis.summary}",
        _list_section("Риски", analysis.risks, "не выявлены"),
        _list_section("План действий", analysis.action_plan, "не указан"),
        f"Черновик отклика:\n{analysis.application_draft}",
        f"Ссылка: {opportunity.url}",
    ]
    text = "\n\n".join(part for part in parts if part)
    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        return text
    suffix = f"\n\nСсылка: {opportunity.url}"
    available = TELEGRAM_MESSAGE_LIMIT - len(suffix) - 1
    return text[: max(0, available)].rstrip() + "…" + suffix


def _details(opportunity: Opportunity, analysis: AIAnalysis) -> str:
    details = [
        f"Источник: {opportunity.source}",
        f"Компания: {opportunity.company_name or 'не указана'}",
        f"Формат: {_remote_type(opportunity)}",
        f"Оплата: {_salary(opportunity)}",
        f"Совпадение: {analysis.score}%",
        f"Сложность: {_difficulty(analysis)}",
        f"Оценка времени: {analysis.estimated_effort}",
    ]
    return "\n".join(details)


def _list_section(title: str, values: tuple[str, ...], empty: str) -> str:
    content = "\n".join(f"• {value}" for value in values) if values else f"• {empty}"
    return f"{title}:\n{content}"


def _salary(opportunity: Opportunity) -> str:
    currency = opportunity.currency or ""
    if opportunity.salary_from is not None and opportunity.salary_to is not None:
        value = f"{opportunity.salary_from:,}–{opportunity.salary_to:,}".replace(",", " ")
    elif opportunity.salary_from is not None:
        value = f"от {opportunity.salary_from:,}".replace(",", " ")
    elif opportunity.salary_to is not None:
        value = f"до {opportunity.salary_to:,}".replace(",", " ")
    else:
        return "не указана"
    return f"{value} {currency}".strip()


def _remote_type(opportunity: Opportunity) -> str:
    return {
        "remote": "удалённо",
        "hybrid": "гибрид",
        "onsite": "офис",
        "unknown": "не указан",
    }[opportunity.remote_type.value]


def _difficulty(analysis: AIAnalysis) -> str:
    return {
        "low": "низкая",
        "medium": "средняя",
        "high": "высокая",
        "unknown": "не указана",
    }[analysis.difficulty.value]
