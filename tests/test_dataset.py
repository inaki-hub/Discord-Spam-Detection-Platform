from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.collector.events import MessageEvent
from app.dataset.labels import normalize_label
from app.dataset.records import build_dataset_sample
from app.dataset.storage import (
    backfill_dataset_samples,
    export_dataset_jsonl,
    save_dataset_sample,
    set_dataset_label,
)
from app.storage.database import save_detection, save_message_event, save_message_features
from app.detection.automation_detector import AutomationDetectionResult
from app.detection.spam_detector import SpamDetectionResult
from app.features.message_features import extract_message_features
from app.features.user_features import UserProfileStore
from app.storage.database import close_db, get_session_factory, init_db
from app.storage.models import DatasetSampleRecord


def test_normalize_label_rejects_invalid():
    with pytest.raises(ValueError):
        normalize_label("ban_hammer")


def test_normalize_label_accepts_valid():
    assert normalize_label("SPAM") == "spam"


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    await init_db()
    yield tmp_path
    await close_db()


@pytest.mark.asyncio
async def test_dataset_save_export_and_label(db):
    event = MessageEvent(
        message_id="99",
        guild_id="g1",
        channel_id="c1",
        author_id="u1",
        timestamp=datetime.now(timezone.utc),
        content="hello dataset",
        urls=(),
        attachments=(),
        mentions=(),
    )
    features = extract_message_features(event)
    profile = UserProfileStore().update(event, features)
    spam = SpamDetectionResult(10, "normal", ())
    automation = AutomationDetectionResult(0, "normal", ())
    sample = build_dataset_sample(event, features, profile, spam, automation)

    assert await save_dataset_sample(sample) is True
    assert await save_dataset_sample(sample) is False

    assert await set_dataset_label("99", "spam") is True

    export_path = db / "out.jsonl"
    count = await export_dataset_jsonl(export_path)
    assert count == 1
    text = export_path.read_text(encoding="utf-8")
    assert '"label": "spam"' in text

    factory = get_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                select(DatasetSampleRecord).where(DatasetSampleRecord.message_id == "99")
            )
        ).scalar_one()
        assert row.label == "spam"
        assert row.spam_score == 10


@pytest.mark.asyncio
async def test_backfill_creates_samples_from_messages(db):
    event = MessageEvent(
        message_id="77",
        guild_id="g1",
        channel_id="c1",
        author_id="u1",
        timestamp=datetime.now(timezone.utc),
        content="backfill me",
        urls=(),
        attachments=(),
        mentions=(),
    )
    features = extract_message_features(event)
    profile = UserProfileStore().update(event, features)
    spam = SpamDetectionResult(40, "suspicious", ("duplicate_content",))
    automation = AutomationDetectionResult(10, "normal", ())

    await save_message_event(event, None)
    await save_message_features(event, features)
    await save_detection(event, spam, automation)

    created, skipped = await backfill_dataset_samples(guild_id="g1", user_id="u1")
    assert created == 1
    assert skipped == 0

    factory = get_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                select(DatasetSampleRecord).where(DatasetSampleRecord.message_id == "77")
            )
        ).scalar_one()
        assert row.label == "unknown"
        assert row.spam_score == 40
