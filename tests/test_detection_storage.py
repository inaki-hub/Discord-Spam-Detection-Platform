from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.collector.events import MessageEvent
from app.detection.automation_detector import AutomationDetector
from app.detection.spam_detector import SpamDetector
from app.features.message_features import extract_message_features
from app.features.user_features import UserProfileStore
from app.storage.database import close_db, get_session_factory, init_db, save_detection
from app.storage.models import DetectionRecord


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
async def test_save_detection(db):
    event = MessageEvent(
        message_id="1",
        guild_id="10",
        channel_id="20",
        author_id="30",
        timestamp=datetime.now(timezone.utc),
        content="spam links https://a.com https://a.com/b",
        urls=("https://a.com", "https://a.com/b"),
        attachments=(),
        mentions=(),
    )
    store = UserProfileStore()
    profile = store.update(event, extract_message_features(event))
    features = extract_message_features(event)
    spam = SpamDetector().evaluate(profile, features)
    automation = AutomationDetector().evaluate(profile)
    await save_detection(event, spam, automation)

    factory = get_session_factory()
    async with factory() as session:
        row = (await session.execute(select(DetectionRecord))).scalar_one()
        assert row.spam_score == spam.score
        assert row.automation_score == automation.score
        assert row.signals["spam"] == list(spam.signals)
        assert row.signals["automation"] == list(automation.signals)

    await save_detection(
        event,
        spam,
        automation,
        ml={"spam_probability": 0.91, "automation_probability": 0.12},
    )
    async with factory() as session:
        rows = (await session.execute(select(DetectionRecord))).scalars().all()
    assert rows[-1].signals["ml"]["spam_probability"] == 0.91
