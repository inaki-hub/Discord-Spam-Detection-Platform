from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import desc, func, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.dashboard.db import get_sync_engine
from app.storage.models import (
    AlertRecord,
    DatasetSampleRecord,
    DetectionRecord,
    MessageRecord,
    UserFeatureRecord,
)


@dataclass(frozen=True)
class OverviewStats:
    messages: int
    detections: int
    alerts: int
    users: int
    dataset_samples: int
    dataset_labeled: int


@dataclass(frozen=True)
class AlertSummary:
    timestamp: datetime
    guild_id: str
    user_id: str
    channel_id: str | None
    spam_score: int | None
    automation_score: int | None


@dataclass(frozen=True)
class SuspiciousUserRow:
    guild_id: str
    user_id: str
    max_spam_score: int
    max_automation_score: int
    last_activity: datetime
    flagged_events: int


@dataclass(frozen=True)
class TimelineItem:
    timestamp: datetime
    kind: str
    title: str
    spam_score: int | None
    automation_score: int | None
    spam_classification: str | None
    automation_classification: str | None
    signals: dict | list | None
    extra: dict


@dataclass(frozen=True)
class MessageTimelineRow:
    """Un mensaje con detección/dataset/alerta fusionados (vista de investigación)."""

    timestamp: datetime
    message_id: str
    channel_id: str
    content: str
    spam_score: int | None
    automation_score: int | None
    spam_classification: str | None
    automation_classification: str | None
    signals: dict | None
    label: str | None
    urls: list
    triggered_alert: bool


def overview_stats(*, engine: Engine | None = None) -> OverviewStats:
    eng = engine or get_sync_engine()
    with Session(eng) as session:
        messages = session.scalar(select(func.count()).select_from(MessageRecord)) or 0
        detections = session.scalar(select(func.count()).select_from(DetectionRecord)) or 0
        alerts = session.scalar(select(func.count()).select_from(AlertRecord)) or 0
        users = session.scalar(
            select(func.count(func.distinct(DetectionRecord.user_id)))
        ) or 0
        dataset_samples = (
            session.scalar(select(func.count()).select_from(DatasetSampleRecord)) or 0
        )
        dataset_labeled = (
            session.scalar(
                select(func.count())
                .select_from(DatasetSampleRecord)
                .where(DatasetSampleRecord.label != "unknown")
            )
            or 0
        )
    return OverviewStats(
        messages=messages,
        detections=detections,
        alerts=alerts,
        users=users,
        dataset_samples=dataset_samples,
        dataset_labeled=dataset_labeled,
    )


def recent_alerts(*, limit: int = 15, engine: Engine | None = None) -> list[AlertSummary]:
    eng = engine or get_sync_engine()
    with Session(eng) as session:
        rows = (
            session.execute(
                select(AlertRecord)
                .order_by(desc(AlertRecord.timestamp))
                .limit(limit)
            )
            .scalars()
            .all()
        )
    return [
        AlertSummary(
            timestamp=row.timestamp,
            guild_id=row.guild_id,
            user_id=row.user_id,
            channel_id=row.channel_id,
            spam_score=row.spam_score,
            automation_score=row.automation_score,
        )
        for row in rows
    ]


def list_guild_ids(*, engine: Engine | None = None) -> list[str]:
    eng = engine or get_sync_engine()
    with Session(eng) as session:
        rows = session.execute(
            select(MessageRecord.guild_id).distinct().order_by(MessageRecord.guild_id)
        ).all()
    return [row[0] for row in rows]


def list_user_ids_in_guild(
    guild_id: str,
    *,
    limit: int = 150,
    engine: Engine | None = None,
) -> list[tuple[str, datetime]]:
    """Usuarios con actividad en el guild, ordenados por último mensaje."""
    eng = engine or get_sync_engine()
    stmt = (
        select(
            MessageRecord.author_id,
            func.max(MessageRecord.timestamp).label("last_seen"),
        )
        .where(MessageRecord.guild_id == guild_id)
        .group_by(MessageRecord.author_id)
        .order_by(desc(func.max(MessageRecord.timestamp)))
        .limit(limit)
    )
    with Session(eng) as session:
        rows = session.execute(stmt).all()
    return [(row.author_id, row.last_seen) for row in rows]


