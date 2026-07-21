"""Domain models shared by all JobMonitor providers."""

from models.analysis import AIAnalysis, Difficulty, RecommendationCategory, TrackAssessment
from models.opportunity import Opportunity, RemoteType
from models.profile import CandidateProfile, ProfileError, SearchTrack

__all__ = [
    "AIAnalysis",
    "CandidateProfile",
    "Difficulty",
    "Opportunity",
    "ProfileError",
    "RecommendationCategory",
    "SearchTrack",
    "TrackAssessment",
    "RemoteType",
]
