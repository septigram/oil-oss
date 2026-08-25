"""チャット定型質問テンプレートの単体テスト。"""

from __future__ import annotations

from app.services.chat_prompt_template import ChatPromptTemplateService

from tests.conftest import make_app_config


def test_list_templates_reads_yaml() -> None:
    service = ChatPromptTemplateService(make_app_config())
    items = service.list_templates()
    assert len(items) == 9
    assert items[0]["id"] == "tpl-store-a-last-month"
    assert "架空食品店A" in items[0]["message"]
    assert items[-1]["id"] == "tpl-incident-location-count"
