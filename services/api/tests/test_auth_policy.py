from datetime import UTC, datetime, timedelta

import pytest

from techgrowth_api.domain.auth import LoginAttempt, LoginPolicy
from techgrowth_api.services.auth import AuthService


def test_five_recent_failures_lock_account_for_thirty_minutes() -> None:
    now = datetime.now(UTC)
    attempts = [LoginAttempt(now - timedelta(minutes=index), False) for index in range(5)]

    locked_until = LoginPolicy.locked_until(attempts, now)

    assert locked_until == attempts[0].created_at + timedelta(minutes=30)


def test_old_failures_do_not_lock_account() -> None:
    now = datetime.now(UTC)
    attempts = [LoginAttempt(now - timedelta(minutes=20 + index), False) for index in range(5)]

    assert LoginPolicy.locked_until(attempts, now) is None


def test_admin_creation_rejects_reserved_email_domain(client) -> None:
    service: AuthService = client.app.state.services.auth

    with pytest.raises(ValueError, match="valid email"):
        service.create_admin("dev@techgrowth.local", "DevelopmentPassword123!")
