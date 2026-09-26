from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.config import get_settings
from app.moderation.settings import (
    ModerationSettings,
    moderation_from_dict,
    moderation_to_dict,
)
from app.storage.database import get_session_factory
from app.storage.models import GuildModerationRecord


async def get_guild_moderation(guild_id: str) -> ModerationSettings | None:
    factory = get_session_factory()
    async with factory() as session:
        row = await session.scalar(
            select(GuildModerationRecord).where(GuildModerationRecord.guild_id == guild_id)
        )
    if row is None:
        return None
    return moderation_from_dict(dict(row.config or {}))


async def save_guild_moderation(guild_id: str, settings: ModerationSettings) -> None:
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    async with factory() as session:
        row = await session.scalar(
            select(GuildModerationRecord).where(GuildModerationRecord.guild_id == guild_id)
        )
        payload = moderation_to_dict(settings)
        if row is None:
            session.add(
                GuildModerationRecord(
                    guild_id=guild_id,
                    config=payload,
                    updated_at=now,
                )
            )
        else:
            row.config = payload
            row.updated_at = now
        await session.commit()


async def get_effective_moderation(guild_id: str) -> ModerationSettings:
    stored = await get_guild_moderation(guild_id)
    if stored is not None:
        return stored
    return get_settings().moderation


async def reset_guild_moderation(guild_id: str) -> None:
    """Vuelve a usar defaults de .env (elimina fila del servidor)."""
    factory = get_session_factory()
    async with factory() as session:
        row = await session.scalar(
            select(GuildModerationRecord).where(GuildModerationRecord.guild_id == guild_id)
        )
        if row is not None:
            await session.delete(row)
            await session.commit()
