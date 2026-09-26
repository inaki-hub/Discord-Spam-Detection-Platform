from __future__ import annotations

from sqlalchemy import select

from app.dataset.records import DatasetSample
from app.storage.database import get_session_factory
from app.storage.models import DatasetSampleRecord


async def load_labeled_samples(*, guild_id: str | None = None) -> list[DatasetSample]:
    factory = get_session_factory()
    async with factory() as session:
        query = (
            select(DatasetSampleRecord)
            .where(DatasetSampleRecord.label != "unknown")
            .order_by(DatasetSampleRecord.id)
        )
        if guild_id:
            query = query.where(DatasetSampleRecord.guild_id == guild_id)
        rows = (await session.execute(query)).scalars().all()

    return [_record_to_sample(row) for row in rows]


def _record_to_sample(row: DatasetSampleRecord) -> DatasetSample:
    return DatasetSample(
        message_id=row.message_id,
        guild_id=row.guild_id,
        channel_id=row.channel_id,
        user_id=row.user_id,
        timestamp=row.timestamp,
        message_features=dict(row.message_features or {}),
        user_features=dict(row.user_features or {}),
        spam_score=int(row.spam_score),
        automation_score=int(row.automation_score),
        spam_classification=row.spam_classification,
        automation_classification=row.automation_classification,
        detection_signals=dict(row.detection_signals or {}),
        label=row.label,
    )
