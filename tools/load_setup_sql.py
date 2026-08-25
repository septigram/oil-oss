#!/usr/bin/env python3
"""Tsurugi へ setup.sql を投入し、必要なら初回 ADMIN を作成する。"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

from app.auth.models import Role
from app.auth.password import hash_password
from app.config import get_settings

load_dotenv(ROOT / ".env", override=False)

SETUP_SQL = ROOT / "data" / "20260624T221136" / "setup.sql"
BOOTSTRAP_EMP = "EMP-00001"


def _endpoint() -> str:
    return os.getenv("OIL_TSURUGI_ENDPOINT", "tcp://127.0.0.1:12345")


def _credentials() -> tuple[str, str]:
    return (
        os.getenv("OIL_TSURUGI_USER", "tsurugi"),
        os.getenv("OIL_TSURUGI_PASSWORD", "password"),
    )


def wait_for_tsurugi(timeout_sec: int = 120) -> None:
    endpoint = os.environ["OIL_TSURUGI_ENDPOINT"]
    user, password = _credentials()
    deadline = time.time() + timeout_sec
    last_error = ""
    import tsurugi_dbapi as tsurugi

    while time.time() < deadline:
        try:
            with tsurugi.connect(
                endpoint=endpoint,
                user=user,
                password=password,
                default_timeout=10,
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.commit()
            print(f"Tsurugi is ready ({endpoint})")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            time.sleep(2)
    raise RuntimeError(
        f"Tsurugi not ready after {timeout_sec}s at {endpoint}: {last_error}"
    )


def split_sql(text: str) -> list[str]:
    """シングルクォート内のセミコロンを無視して文を分割する。"""
    statements: list[str] = []
    buf: list[str] = []
    in_single = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "'" and not in_single:
            in_single = True
            buf.append(ch)
        elif ch == "'" and in_single:
            if i + 1 < len(text) and text[i + 1] == "'":
                buf.append("''")
                i += 1
            else:
                in_single = False
                buf.append(ch)
        elif ch == ";" and not in_single:
            stmt = "".join(buf).strip()
            if stmt:
                lines = [
                    line
                    for line in stmt.splitlines()
                    if line.strip() and not line.strip().startswith("--")
                ]
                cleaned = "\n".join(lines).strip()
                if cleaned:
                    statements.append(cleaned)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        lines = [line for line in tail.splitlines() if line.strip() and not line.strip().startswith("--")]
        cleaned = "\n".join(lines).strip()
        if cleaned:
            statements.append(cleaned)
    return statements


def database_initialized(conn) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM oil_company")
            row = cur.fetchone()
        conn.commit()
        return row is not None and int(row[0]) > 0
    except Exception:
        conn.rollback()
        return False


def _apply_tsurugi_env() -> None:
    os.environ["OIL_TSURUGI_ENDPOINT"] = os.getenv("OIL_TSURUGI_ENDPOINT", _endpoint())
    os.environ["OIL_TSURUGI_USER"] = os.getenv("OIL_TSURUGI_USER", "tsurugi")
    os.environ["OIL_TSURUGI_PASSWORD"] = os.getenv("OIL_TSURUGI_PASSWORD", "password")
    get_settings.cache_clear()


def load_setup_sql(conn) -> None:
    if not SETUP_SQL.exists():
        raise FileNotFoundError(f"setup.sql not found: {SETUP_SQL}")
    text = SETUP_SQL.read_text(encoding="utf-8")
    statements = split_sql(text)
    print(f"Executing {len(statements)} SQL statements from setup.sql ...")
    with conn.cursor() as cur:
        for idx, stmt in enumerate(statements, start=1):
            try:
                cur.execute(stmt)
            except Exception as exc:  # noqa: BLE001
                preview = stmt[:120].replace("\n", " ")
                raise RuntimeError(f"Statement {idx} failed: {exc}\nSQL: {preview}...") from exc
            if idx % 200 == 0:
                print(f"  ... {idx}/{len(statements)}")
    conn.commit()
    print("setup.sql loaded")


def bootstrap_admin(conn, password: str) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM oil_users")
        count = int(cur.fetchone()[0])
    conn.commit()
    if count > 0:
        print("Users already exist; skipping bootstrap")
        return
    now = datetime.now(tz=timezone.utc)
    pwd_hash = hash_password(password)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO oil_users (
                user_id, employee_id, login_name, password_hash, is_active,
                row_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, 1, ?, ?)
            """,
            ("USR-00001", BOOTSTRAP_EMP, "admin", pwd_hash, now, now),
        )
        cur.execute(
            "INSERT INTO oil_user_roles (user_id, user_role) VALUES (?, ?)",
            ("USR-00001", Role.ADMIN.value),
        )
    conn.commit()
    print("Bootstrap ADMIN created: login=admin")


RFC008_DDL = (
    (
        "oil_webhook_api_keys",
        """
CREATE TABLE oil_webhook_api_keys (
  key_id                 VARCHAR(16)  NOT NULL PRIMARY KEY,
  name                   VARCHAR(128) NOT NULL,
  api_key_hash           VARCHAR(128) NOT NULL,
  operator_employee_id   VARCHAR(16)  NOT NULL,
  expires_at             TIMESTAMP WITH TIME ZONE,
  is_active              INTEGER      NOT NULL,
  created_by_user_id     VARCHAR(16)  NOT NULL,
  created_at             TIMESTAMP WITH TIME ZONE NOT NULL,
  updated_at             TIMESTAMP WITH TIME ZONE NOT NULL
)
""",
    ),
    (
        "oil_notification_channels",
        """
CREATE TABLE oil_notification_channels (
  channel_id             VARCHAR(16)  NOT NULL PRIMARY KEY,
  name                   VARCHAR(128) NOT NULL,
  webhook_url            VARCHAR(512) NOT NULL,
  is_active              INTEGER      NOT NULL,
  row_version            INTEGER      NOT NULL,
  created_at             TIMESTAMP WITH TIME ZONE NOT NULL,
  updated_at             TIMESTAMP WITH TIME ZONE NOT NULL,
  updated_by_employee_id VARCHAR(16)
)
""",
    ),
    (
        "oil_notification_channel_types",
        """
CREATE TABLE oil_notification_channel_types (
  channel_id VARCHAR(16) NOT NULL,
  type_id    VARCHAR(16) NOT NULL,
  PRIMARY KEY (channel_id, type_id)
)
""",
    ),
)


def _table_exists(conn, name: str) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {name}")
            cur.fetchone()
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def apply_rfc008_migration(conn) -> None:
    for table_name, ddl in RFC008_DDL:
        if _table_exists(conn, table_name):
            print(f"RFC008 skip: {table_name} already exists")
            continue
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
        print(f"RFC008 created: {table_name}")
    print("RFC008 migration complete")


def main() -> None:
    _apply_tsurugi_env()
    wait_for_tsurugi()
    bootstrap_password = os.getenv("OIL_BOOTSTRAP_PASSWORD", "admin")

    import tsurugi_dbapi as tsurugi

    user, password = _credentials()
    with tsurugi.connect(
        endpoint=os.environ["OIL_TSURUGI_ENDPOINT"],
        user=user,
        password=password,
        default_timeout=120,
    ) as conn:
        if database_initialized(conn):
            print("Database already initialized; skipping setup.sql")
        else:
            load_setup_sql(conn)
        apply_rfc008_migration(conn)
        bootstrap_admin(conn, bootstrap_password)
    print("db-init complete")


if __name__ == "__main__":
    main()