def list_suspicious_users(
    *,
    guild_id: str | None = None,
    min_score: int = 1,
    limit: int = 50,
    engine: Engine | None = None,
) -> list[SuspiciousUserRow]:
    eng = engine or get_sync_engine()
    flagged = or_(
        DetectionRecord.spam_classification != "normal",
        DetectionRecord.automation_classification != "normal",
        DetectionRecord.spam_score >= min_score,
        DetectionRecord.automation_score >= min_score,
    )
    stmt = (
        select(
            DetectionRecord.guild_id,
            DetectionRecord.user_id,
            func.max(DetectionRecord.spam_score).label("max_spam"),
            func.max(DetectionRecord.automation_score).label("max_automation"),
            func.max(DetectionRecord.timestamp).label("last_activity"),
            func.count().label("events"),
        )
        .where(flagged)
        .group_by(DetectionRecord.guild_id, DetectionRecord.user_id)
        .order_by(
            desc(func.max(DetectionRecord.spam_score) + func.max(DetectionRecord.automation_score))
        )
        .limit(limit)
    )
    if guild_id:
        stmt = stmt.where(DetectionRecord.guild_id == guild_id)

    with Session(eng) as session:
        rows = session.execute(stmt).all()

    return [
        SuspiciousUserRow(
            guild_id=row.guild_id,
            user_id=row.user_id,
            max_spam_score=int(row.max_spam or 0),
            max_automation_score=int(row.max_automation or 0),
            last_activity=row.last_activity,
            flagged_events=int(row.events),
        )
        for row in rows
    ]


def user_profile_snapshot(
    guild_id: str,
    user_id: str,
    *,
    engine: Engine | None = None,
) -> dict | None:
    eng = engine or get_sync_engine()
    with Session(eng) as session:
        row = session.scalar(
            select(UserFeatureRecord).where(
                UserFeatureRecord.guild_id == guild_id,
                UserFeatureRecord.user_id == user_id,
            )
        )
    return dict(row.profile) if row else None


def user_timeline(
    guild_id: str,
    user_id: str,
    *,
    limit: int = 80,
    engine: Engine | None = None,
) -> list[TimelineItem]:
    eng = engine or get_sync_engine()
    items: list[TimelineItem] = []

    with Session(eng) as session:
        messages = (
            session.execute(
                select(MessageRecord)
                .where(
                    MessageRecord.guild_id == guild_id,
                    MessageRecord.author_id == user_id,
                )
                .order_by(desc(MessageRecord.timestamp))
                .limit(limit)
            )
            .scalars()
            .all()
        )
        detections = (
            session.execute(
                select(DetectionRecord)
                .where(
                    DetectionRecord.guild_id == guild_id,
                    DetectionRecord.user_id == user_id,
                )
                .order_by(desc(DetectionRecord.timestamp))
                .limit(limit)
            )
            .scalars()
            .all()
        )
        alerts = (
            session.execute(
                select(AlertRecord)
                .where(
                    AlertRecord.guild_id == guild_id,
                    AlertRecord.user_id == user_id,
                )
                .order_by(desc(AlertRecord.timestamp))
                .limit(limit)
            )
            .scalars()
            .all()
        )
        samples = (
            session.execute(
                select(DatasetSampleRecord)
                .where(
                    DatasetSampleRecord.guild_id == guild_id,
                    DatasetSampleRecord.user_id == user_id,
                )
                .order_by(desc(DatasetSampleRecord.timestamp))
                .limit(limit)
            )
            .scalars()
            .all()
        )

    label_by_message = {row.message_id: row.label for row in samples}

    for msg in messages:
        preview = msg.content.replace("\n", " ")
        if len(preview) > 120:
            preview = preview[:117] + "..."
        items.append(
            TimelineItem(
                timestamp=msg.timestamp,
                kind="message",
                title=preview or "(vacío)",
                spam_score=None,
                automation_score=None,
                spam_classification=None,
                automation_classification=None,
                signals=None,
                extra={
                    "message_id": msg.message_id,
                    "channel_id": msg.channel_id,
                    "urls": msg.urls,
                    "label": label_by_message.get(msg.message_id),
                },
            )
        )

    for det in detections:
        items.append(
            TimelineItem(
                timestamp=det.timestamp,
                kind="detection",
                title="Evaluación de detección",
                spam_score=det.spam_score,
                automation_score=det.automation_score,
                spam_classification=det.spam_classification,
                automation_classification=det.automation_classification,
                signals=det.signals,
                extra={},
            )
        )

    for alert in alerts:
        payload = alert.payload or {}
        items.append(
            TimelineItem(
                timestamp=alert.timestamp,
                kind="alert",
                title="Alerta registrada",
                spam_score=alert.spam_score,
                automation_score=alert.automation_score,
                spam_classification=payload.get("spam_classification"),
                automation_classification=payload.get("automation_classification"),
                signals=alert.signals,
                extra={"channel_id": alert.channel_id, "evidence": payload.get("evidence", [])},
            )
        )

    for sample in samples:
        items.append(
            TimelineItem(
                timestamp=sample.timestamp,
                kind="dataset",
                title=f"Muestra dataset — label={sample.label}",
                spam_score=sample.spam_score,
                automation_score=sample.automation_score,
                spam_classification=sample.spam_classification,
                automation_classification=sample.automation_classification,
                signals=sample.detection_signals,
                extra={"message_id": sample.message_id, "label": sample.label},
            )
        )

    items.sort(key=lambda item: item.timestamp, reverse=True)
    return items[:limit]


