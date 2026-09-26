from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection

from app.storage.models import SchemaMigrationRecord

MigrationFn = Callable[[Connection], None]

# Identificador de la última migración registrada (documentación / logs).
CURRENT_SCHEMA_VERSION = "001_users_guild_id"


def apply_sqlite_migrations(connection: Connection) -> None:
    """Aplica migraciones pendientes de forma idempotente (SQLite)."""
    for migration_id, fn in _registered_migrations():
        if _is_migration_applied(connection, migration_id):
            continue
        fn(connection)
        _record_migration(connection, migration_id)


def _is_migration_applied(connection: Connection, migration_id: str) -> bool:
    inspector = inspect(connection)
    if not inspector.has_table("schema_migrations"):
        return False
    row = connection.execute(
        select(SchemaMigrationRecord.id).where(SchemaMigrationRecord.id == migration_id)
    ).first()
    return row is not None


def _record_migration(connection: Connection, migration_id: str) -> None:
    connection.execute(
        text(
            "INSERT INTO schema_migrations (id, applied_at) VALUES (:id, :applied_at)"
        ),
        {"id": migration_id, "applied_at": datetime.now(timezone.utc)},
    )


def _migrate_users_add_guild_id(connection: Connection) -> None:
    inspector = inspect(connection)
    if not inspector.has_table("users"):
        return

    column_names = {col["name"] for col in inspector.get_columns("users")}
    if "guild_id" in column_names:
        return

    # Esquema antiguo: user_id único global, sin guild_id. Recrear tabla.
    connection.execute(
        text(
            """
            CREATE TABLE users_new (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                guild_id VARCHAR(32) NOT NULL,
                user_id VARCHAR(32) NOT NULL,
                first_seen DATETIME,
                last_seen DATETIME,
                CONSTRAINT uq_users_guild_user UNIQUE (guild_id, user_id)
            )
            """
        )
    )
    connection.execute(text("DROP TABLE users"))
    connection.execute(text("ALTER TABLE users_new RENAME TO users"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_users_guild_id ON users (guild_id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_users_user_id ON users (user_id)"))


def _registered_migrations() -> list[tuple[str, MigrationFn]]:
    return [
        ("001_users_guild_id", _migrate_users_add_guild_id),
    ]
