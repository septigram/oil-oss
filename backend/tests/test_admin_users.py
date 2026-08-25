"""ユーザ管理 API テスト。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.models import Role
from tests.conftest import API_PREFIX, auth_tables_available, override_current_user


@pytest.mark.skipif(not auth_tables_available(), reason="oil_users 未作成")
def test_admin_users_list(client: TestClient) -> None:
    with override_current_user(Role.ADMIN):
        r = client.get(f"{API_PREFIX}/admin/users")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["items"], list)


def test_viewer_denied_admin_users(client: TestClient) -> None:
    with override_current_user(Role.VIEWER):
        r = client.get(f"{API_PREFIX}/admin/users")
    assert r.status_code == 403
