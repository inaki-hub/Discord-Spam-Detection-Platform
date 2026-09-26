from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.collector.events import MessageEvent
from app.features.message_features import extract_message_features
from app.features.user_features import UserProfileStore
from app.storage.database import close_db, get_session_factory, init_db, save_user_profile
from app.storage.models import UserFeatureRecord, UserRecord


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
async def test_save_user_profile_upsert(db):
    store = UserProfileStore()
    event = MessageEvent(
        message_id="1",
        guild_id="10",
        channel_id="20",
        author_id="30",
        timestamp=datetime.now(timezone.utc),
        content="hola mundo",
        urls=(),
        attachments=(),
        mentions=(),
    )
    profile = store.update(event, extract_message_features(event))
    await save_user_profile(profile)

    event2 = MessageEvent(
        message_id="2",
        guild_id="10",
        channel_id="21",
        author_id="30",
        timestamp=datetime.now(timezone.utc),
        content="otro",
        urls=(),
        attachments=(),
        mentions=(),
    )
    profile2 = store.update(event2, extract_message_features(event2))
    await save_user_profile(profile2)

    factory = get_session_factory()
    async with factory() as session:
        users = await session.execute(select(UserRecord))
        assert len(users.scalars().all()) == 1

        feats = await session.execute(
            select(UserFeatureRecord).where(UserFeatureRecord.user_id == "30")
        )
        row = feats.scalar_one()
        assert row.profile["total_messages"] == 2
        assert row.profile["unique_channels"] == 2
