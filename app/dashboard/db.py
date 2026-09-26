from __future__ import annotations

from functools import lru_cache

from sqlalchemy.engine import Engine, create_engine

from app.config import DATA_DIR, ensure_data_dir, get_settings


def sync_database_url() -> str:
    url = get_settings().database_url.strip()
    if url.startswith("sqlite+aiosqlite:///./"):
        ensure_data_dir()
        db_path = (DATA_DIR / "spam_detector.db").resolve()
        return f"sqlite:///{db_path.as_posix()}"
    if url.startswith("sqlite+aiosqlite:///"):
        path = url.removeprefix("sqlite+aiosqlite:///")
        return f"sqlite:///{path}"
    return url.replace("sqlite+aiosqlite", "sqlite")


@lru_cache
def get_sync_engine() -> Engine:
    return create_engine(
        sync_database_url(),
        connect_args={"check_same_thread": False},
    )
