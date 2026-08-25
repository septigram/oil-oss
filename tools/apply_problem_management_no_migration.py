#!/usr/bin/env python3
"""oil_incidents に problem_management_no 列を追加する（Tsurugi は ALTER 非対応のためテーブル再作成）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

from app.logging_config import setup_logging
from app.repository.tsurugi_conn import TsurugiConnection

load_dotenv(ROOT / ".env")
setup_logging()

DDL_WITH_ROW_VERSION = """
CREATE TABLE oil_incidents (
  incident_id            VARCHAR(24)   NOT NULL PRIMARY KEY,
  company_id             VARCHAR(16)   NOT NULL,
  type_id                VARCHAR(16)   NOT NULL,
  occurred_at            TIMESTAMP WITH TIME ZONE NOT NULL,
  detected_at            TIMESTAMP WITH TIME ZONE NOT NULL,
  title                  VARCHAR(512)  NOT NULL,
  description            VARCHAR(4096) NOT NULL,
  location_name          VARCHAR(256)  NOT NULL,
  affected_service_ids   VARCHAR(512)  NOT NULL,
  detector_employee_id   VARCHAR(16)   NOT NULL,
  detector_department_id VARCHAR(16)   NOT NULL,
  severity               VARCHAR(16)   NOT NULL,
  status                 VARCHAR(32)   NOT NULL,
  detection_source       VARCHAR(32)   NOT NULL,
  related_event_id       VARCHAR(16),
  problem_management_no  VARCHAR(128),
  row_version            INTEGER NOT NULL DEFAULT 1,
  updated_at             TIMESTAMP WITH TIME ZONE NOT NULL,
  updated_by_employee_id VARCHAR(16)
)
"""

DDL_WITHOUT_ROW_VERSION = """
CREATE TABLE oil_incidents (
  incident_id            VARCHAR(24)   NOT NULL PRIMARY KEY,
  company_id             VARCHAR(16)   NOT NULL,
  type_id                VARCHAR(16)   NOT NULL,
  occurred_at            TIMESTAMP WITH TIME ZONE NOT NULL,
  detected_at            TIMESTAMP WITH TIME ZONE NOT NULL,
  title                  VARCHAR(512)  NOT NULL,
  description            VARCHAR(4096) NOT NULL,
  location_name          VARCHAR(256)  NOT NULL,
  affected_service_ids   VARCHAR(512)  NOT NULL,
  detector_employee_id   VARCHAR(16)   NOT NULL,
  detector_department_id VARCHAR(16)   NOT NULL,
  severity               VARCHAR(16)   NOT NULL,
  status                 VARCHAR(32)   NOT NULL,
  detection_source       VARCHAR(32)   NOT NULL,
  related_event_id       VARCHAR(16),
  problem_management_no  VARCHAR(128)
)
"""


def _column_exists(db: TsurugiConnection, table: str, column: str) -> bool:
    try:
        db.fetchone(f"SELECT {column} FROM {table}")
        return True
    except Exception:
        return False


def _migrate(db: TsurugiConnection) -> None:
    if _column_exists(db, "oil_incidents", "problem_management_no"):
        print("oil_incidents: problem_management_no already present")
        return

    has_row_version = _column_exists(db, "oil_incidents", "row_version")
    temp = "oil_incidents__pmno"
    final_ddl = DDL_WITH_ROW_VERSION if has_row_version else DDL_WITHOUT_ROW_VERSION

    print(f"oil_incidents: migrating via {temp} ...")
    db.execute(f"DROP TABLE IF EXISTS {temp}")
    db.execute(final_ddl.replace("CREATE TABLE oil_incidents", f"CREATE TABLE {temp}"))

    if has_row_version:
        db.execute(
            f"""
            INSERT INTO {temp}
            SELECT incident_id, company_id, type_id, occurred_at, detected_at, title, description,
                   location_name, affected_service_ids, detector_employee_id, detector_department_id,
                   severity, status, detection_source, related_event_id,
                   NULL, row_version, updated_at, updated_by_employee_id
            FROM oil_incidents
            """
        )
    else:
        db.execute(
            f"""
            INSERT INTO {temp}
            SELECT incident_id, company_id, type_id, occurred_at, detected_at, title, description,
                   location_name, affected_service_ids, detector_employee_id, detector_department_id,
                   severity, status, detection_source, related_event_id, NULL
            FROM oil_incidents
            """
        )

    db.execute("DROP TABLE oil_incidents")
    db.execute(final_ddl)
    db.execute(f"INSERT INTO oil_incidents SELECT * FROM {temp}")
    db.execute(f"DROP TABLE {temp}")
    print("oil_incidents: migration complete")


def main() -> int:
    parser = argparse.ArgumentParser(description="Add problem_management_no to oil_incidents")
    parser.parse_args()
    db = TsurugiConnection()
    _migrate(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
