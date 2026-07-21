from __future__ import annotations

import sqlite3
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from models import (
    AIAnalysis,
    CandidateProfile,
    Difficulty,
    Opportunity,
    RecommendationCategory,
    RemoteType,
    SearchTrack,
    TrackAssessment,
)
from utils.deduplication import canonicalize_url, opportunity_fingerprint


class StorageError(RuntimeError):
    """Raised when the local opportunity store cannot complete an operation."""


class OpportunityStatus(str, Enum):
    NEW = "new"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    NOTIFIED = "notified"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SaveBatchResult:
    inserted: tuple[Opportunity, ...]
    duplicates: tuple[Opportunity, ...]
    merged: tuple[Opportunity, ...] = ()
    deferred: tuple[Opportunity, ...] = ()

    @property
    def inserted_count(self) -> int:
        return len(self.inserted)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicates)

    @property
    def merged_count(self) -> int:
        return len(self.merged)

    @property
    def deferred_count(self) -> int:
        return len(self.deferred)


@dataclass(frozen=True, slots=True)
class OpportunitySource:
    opportunity_id: int
    source: str
    external_id: str
    url: str
    canonical_url: str
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True, slots=True)
class StoredOpportunity:
    id: int
    opportunity: Opportunity
    status: OpportunityStatus
    last_error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class StoredAnalysis:
    opportunity_id: int
    model: str
    analysis: AIAnalysis
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ProfileSession:
    chat_id: str
    step: int
    draft: dict[str, Any]
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class NotificationCandidate:
    opportunity: StoredOpportunity
    analysis: StoredAnalysis


@dataclass(frozen=True, slots=True)
class SystemRun:
    id: int
    status: str
    summary: dict[str, Any]
    last_error: str | None
    started_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class SourceState:
    source: str
    last_attempt_at: datetime
    last_success_at: datetime | None
    last_status: str
    last_error: str | None
    last_received: int
    last_saved: int
    last_duplicates: int
    last_deferred: int
    updated_at: datetime


