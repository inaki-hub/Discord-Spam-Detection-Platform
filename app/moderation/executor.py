from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import discord

from app.detection.hybrid import HybridEvaluation
from app.moderation.policy import ModerationDecision, decide_moderation
from app.moderation.settings import ModerationSettings

logger = logging.getLogger(__name__)

CooldownKey = tuple[str, str]


async def apply_moderation_if_needed(
    message: discord.Message,
    hybrid: HybridEvaluation,
    settings: ModerationSettings,
    cooldowns: dict[CooldownKey, float],
) -> ModerationDecision | None:
    decision = decide_moderation(hybrid, settings)
    if decision is None:
        return None

    if message.guild is None:
        return None

    member = message.author
    if not isinstance(member, discord.Member):
        return None
    if member.bot:
        return None
    if member.guild_permissions.administrator:
        logger.info(
            "[MODERATION] omitido (administrador) user=%s guild=%s",
            member.id,
            message.guild.id,
        )
        return None

    key: CooldownKey = (str(message.guild.id), str(member.id))
    now = time.monotonic()
    last = cooldowns.get(key)
    if last is not None and (now - last) < settings.cooldown_seconds:
        logger.debug(
            "[MODERATION] cooldown activo user=%s guild=%s",
            member.id,
            message.guild.id,
        )
        return None

    me = message.guild.me
    if me is None or not me.guild_permissions.moderate_members:
        logger.warning(
            "[MODERATION] sin permiso moderate_members en guild=%s",
            message.guild.id,
        )
        return None
    if member.top_role >= me.top_role:
        logger.warning(
            "[MODERATION] rol del usuario >= rol del bot user=%s guild=%s",
            member.id,
            message.guild.id,
        )
        return None

    if settings.dry_run:
        logger.warning(
            "[MODERATION] dry-run timeout=%ss user=%s guild=%s trigger=%s",
            decision.duration_seconds,
            member.id,
            message.guild.id,
            decision.trigger,
        )
        cooldowns[key] = now
        return decision

    until = datetime.now(timezone.utc) + timedelta(seconds=decision.duration_seconds)
    try:
        await member.timeout(until, reason=decision.reason)
    except discord.Forbidden:
        logger.warning(
            "[MODERATION] Forbidden al aplicar timeout user=%s guild=%s",
            member.id,
            message.guild.id,
        )
        return None
    except discord.HTTPException as exc:
        logger.warning(
            "[MODERATION] HTTP error user=%s guild=%s: %s",
            member.id,
            message.guild.id,
            exc,
        )
        return None

    cooldowns[key] = now
    logger.warning(
        "[MODERATION] timeout=%ss user=%s guild=%s trigger=%s",
        decision.duration_seconds,
        member.id,
        message.guild.id,
        decision.trigger,
    )
    return decision
