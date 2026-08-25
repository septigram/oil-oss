"""pytest 共通フィクスチャ。"""

from __future__ import annotations

import os

# app  import 時に AgentService → FaissStore が埋め込みクライアントを生成するため、
# 単体テスト収集時はダミーキーで足りる（実 API は呼ばない）。
os.environ.setdefault("OPENAI_API_KEY", "sk-unit-test")

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import (
    AiConfig,
    AppConfig,
    OperatorConfig,
    PathsConfig,
    RagConfig,
    ReferenceDateConfig,
    SlackConfig,
    TsurugiConfig,
    default_auth_config,
)
from app.config import get_settings
from app.domain.models import IncidentStatus
from app.main import app
from app.repository.incident import IncidentRepository, IncidentSearchParams
from app.repository.tsurugi_conn import TsurugiConnection
from app.services.reference_date import ReferenceDateService

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INTEG_TEST_TITLE_PREFIX = "INTEG-TEST"

_settings = get_settings()
CONTEXT_PATH = _settings.context_path
API_PREFIX = f"{CONTEXT_PATH}/api"
HEALTH_PATH = f"{CONTEXT_PATH}/health"


def make_app_config(
    *,
    reference_date_mode: str = "fixed",
    fixed_date: str = "2020-05-31",
    llm_provider: str = "openai",
    embedding_provider: str | None = None,
    context_path: str = "/oil",
    base_url: str = "http://localhost:8000/oil",
) -> AppConfig:
    """単体テスト用 AppConfig。AppConfig フィールド追加時はここだけ更新する。"""
    provider = embedding_provider if embedding_provider is not None else "openai"
    return AppConfig(
        timezone="Asia/Tokyo",
        context_path=context_path,
        base_url=base_url,
        operator=OperatorConfig(employee_id="EMP-00001", display_name="運用 一郎"),
        auth=default_auth_config(),
        reference_date=ReferenceDateConfig(mode=reference_date_mode, fixed_date=fixed_date),
        tsurugi=TsurugiConfig(
            endpoint="tcp://localhost:12345",
            user="tsurugi",
            password="password",
        ),
        paths=PathsConfig(
            corpus_jsonl=PROJECT_ROOT / "data" / "20260624T221136" / "corpus.jsonl",
            rag_summary_dir=PROJECT_ROOT / "data" / "rag-summary",
            faiss_dir=PROJECT_ROOT / "data" / "faiss",
            chat_prompt_templates=PROJECT_ROOT / "data" / "chat-prompt-templates.yaml",
        ),
        rag=RagConfig(top_k=5),
        ai=AiConfig(
            provider=provider,
            llm_provider=llm_provider,
            llm_model="gpt-4o-mini",
            embedding_model="text-embedding-3-small",
            ollama_base_url="http://localhost:11434",
            ollama_llm_model="qwen3.6:27b",
            ollama_embedding_model="nomic-embed-text",
        ),
        slack=SlackConfig(bot_token=None, app_token=None),
        project_root=PROJECT_ROOT,
    )


@pytest.fixture
def fixed_settings() -> AppConfig:
    return make_app_config()


@dataclass(frozen=True)
class SeedExpectations:
    initial_unresolved_in_past_month: int
    current_month_all: int
    previous_month_all: int
    unresolved_all: int


def tsurugi_available() -> bool:
    try:
        TsurugiConnection().fetchone("SELECT 1")
        return True
    except Exception:
        return False


def auth_tables_available() -> bool:
    if not tsurugi_available():
        return False
    try:
        TsurugiConnection().fetchone("SELECT COUNT(*) FROM oil_users")
        return True
    except Exception:
        return False


def master_write_available() -> bool:
    if not tsurugi_available():
        return False
    from app.repository.schema_compat import has_column

    return has_column("oil_incident_types", "row_version")


