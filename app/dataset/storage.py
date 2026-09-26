from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dataset.labels import DATASET_LABEL_UNKNOWN, normalize_label
from app.dataset.records import DatasetSample
from app.storage.database import get_session_factory
from app.storage.models import (
    DatasetSampleRecord,
    DetectionRecord,
    MessageFeatureRecord,
    MessageRecord,
    UserFeatureRecord,
)


async def save_dataset_sample(sample: DatasetSample) -> bool:
    """Inserta una muestra; False si el message_id ya existía."""
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    record = DatasetSampleRecord(
        message_id=sample.message_id,
        guild_id=sample.guild_id,
        channel_id=sample.channel_id,
        user_id=sample.user_id,
        timestamp=sample.timestamp,
        message_features=sample.message_features,
        user_features=sample.user_features,
        spam_score=sample.spam_score,
        automation_score=sample.automation_score,
        spam_classification=sample.spam_classification,
        automation_classification=sample.automation_classification,
        detection_signals=sample.detection_signals,
        label=sample.label,
        created_at=now,
    )
    async with factory() as session:
        session.add(record)
        try:
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()
            return False


async def get_dataset_label(message_id: str) -> str | None:
    factory = get_session_factory()
    async with factory() as session:
        row = await session.scalar(
            select(DatasetSampleRecord.label).where(
                DatasetSampleRecord.message_id == message_id
            )
        )
    return row


async def set_dataset_label(message_id: str, label: str) -> bool:
    """Actualiza etiqueta humana de una muestra."""
    normalized = normalize_label(label)
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(DatasetSampleRecord).where(DatasetSampleRecord.message_id == message_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        row.label = normalized
        await session.commit()
        return True


async def apply_dataset_label(message_id: str, label: str) -> bool:
    """Crea la fila en dataset si falta (backfill) y aplica la etiqueta."""
    if not await ensure_dataset_sample(message_id):
        return False
    return await set_dataset_label(message_id, label)


async def ensure_dataset_sample(message_id: str) -> bool:
    factory = get_session_factory()
    async with factory() as session:
        exists = await session.scalar(
            select(DatasetSampleRecord.id).where(
                DatasetSampleRecord.message_id == message_id
            )
        )
        if exists is not None:
            return True

        msg = await session.scalar(
            select(MessageRecord).where(MessageRecord.message_id == message_id)
        )
        if msg is None:
            return False

        feat = await session.scalar(
            select(MessageFeatureRecord).where(
                MessageFeatureRecord.message_id == message_id
            )
        )
        det = await session.scalar(
            select(DetectionRecord).where(
                DetectionRecord.guild_id == msg.guild_id,
                DetectionRecord.user_id == msg.author_id,
                DetectionRecord.timestamp == msg.timestamp,
            )
        )
        if det is None:
            det = await session.scalar(
                select(DetectionRecord)
                .where(
                    DetectionRecord.guild_id == msg.guild_id,
                    DetectionRecord.user_id == msg.author_id,
                )
                .order_by(DetectionRecord.timestamp.desc())
                .limit(1)
            )

        user_feat = await session.scalar(
            select(UserFeatureRecord).where(
                UserFeatureRecord.guild_id == msg.guild_id,
                UserFeatureRecord.user_id == msg.author_id,
            )
        )

    sample = _build_sample_from_rows(msg, feat, det, user_feat)
    return await save_dataset_sample(sample)


async def backfill_dataset_samples(
    *,
    guild_id: str | None = None,
    user_id: str | None = None,
    limit: int | None = None,
) -> tuple[int, int]:
    """
    Crea dataset_samples para mensajes que aún no tienen fila.
    Devuelve (creadas, omitidas).
    """
    factory = get_session_factory()
    async with factory() as session:
        sample_ids = set(
            (
                await session.execute(select(DatasetSampleRecord.message_id))
            )
            .scalars()
            .all()
        )
        query = select(MessageRecord).order_by(MessageRecord.id.desc())
        if guild_id:
            query = query.where(MessageRecord.guild_id == guild_id)
        if user_id:
            query = query.where(MessageRecord.author_id == user_id)
        if limit:
            query = query.limit(limit)
        messages = (await session.execute(query)).scalars().all()

    created = 0
    skipped = 0
    for msg in messages:
        if msg.message_id in sample_ids:
            skipped += 1
            continue
        if await ensure_dataset_sample(msg.message_id):
            created += 1
        else:
            skipped += 1
    return created, skipped


def _build_sample_from_rows(msg, feat, det, user_feat) -> DatasetSample:
    signals: dict[str, list] = {"spam": [], "automation": []}
    spam_score = 0
    automation_score = 0
    spam_class = "normal"
    auto_class = "normal"
    if det is not None:
        spam_score = int(det.spam_score or 0)
        automation_score = int(det.automation_score or 0)
        spam_class = det.spam_classification or "normal"
        auto_class = det.automation_classification or "normal"
        raw = det.signals
        if isinstance(raw, dict):
            signals["spam"] = list(raw.get("spam") or [])
            signals["automation"] = list(raw.get("automation") or [])

    return DatasetSample(
        message_id=msg.message_id,
        guild_id=msg.guild_id,
        channel_id=msg.channel_id,
        user_id=msg.author_id,
        timestamp=msg.timestamp,
        message_features=dict(feat.features) if feat else {},
        user_features=dict(user_feat.profile) if user_feat else {},
        spam_score=spam_score,
        automation_score=automation_score,
        spam_classification=spam_class,
        automation_classification=auto_class,
        detection_signals=signals,
        label=DATASET_LABEL_UNKNOWN,
    )


async def export_dataset_jsonl(path: Path, *, guild_id: str | None = None) -> int:
    factory = get_session_factory()
    async with factory() as session:
        query = select(DatasetSampleRecord).order_by(DatasetSampleRecord.id)
        if guild_id:
            query = query.where(DatasetSampleRecord.guild_id == guild_id)
        rows = (await session.execute(query)).scalars().all()

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            payload = _row_to_export(row)
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return len(rows)


def _row_to_export(row: DatasetSampleRecord) -> dict:
    return {
        "message_id": row.message_id,
        "guild_id": row.guild_id,
        "channel_id": row.channel_id,
        "user_id": row.user_id,
        "timestamp": row.timestamp.isoformat(),
        "message_features": row.message_features,
        "user_features": row.user_features,
        "spam_score": row.spam_score,
        "automation_score": row.automation_score,
        "spam_classification": row.spam_classification,
        "automation_classification": row.automation_classification,
        "detection_signals": row.detection_signals,
        "label": row.label or DATASET_LABEL_UNKNOWN,
    }
