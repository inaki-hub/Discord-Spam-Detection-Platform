from app.features.message_features import (
    MessageFeatures,
    extract_message_features,
    normalize_message,
    normalized_content_hash,
)
from app.features.burst_detection import TemporalSignals, evaluate_temporal_signals
from app.features.duplicate_detection import DuplicateObservation, observe_content_hash
from app.features.cross_channel import CrossChannelResult, detect_cross_channel_repetition
from app.features.domain_analysis import DomainMetrics, observe_domains
from app.features.message_similarity import (
    HIGH_SIMILARITY_THRESHOLD,
    SimilarityResult,
    compare_to_recent,
    text_similarity,
)
from app.features.url_utils import extract_domain, extract_urls
from app.features.user_features import UserProfile, UserProfileStore

__all__ = [
    "MessageFeatures",
    "DuplicateObservation",
    "HIGH_SIMILARITY_THRESHOLD",
    "SimilarityResult",
    "TemporalSignals",
    "CrossChannelResult",
    "compare_to_recent",
    "DomainMetrics",
    "detect_cross_channel_repetition",
    "observe_domains",
    "text_similarity",
    "UserProfile",
    "UserProfileStore",
    "evaluate_temporal_signals",
    "observe_content_hash",
    "extract_domain",
    "extract_message_features",
    "extract_urls",
    "normalize_message",
    "normalized_content_hash",
]
