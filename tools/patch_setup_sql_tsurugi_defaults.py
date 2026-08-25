#!/usr/bin/env python3
"""setup.sql を Tsurugi 制約向けに修正する。

- TIMESTAMP WITH TIME ZONE 列の DEFAULT 式は Tsurugi 非対応のため削除
- row_version / updated_at / updated_by_employee_id 列は INSERT 側で明示
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "data" / "20260624T221136" / "setup.sql"

TS_DEFAULT = " DEFAULT TIMESTAMP WITH TIME ZONE '2020-05-01T00:00:00+09:00'"

TABLES_WITH_VERSION_COLS = (
    "oil_departments",
    "oil_personnel_history",
    "oil_services",
    "oil_customers",
    "oil_incident_types",
    "oil_incident_type_locations",
    "oil_incidents",
    "oil_incident_investigations",
    "oil_incident_responses",
)

EXTRA_COLS = ", row_version, updated_at, updated_by_employee_id"
EXTRA_VALS = ", 1, TIMESTAMP WITH TIME ZONE '2020-05-01T00:00:00+09:00', 'EMP-00001'"

TABLES_PATTERN = "|".join(re.escape(t) for t in TABLES_WITH_VERSION_COLS)


def _patch_insert(stmt: str) -> str:
    if "row_version" in stmt:
        return stmt
    stmt = re.sub(r"\)\s*VALUES\s*\(", f"{EXTRA_COLS}) VALUES (", stmt, count=1)
    stmt = stmt.rstrip()
    if stmt.endswith(");"):
        return stmt[:-2] + EXTRA_VALS + ");"
    return stmt


def patch_setup(text: str) -> str:
    text = text.replace(TS_DEFAULT, "")

    def repl(match: re.Match[str]) -> str:
        return _patch_insert(match.group(0))

    return re.sub(
        rf"INSERT INTO ({TABLES_PATTERN})[^;]*;",
        repl,
        text,
        flags=re.S,
    )


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else SETUP
    original = path.read_text(encoding="utf-8")
    patched = patch_setup(original)
    path.write_text(patched, encoding="utf-8")
    print(f"Patched {path}")
    print(f"  removed TS DEFAULT: {original.count(TS_DEFAULT)}")
    for table in TABLES_WITH_VERSION_COLS:
        inserts = re.findall(rf"INSERT INTO {table}[^;]*;", patched, re.S)
        missing = sum(1 for s in inserts if "row_version" not in s)
        print(f"  {table}: {len(inserts)} inserts, missing row_version: {missing}")


if __name__ == "__main__":
    main()
