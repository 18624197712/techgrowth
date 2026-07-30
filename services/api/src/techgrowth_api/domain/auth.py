from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class LoginAttempt:
    created_at: datetime
    successful: bool


class LoginPolicy:
    WINDOW = timedelta(minutes=15)
    LOCK_DURATION = timedelta(minutes=30)
    FAILURE_LIMIT = 5

    @classmethod
    def locked_until(cls, attempts: list[LoginAttempt], now: datetime) -> datetime | None:
        recent_failures = sorted(
            (
                attempt
                for attempt in attempts
                if not attempt.successful and attempt.created_at >= now - cls.WINDOW
            ),
            key=lambda attempt: attempt.created_at,
        )
        if len(recent_failures) < cls.FAILURE_LIMIT:
            return None
        lock_start = recent_failures[-1].created_at
        locked_until = lock_start + cls.LOCK_DURATION
        return locked_until if locked_until > now else None
