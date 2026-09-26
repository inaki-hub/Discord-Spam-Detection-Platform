from __future__ import annotations

import asyncio

import discord

from app.alerts.alert_manager import Alert

AlertMessageKey = tuple[str, str, str]

_update_locks: dict[AlertMessageKey, asyncio.Lock] = {}


def alert_message_key(alert: Alert, mod_channel_id: str) -> AlertMessageKey:
    return (alert.guild_id, alert.user_id, mod_channel_id)


def alert_to_embed(alert: Alert) -> discord.Embed:
    spam_signals = ", ".join(alert.signals.get("spam", [])) or "—"
    auto_signals = ", ".join(alert.signals.get("automation", [])) or "—"
    evidence = ", ".join(alert.evidence) or "—"

    embed = discord.Embed(
        title="Alerta de detección (revisión humana)",
        description=(
            "Señales comportamentales; no implica ban automático. "
            "Comprueba contexto antes de moderar."
        ),
        color=discord.Color.orange(),
        timestamp=alert.timestamp,
    )
    embed.add_field(name="Usuario", value=f"`{alert.user_id}`", inline=True)
    embed.add_field(name="Canal origen", value=f"`{alert.channel_id}`", inline=True)
    embed.add_field(name="Servidor", value=f"`{alert.guild_id}`", inline=True)
    score_note = str(alert.spam_score)
    auto_note = str(alert.automation_score)
    if alert.spam_score_rules is not None and alert.spam_score_rules != alert.spam_score:
        score_note = f"{alert.spam_score} (reglas: {alert.spam_score_rules})"
    if (
        alert.automation_score_rules is not None
        and alert.automation_score_rules != alert.automation_score
    ):
        auto_note = f"{alert.automation_score} (reglas: {alert.automation_score_rules})"
    embed.add_field(name="Spam score", value=score_note, inline=True)
    embed.add_field(name="Automation score", value=auto_note, inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="Spam", value=alert.spam_classification, inline=True)
    embed.add_field(name="Automation", value=alert.automation_classification, inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="Señales spam", value=spam_signals, inline=False)
    embed.add_field(name="Señales automation", value=auto_signals, inline=False)
    embed.add_field(name="Evidencias", value=evidence, inline=False)
    if alert.ml_spam_probability is not None:
        embed.add_field(
            name="ML (probabilidad)",
            value=(
                f"spam **{alert.ml_spam_probability:.2f}** · "
                f"automation **{(alert.ml_automation_probability or 0):.2f}**"
            ),
            inline=False,
        )
    embed.set_footer(text="Se actualiza mientras el usuario siga activo")
    return embed


async def _resolve_messageable_channel(
    bot: discord.Client,
    channel_id: int,
    alert: Alert,
) -> discord.abc.Messageable | None:
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.HTTPException:
            return None

    if not isinstance(channel, discord.abc.Messageable):
        return None

    if hasattr(channel, "guild") and channel.guild is not None:
        if str(channel.guild.id) != alert.guild_id:
            return None

    return channel


async def send_or_update_alert_to_channel(
    bot: discord.Client,
    alert: Alert,
    channel_id: int,
    message_cache: dict[AlertMessageKey, int],
) -> bool:
    """
    Publica una alerta en el canal de moderación.
    Si ya hay un mensaje reciente del mismo usuario en ese canal, lo edita.
    """
    channel = await _resolve_messageable_channel(bot, channel_id, alert)
    if channel is None:
        return False

    key = alert_message_key(alert, str(channel_id))
    lock = _update_locks.setdefault(key, asyncio.Lock())

    async with lock:
        embed = alert_to_embed(alert)
        existing_id = message_cache.get(key)

        if existing_id is not None:
            try:
                message = await channel.fetch_message(existing_id)
                if message.author.id != bot.user.id:
                    message_cache.pop(key, None)
                else:
                    await message.edit(embed=embed)
                    return True
            except discord.NotFound:
                message_cache.pop(key, None)
            except discord.HTTPException:
                message_cache.pop(key, None)

        message = await channel.send(embed=embed)
        message_cache[key] = message.id
        return True


async def send_alert_to_channel(
    bot: discord.Client,
    alert: Alert,
    channel_id: int,
) -> bool:
    """Compatibilidad: siempre envía un mensaje nuevo."""
    return await send_or_update_alert_to_channel(bot, alert, channel_id, {})
