from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.config import get_settings
from app.storage.database import get_session_factory
from app.storage.models import (
    AlertRecord,
    DatasetSampleRecord,
    DetectionRecord,
    MessageFeatureRecord,
    MessageRecord,
    UserFeatureRecord,
    UserRecord,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetentionStats:
    messages: int = 0
    message_features: int = 0
    detections: int = 0
    alerts: int = 0
    dataset_unknown: int = 0
    users: int = 0
    user_features: int = 0

    @property
    def total(self) -> int:
        return (
            self.messages
            + self.message_features
            + self.detections
            + self.alerts
            + self.dataset_unknown
            + self.users
            + self.user_features
        )


async def run_data_retention() -> RetentionStats:
    """
    Elimina datos más antiguos que DATA_RETENTION_DAYS (0 = desactivado).
    Las muestras del dataset con etiqueta distinta de ``unknown`` no se borran.
    """
    days = get_settings().data_retention_days
    if days <= 0:
        return RetentionStats()

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    factory = get_session_factory()
    stats = RetentionStats()

    async with factory() as session:
        stats = RetentionStats(
            message_features=_rows_deleted(
                await session.execute(
                    delete(MessageFeatureRecord).where(
                        MessageFeatureRecord.created_at < cutoff
                    )
                )
            ),
            messages=_rows_deleted(
                await session.execute(
                    delete(MessageRecord).where(MessageRecord.created_at < cutoff)
                )
            ),
            detections=_rows_deleted(
                await session.execute(
                    delete(DetectionRecord).where(DetectionRecord.timestamp < cutoff)
                )
            ),
            alerts=_rows_deleted(
                await session.execute(
                    delete(AlertRecord).where(AlertRecord.timestamp < cutoff)
                )
            ),
            dataset_unknown=_rows_deleted(
                await session.execute(
                    delete(DatasetSampleRecord).where(
                        DatasetSampleRecord.label == "unknown",
                        DatasetSampleRecord.created_at < cutoff,
                    )
                )
            ),
            user_features=_rows_deleted(
                await session.execute(
                    delete(UserFeatureRecord).where(
                        UserFeatureRecord.updated_at < cutoff
                    )
                )
            ),
            users=_rows_deleted(
                await session.execute(
                    delete(UserRecord).where(
                        UserRecord.last_seen.is_not(None),
                        UserRecord.last_seen < cutoff,
                    )
                )
            ),
        )
        await session.commit()

    if stats.total:
        logger.info(
            "Retención (%sd): eliminados messages=%s message_features=%s "
            "detections=%s alerts=%s dataset_unknown=%s users=%s user_features=%s",
            days,
            stats.messages,
            stats.message_features,
            stats.detections,
            stats.alerts,
            stats.dataset_unknown,
            stats.users,
            stats.user_features,
        )
    return stats


def _rows_deleted(result) -> int:
    return int(result.rowcount or 0)
