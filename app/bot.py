from __future__ import annotations

import asyncio
import logging
import sys

from dataclasses import replace

import discord
from discord.ext import commands
from app.alerts import AlertManager
from app.alerts.discord_notify import send_or_update_alert_to_channel
from app.collector import MessageCollector
from app.dataset import build_dataset_sample, save_dataset_sample
from app.detection import AutomationDetector, SpamDetector
from app.detection.hybrid import evaluate_hybrid
from app.config import get_settings
from app.ml.advisor import MlAdvisor
from app.ml.prediction import MlPrediction
from app.moderation.commands import ModerationConfigCog
from app.moderation.executor import apply_moderation_if_needed
from app.moderation.store import get_effective_moderation
from app.features import UserProfileStore, extract_message_features
from app.features.message_features import (
    with_cross_channel,
    with_domain_metrics,
    with_similarity,
)
from app.storage import (
    close_db,
    init_db,
    save_alert,
    save_message_event,
    save_detection,
    save_message_features,
    save_user_profile,
)

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(message)s",
    )


class SpamDetectionBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
        self.collector = MessageCollector()
        self.profile_store = UserProfileStore()
        self.spam_detector = SpamDetector()
        self.automation_detector = AutomationDetector()
        self.alert_manager = AlertManager(logger)
        self._alert_channels: dict[str, str] = {}
        self._default_alert_channel: str = ""
        self._alert_discord_messages: dict[tuple[str, str, str], int] = {}
        self._ml_enabled = False
        self.ml_advisor: MlAdvisor | None = None
        self._moderation_cooldowns: dict[tuple[str, str], float] = {}

    async def setup_hook(self) -> None:
        settings = get_settings()
        self._alert_channels = settings.alert_channels
        self._default_alert_channel = settings.default_alert_channel
        self._ml_enabled = settings.ml_enabled
        if settings.ml_enabled:
            advisor = MlAdvisor()
            self.ml_advisor = advisor if advisor.enabled else None
            if settings.ml_enabled and self.ml_advisor is None:
                logger.warning(
                    "ML_ENABLED=true pero no hay modelo válido en %s",
                    advisor.model_path,
                )
        await init_db()
        await self.add_cog(ModerationConfigCog(self))

    async def close(self) -> None:
        await close_db()
        await super().close()

    async def on_ready(self) -> None:
        logger.info("Discord bot started")
        if self._alert_channels or self._default_alert_channel:
            logger.info(
                "Alertas Discord: %s mapeo(s) guild:canal%s",
                len(self._alert_channels),
                f", canal por defecto {self._default_alert_channel}"
                if self._default_alert_channel
                else "",
            )
        settings = get_settings()
        if settings.mod_config_channel_id:
            logger.info(
                "Comandos !mod en canal %s (MOD_CONFIG_CHANNEL_ID)",
                settings.mod_config_channel_id,
            )
        if settings.raw_alert_channels and not (
            self._alert_channels or self._default_alert_channel
        ):
            logger.warning(
                "ALERT_CHANNELS no se pudo interpretar. Usa guild_id:channel_id "
                "o solo channel_id."
            )

    async def _publish_alert_to_mod_channel(self, alert) -> None:
        channel_id = self._alert_channels.get(alert.guild_id) or self._default_alert_channel
        if not channel_id:
            return
        try:
            sent = await send_or_update_alert_to_channel(
                self,
                alert,
                int(channel_id),
                self._alert_discord_messages,
            )
            if not sent:
                logger.warning(
                    "No se pudo enviar alerta al canal %s (guild %s)",
                    channel_id,
                    alert.guild_id,
                )
        except discord.HTTPException as exc:
            logger.warning("Error enviando alerta a Discord: %s", exc)

    def _ml_predict(
        self, features, profile, spam, automation
    ) -> tuple[dict | None, MlPrediction | None]:
        if not self._ml_enabled or self.ml_advisor is None:
            return None, None
        pred = self.ml_advisor.predict(
            message_features=features.to_dict(),
            user_features=profile.to_dict(),
            spam_score=spam.score,
            automation_score=automation.score,
            detection_signals={
                "spam": list(spam.signals),
                "automation": list(automation.signals),
            },
        )
        if pred is None:
            return None, None
        logger.info(
            "[ML] user=%s guild=%s spam_p=%.3f auto_p=%.3f",
            profile.user_id,
            profile.guild_id,
            pred.spam_probability,
            pred.automation_probability,
        )
        payload = {
            "spam_probability": round(pred.spam_probability, 4),
            "automation_probability": round(pred.automation_probability, 4),
        }
        return payload, pred

    async def on_message(self, message: discord.Message) -> None:
        if message.author.id == self.user.id:
            return

        if message.content.startswith(self.command_prefix):
            await self.process_commands(message)
            return

        event = self.collector.from_discord_message(message)
        if event is None:
            await self.process_commands(message)
            return

        features = extract_message_features(event)
        logger.info(self.collector.format_log_line(event))
        logger.debug(
            "[FEATURES] message=%s hash=%s words=%s urls=%s",
            event.message_id,
            features.content_hash[:12],
            features.word_count,
            features.url_count,
        )

        inserted = await save_message_event(event, None)
        if inserted:
            profile, similarity, cross, domain = self.profile_store.update_with_similarity(
                event, features
            )
            features = with_domain_metrics(
                with_cross_channel(with_similarity(features, similarity), cross),
                domain,
            )
            await save_message_features(event, features)
            spam = self.spam_detector.evaluate(profile, features)
            automation = self.automation_detector.evaluate(profile)
            profile = replace(
                profile,
                spam_score=spam.score,
                spam_classification=spam.classification,
                automation_score=automation.score,
                automation_classification=automation.classification,
            )
            await save_user_profile(profile)
            ml_payload, ml_pred = self._ml_predict(features, profile, spam, automation)
            settings = get_settings()
            hybrid = evaluate_hybrid(
                spam, automation, profile, ml_pred, settings.hybrid
            )
            hybrid_meta = (
                hybrid.hybrid_payload() if hybrid.ml_spam_probability is not None else None
            )
            await save_detection(
                event, spam, automation, ml=ml_payload, hybrid=hybrid_meta
            )
            sample = build_dataset_sample(event, features, profile, spam, automation)
            await save_dataset_sample(sample)
            if hybrid.should_alert():
                alert = self.alert_manager.build(
                    event, spam, automation, hybrid=hybrid
                )
                self.alert_manager.emit(alert)
                await save_alert(alert)
                await self._publish_alert_to_mod_channel(alert)
            mod_settings = await get_effective_moderation(event.guild_id)
            if mod_settings.enabled:
                await apply_moderation_if_needed(
                    message,
                    hybrid,
                    mod_settings,
                    self._moderation_cooldowns,
                )
            if profile.repeated_domain:
                logger.info(
                    "[SIGNAL] repeated_domain user=%s guild=%s ratio=%.2f domains_per_min=%.1f signals=%s",
                    profile.user_id,
                    profile.guild_id,
                    profile.repeated_domain_ratio,
                    profile.domains_per_minute,
                    ",".join(profile.domain_signals),
                )
            if profile.cross_channel_repetition:
                logger.info(
                    "[SIGNAL] cross_channel_repetition user=%s guild=%s interval_s=%s signals=%s",
                    profile.user_id,
                    profile.guild_id,
                    profile.cross_channel_interval,
                    ",".join(profile.cross_channel_signals),
                )
            if profile.high_similarity_content:
                logger.info(
                    "[SIGNAL] similar_content user=%s guild=%s similarity=%.2f",
                    profile.user_id,
                    profile.guild_id,
                    profile.max_similarity_to_recent,
                )
            if profile.repeated_content_interval is not None:
                logger.info(
                    "[SIGNAL] duplicate_content user=%s guild=%s repeats=%s interval_s=%.2f",
                    profile.user_id,
                    profile.guild_id,
                    profile.repeated_content_count,
                    profile.repeated_content_interval,
                )
            if profile.burst_activity:
                logger.info(
                    "[SIGNAL] burst_activity user=%s guild=%s msgs_10s=%s signals=%s",
                    profile.user_id,
                    profile.guild_id,
                    profile.messages_last_10s,
                    ",".join(profile.temporal_signals),
                )
            logger.debug(
                "[PROFILE] user=%s guild=%s total=%s dup_ratio=%.2f msgs_10s=%s burst=%s",
                profile.user_id,
                profile.guild_id,
                profile.total_messages,
                profile.duplicate_ratio,
                profile.messages_last_10s,
                profile.burst_activity,
            )

async def _run() -> None:
    settings = get_settings()
    if not settings.discord_token:
        print(
            "DISCORD_TOKEN no configurado. Copia .env.example a .env y añade tu token.",
            file=sys.stderr,
        )
        sys.exit(1)

    _configure_logging(settings.log_level)
    bot = SpamDetectionBot()
    async with bot:
        await bot.start(settings.discord_token)


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("Bot detenido (Ctrl+C).")


if __name__ == "__main__":
    main()
