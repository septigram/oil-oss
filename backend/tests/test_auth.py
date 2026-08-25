"""認証・パスワードの単体テスト。"""

from __future__ import annotations

from app.auth.password import hash_password, verify_password


def test_hash_and_verify_password() -> None:
    hashed = hash_password("secret")
    assert hashed != "secret"
    assert verify_password("secret", hashed)
    assert not verify_password("wrong", hashed)


def test_login_rate_limit() -> None:
    from app.auth import rate_limit

    rate_limit._attempts.clear()
    ip, name = "192.0.2.1", "admin"
    for _ in range(5):
        rate_limit.record_failed_attempt(ip, name)
    assert rate_limit.is_rate_limited(ip, name)
    assert not rate_limit.is_rate_limited(ip, "other")
