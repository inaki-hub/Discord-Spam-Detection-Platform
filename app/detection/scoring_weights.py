"""Pesos centralizados para motores de detección (reglas explicables)."""

# --- Spam ---
SCORE_HIGH_MESSAGE_RATE = 20
SCORE_DUPLICATE_CONTENT = 25
SCORE_CROSS_CHANNEL_REPETITION = 30
SCORE_REPEATED_DOMAIN = 15
SCORE_SIMILAR_CONTENT = 15
SCORE_HIGH_DUPLICATE_RATIO = 10

SPAM_THRESHOLD_SUSPICIOUS = 40
SPAM_THRESHOLD_LIKELY = 70

# --- Automatización ---
SCORE_REGULAR_INTERVALS = 35
SCORE_AUTOMATION_BURST = 25
SCORE_REPETITIVE_PATTERN = 20
SCORE_MULTI_CHANNEL_ACTIVITY = 20
SCORE_FAST_ACTIVITY = 15

AUTOMATION_THRESHOLD_SUSPICIOUS = 40
AUTOMATION_THRESHOLD_LIKELY = 70


def classify_spam_score(score: int) -> str:
    if score >= SPAM_THRESHOLD_LIKELY:
        return "spam_likely"
    if score >= SPAM_THRESHOLD_SUSPICIOUS:
        return "suspicious"
    return "normal"


def classify_automation_score(score: int) -> str:
    if score >= AUTOMATION_THRESHOLD_LIKELY:
        return "automation_likely"
    if score >= AUTOMATION_THRESHOLD_SUSPICIOUS:
        return "automation_suspicious"
    return "normal"