def _timeline_is_relevant(row: MessageTimelineRow) -> bool:
    if row.triggered_alert:
        return True
    if (row.spam_classification or "normal") != "normal":
        return True
    if (row.automation_classification or "normal") != "normal":
        return True
    if row.signals:
        spam = row.signals.get("spam") or []
        auto = row.signals.get("automation") or []
        if spam or auto:
            return True
    if row.label and row.label != "unknown":
        return True
    return False


def user_message_timeline(
    guild_id: str,
    user_id: str,
    *,
    limit: int = 80,
    only_relevant: bool = False,
    engine: Engine | None = None,
) -> list[MessageTimelineRow]:
    """
    Línea temporal centrada en mensajes: evita duplicar detection/dataset/alert
    como entradas separadas.
    """
    eng = engine or get_sync_engine()
    with Session(eng) as session:
        messages = (
            session.execute(
                select(MessageRecord)
                .where(
                    MessageRecord.guild_id == guild_id,
                    MessageRecord.author_id == user_id,
                )
                .order_by(desc(MessageRecord.timestamp))
                .limit(limit)
            )
            .scalars()
            .all()
        )
        if not messages:
            return []

        detections = (
            session.execute(
                select(DetectionRecord)
                .where(
                    DetectionRecord.guild_id == guild_id,
                    DetectionRecord.user_id == user_id,
                )
                .order_by(desc(DetectionRecord.timestamp))
                .limit(limit * 2)
            )
            .scalars()
            .all()
        )
        alerts = (
            session.execute(
                select(AlertRecord)
                .where(
                    AlertRecord.guild_id == guild_id,
                    AlertRecord.user_id == user_id,
                )
                .order_by(desc(AlertRecord.timestamp))
                .limit(limit * 2)
            )
            .scalars()
            .all()
        )
        samples = (
            session.execute(
                select(DatasetSampleRecord)
                .where(
                    DatasetSampleRecord.guild_id == guild_id,
                    DatasetSampleRecord.user_id == user_id,
                )
                .order_by(desc(DatasetSampleRecord.timestamp))
                .limit(limit * 2)
            )
            .scalars()
            .all()
        )

    det_by_ts = {d.timestamp: d for d in detections}
    alert_ts = {a.timestamp for a in alerts}
    sample_by_mid = {s.message_id: s for s in samples}

    rows: list[MessageTimelineRow] = []
    for msg in messages:
        det = det_by_ts.get(msg.timestamp)
        sample = sample_by_mid.get(msg.message_id)
        signals = det.signals if det and isinstance(det.signals, dict) else None
        if sample and not signals:
            signals = sample.detection_signals

        spam_score = det.spam_score if det else (sample.spam_score if sample else None)
        auto_score = det.automation_score if det else (
            sample.automation_score if sample else None
        )
        spam_cls = (
            det.spam_classification
            if det
            else (sample.spam_classification if sample else None)
        )
        auto_cls = (
            det.automation_classification
            if det
            else (sample.automation_classification if sample else None)
        )
        label = sample.label if sample else None

        rows.append(
            MessageTimelineRow(
                timestamp=msg.timestamp,
                message_id=msg.message_id,
                channel_id=msg.channel_id,
                content=msg.content,
                spam_score=spam_score,
                automation_score=auto_score,
                spam_classification=spam_cls,
                automation_classification=auto_cls,
                signals=signals,
                label=label,
                urls=list(msg.urls or []),
                triggered_alert=msg.timestamp in alert_ts,
            )
        )

    if only_relevant:
        rows = [r for r in rows if _timeline_is_relevant(r)]
    return rows
