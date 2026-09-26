from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import inspect

from app.storage.database import close_db, get_session_factory, init_db
from app.storage.migrations import CURRENT_SCHEMA_VERSION
from app.storage.models import SchemaMigrationRecord


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_file = tmp_path / "legacy.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    yield db_file
    await close_db()


@pytest.mark.asyncio
async def test_migrate_users_table_adds_guild_id(db):
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(32) NOT NULL UNIQUE,
            first_seen DATETIME,
            last_seen DATETIME
        )
        """
    )
    conn.commit()
    conn.close()

    await init_db()

    factory = get_session_factory()
    async with factory() as session:
        sync_conn = await session.connection()

        def _check(connection):
            cols = {c["name"] for c in inspect(connection).get_columns("users")}
            assert "guild_id" in cols

        await sync_conn.run_sync(_check)


@pytest.mark.asyncio
async def test_init_db_records_schema_migration(db):
    await init_db()

    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select

        row = await session.scalar(
            select(SchemaMigrationRecord.id).where(
                SchemaMigrationRecord.id == CURRENT_SCHEMA_VERSION
            )
        )
    assert row == CURRENT_SCHEMA_VERSION
