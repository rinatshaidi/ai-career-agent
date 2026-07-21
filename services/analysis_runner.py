from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from models import CandidateProfile
from services.ai_service import AIAnalyzer, AIAnalyzerError
from storage import OpportunityRepository, OpportunityStatus
from utils import RetryPolicy, retry_call


logger = logging.getLogger("jobmonitor.analysis")


@dataclass(frozen=True, slots=True)
class AnalysisRunResult:
    claimed: int
    analyzed: int
    rejected: int
    failed: int


@dataclass(slots=True)
class AnalysisRunner:
    repository: OpportunityRepository
    analyzer: AIAnalyzer
    profile: CandidateProfile
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False)

    def run(self, *, batch_size: int) -> AnalysisRunResult:
        claimed = self.repository.claim_for_analysis(limit=batch_size)
        analyzed = 0
        rejected = 0
        failed = 0

        for stored in claimed:
            try:
                analysis = retry_call(
                    lambda: self.analyzer.analyze(stored.opportunity, self.profile),
                    exceptions=(AIAnalyzerError,),
                    policy=self.retry_policy,
                    sleep=self.sleep,
                    on_retry=lambda exc, attempt, total: logger.warning(
                        "AI analysis retry %s/%s for opportunity_id=%s: %s",
                        attempt,
                        total,
                        stored.id,
                        exc,
                    ),
                )
            except AIAnalyzerError as exc:
                self.repository.set_status(
                    stored.opportunity.source,
                    stored.opportunity.external_id,
                    OpportunityStatus.FAILED,
                    last_error=str(exc)[:1000],
                )
                failed += 1
                logger.error("AI analysis failed for opportunity_id=%s: %s", stored.id, exc)
                continue

            self.repository.save_analysis(
                stored.id,
                analysis,
                model=self.analyzer.model,
            )
            if analysis.suitable:
                analyzed += 1
            else:
                rejected += 1
            logger.info(
                "AI analysis saved for opportunity_id=%s suitable=%s score=%s tokens=%s",
                stored.id,
                analysis.suitable,
                analysis.score,
                analysis.total_tokens,
            )

        return AnalysisRunResult(
            claimed=len(claimed),
            analyzed=analyzed,
            rejected=rejected,
            failed=failed,
        )
