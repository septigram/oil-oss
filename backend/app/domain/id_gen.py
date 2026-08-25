"""ID 採番ユーティリティ。"""

from __future__ import annotations

import re


def parse_incident_sequence(incident_id: str) -> int:
    match = re.search(r"INC-\d{4}-(\d+)$", incident_id)
    if not match:
        raise ValueError(f"invalid incident_id: {incident_id}")
    return int(match.group(1))


def format_incident_id(year: int, seq: int) -> str:
    return f"INC-{year}-{seq:05d}"


def parse_response_sequence(response_id: str) -> int:
    match = re.search(r"RSP-(\d+)$", response_id)
    if not match:
        raise ValueError(f"invalid response_id: {response_id}")
    return int(match.group(1))


def format_response_id(seq: int) -> str:
    return f"RSP-{seq:05d}"


def format_investigation_id(seq: int) -> str:
    return f"INV-{seq:05d}"


def parse_procedure_sequence(procedure_id: str) -> int:
    match = re.search(r"PRC-(\d+)$", procedure_id)
    if not match:
        raise ValueError(f"invalid procedure_id: {procedure_id}")
    return int(match.group(1))


def format_procedure_id(seq: int) -> str:
    return f"PRC-{seq:05d}"


def parse_user_sequence(user_id: str) -> int:
    match = re.search(r"USR-(\d+)$", user_id)
    if not match:
        raise ValueError(f"invalid user_id: {user_id}")
    return int(match.group(1))


def format_user_id(seq: int) -> str:
    return f"USR-{seq:05d}"


def parse_type_sequence(type_id: str) -> int:
    match = re.search(r"ITYP-(\d+)$", type_id)
    if not match:
        raise ValueError(f"invalid type_id: {type_id}")
    return int(match.group(1))


def format_type_id(seq: int) -> str:
    return f"ITYP-{seq:03d}"


def parse_customer_sequence(customer_id: str) -> int:
    match = re.search(r"CUST-(\d+)$", customer_id)
    if not match:
        raise ValueError(f"invalid customer_id: {customer_id}")
    return int(match.group(1))


def format_customer_id(seq: int) -> str:
    return f"CUST-{seq:04d}"


def parse_service_sequence(service_id: str) -> int:
    match = re.search(r"SVC-(\d+)$", service_id)
    if not match:
        raise ValueError(f"invalid service_id: {service_id}")
    return int(match.group(1))


def format_service_id(seq: int) -> str:
    return f"SVC-{seq:03d}"


def parse_employee_sequence(employee_id: str) -> int:
    match = re.search(r"EMP-(\d+)$", employee_id)
    if not match:
        raise ValueError(f"invalid employee_id: {employee_id}")
    return int(match.group(1))


def format_employee_id(seq: int) -> str:
    return f"EMP-{seq:05d}"


def parse_webhook_key_sequence(key_id: str) -> int:
    match = re.search(r"WHK-(\d+)$", key_id)
    if not match:
        raise ValueError(f"invalid key_id: {key_id}")
    return int(match.group(1))


def format_webhook_key_id(seq: int) -> str:
    return f"WHK-{seq:05d}"


def parse_channel_sequence(channel_id: str) -> int:
    match = re.search(r"CHN-(\d+)$", channel_id)
    if not match:
        raise ValueError(f"invalid channel_id: {channel_id}")
    return int(match.group(1))


def format_channel_id(seq: int) -> str:
    return f"CHN-{seq:05d}"


def parse_personnel_history_sequence(history_id: str) -> int:
    match = re.search(r"PH-(\d+)$", history_id)
    if not match:
        raise ValueError(f"invalid history_id: {history_id}")
    return int(match.group(1))


def format_personnel_history_id(seq: int) -> str:
    return f"PH-{seq:05d}"