def compute_seed_expectations() -> SeedExpectations:
    ref = ReferenceDateService()
    repo = IncidentRepository()

    past = ref.past_one_month()
    _, initial = repo.search(
        IncidentSearchParams(
            occurred_from=past.start,
            occurred_to=past.end,
            statuses=[IncidentStatus.OPEN.value, IncidentStatus.IN_PROGRESS.value],
            page=1,
            page_size=1,
        )
    )

    cur = ref.current_month()
    _, current_month = repo.search(
        IncidentSearchParams(
            occurred_from=cur.start,
            occurred_to=cur.end,
            page=1,
            page_size=1,
        )
    )

    prev = ref.previous_month()
    _, previous_month = repo.search(
        IncidentSearchParams(
            occurred_from=prev.start,
            occurred_to=prev.end,
            page=1,
            page_size=1,
        )
    )

    _, unresolved = repo.search(
        IncidentSearchParams(
            statuses=[IncidentStatus.OPEN.value, IncidentStatus.IN_PROGRESS.value],
            page=1,
            page_size=1,
        )
    )

    return SeedExpectations(
        initial_unresolved_in_past_month=initial,
        current_month_all=current_month,
        previous_month_all=previous_month,
        unresolved_all=unresolved,
    )


def delete_incident_cascade(db: TsurugiConnection, incident_id: str) -> None:
    db.execute("DELETE FROM oil_incident_customers WHERE incident_id = ?", (incident_id,))
    db.execute("DELETE FROM oil_incident_responses WHERE incident_id = ?", (incident_id,))
    db.execute("DELETE FROM oil_incident_investigations WHERE incident_id = ?", (incident_id,))
    db.execute("DELETE FROM oil_incidents WHERE incident_id = ?", (incident_id,))


def cleanup_integration_test_data(db: TsurugiConnection | None = None) -> int:
    conn = db or TsurugiConnection()
    rows = conn.fetchall(
        "SELECT incident_id FROM oil_incidents WHERE title LIKE ?",
        (f"{INTEG_TEST_TITLE_PREFIX}%",),
    )
    for row in rows:
        delete_incident_cascade(conn, row[0])
    return len(rows)


@pytest.fixture
def seed_expectations() -> SeedExpectations:
    if not tsurugi_available():
        pytest.skip("Tsurugi に接続できません")
    return compute_seed_expectations()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@contextmanager
def override_current_user(*roles):
    """RBAC テスト用に get_current_user を上書きする。"""
    from app.auth.dependencies import get_current_user
    from app.auth.models import CurrentUser, Role

    if not roles:
        roles = (Role.ADMIN,)

    async def _dep() -> CurrentUser:
        return CurrentUser(
            user_id="USR-TEST",
            employee_id="EMP-00001",
            display_name="Test User",
            login_name="test",
            roles=list(roles),
        )

    app.dependency_overrides[get_current_user] = _dep
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def tsurugi_client() -> TestClient:
    if not tsurugi_available():
        pytest.skip("Tsurugi に接続できません")
    cleanup_integration_test_data()
    yield TestClient(app)
    cleanup_integration_test_data()


@pytest.fixture
def integration_incident(tsurugi_client: TestClient) -> str:
    """結合テスト用インシデント（自動クリーンアップ）。"""
    body = {
        "incident": {
            "type_id": "ITYP-001",
            "occurred_at": "2020-05-15T10:00:00+09:00",
            "title": f"{INTEG_TEST_TITLE_PREFIX} incident",
            "description": "integration test fixture",
            "location_name": "test loc",
            "affected_service_ids": ["SVC-001"],
            "detector_employee_id": "EMP-00001",
            "detector_department_id": "DEPT-OPS",
            "severity": "LOW",
            "status": "OPEN",
            "detection_source": "OPS_MONITORING",
        },
        "customer_ids": ["CUST-0001"],
    }
    r = tsurugi_client.post(f"{API_PREFIX}/incidents", json=body)
    assert r.status_code == 201
    return r.json()["incident_id"]