class OpportunityRepository:
    """SQLite repository with database-enforced opportunity deduplication."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    url TEXT NOT NULL,
                    company_name TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    remote_type TEXT NOT NULL,
                    salary_from INTEGER,
                    salary_to INTEGER,
                    currency TEXT,
                    published_at TEXT,
                    collected_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new',
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (source, external_id),
                    CHECK (remote_type IN ('remote', 'hybrid', 'onsite', 'unknown')),
                    CHECK (status IN ('new', 'analyzing', 'analyzed', 'notified', 'rejected', 'failed')),
                    CHECK (salary_from IS NULL OR salary_from >= 0),
                    CHECK (salary_to IS NULL OR salary_to >= 0),
                    CHECK (salary_from IS NULL OR salary_to IS NULL OR salary_from <= salary_to)
                );

                CREATE INDEX IF NOT EXISTS idx_opportunities_status
                    ON opportunities (status, published_at);

                CREATE TABLE IF NOT EXISTS ai_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opportunity_id INTEGER NOT NULL UNIQUE,
                    model TEXT NOT NULL,
                    suitable INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    estimated_effort TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    risks_json TEXT NOT NULL,
                    action_plan_json TEXT NOT NULL,
                    application_draft TEXT NOT NULL,
                    missing_information_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE,
                    CHECK (suitable IN (0, 1)),
                    CHECK (score BETWEEN 0 AND 100),
                    CHECK (difficulty IN ('low', 'medium', 'high', 'unknown'))
                );

                CREATE INDEX IF NOT EXISTS idx_ai_analyses_score
                    ON ai_analyses (suitable, score DESC);

                CREATE TABLE IF NOT EXISTS user_profiles (
                    chat_id TEXT PRIMARY KEY,
                    positioning TEXT NOT NULL,
                    skills_json TEXT NOT NULL,
                    preferred_tasks_json TEXT NOT NULL,
                    avoid_tasks_json TEXT NOT NULL,
                    preferences_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS profile_sessions (
                    chat_id TEXT PRIMARY KEY,
                    step INTEGER NOT NULL,
                    draft_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    CHECK (step >= 0)
                );

                CREATE TABLE IF NOT EXISTS bot_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telegram_notifications (
                    opportunity_id INTEGER PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE,
                    CHECK (status IN ('pending', 'sending', 'sent', 'failed')),
                    CHECK (attempt_count >= 0)
                );

                CREATE INDEX IF NOT EXISTS idx_telegram_notifications_status
                    ON telegram_notifications (status, updated_at);

                CREATE TABLE IF NOT EXISTS system_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL,
                    summary_json TEXT NOT NULL DEFAULT '{}',
                    last_error TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    CHECK (status IN ('running', 'completed', 'failed'))
                );

                CREATE INDEX IF NOT EXISTS idx_system_runs_started_at
                    ON system_runs (started_at DESC);

                CREATE TABLE IF NOT EXISTS source_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    received_count INTEGER NOT NULL DEFAULT 0,
                    saved_count INTEGER NOT NULL DEFAULT 0,
                    duplicate_count INTEGER NOT NULL DEFAULT 0,
                    deferred_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    CHECK (status IN ('running', 'completed', 'failed')),
                    CHECK (received_count >= 0),
                    CHECK (saved_count >= 0),
                    CHECK (duplicate_count >= 0),
                    CHECK (deferred_count >= 0)
                );

                CREATE INDEX IF NOT EXISTS idx_source_runs_source_started
                    ON source_runs (source, started_at DESC);

                CREATE TABLE IF NOT EXISTS source_states (
                    source TEXT PRIMARY KEY,
                    last_attempt_at TEXT NOT NULL,
                    last_success_at TEXT,
                    last_status TEXT NOT NULL,
                    last_error TEXT,
                    last_received INTEGER NOT NULL DEFAULT 0,
                    last_saved INTEGER NOT NULL DEFAULT 0,
                    last_duplicates INTEGER NOT NULL DEFAULT 0,
                    last_deferred INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    CHECK (last_status IN ('running', 'completed', 'failed')),
                    CHECK (last_received >= 0),
                    CHECK (last_saved >= 0),
                    CHECK (last_duplicates >= 0),
                    CHECK (last_deferred >= 0)
                );
                """
            )

            self._ensure_column(connection, "opportunities", "canonical_url", "TEXT")
            self._ensure_column(connection, "opportunities", "content_fingerprint", "TEXT")
            self._ensure_column(connection, "user_profiles", "common_preferences_json", "TEXT")
            self._ensure_column(connection, "ai_analyses", "recommendation", "TEXT")
            self._ensure_column(connection, "ai_analyses", "primary_track_id", "TEXT")
            self._ensure_column(connection, "ai_analyses", "primary_track_name", "TEXT")
            self._ensure_column(connection, "ai_analyses", "match_reasons_json", "TEXT")
            self._ensure_column(connection, "ai_analyses", "required_actions_json", "TEXT")
            self._ensure_column(connection, "ai_analyses", "employment_type", "TEXT")
            self._ensure_column(connection, "ai_analyses", "track_assessments_json", "TEXT")
            self._ensure_column(connection, "ai_analyses", "input_tokens", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "ai_analyses", "output_tokens", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "ai_analyses", "total_tokens", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(
                connection,
                "source_runs",
                "deferred_count",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self._ensure_column(
                connection,
                "source_states",
                "last_deferred",
                "INTEGER NOT NULL DEFAULT 0",
            )
            connection.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_opportunities_canonical_url
                    ON opportunities (canonical_url);
                CREATE INDEX IF NOT EXISTS idx_opportunities_content_fingerprint
                    ON opportunities (content_fingerprint);

                CREATE TABLE IF NOT EXISTS opportunity_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opportunity_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    canonical_url TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE,
                    UNIQUE (source, external_id)
                );

                CREATE INDEX IF NOT EXISTS idx_opportunity_sources_opportunity
                    ON opportunity_sources (opportunity_id);
                CREATE INDEX IF NOT EXISTS idx_opportunity_sources_canonical_url
                    ON opportunity_sources (canonical_url);

                CREATE TABLE IF NOT EXISTS profile_directions (
                    chat_id TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (chat_id, direction),
                    FOREIGN KEY (chat_id) REFERENCES user_profiles(chat_id) ON DELETE CASCADE,
                    CHECK (direction IN ('ai_automation', 'infrastructure_business_projects'))
                );

                CREATE INDEX IF NOT EXISTS idx_profile_directions_chat_id
                    ON profile_directions (chat_id);

                CREATE TABLE IF NOT EXISTS profile_search_tracks (
                    chat_id TEXT NOT NULL,
                    track_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (chat_id, track_id),
                    FOREIGN KEY (chat_id) REFERENCES user_profiles(chat_id) ON DELETE CASCADE,
                    CHECK (enabled IN (0, 1))
                );

                CREATE INDEX IF NOT EXISTS idx_profile_search_tracks_chat_id
                    ON profile_search_tracks (chat_id, enabled);
                """
            )
            self._migrate_legacy_profile_directions(connection)
            self._backfill_opportunity_identity(connection)

    def add_many(
        self,
        opportunities: Iterable[Opportunity],
        *,
        max_new: int | None = None,
    ) -> SaveBatchResult:
        if max_new is not None and max_new < 0:
            raise ValueError("max_new cannot be negative.")
        inserted: list[Opportunity] = []
        duplicates: list[Opportunity] = []
        merged: list[Opportunity] = []
        deferred: list[Opportunity] = []
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as connection:
            for opportunity in opportunities:
                canonical_url = canonicalize_url(opportunity.url)
                fingerprint = opportunity_fingerprint(opportunity)
                known_source = connection.execute(
                    """
                    SELECT opportunity_id FROM opportunity_sources
                    WHERE source = ? AND external_id = ?
                    """,
                    (opportunity.source, opportunity.external_id),
                ).fetchone()
                if known_source is not None:
                    connection.execute(
                        """
                        UPDATE opportunity_sources
                        SET url = ?, canonical_url = ?, last_seen_at = ?
                        WHERE source = ? AND external_id = ?
                        """,
                        (
                            opportunity.url,
                            canonical_url,
                            now,
                            opportunity.source,
                            opportunity.external_id,
                        ),
                    )
                    duplicates.append(opportunity)
                    continue

                existing = connection.execute(
                    """
                    SELECT id FROM opportunities
                    WHERE canonical_url = ? OR content_fingerprint = ?
                    ORDER BY CASE WHEN canonical_url = ? THEN 0 ELSE 1 END, id ASC
                    LIMIT 1
                    """,
                    (canonical_url, fingerprint, canonical_url),
                ).fetchone()
                if existing is not None:
                    self._insert_opportunity_source(
                        connection,
                        opportunity_id=int(existing["id"]),
                        opportunity=opportunity,
                        canonical_url=canonical_url,
                        seen_at=now,
                    )
                    duplicates.append(opportunity)
                    merged.append(opportunity)
                    continue

                if max_new is not None and len(inserted) >= max_new:
                    deferred.append(opportunity)
                    continue

                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO opportunities (
                        source, external_id, title, description, url,
                        company_name, location, remote_type,
                        salary_from, salary_to, currency,
                        published_at, collected_at, status, canonical_url,
                        content_fingerprint, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        opportunity.source,
                        opportunity.external_id,
                        opportunity.title,
                        opportunity.description,
                        opportunity.url,
                        opportunity.company_name,
                        opportunity.location,
                        opportunity.remote_type.value,
                        opportunity.salary_from,
                        opportunity.salary_to,
                        opportunity.currency,
                        opportunity.published_at.isoformat() if opportunity.published_at else None,
                        opportunity.collected_at.isoformat(),
                        OpportunityStatus.NEW.value,
                        canonical_url,
                        fingerprint,
                        now,
                        now,
                    ),
                )
                if cursor.rowcount == 1:
                    inserted.append(opportunity)
                    self._insert_opportunity_source(
                        connection,
                        opportunity_id=int(cursor.lastrowid),
                        opportunity=opportunity,
                        canonical_url=canonical_url,
                        seen_at=now,
                    )
                else:
                    duplicates.append(opportunity)

        return SaveBatchResult(
            tuple(inserted),
            tuple(duplicates),
            tuple(merged),
            tuple(deferred),
        )

    def get_by_status(
        self,
        status: OpportunityStatus,
        *,
        limit: int = 100,
    ) -> list[StoredOpportunity]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM opportunities
                WHERE status = ?
                ORDER BY COALESCE(published_at, collected_at) ASC, id ASC
                LIMIT ?
                """,
                (status.value, limit),
            ).fetchall()
        return [self._to_stored_opportunity(row) for row in rows]

    def set_status(
        self,
        source: str,
        external_id: str,
        status: OpportunityStatus,
        *,
        last_error: str | None = None,
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE opportunities
                SET status = ?, last_error = ?, updated_at = ?
                WHERE source = ? AND external_id = ?
                """,
                (status.value, last_error, now, source, external_id),
            )
        return cursor.rowcount == 1

    def claim_for_analysis(self, *, limit: int) -> list[StoredOpportunity]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")
        now = datetime.now(timezone.utc).isoformat()
        claimed_ids: list[int] = []
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id FROM opportunities
                WHERE status = ?
                ORDER BY COALESCE(published_at, collected_at) ASC, id ASC
                LIMIT ?
                """,
                (OpportunityStatus.NEW.value, limit),
            ).fetchall()
            for row in rows:
                cursor = connection.execute(
                    """
                    UPDATE opportunities
                    SET status = ?, last_error = NULL, updated_at = ?
                    WHERE id = ? AND status = ?
                    """,
                    (
                        OpportunityStatus.ANALYZING.value,
                        now,
                        row["id"],
                        OpportunityStatus.NEW.value,
                    ),
                )
                if cursor.rowcount == 1:
                    claimed_ids.append(row["id"])

            if not claimed_ids:
                return []
            placeholders = ",".join("?" for _ in claimed_ids)
            claimed_rows = connection.execute(
                f"SELECT * FROM opportunities WHERE id IN ({placeholders}) ORDER BY id ASC",
                claimed_ids,
            ).fetchall()
        return [self._to_stored_opportunity(row) for row in claimed_rows]

    def save_analysis(self, opportunity_id: int, analysis: AIAnalysis, *, model: str) -> None:
        model = model.strip()
        if not model:
            raise ValueError("model cannot be empty.")
        now = datetime.now(timezone.utc).isoformat()
        recommendation = analysis.recommendation
        final_status = (
            OpportunityStatus.REJECTED
            if recommendation is RecommendationCategory.ARCHIVE or not analysis.suitable
            else OpportunityStatus.ANALYZED
        )
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT status FROM opportunities WHERE id = ?",
                (opportunity_id,),
            ).fetchone()
            if cursor is None:
                raise StorageError(f"Opportunity {opportunity_id} does not exist.")
            if cursor["status"] != OpportunityStatus.ANALYZING.value:
                raise StorageError(
                    f"Opportunity {opportunity_id} is not claimed for analysis."
                )

            connection.execute(
                """
                INSERT INTO ai_analyses (
                    opportunity_id, model, suitable, score, summary,
                    estimated_effort, difficulty, risks_json, action_plan_json,
                    application_draft, missing_information_json, recommendation,
                    primary_track_id, primary_track_name, match_reasons_json,
                    required_actions_json, employment_type, track_assessments_json,
                    input_tokens, output_tokens, total_tokens, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(opportunity_id) DO UPDATE SET
                    model = excluded.model,
                    suitable = excluded.suitable,
                    score = excluded.score,
                    summary = excluded.summary,
                    estimated_effort = excluded.estimated_effort,
                    difficulty = excluded.difficulty,
                    risks_json = excluded.risks_json,
                    action_plan_json = excluded.action_plan_json,
                    application_draft = excluded.application_draft,
                    missing_information_json = excluded.missing_information_json,
                    recommendation = excluded.recommendation,
                    primary_track_id = excluded.primary_track_id,
                    primary_track_name = excluded.primary_track_name,
                    match_reasons_json = excluded.match_reasons_json,
                    required_actions_json = excluded.required_actions_json,
                    employment_type = excluded.employment_type,
                    track_assessments_json = excluded.track_assessments_json,
                    input_tokens = excluded.input_tokens,
                    output_tokens = excluded.output_tokens,
                    total_tokens = excluded.total_tokens,
                    updated_at = excluded.updated_at
                """,
                (
                    opportunity_id,
                    model,
                    int(analysis.suitable),
                    analysis.score,
                    analysis.summary,
                    analysis.estimated_effort,
                    analysis.difficulty.value,
                    json.dumps(analysis.risks, ensure_ascii=False),
                    json.dumps(analysis.action_plan, ensure_ascii=False),
                    analysis.application_draft,
                    json.dumps(analysis.missing_information, ensure_ascii=False),
                    recommendation.value if recommendation else None,
                    analysis.primary_track_id,
                    analysis.primary_track_name,
                    json.dumps(analysis.match_reasons, ensure_ascii=False),
                    json.dumps(analysis.required_actions, ensure_ascii=False),
                    analysis.employment_type,
                    json.dumps(
                        [item.to_dict() for item in analysis.track_assessments],
                        ensure_ascii=False,
                    ),
                    analysis.input_tokens,
                    analysis.output_tokens,
                    analysis.total_tokens,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE opportunities
                SET status = ?, last_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (final_status.value, now, opportunity_id),
            )

    def get_analysis(self, opportunity_id: int) -> StoredAnalysis | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ai_analyses WHERE opportunity_id = ?",
                (opportunity_id,),
            ).fetchone()
        if row is None:
            return None
        recommendation_raw = row["recommendation"]
        track_assessments_raw = row["track_assessments_json"]
        analysis = AIAnalysis(
            suitable=bool(row["suitable"]),
            score=row["score"],
            summary=row["summary"],
            estimated_effort=row["estimated_effort"],
            difficulty=Difficulty(row["difficulty"]),
            risks=tuple(json.loads(row["risks_json"])),
            action_plan=tuple(json.loads(row["action_plan_json"])),
            application_draft=row["application_draft"],
            missing_information=tuple(json.loads(row["missing_information_json"])),
            recommendation=(
                RecommendationCategory(recommendation_raw)
                if recommendation_raw
                else None
            ),
            primary_track_id=row["primary_track_id"],
            primary_track_name=row["primary_track_name"],
            match_reasons=tuple(json.loads(row["match_reasons_json"] or "[]")),
            required_actions=tuple(json.loads(row["required_actions_json"] or "[]")),
            employment_type=row["employment_type"] or "не указана",
            track_assessments=tuple(
                TrackAssessment.from_mapping(item)
                for item in json.loads(track_assessments_raw or "[]")
            ),
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            total_tokens=row["total_tokens"],
        )
        return StoredAnalysis(
            opportunity_id=row["opportunity_id"],
            model=row["model"],
            analysis=analysis,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def claim_for_notification(
        self,
        *,
        minimum_score: int,
        limit: int,
        lock_timeout_minutes: int = 30,
    ) -> list[NotificationCandidate]:
        if not 0 <= minimum_score <= 100:
            raise ValueError("minimum_score must be between 0 and 100.")
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")
        if lock_timeout_minutes < 1:
            raise ValueError("lock_timeout_minutes must be positive.")

        now = datetime.now(timezone.utc)
        now_text = now.isoformat()
        stale_before = (now - timedelta(minutes=lock_timeout_minutes)).isoformat()
        claimed_ids: list[int] = []
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE telegram_notifications
                SET status = 'failed',
                    last_error = 'Recovered stale notification claim.',
                    updated_at = ?
                WHERE status = 'sending' AND updated_at < ?
                """,
                (now_text, stale_before),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO telegram_notifications (
                    opportunity_id, status, attempt_count, created_at, updated_at
                )
                SELECT o.id, 'pending', 0, ?, ?
                FROM opportunities AS o
                JOIN ai_analyses AS a ON a.opportunity_id = o.id
                WHERE o.status = 'analyzed'
                  AND (
                      a.recommendation IN ('priority', 'review')
                      OR (
                          a.recommendation IS NULL
                          AND a.suitable = 1
                          AND a.score >= ?
                      )
                  )
                """,
                (now_text, now_text, minimum_score),
            )
            rows = connection.execute(
                """
                SELECT n.opportunity_id
                FROM telegram_notifications AS n
                JOIN opportunities AS o ON o.id = n.opportunity_id
                JOIN ai_analyses AS a ON a.opportunity_id = o.id
                WHERE n.status IN ('pending', 'failed')
                  AND o.status = 'analyzed'
                  AND (
                      a.recommendation IN ('priority', 'review')
                      OR (
                          a.recommendation IS NULL
                          AND a.suitable = 1
                          AND a.score >= ?
                      )
                  )
                ORDER BY
                    CASE a.recommendation
                        WHEN 'priority' THEN 0
                        WHEN 'review' THEN 1
                        ELSE 2
                    END,
                    a.score DESC,
                    n.created_at ASC
                LIMIT ?
                """,
                (minimum_score, limit),
            ).fetchall()
            for row in rows:
                cursor = connection.execute(
                    """
                    UPDATE telegram_notifications
                    SET status = 'sending', attempt_count = attempt_count + 1,
                        last_error = NULL, updated_at = ?
                    WHERE opportunity_id = ? AND status IN ('pending', 'failed')
                    """,
                    (now_text, row["opportunity_id"]),
                )
                if cursor.rowcount == 1:
                    claimed_ids.append(row["opportunity_id"])

        candidates: list[NotificationCandidate] = []
        for opportunity_id in claimed_ids:
            opportunity = self.get_opportunity(opportunity_id)
            analysis = self.get_analysis(opportunity_id)
            if opportunity is None or analysis is None:
                raise StorageError(
                    f"Claimed notification {opportunity_id} has incomplete stored data."
                )
            candidates.append(NotificationCandidate(opportunity, analysis))
        return candidates

    def mark_notification_sent(self, opportunity_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE telegram_notifications
                SET status = 'sent', last_error = NULL, updated_at = ?
                WHERE opportunity_id = ? AND status = 'sending'
                """,
                (now, opportunity_id),
            )
            if cursor.rowcount != 1:
                raise StorageError(f"Notification {opportunity_id} is not claimed for sending.")
            connection.execute(
                """
                UPDATE opportunities
                SET status = ?, last_error = NULL, updated_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    OpportunityStatus.NOTIFIED.value,
                    now,
                    opportunity_id,
                    OpportunityStatus.ANALYZED.value,
                ),
            )

    def mark_notification_failed(self, opportunity_id: int, error: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE telegram_notifications
                SET status = 'failed', last_error = ?, updated_at = ?
                WHERE opportunity_id = ? AND status = 'sending'
                """,
                (error[:1000], now, opportunity_id),
            )
            if cursor.rowcount != 1:
                raise StorageError(f"Notification {opportunity_id} is not claimed for sending.")

    def get_opportunity(self, opportunity_id: int) -> StoredOpportunity | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM opportunities WHERE id = ?",
                (opportunity_id,),
            ).fetchone()
        return self._to_stored_opportunity(row) if row is not None else None

    def save_user_profile(self, chat_id: str | int, profile: CandidateProfile) -> None:
        normalized_chat_id = str(chat_id).strip()
        if not normalized_chat_id:
            raise ValueError("chat_id cannot be empty.")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_profiles (
                    chat_id, positioning, skills_json, preferred_tasks_json,
                    avoid_tasks_json, preferences_json, common_preferences_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    positioning = excluded.positioning,
                    skills_json = excluded.skills_json,
                    preferred_tasks_json = excluded.preferred_tasks_json,
                    avoid_tasks_json = excluded.avoid_tasks_json,
                    preferences_json = excluded.preferences_json,
                    common_preferences_json = excluded.common_preferences_json,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_chat_id,
                    profile.positioning,
                    json.dumps(profile.skills, ensure_ascii=False),
                    json.dumps(profile.preferred_tasks, ensure_ascii=False),
                    json.dumps(profile.avoid_tasks, ensure_ascii=False),
                    json.dumps(profile.preferences, ensure_ascii=False),
                    json.dumps(profile.common_preferences, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            connection.execute(
                "DELETE FROM profile_search_tracks WHERE chat_id = ?",
                (normalized_chat_id,),
            )
            for track in profile.search_tracks:
                connection.execute(
                    """
                    INSERT INTO profile_search_tracks (
                        chat_id, track_id, name, details_json, enabled, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_chat_id,
                        track.track_id,
                        track.name,
                        json.dumps(track.to_dict(), ensure_ascii=False),
                        int(track.enabled),
                        now,
                        now,
                    ),
                )

    def get_user_profile(self, chat_id: str | int) -> CandidateProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM user_profiles WHERE chat_id = ?",
                (str(chat_id).strip(),),
            ).fetchone()
        if row is None:
            return None
        with self._connect() as connection:
            track_rows = connection.execute(
                """
                SELECT track_id, name, details_json, enabled
                FROM profile_search_tracks
                WHERE chat_id = ?
                ORDER BY rowid ASC
                """,
                (str(chat_id).strip(),),
            ).fetchall()
        search_tracks: list[SearchTrack] = []
        for track_row in track_rows:
            try:
                details = json.loads(track_row["details_json"])
            except json.JSONDecodeError as exc:
                raise StorageError("Stored search track contains invalid JSON.") from exc
            if not isinstance(details, dict):
                raise StorageError("Stored search track must be a JSON object.")
            details["track_id"] = track_row["track_id"]
            details["name"] = track_row["name"]
            details["enabled"] = bool(track_row["enabled"])
            try:
                search_tracks.append(SearchTrack.from_mapping(details))
            except ValueError as exc:
                raise StorageError("Stored search track is invalid.") from exc
        common_preferences_raw = row["common_preferences_json"]
        if common_preferences_raw is None:
            common_preferences: tuple[str, ...] = ()
        else:
            try:
                common_preferences = tuple(json.loads(common_preferences_raw))
            except (TypeError, json.JSONDecodeError) as exc:
                raise StorageError("Stored common profile preferences are invalid.") from exc
        return CandidateProfile(
            positioning=row["positioning"],
            skills=tuple(json.loads(row["skills_json"])),
            preferred_tasks=tuple(json.loads(row["preferred_tasks_json"])),
            avoid_tasks=tuple(json.loads(row["avoid_tasks_json"])),
            preferences=tuple(json.loads(row["preferences_json"])),
            common_preferences=common_preferences,
            search_tracks=tuple(search_tracks),
        )

    def save_profile_session(
        self,
        chat_id: str | int,
        *,
        step: int,
        draft: Mapping[str, Any],
    ) -> None:
        if step < 0:
            raise ValueError("Profile session step cannot be negative.")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO profile_sessions (chat_id, step, draft_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    step = excluded.step,
                    draft_json = excluded.draft_json,
                    updated_at = excluded.updated_at
                """,
                (str(chat_id).strip(), step, json.dumps(dict(draft), ensure_ascii=False), now),
            )

    def get_profile_session(self, chat_id: str | int) -> ProfileSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM profile_sessions WHERE chat_id = ?",
                (str(chat_id).strip(),),
            ).fetchone()
        if row is None:
            return None
        draft = json.loads(row["draft_json"])
        if not isinstance(draft, dict):
            raise StorageError("Stored profile draft must be a JSON object.")
        return ProfileSession(
            chat_id=row["chat_id"],
            step=row["step"],
            draft=draft,
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def delete_profile_session(self, chat_id: str | int) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM profile_sessions WHERE chat_id = ?",
                (str(chat_id).strip(),),
            )

    def get_bot_offset(self) -> int | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM bot_state WHERE key = 'telegram_update_offset'"
            ).fetchone()
        return int(row["value"]) if row is not None else None

    def set_bot_offset(self, offset: int) -> None:
        if offset < 0:
            raise ValueError("Telegram update offset cannot be negative.")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO bot_state (key, value) VALUES ('telegram_update_offset', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (str(offset),),
            )

    def get_paired_chat_id(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM bot_state WHERE key = 'telegram_paired_chat_id'"
            ).fetchone()
        return row["value"] if row is not None else None

    def set_paired_chat_id(self, chat_id: str | int) -> None:
        normalized_chat_id = str(chat_id).strip()
        if not normalized_chat_id:
            raise ValueError("Paired Telegram chat ID cannot be empty.")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO bot_state (key, value) VALUES ('telegram_paired_chat_id', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (normalized_chat_id,),
            )

    def set_service_heartbeat(self, service_name: str) -> None:
        key = self._heartbeat_key(service_name)
        value = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO bot_state (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def get_service_heartbeat(self, service_name: str) -> datetime | None:
        key = self._heartbeat_key(service_name)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM bot_state WHERE key = ?",
                (key,),
            ).fetchone()
        return datetime.fromisoformat(row["value"]) if row is not None else None

    def source_is_due(
        self,
        source: str,
        interval_seconds: int,
        *,
        now: datetime | None = None,
    ) -> bool:
        source = self._source_name(source)
        if interval_seconds < 1:
            raise ValueError("Source interval must be greater than or equal to 1.")
        current = self._aware_utc(now)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT last_attempt_at FROM source_states WHERE source = ?",
                (source,),
            ).fetchone()
        if row is None:
            return True
        last_attempt = datetime.fromisoformat(row["last_attempt_at"])
        if last_attempt.tzinfo is None:
            raise StorageError(f"Source state for {source} contains a naive timestamp.")
        return (current - last_attempt.astimezone(timezone.utc)).total_seconds() >= interval_seconds

    def start_source_run(self, source: str, *, started_at: datetime | None = None) -> int:
        source = self._source_name(source)
        started = self._aware_utc(started_at).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO source_runs (source, status, started_at)
                VALUES (?, 'running', ?)
                """,
                (source, started),
            )
            connection.execute(
                """
                INSERT INTO source_states (
                    source, last_attempt_at, last_status, updated_at
                ) VALUES (?, ?, 'running', ?)
                ON CONFLICT(source) DO UPDATE SET
                    last_attempt_at = excluded.last_attempt_at,
                    last_status = 'running',
                    last_error = NULL,
                    updated_at = excluded.updated_at
                """,
                (source, started, started),
            )
        return int(cursor.lastrowid)

    def finish_source_run(
        self,
        run_id: int,
        source: str,
        *,
        status: str,
        received_count: int = 0,
        saved_count: int = 0,
        duplicate_count: int = 0,
        deferred_count: int = 0,
        last_error: str | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        source = self._source_name(source)
        if status not in {"completed", "failed"}:
            raise ValueError("Finished source run status must be completed or failed.")
        counts = (received_count, saved_count, duplicate_count, deferred_count)
        if any(value < 0 for value in counts):
            raise ValueError("Source run counters cannot be negative.")
        finished = self._aware_utc(finished_at).isoformat()
        error = last_error[:1000] if last_error else None
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE source_runs
                SET status = ?, received_count = ?, saved_count = ?,
                    duplicate_count = ?, deferred_count = ?, last_error = ?, finished_at = ?
                WHERE id = ? AND source = ? AND status = 'running'
                """,
                (
                    status,
                    received_count,
                    saved_count,
                    duplicate_count,
                    deferred_count,
                    error,
                    finished,
                    run_id,
                    source,
                ),
            )
            if cursor.rowcount != 1:
                raise StorageError(f"Source run {run_id} for {source} is not active.")
            state_cursor = connection.execute(
                """
                UPDATE source_states
                SET last_success_at = CASE WHEN ? = 'completed' THEN ? ELSE last_success_at END,
                    last_status = ?, last_error = ?, last_received = ?,
                    last_saved = ?, last_duplicates = ?, last_deferred = ?, updated_at = ?
                WHERE source = ?
                """,
                (
                    status,
                    finished,
                    status,
                    error,
                    received_count,
                    saved_count,
                    duplicate_count,
                    deferred_count,
                    finished,
                    source,
                ),
            )
            if state_cursor.rowcount != 1:
                raise StorageError(f"Source state for {source} does not exist.")

    def recover_interrupted_source_runs(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        error = "Worker stopped before the source collection completed."
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT source FROM source_runs WHERE status = 'running'"
            ).fetchall()
            cursor = connection.execute(
                """
                UPDATE source_runs
                SET status = 'failed', last_error = ?, finished_at = ?
                WHERE status = 'running'
                """,
                (error, now),
            )
            for row in rows:
                connection.execute(
                    """
                    UPDATE source_states
                    SET last_status = 'failed', last_error = ?, updated_at = ?
                    WHERE source = ? AND last_status = 'running'
                    """,
                    (error, now, row["source"]),
                )
        return cursor.rowcount

    def get_source_state(self, source: str) -> SourceState | None:
        source = self._source_name(source)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM source_states WHERE source = ?",
                (source,),
            ).fetchone()
        if row is None:
            return None
        return SourceState(
            source=row["source"],
            last_attempt_at=datetime.fromisoformat(row["last_attempt_at"]),
            last_success_at=(
                datetime.fromisoformat(row["last_success_at"])
                if row["last_success_at"]
                else None
            ),
            last_status=row["last_status"],
            last_error=row["last_error"],
            last_received=row["last_received"],
            last_saved=row["last_saved"],
            last_duplicates=row["last_duplicates"],
            last_deferred=row["last_deferred"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def start_system_run(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO system_runs (status, summary_json, started_at)
                VALUES ('running', '{}', ?)
                """,
                (now,),
            )
        return int(cursor.lastrowid)

    def finish_system_run(
        self,
        run_id: int,
        *,
        status: str,
        summary: Mapping[str, Any],
        last_error: str | None = None,
    ) -> None:
        if status not in {"completed", "failed"}:
            raise ValueError("Finished system run status must be completed or failed.")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE system_runs
                SET status = ?, summary_json = ?, last_error = ?, finished_at = ?
                WHERE id = ? AND status = 'running'
                """,
                (
                    status,
                    json.dumps(dict(summary), ensure_ascii=False),
                    last_error[:1000] if last_error else None,
                    now,
                    run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise StorageError(f"System run {run_id} is not active.")

    def recover_interrupted_system_runs(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE system_runs
                SET status = 'failed',
                    last_error = 'Worker stopped before the cycle completed.',
                    finished_at = ?
                WHERE status = 'running'
                """,
                (now,),
            )
        return cursor.rowcount

    def recover_interrupted_analyses(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE opportunities
                SET status = ?,
                    last_error = 'Recovered analysis interrupted by worker shutdown.',
                    updated_at = ?
                WHERE status = ?
                """,
                (
                    OpportunityStatus.NEW.value,
                    now,
                    OpportunityStatus.ANALYZING.value,
                ),
            )
        return cursor.rowcount

    def get_latest_system_run(self) -> SystemRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM system_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        summary = json.loads(row["summary_json"])
        if not isinstance(summary, dict):
            raise StorageError("Stored system run summary must be a JSON object.")
        return SystemRun(
            id=row["id"],
            status=row["status"],
            summary=summary,
            last_error=row["last_error"],
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=(
                datetime.fromisoformat(row["finished_at"])
                if row["finished_at"]
                else None
            ),
        )

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM opportunities").fetchone()
        return int(row["count"])

    def count_pending_analysis(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM opportunities WHERE status = ?",
                (OpportunityStatus.NEW.value,),
            ).fetchone()
        return int(row["count"])

    def get_opportunity_sources(self, opportunity_id: int) -> list[OpportunitySource]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT opportunity_id, source, external_id, url, canonical_url,
                       first_seen_at, last_seen_at
                FROM opportunity_sources
                WHERE opportunity_id = ?
                ORDER BY first_seen_at ASC, id ASC
                """,
                (opportunity_id,),
            ).fetchall()
        return [
            OpportunitySource(
                opportunity_id=row["opportunity_id"],
                source=row["source"],
                external_id=row["external_id"],
                url=row["url"],
                canonical_url=row["canonical_url"],
                first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
                last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
            )
            for row in rows
        ]

    @staticmethod
    def _ensure_column(
        connection: sqlite3.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        columns = {
            row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _migrate_legacy_profile_directions(connection: sqlite3.Connection) -> None:
        """Preserve Block 9.1 profiles while replacing fixed directions with free tracks."""
        rows = connection.execute(
            """
            SELECT legacy.chat_id, legacy.direction, legacy.details_json,
                   legacy.created_at, legacy.updated_at
            FROM profile_directions AS legacy
            WHERE NOT EXISTS (
                SELECT 1 FROM profile_search_tracks AS tracks
                WHERE tracks.chat_id = legacy.chat_id
            )
            ORDER BY legacy.chat_id ASC, legacy.direction ASC
            """
        ).fetchall()
        names = {
            "ai_automation": "AI Automation",
            "infrastructure_business_projects": "Infrastructure & Business Projects",
        }
        for row in rows:
            try:
                legacy = json.loads(row["details_json"])
            except json.JSONDecodeError as exc:
                raise StorageError("Legacy profile direction contains invalid JSON.") from exc
            if not isinstance(legacy, dict):
                raise StorageError("Legacy profile direction must be a JSON object.")
            direction = row["direction"]
            track_id = f"legacy-{direction}"
            details = {
                "track_id": track_id,
                "name": names.get(direction, direction.replace("_", " ").title()),
                "target_description": names.get(direction, direction.replace("_", " ").title()),
                "roles_and_signals": legacy.get("matching_signals", []),
                "skills_and_experience": legacy.get("skills", []),
                "tasks_and_outcomes": legacy.get("task_outcomes", []),
                "locations": [],
                "work_formats": legacy.get("role_preferences", []),
                "growth_opportunities": legacy.get("growth_opportunities", []),
                "enabled": True,
            }
            connection.execute(
                """
                INSERT INTO profile_search_tracks (
                    chat_id, track_id, name, details_json, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    row["chat_id"],
                    track_id,
                    details["name"],
                    json.dumps(details, ensure_ascii=False),
                    row["created_at"],
                    row["updated_at"],
                ),
            )

    @staticmethod
    def _insert_opportunity_source(
        connection: sqlite3.Connection,
        *,
        opportunity_id: int,
        opportunity: Opportunity,
        canonical_url: str,
        seen_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO opportunity_sources (
                opportunity_id, source, external_id, url, canonical_url,
                first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity_id,
                opportunity.source,
                opportunity.external_id,
                opportunity.url,
                canonical_url,
                seen_at,
                seen_at,
            ),
        )

    @staticmethod
    def _backfill_opportunity_identity(connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT * FROM opportunities
            WHERE canonical_url IS NULL OR content_fingerprint IS NULL
               OR NOT EXISTS (
                   SELECT 1 FROM opportunity_sources AS source
                   WHERE source.source = opportunities.source
                     AND source.external_id = opportunities.external_id
               )
            ORDER BY id ASC
            """
        ).fetchall()
        for row in rows:
            opportunity = OpportunityRepository._to_stored_opportunity(row).opportunity
            canonical_url = canonicalize_url(opportunity.url)
            fingerprint = opportunity_fingerprint(opportunity)
            connection.execute(
                """
                UPDATE opportunities
                SET canonical_url = ?, content_fingerprint = ?
                WHERE id = ?
                """,
                (canonical_url, fingerprint, row["id"]),
            )
            connection.execute(
                """
                INSERT INTO opportunity_sources (
                    opportunity_id, source, external_id, url, canonical_url,
                    first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    opportunity_id = excluded.opportunity_id,
                    url = excluded.url,
                    canonical_url = excluded.canonical_url,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    row["id"],
                    opportunity.source,
                    opportunity.external_id,
                    opportunity.url,
                    canonical_url,
                    row["created_at"],
                    row["updated_at"],
                ),
            )

    @staticmethod
    def _heartbeat_key(service_name: str) -> str:
        normalized = service_name.strip().lower()
        if not re.fullmatch(r"[a-z0-9_-]+", normalized):
            raise ValueError("Service name may contain only a-z, 0-9, underscore and hyphen.")
        return f"heartbeat:{normalized}"

    @staticmethod
    def _source_name(source: str) -> str:
        normalized = source.strip().lower()
        if not re.fullmatch(r"[a-z0-9_-]+", normalized):
            raise ValueError("Source name may contain only a-z, 0-9, underscore and hyphen.")
        return normalized

    @staticmethod
    def _aware_utc(value: datetime | None) -> datetime:
        current = value or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("Source schedule timestamps must include timezone information.")
        return current.astimezone(timezone.utc)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.database_path, timeout=10)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            yield connection
            connection.commit()
        except sqlite3.Error as exc:
            if connection is not None:
                connection.rollback()
            raise StorageError(f"SQLite operation failed for {self.database_path}: {exc}") from exc
        except Exception:
            if connection is not None:
                connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _to_stored_opportunity(row: sqlite3.Row) -> StoredOpportunity:
        opportunity = Opportunity(
            source=row["source"],
            external_id=row["external_id"],
            title=row["title"],
            description=row["description"],
            url=row["url"],
            company_name=row["company_name"],
            location=row["location"],
            remote_type=RemoteType(row["remote_type"]),
            salary_from=row["salary_from"],
            salary_to=row["salary_to"],
            currency=row["currency"],
            published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
            collected_at=datetime.fromisoformat(row["collected_at"]),
        )
        return StoredOpportunity(
            id=row["id"],
            opportunity=opportunity,
            status=OpportunityStatus(row["status"]),
            last_error=row["last_error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
