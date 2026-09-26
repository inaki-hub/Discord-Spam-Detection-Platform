from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.collector.events import MessageEvent
from app.features.message_features import extract_message_features
from app.storage.database import close_db, get_session_factory, init_db, save_message_event
from app.storage.models import MessageFeatureRecord, MessageRecord


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    await init_db()
    yield
    await close_db()


@pytest.mark.asyncio
async def test_save_message_event(db):
    event = MessageEvent(
        message_id="42",
        guild_id="10",
        channel_id="20",
        author_id="30",
        timestamp=datetime.now(timezone.utc),
        content="hello",
        urls=("https://a.com",),
        attachments=(),
        mentions=("40",),
    )
    features = extract_message_features(event)
    assert await save_message_event(event, features) is True
    assert await save_message_event(event, features) is False

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(MessageRecord).where(MessageRecord.message_id == "42")
        )
        row = result.scalar_one()
        assert row.guild_id == "10"
        assert row.urls == ["https://a.com"]
        assert row.mentions == ["40"]

        count = await session.execute(select(MessageRecord))
        assert len(count.scalars().all()) == 1

        feat = await session.execute(
            select(MessageFeatureRecord).where(MessageFeatureRecord.message_id == "42")
        )
        feat_row = feat.scalar_one()
        assert feat_row.content_hash == features.content_hash
        assert feat_row.features["word_count"] == features.word_count
