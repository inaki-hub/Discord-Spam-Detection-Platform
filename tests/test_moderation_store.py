from __future__ import annotations

import pytest

from app.config import get_settings
from app.moderation.settings import ModerationSettings, moderation_from_dict, moderation_to_dict
from app.moderation.store import get_effective_moderation, reset_guild_moderation, save_guild_moderation
from app.storage.database import close_db, init_db


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_file = tmp_path / "mod.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    await init_db()
    yield
    await close_db()


@pytest.mark.asyncio
async def test_save_and_load_guild_moderation(db):
    custom = ModerationSettings(
        enabled=True,
        dry_run=False,
        cooldown_seconds=120,
        penalize_spam=True,
        penalize_automation=False,
        min_effective_spam_score=50,
        min_effective_automation_score=40,
        timeout_spam_likely_seconds=100,
        timeout_suspicious_seconds=200,
        timeout_automation_likely_seconds=0,
        timeout_automation_suspicious_seconds=0,
    )
    await save_guild_moderation("g1", custom)
    effective = await get_effective_moderation("g1")
    assert effective.timeout_suspicious_seconds == 200
    assert effective.dry_run is False


@pytest.mark.asyncio
async def test_reset_falls_back_to_env(db):
    await save_guild_moderation(
        "g2",
        ModerationSettings(
            enabled=True,
            dry_run=True,
            cooldown_seconds=1,
            penalize_spam=True,
            penalize_automation=False,
            min_effective_spam_score=40,
            min_effective_automation_score=40,
            timeout_spam_likely_seconds=0,
            timeout_suspicious_seconds=999,
            timeout_automation_likely_seconds=0,
            timeout_automation_suspicious_seconds=0,
        ),
    )
    await reset_guild_moderation("g2")
    effective = await get_effective_moderation("g2")
    assert effective.timeout_suspicious_seconds == get_settings().moderation.timeout_suspicious_seconds


def test_moderation_roundtrip_dict():
    s = moderation_from_dict(moderation_to_dict(get_settings().moderation))
    assert s.enabled == get_settings().moderation.enabled
