from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.detection.hybrid_config import HybridConfig
from app.moderation.settings import ModerationSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    discord_token: str
    database_url: str
    log_level: str
    """Días de retención en SQLite; 0 = no purgar."""
    data_retention_days: int
    """guild_id -> channel_id de moderación para alertas del bot."""
    alert_channels: dict[str, str]
    """Atajo: solo channel_id (un servidor / canal único)."""
    default_alert_channel: str
    raw_alert_channels: str
    """Activa predicción ML complementaria (requiere modelo entrenado)."""
    ml_enabled: bool
    ml_model_path: str
    ml_hybrid_enabled: bool
    ml_score_boost_max: int
    ml_alert_spam_threshold: float
    ml_alert_automation_threshold: float
    ml_hybrid_min_duplicate_ratio: float
    moderation: ModerationSettings
    hybrid: HybridConfig
    """Canal opcional donde solo se aceptan comandos !mod (vacío = cualquier canal)."""
    mod_config_channel_id: str


def _parse_positive_int(raw: str, default: int) -> int:
    text = raw.strip()
    if not text:
        return default
    try:
        value = int(text)
    except ValueError:
        return default
    return max(0, value)


def _parse_float(raw: str, default: float) -> float:
    text = raw.strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _parse_bool(raw: str, default: bool = False) -> bool:
    text = raw.strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on"}


def get_ml_model_path() -> Path:
    settings = get_settings()
    raw = settings.ml_model_path.strip()
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        return path
    return (DATA_DIR / "models" / "ml_bundle.joblib").resolve()


def _parse_alert_channels(raw: str) -> tuple[dict[str, str], str]:
    """
    Formatos aceptados (separados por coma):
    - guild_id:channel_id  →  recomendado
    - channel_id           →  atajo (valida guild al enviar)
    """
    mapping: dict[str, str] = {}
    default_channel = ""
    if not raw.strip():
        return mapping, default_channel
    for part in raw.split(","):
        piece = part.strip()
        if not piece:
            continue
        if ":" in piece:
            guild_id, channel_id = piece.split(":", 1)
            guild_id = guild_id.strip()
            channel_id = channel_id.strip()
            if guild_id.isdigit() and channel_id.isdigit():
                mapping[guild_id] = channel_id
        elif piece.isdigit() and not default_channel:
            default_channel = piece
    return mapping, default_channel


def get_settings() -> Settings:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    database_url = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./data/spam_detector.db",
    ).strip()
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    raw_alert = os.getenv("ALERT_CHANNELS", "").strip()
    alert_channels, default_alert_channel = _parse_alert_channels(raw_alert)
    data_retention_days = _parse_positive_int(os.getenv("DATA_RETENTION_DAYS", "0"), 0)
    ml_enabled = _parse_bool(os.getenv("ML_ENABLED", "false"))
    ml_model_path = os.getenv("ML_MODEL_PATH", "").strip()
    ml_hybrid_enabled = _parse_bool(os.getenv("ML_HYBRID_ENABLED", "true"))
    ml_score_boost_max = _parse_positive_int(os.getenv("ML_SCORE_BOOST_MAX", "20"), 20)
    ml_alert_spam_threshold = _parse_float(os.getenv("ML_ALERT_SPAM_THRESHOLD", "0.85"), 0.85)
    ml_alert_automation_threshold = _parse_float(
        os.getenv("ML_ALERT_AUTOMATION_THRESHOLD", "0.85"), 0.85
    )
    ml_hybrid_min_duplicate_ratio = _parse_float(
        os.getenv("ML_HYBRID_MIN_DUPLICATE_RATIO", "0.25"), 0.25
    )
    hybrid = HybridConfig(
        ml_hybrid_enabled=ml_hybrid_enabled,
        ml_score_boost_max=ml_score_boost_max,
        ml_alert_spam_threshold=ml_alert_spam_threshold,
        ml_alert_automation_threshold=ml_alert_automation_threshold,
        ml_hybrid_min_duplicate_ratio=ml_hybrid_min_duplicate_ratio,
    )
    mod_config_channel_id = os.getenv("MOD_CONFIG_CHANNEL_ID", "").strip()
    moderation = ModerationSettings(
        enabled=_parse_bool(os.getenv("MODERATION_ENABLED", "false")),
        dry_run=_parse_bool(os.getenv("MODERATION_DRY_RUN", "true")),
        cooldown_seconds=_parse_positive_int(os.getenv("MODERATION_COOLDOWN_SECONDS", "300"), 300),
        penalize_spam=_parse_bool(os.getenv("MODERATION_PENALIZE_SPAM", "true")),
        penalize_automation=_parse_bool(os.getenv("MODERATION_PENALIZE_AUTOMATION", "false")),
        min_effective_spam_score=_parse_positive_int(
            os.getenv("MODERATION_MIN_SPAM_SCORE", "40"), 40
        ),
        min_effective_automation_score=_parse_positive_int(
            os.getenv("MODERATION_MIN_AUTOMATION_SCORE", "40"), 40
        ),
        timeout_spam_likely_seconds=_parse_positive_int(
            os.getenv("MODERATION_TIMEOUT_SPAM_LIKELY", "0"), 0
        ),
        timeout_suspicious_seconds=_parse_positive_int(
            os.getenv("MODERATION_TIMEOUT_SUSPICIOUS", "0"), 0
        ),
        timeout_automation_likely_seconds=_parse_positive_int(
            os.getenv("MODERATION_TIMEOUT_AUTOMATION_LIKELY", "0"), 0
        ),
        timeout_automation_suspicious_seconds=_parse_positive_int(
            os.getenv("MODERATION_TIMEOUT_AUTOMATION_SUSPICIOUS", "0"), 0
        ),
    )
    return Settings(
        discord_token=token,
        database_url=database_url,
        log_level=log_level,
        data_retention_days=data_retention_days,
        alert_channels=alert_channels,
        default_alert_channel=default_alert_channel,
        raw_alert_channels=raw_alert,
        ml_enabled=ml_enabled,
        ml_model_path=ml_model_path,
        ml_hybrid_enabled=ml_hybrid_enabled,
        ml_score_boost_max=ml_score_boost_max,
        ml_alert_spam_threshold=ml_alert_spam_threshold,
        ml_alert_automation_threshold=ml_alert_automation_threshold,
        ml_hybrid_min_duplicate_ratio=ml_hybrid_min_duplicate_ratio,
        moderation=moderation,
        hybrid=hybrid,
        mod_config_channel_id=mod_config_channel_id,
    )


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
