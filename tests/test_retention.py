from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.dataset.records import DatasetSample
from app.dataset.storage import save_dataset_sample, set_dataset_label
from app.storage.database import close_db, get_session_factory, init_db
from app.storage.models import DatasetSampleRecord, MessageRecord
from app.storage.retention import run_data_retention


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_file = tmp_path / "retention.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("DATA_RETENTION_DAYS", "0")
    yield
    await close_db()


@pytest.mark.asyncio
async def test_retention_disabled_by_default(db, monkeypatch):
    monkeypatch.setenv("DATA_RETENTION_DAYS", "0")
    await init_db()

    factory = get_session_factory()
    async with factory() as session:
        session.add(
            MessageRecord(
                message_id="1",
                guild_id="g1",
                channel_id="c1",
                author_id="u1",
                timestamp=datetime.now(timezone.utc),
                content="x",
                created_at=datetime.now(timezone.utc) - timedelta(days=365),
            )
        )
        await session.commit()

    stats = await run_data_retention()
    assert stats.total == 0

    async with factory() as session:
        count = await session.scalar(select(func.count()).select_from(MessageRecord))
    assert count == 1


@pytest.mark.asyncio
async def test_retention_purges_old_rows_keeps_labeled_dataset(db, monkeypatch):
    monkeypatch.setenv("DATA_RETENTION_DAYS", "30")
    await init_db()

    old = datetime.now(timezone.utc) - timedelta(days=60)
    recent = datetime.now(timezone.utc) - timedelta(days=1)

    factory = get_session_factory()
    async with factory() as session:
        session.add(
            MessageRecord(
                message_id="old-msg",
                guild_id="g1",
                channel_id="c1",
                author_id="u1",
                timestamp=old,
                content="old",
                created_at=old,
            )
        )
        session.add(
            MessageRecord(
                message_id="new-msg",
                guild_id="g1",
                channel_id="c1",
                author_id="u1",
                timestamp=recent,
                content="new",
                created_at=recent,
            )
        )
        await session.commit()

    assert await save_dataset_sample(
        DatasetSample(
            message_id="old-labeled",
            guild_id="g1",
            channel_id="c1",
            user_id="u1",
            timestamp=old,
            message_features={},
            user_features={},
            spam_score=0,
            automation_score=0,
            spam_classification="normal",
            automation_classification="normal",
            detection_signals={},
            label="unknown",
        )
    )
    assert await save_dataset_sample(
        DatasetSample(
            message_id="old-spam",
            guild_id="g1",
            channel_id="c1",
            user_id="u1",
            timestamp=old,
            message_features={},
            user_features={},
            spam_score=80,
            automation_score=0,
            spam_classification="spam",
            automation_classification="normal",
            detection_signals={},
        )
    )
    await set_dataset_label("old-spam", "spam")

    async with factory() as session:
        rows = (
            await session.execute(select(DatasetSampleRecord))
        ).scalars().all()
        for row in rows:
            row.created_at = old
        await session.commit()

    stats = await run_data_retention()
    assert stats.messages == 1
    assert stats.dataset_unknown == 1

    async with factory() as session:
        remaining_msgs = (
            await session.execute(select(MessageRecord.message_id))
        ).scalars().all()
        remaining_samples = (
            await session.execute(select(DatasetSampleRecord.message_id))
        ).scalars().all()

    assert remaining_msgs == ["new-msg"]
    assert set(remaining_samples) == {"old-spam"}
