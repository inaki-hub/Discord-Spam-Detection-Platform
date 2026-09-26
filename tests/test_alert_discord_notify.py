from __future__ import annotations

from datetime import datetime, timezone

from app.alerts.alert_manager import Alert
from app.alerts.discord_notify import alert_message_key


def test_alert_message_key_per_user_and_channel():
    alert = Alert(
        user_id="u1",
        guild_id="g1",
        channel_id="origin",
        timestamp=datetime.now(timezone.utc),
        spam_score=50,
        automation_score=10,
        spam_classification="suspicious",
        automation_classification="normal",
        signals={"spam": ["a"], "automation": []},
        evidence=("spam:a",),
    )
    assert alert_message_key(alert, "mod1") == ("g1", "u1", "mod1")
    assert alert_message_key(alert, "mod2") != alert_message_key(alert, "mod1")
