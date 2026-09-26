from __future__ import annotations

from app.config import _parse_alert_channels


def test_parse_alert_channels():
    raw = "111:222, 333:444"
    mapping, default = _parse_alert_channels(raw)
    assert mapping == {"111": "222", "333": "444"}
    assert default == ""


def test_parse_alert_channels_ignores_invalid():
    mapping, default = _parse_alert_channels("bad,111:222")
    assert mapping == {"111": "222"}
    assert default == ""


def test_parse_alert_channels_channel_only_shorthand():
    mapping, default = _parse_alert_channels("1553016584619040878")
    assert mapping == {}
    assert default == "1553016584619040878"
