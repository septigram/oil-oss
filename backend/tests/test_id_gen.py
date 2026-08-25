"""ID 採番の単体テスト。"""

from app.domain.id_gen import (
    format_incident_id,
    format_procedure_id,
    format_response_id,
    parse_incident_sequence,
    parse_procedure_sequence,
    parse_response_sequence,
)


def test_parse_incident_sequence() -> None:
    assert parse_incident_sequence("INC-2020-00305") == 305


def test_format_incident_id() -> None:
    assert format_incident_id(2020, 305) == "INC-2020-00305"


def test_parse_response_sequence() -> None:
    assert parse_response_sequence("RSP-00450") == 450


def test_format_response_id() -> None:
    assert format_response_id(450) == "RSP-00450"


def test_parse_procedure_sequence() -> None:
    assert parse_procedure_sequence("PRC-00001") == 1


def test_format_procedure_id() -> None:
    assert format_procedure_id(42) == "PRC-00042"
