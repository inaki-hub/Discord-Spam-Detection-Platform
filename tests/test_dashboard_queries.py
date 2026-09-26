from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.dashboard.queries import (
    list_suspicious_users,
    overview_stats,
    user_message_timeline,
    user_timeline,
)
from app.storage.models import (
    AlertRecord,
    Base,
    DetectionRecord,
    MessageRecord,
)


@pytest.fixture
def sync_engine(tmp_path, monkeypatch):
    db_file = tmp_path / "dash.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file.as_posix()}")
    from sqlalchemy import create_engine

    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add(
            MessageRecord(
                message_id="m1",
                guild_id="g1",
                channel_id="c1",
                author_id="u1",
                timestamp=now,
                content="hello spam link",
                created_at=now,
            )
        )
        session.add(
            DetectionRecord(
                user_id="u1",
                guild_id="g1",
                timestamp=now,
                spam_score=70,
                automation_score=10,
                spam_classification="suspicious",
                automation_classification="normal",
                signals={"spam": ["repeated_domain"], "automation": []},
            )
        )
        session.add(
            DetectionRecord(
                user_id="u2",
                guild_id="g1",
                timestamp=now,
                spam_score=0,
                automation_score=0,
                spam_classification="normal",
                automation_classification="normal",
                signals={"spam": [], "automation": []},
            )
        )
        session.add(
            AlertRecord(
                user_id="u1",
                guild_id="g1",
                channel_id="c1",
                timestamp=now,
                spam_score=70,
                automation_score=10,
                signals=["repeated_domain"],
                payload={"spam_classification": "suspicious"},
            )
        )
        session.commit()
    yield engine
    engine.dispose()


def test_overview_stats(sync_engine):
    stats = overview_stats(engine=sync_engine)
    assert stats.messages == 1
    assert stats.detections == 2
    assert stats.alerts == 1


def test_list_suspicious_users_excludes_normal_only(sync_engine):
    rows = list_suspicious_users(engine=sync_engine, min_score=1)
    assert len(rows) == 1
    assert rows[0].user_id == "u1"
    assert rows[0].max_spam_score == 70


def test_user_timeline_merges_events(sync_engine):
    items = user_timeline("g1", "u1", engine=sync_engine)
    kinds = {item.kind for item in items}
    assert "message" in kinds
    assert "detection" in kinds
    assert "alert" in kinds


def test_user_message_timeline_unifies_per_message(sync_engine):
    rows = user_message_timeline("g1", "u1", engine=sync_engine)
    assert len(rows) == 1
    row = rows[0]
    assert row.message_id == "m1"
    assert row.spam_score == 70
    assert row.triggered_alert is True
    assert row.signals == {"spam": ["repeated_domain"], "automation": []}
