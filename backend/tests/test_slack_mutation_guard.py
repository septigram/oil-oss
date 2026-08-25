"""Slack 更新意図検出の単体テスト。"""

from __future__ import annotations

from app.agent.service import is_slack_mutation_request


def test_detect_update_request() -> None:
    assert is_slack_mutation_request("INC-2020-00001 を HIGH に更新して")
    assert not is_slack_mutation_request("未完了のインシデント一覧を教えて")
