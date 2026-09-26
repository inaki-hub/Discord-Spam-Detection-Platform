from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModerationSettings:
    """Política de sanciones (opt-in). 0 segundos = no aplicar ese nivel."""

    enabled: bool
    """Si true, solo registra la acción sin timeout en Discord."""
    dry_run: bool
    cooldown_seconds: int
    penalize_spam: bool
    penalize_automation: bool
    min_effective_spam_score: int
    min_effective_automation_score: int
    timeout_spam_likely_seconds: int
    timeout_suspicious_seconds: int
    timeout_automation_likely_seconds: int
    timeout_automation_suspicious_seconds: int


def moderation_to_dict(settings: ModerationSettings) -> dict:
    return asdict(settings)


def moderation_from_dict(data: dict) -> ModerationSettings:
    return ModerationSettings(
        enabled=bool(data.get("enabled", False)),
        dry_run=bool(data.get("dry_run", True)),
        cooldown_seconds=int(data.get("cooldown_seconds", 300)),
        penalize_spam=bool(data.get("penalize_spam", True)),
        penalize_automation=bool(data.get("penalize_automation", False)),
        min_effective_spam_score=int(data.get("min_effective_spam_score", 40)),
        min_effective_automation_score=int(data.get("min_effective_automation_score", 40)),
        timeout_spam_likely_seconds=int(data.get("timeout_spam_likely_seconds", 0)),
        timeout_suspicious_seconds=int(data.get("timeout_suspicious_seconds", 0)),
        timeout_automation_likely_seconds=int(data.get("timeout_automation_likely_seconds", 0)),
        timeout_automation_suspicious_seconds=int(
            data.get("timeout_automation_suspicious_seconds", 0)
        ),
    )


def format_moderation_summary(settings: ModerationSettings) -> str:
    mode = "activa" if settings.enabled else "off"
    run = "dry-run" if settings.dry_run else "aplica timeouts"
    return (
        f"Moderación: **{mode}** ({run})\n"
        f"Cooldown: {settings.cooldown_seconds}s · "
        f"Penalizar spam: {settings.penalize_spam} · automation: {settings.penalize_automation}\n"
        f"Min scores: spam={settings.min_effective_spam_score} "
        f"auto={settings.min_effective_automation_score}\n"
        f"Timeouts (s): suspicious={settings.timeout_suspicious_seconds}, "
        f"spam_likely={settings.timeout_spam_likely_seconds}, "
        f"auto_suspicious={settings.timeout_automation_suspicious_seconds}, "
        f"auto_likely={settings.timeout_automation_likely_seconds}"
    )
