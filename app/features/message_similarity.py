from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

# Umbral documentado: texto muy parecido sin ser hash idéntico.
HIGH_SIMILARITY_THRESHOLD = 0.85

# Mensajes recientes con los que comparar (mismo usuario en el guild).
RECENT_MESSAGES_FOR_SIMILARITY = 20


@dataclass(frozen=True)
class SimilarityResult:
    max_similarity: float
    high_similarity_content: bool
    exact_hash_match: bool

    def to_feature_dict(self) -> dict:
        return {
            "max_similarity_to_recent": round(self.max_similarity, 4),
            "high_similarity_content": self.high_similarity_content,
        }


def text_similarity(normalized_a: str, normalized_b: str) -> float:
    if not normalized_a or not normalized_b:
        return 0.0
    if normalized_a == normalized_b:
        return 1.0
    return SequenceMatcher(None, normalized_a, normalized_b).ratio()


def compare_to_recent(
    normalized_text: str,
    content_hash: str,
    recent: list[tuple[str, str]],
) -> SimilarityResult:
    """
    Compara con mensajes previos (normalizado, hash).
    `recent` no debe incluir el mensaje actual.
    """
    max_sim = 0.0
    exact_hash = False
    for prev_norm, prev_hash in recent:
        if prev_hash == content_hash:
            exact_hash = True
            max_sim = 1.0
            break
        sim = text_similarity(normalized_text, prev_norm)
        if sim > max_sim:
            max_sim = sim

    high = max_sim >= HIGH_SIMILARITY_THRESHOLD and not exact_hash
    if exact_hash:
        high = False
    return SimilarityResult(
        max_similarity=max_sim,
        high_similarity_content=high,
        exact_hash_match=exact_hash,
    )
