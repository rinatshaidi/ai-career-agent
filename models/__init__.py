"""Domain models shared by all JobMonitor providers."""

from models.analysis import AIAnalysis, Difficulty
from models.opportunity import Opportunity, RemoteType
from models.profile import CandidateProfile, ProfileError

__all__ = [
    "AIAnalysis",
    "CandidateProfile",
    "Difficulty",
    "Opportunity",
    "ProfileError",
    "RemoteType",
]
