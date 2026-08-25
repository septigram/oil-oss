"""Slack Bot 起動スキップの単体テスト。"""

from __future__ import annotations

from unittest.mock import patch

from app.slack.bot import start_slack_bot_if_configured


@patch("app.slack.bot.get_settings")
def test_start_skipped_without_tokens(mock_settings) -> None:
    mock_settings.return_value.slack.bot_token = None
    mock_settings.return_value.slack.app_token = None
    task = start_slack_bot_if_configured()
    assert task is None
