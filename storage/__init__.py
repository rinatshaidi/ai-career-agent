"""Persistent storage for normalized opportunities."""

from storage.repository import (
    NotificationCandidate,
    OpportunityRepository,
    OpportunityStatus,
    ProfileSession,
    SaveBatchResult,
    SourceState,
    StorageError,
    StoredAnalysis,
    StoredOpportunity,
    SystemRun,
)

__all__ = [
    "NotificationCandidate",
    "OpportunityRepository",
    "OpportunityStatus",
    "ProfileSession",
    "SaveBatchResult",
    "SourceState",
    "StorageError",
    "StoredAnalysis",
    "StoredOpportunity",
    "SystemRun",
]
