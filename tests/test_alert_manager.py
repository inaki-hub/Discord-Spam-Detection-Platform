from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.alerts.alert_manager import AlertManager
from app.collector.events import MessageEvent
from app.detection.automation_detector import AutomationDetectionResult
from app.detection.spam_detector import SpamDetectionResult
from app.storage.database import close_db, get_session_factory, init_db, save_alert
from app.storage.models import AlertRecord


def test_should_alert_only_when_classification_elevated():
    manager = AlertManager()
    normal_spam = SpamDetectionResult(0, "normal", ())
    normal_auto = AutomationDetectionResult(0, "normal", ())
    hot_spam = SpamDetectionResult(80, "spam_likely", ("duplicate_content",))

    assert manager.should_alert(normal_spam, normal_auto) is False
    assert manager.should_alert(hot_spam, normal_auto) is True


def test_alert_log_block_contains_scores():
    manager = AlertManager()
    event = MessageEvent(
        message_id="1",
        guild_id="g",
        channel_id="c",
        author_id="u",
        timestamp=datetime.now(timezone.utc),
        content="test",
        urls=(),
        attachments=(),
        mentions=(),
    )
    spam = SpamDetectionResult(87, "spam_likely", ("duplicate_content",))
    automation = AutomationDetectionResult(92, "automation_likely", ("burst_activity",))
    alert = manager.build(event, spam, automation)
    block = alert.to_log_block()
    assert "Spam score: 87" in block
    assert "Automation score: 92" in block
    assert "duplicate_content" in block


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
async def test_save_alert(db):
    manager = AlertManager()
    event = MessageEvent(
        message_id="1",
        guild_id="10",
        channel_id="20",
        author_id="30",
        timestamp=datetime.now(timezone.utc),
        content="x",
        urls=(),
        attachments=(),
        mentions=(),
    )
    spam = SpamDetectionResult(50, "suspicious", ("repeated_domain",))
    automation = AutomationDetectionResult(0, "normal", ())
    alert = manager.build(event, spam, automation)
    await save_alert(alert)

    factory = get_session_factory()
    async with factory() as session:
        row = (await session.execute(select(AlertRecord))).scalar_one()
        assert row.user_id == "30"
        assert row.spam_score == 50
        assert row.payload["evidence"] == ["spam:repeated_domain"]
