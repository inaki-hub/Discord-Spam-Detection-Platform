from __future__ import annotations

import discord
from discord.ext import commands

from app.config import get_settings
from app.moderation.settings import ModerationSettings, format_moderation_summary
from app.moderation.store import get_effective_moderation, reset_guild_moderation, save_guild_moderation


def _can_configure(ctx: commands.Context) -> bool:
    if ctx.guild is None:
        return False
    channel_id = get_settings().mod_config_channel_id
    if channel_id and str(ctx.channel.id) != channel_id:
        return False
    perms = ctx.author.guild_permissions if isinstance(ctx.author, discord.Member) else None
    return bool(perms and perms.manage_guild)


class ModerationConfigCog(commands.Cog):
    """Comandos !mod para configurar sanciones sin tocar código."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if not _can_configure(ctx):
            channel_id = get_settings().mod_config_channel_id
            if channel_id:
                raise commands.CheckFailure(
                    f"Usa el canal <#{channel_id}> y permiso Gestionar servidor."
                )
            raise commands.CheckFailure("Necesitas permiso Gestionar servidor.")
        return True

    @commands.group(name="mod", invoke_without_command=True)
    async def mod_group(self, ctx: commands.Context) -> None:
        await ctx.send(
            "Comandos: `!mod status`, `!mod enable on|off`, `!mod dryrun on|off`, "
            "`!mod timeout suspicious 600`, `!mod penalize spam on`, `!mod cooldown 300`, "
            "`!mod reset` (volver a .env). Escribe `!mod help`."
        )

    @mod_group.command(name="help")
    async def mod_help(self, ctx: commands.Context) -> None:
        embed = discord.Embed(
            title="Configuración de moderación",
            description=(
                "Los timeouts son en **segundos** (0 = desactivado para ese nivel).\n"
                "Prueba primero `!mod dryrun on`."
            ),
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Estado",
            value="`!mod status` · `!mod enable on|off` · `!mod dryrun on|off` · `!mod reset`",
            inline=False,
        )
        embed.add_field(
            name="Timeouts",
            value=(
                "`!mod timeout suspicious 600`\n"
                "`!mod timeout spam_likely 3600`\n"
                "`!mod timeout automation_suspicious 300`\n"
                "`!mod timeout automation_likely 600`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Otros",
            value=(
                "`!mod penalize spam on|off`\n"
                "`!mod penalize automation on|off`\n"
                "`!mod minscore spam 40`\n"
                "`!mod minscore automation 40`\n"
                "`!mod cooldown 300`"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @mod_group.command(name="status")
    async def mod_status(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        settings = await get_effective_moderation(str(ctx.guild.id))
        embed = discord.Embed(
            title=f"Moderación — guild {ctx.guild.id}",
            description=format_moderation_summary(settings),
            color=discord.Color.green() if settings.enabled else discord.Color.light_grey(),
        )
        await ctx.send(embed=embed)

    @mod_group.command(name="reset")
    async def mod_reset(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        await reset_guild_moderation(str(ctx.guild.id))
        await ctx.send("Configuración del servidor eliminada; se usan valores de `.env`.")

    @mod_group.command(name="enable")
    async def mod_enable(self, ctx: commands.Context, state: str) -> None:
        await self._patch(ctx, enabled=_on_off(state))

    @mod_group.command(name="dryrun")
    async def mod_dryrun(self, ctx: commands.Context, state: str) -> None:
        await self._patch(ctx, dry_run=_on_off(state))

    @mod_group.command(name="cooldown")
    async def mod_cooldown(self, ctx: commands.Context, seconds: int) -> None:
        await self._patch(ctx, cooldown_seconds=max(0, seconds))

    @mod_group.group(name="penalize", invoke_without_command=True)
    async def mod_penalize(self, ctx: commands.Context) -> None:
        await ctx.send("Uso: `!mod penalize spam on|off` o `automation on|off`")

    @mod_penalize.command(name="spam")
    async def mod_penalize_spam(self, ctx: commands.Context, state: str) -> None:
        await self._patch(ctx, penalize_spam=_on_off(state))

    @mod_penalize.command(name="automation")
    async def mod_penalize_automation(self, ctx: commands.Context, state: str) -> None:
        await self._patch(ctx, penalize_automation=_on_off(state))

    @mod_group.group(name="minscore", invoke_without_command=True)
    async def mod_minscore(self, ctx: commands.Context) -> None:
        await ctx.send("Uso: `!mod minscore spam 40` o `!mod minscore automation 40`")

    @mod_minscore.command(name="spam")
    async def mod_minscore_spam(self, ctx: commands.Context, value: int) -> None:
        await self._patch(ctx, min_effective_spam_score=max(0, min(100, value)))

    @mod_minscore.command(name="automation")
    async def mod_minscore_automation(self, ctx: commands.Context, value: int) -> None:
        await self._patch(ctx, min_effective_automation_score=max(0, min(100, value)))

    @mod_group.group(name="timeout", invoke_without_command=True)
    async def mod_timeout(self, ctx: commands.Context) -> None:
        await ctx.send(
            "Niveles: `suspicious`, `spam_likely`, `automation_suspicious`, `automation_likely`"
        )

    @mod_timeout.command(name="suspicious")
    async def mod_timeout_suspicious(self, ctx: commands.Context, seconds: int) -> None:
        await self._patch(ctx, timeout_suspicious_seconds=max(0, seconds))

    @mod_timeout.command(name="spam_likely")
    async def mod_timeout_spam_likely(self, ctx: commands.Context, seconds: int) -> None:
        await self._patch(ctx, timeout_spam_likely_seconds=max(0, seconds))

    @mod_timeout.command(name="automation_suspicious")
    async def mod_timeout_auto_suspicious(self, ctx: commands.Context, seconds: int) -> None:
        await self._patch(ctx, timeout_automation_suspicious_seconds=max(0, seconds))

    @mod_timeout.command(name="automation_likely")
    async def mod_timeout_auto_likely(self, ctx: commands.Context, seconds: int) -> None:
        await self._patch(ctx, timeout_automation_likely_seconds=max(0, seconds))

    async def _patch(self, ctx: commands.Context, **changes) -> None:
        assert ctx.guild is not None
        current = await get_effective_moderation(str(ctx.guild.id))
        updated = _replace_settings(current, **changes)
        await save_guild_moderation(str(ctx.guild.id), updated)
        await ctx.send(format_moderation_summary(updated))


def _on_off(raw: str) -> bool:
    text = raw.strip().lower()
    if text in {"on", "true", "1", "si", "sí", "yes"}:
        return True
    if text in {"off", "false", "0", "no"}:
        return False
    raise commands.BadArgument("Usa on u off.")


def _replace_settings(current: ModerationSettings, **changes) -> ModerationSettings:
    data = {
        "enabled": current.enabled,
        "dry_run": current.dry_run,
        "cooldown_seconds": current.cooldown_seconds,
        "penalize_spam": current.penalize_spam,
        "penalize_automation": current.penalize_automation,
        "min_effective_spam_score": current.min_effective_spam_score,
        "min_effective_automation_score": current.min_effective_automation_score,
        "timeout_spam_likely_seconds": current.timeout_spam_likely_seconds,
        "timeout_suspicious_seconds": current.timeout_suspicious_seconds,
        "timeout_automation_likely_seconds": current.timeout_automation_likely_seconds,
        "timeout_automation_suspicious_seconds": current.timeout_automation_suspicious_seconds,
    }
    data.update(changes)
    return ModerationSettings(**data)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationConfigCog(bot))
