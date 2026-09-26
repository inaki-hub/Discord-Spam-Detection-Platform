from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.collector.events import MessageEvent
from app.config import DATA_DIR, ensure_data_dir, get_settings
from app.storage.migrations import apply_sqlite_migrations

from app.features.message_features import MessageFeatures
from app.features.user_features import UserProfile
from app.alerts.alert_manager import Alert
from app.detection.automation_detector import AutomationDetectionResult
from app.detection.spam_detector import SpamDetectionResult
from app.storage.models import (
    Base,
    DetectionRecord,
    MessageFeatureRecord,
    MessageRecord,
    UserFeatureRecord,
    UserRecord,
    AlertRecord,
)

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _resolve_sqlite_url(url: str) -> str:
    if url.startswith("sqlite+aiosqlite:///./"):
        ensure_data_dir()
        db_path = (DATA_DIR / "spam_detector.db").resolve()
        return f"sqlite+aiosqlite:///{db_path.as_posix()}"
    return url


async def init_db() -> None:
    global _engine, _session_factory
    settings = get_settings()
    url = _resolve_sqlite_url(settings.database_url)
    _engine = create_async_engine(url, echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(apply_sqlite_migrations)

    from app.storage.retention import run_data_retention

    await run_data_retention()


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _session_factory


async def save_message_event(
    event: MessageEvent,
    features: MessageFeatures | None = None,
) -> bool:
    """
    Persiste MessageEvent y, opcionalmente, sus características.
    Devuelve True si el mensaje es nuevo; False si ya existía.
    """
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    record = MessageRecord(
        message_id=event.message_id,
        guild_id=event.guild_id,
        channel_id=event.channel_id,
        author_id=event.author_id,
        timestamp=event.timestamp,
        content=event.content,
        urls=list(event.urls),
        attachments=list(event.attachments),
        mentions=list(event.mentions),
        created_at=now,
    )
    async with factory() as session:
        session.add(record)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return False

    if features is not None:
        feature_record = MessageFeatureRecord(
            message_id=event.message_id,
            guild_id=event.guild_id,
            author_id=event.author_id,
            content_hash=features.content_hash,
            features=features.to_dict(),
            created_at=now,
        )
        async with factory() as session:
            session.add(feature_record)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()

    return True


async def save_message_features(event: MessageEvent, features: MessageFeatures) -> None:
    """Persiste características de un mensaje ya guardado."""
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    feature_record = MessageFeatureRecord(
        message_id=event.message_id,
        guild_id=event.guild_id,
        author_id=event.author_id,
        content_hash=features.content_hash,
        features=features.to_dict(),
        created_at=now,
    )
    async with factory() as session:
        session.add(feature_record)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()


async def save_user_profile(profile: UserProfile) -> None:
    """Persiste snapshot del perfil (upsert por guild + usuario)."""
    factory = get_session_factory()
    now = datetime.now(timezone.utc)

    async with factory() as session:
        user_result = await session.execute(
            select(UserRecord).where(
                UserRecord.guild_id == profile.guild_id,
                UserRecord.user_id == profile.user_id,
            )
        )
        user_row = user_result.scalar_one_or_none()
        if user_row is None:
            session.add(
                UserRecord(
                    guild_id=profile.guild_id,
                    user_id=profile.user_id,
                    first_seen=profile.first_seen,
                    last_seen=profile.last_seen,
                )
            )
        else:
            user_row.last_seen = profile.last_seen

        feat_result = await session.execute(
            select(UserFeatureRecord).where(
                UserFeatureRecord.guild_id == profile.guild_id,
                UserFeatureRecord.user_id == profile.user_id,
            )
        )
        feat_row = feat_result.scalar_one_or_none()
        if feat_row is None:
            session.add(
                UserFeatureRecord(
                    guild_id=profile.guild_id,
                    user_id=profile.user_id,
                    profile=profile.to_dict(),
                    updated_at=now,
                )
            )
        else:
            feat_row.profile = profile.to_dict()
            feat_row.updated_at = now

        await session.commit()


async def save_detection(
    event: MessageEvent,
    spam: SpamDetectionResult,
    automation: AutomationDetectionResult | None = None,
    *,
    ml: dict | None = None,
    hybrid: dict | None = None,
) -> None:
    """Registra una evaluación de detección (observación, sin moderación)."""
    factory = get_session_factory()
    signals_payload: dict = {
        "spam": list(spam.signals),
        "automation": list(automation.signals) if automation else [],
    }
    if ml:
        signals_payload["ml"] = ml
    if hybrid:
        signals_payload["hybrid"] = hybrid
    record = DetectionRecord(
        user_id=event.author_id,
        guild_id=event.guild_id,
        timestamp=event.timestamp,
        spam_score=spam.score,
        automation_score=automation.score if automation else None,
        spam_classification=spam.classification,
        automation_classification=automation.classification if automation else None,
        signals=signals_payload,
    )
    async with factory() as session:
        session.add(record)
        await session.commit()


async def save_alert(alert: Alert) -> None:
    """Persiste una alerta (sin contenido completo del historial del usuario)."""
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    record = AlertRecord(
        user_id=alert.user_id,
        guild_id=alert.guild_id,
        channel_id=alert.channel_id,
        timestamp=alert.timestamp,
        spam_score=alert.spam_score,
        automation_score=alert.automation_score,
        signals=alert.signals,
        payload={
            "spam_classification": alert.spam_classification,
            "automation_classification": alert.automation_classification,
            "evidence": list(alert.evidence),
        },
    )
    async with factory() as session:
        session.add(record)
        await session.commit()
