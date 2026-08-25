"""ドメイン列値の正規化テスト。"""

from app.domain.models import (
    SEVERITY_SPECS,
    STATUS_SPECS,
    format_domain_enums_for_prompt,
    normalize_severities,
    normalize_statuses,
)


def test_normalize_statuses_from_display_labels() -> None:
    assert normalize_statuses(["未着手"]) == ["OPEN"]
    assert normalize_statuses(["対応中", "解決済み"]) == ["IN_PROGRESS", "RESOLVED"]


def test_normalize_statuses_from_db_values() -> None:
    assert normalize_statuses(["OPEN", "in_progress"]) == ["OPEN", "IN_PROGRESS"]


def test_normalize_statuses_composite_filters() -> None:
    assert normalize_statuses(["未完了"]) == ["OPEN", "IN_PROGRESS"]
    assert normalize_statuses(["未解決"]) == ["OPEN", "IN_PROGRESS"]


def test_normalize_statuses_rejects_unknown() -> None:
    assert normalize_statuses(["unassigned"]) is None
    assert normalize_statuses(["pending"]) is None
    assert normalize_statuses(["invalid_status"]) is None


def test_normalize_severities_from_db_values() -> None:
    assert normalize_severities(["CRITICAL", "medium"]) == ["CRITICAL", "MEDIUM"]


def test_normalize_severities_rejects_unknown() -> None:
    assert normalize_severities(["重大"]) is None
    assert normalize_severities(["invalid"]) is None


def test_status_display_label() -> None:
    from app.domain.models import status_display_label

    assert status_display_label("OPEN") == "未着手"
    assert status_display_label("IN_PROGRESS") == "対応中"
    assert status_display_label("RESOLVED") == "解決済み"
    assert status_display_label("UNKNOWN") == "UNKNOWN"


def test_format_domain_enums_lists_all_specs() -> None:
    text = format_domain_enums_for_prompt()
    for db, display in STATUS_SPECS:
        assert f"| {db} | {display} |" in text
    for db, display in SEVERITY_SPECS:
        assert f"| {db} | {display} |" in text
    assert "未完了" in text
    assert "未解決" in text
    assert "unassigned" in text
