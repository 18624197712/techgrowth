import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..crypto import SecretCipher, constant_time_matches, token_hash
from ..domain.auth import LoginAttempt, LoginPolicy
from ..models import AuditLog, AuthSession, LoginAttemptRecord, User


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class SessionResult:
    token: str
    next_step: str


class AuthService:
    def __init__(self, session_factory, settings: Settings) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.hasher = PasswordHasher()
        self.cipher = SecretCipher(settings.encryption_key)

    def create_admin(self, email: str, password: str) -> User:
        if len(password) < 12:
            raise ValueError("password must have at least 12 characters")
        try:
            normalized_email = TypeAdapter(EmailStr).validate_python(email)
        except ValidationError as exc:
            raise ValueError("administrator must use a valid email address") from exc
        with self.session_factory() as db:
            existing = db.scalar(select(User))
            if existing:
                raise ValueError("administrator already exists")
            secret = pyotp.random_base32()
            user = User(
                email=normalized_email.casefold().strip(),
                password_hash=self.hasher.hash(password),
                totp_secret_enc=self.cipher.encrypt(secret),
            )
            db.add(user)
            db.add(AuditLog(event="admin.created", actor_id=user.id))
            db.commit()
            return user

    def login(self, email: str, password: str, ip_address: str) -> SessionResult:
        now = datetime.now(UTC)
        normalized = email.casefold().strip()
        with self.session_factory() as db:
            attempts = db.scalars(
                select(LoginAttemptRecord).where(
                    LoginAttemptRecord.email == normalized,
                    LoginAttemptRecord.ip_address == ip_address,
                )
            ).all()
            domain_attempts = [
                LoginAttempt(self._aware(item.created_at), item.successful) for item in attempts
            ]
            locked_until = LoginPolicy.locked_until(domain_attempts, now)
            if locked_until:
                raise AuthError("Too many login attempts", 429)
            user = db.scalar(select(User).where(User.email == normalized))
            valid = False
            if user:
                try:
                    valid = self.hasher.verify(user.password_hash, password)
                except VerifyMismatchError:
                    valid = False
            db.add(
                LoginAttemptRecord(email=normalized, ip_address=ip_address, successful=bool(valid))
            )
            if not user or not valid:
                db.commit()
                raise AuthError("Invalid credentials")
            state = "preauth" if user.totp_enabled else "setup"
            token = secrets.token_urlsafe(48)
            csrf = secrets.token_urlsafe(32)
            db.add(
                AuthSession(
                    user_id=user.id,
                    token_hash=token_hash(token),
                    csrf_hash=token_hash(csrf),
                    state=state,
                    expires_at=now + timedelta(minutes=10),
                )
            )
            db.add(AuditLog(event="auth.password_verified", actor_id=user.id))
            db.commit()
            return SessionResult(token, "totp" if user.totp_enabled else "totp_setup")

    def totp_setup(self, raw_token: str) -> dict[str, str]:
        with self.session_factory() as db:
            session = self._session(db, raw_token, allowed_states={"setup"})
            secret = self.cipher.decrypt(session.user.totp_secret_enc)
            return {
                "secret": secret,
                "provisioning_uri": pyotp.TOTP(secret).provisioning_uri(
                    name=session.user.email, issuer_name=self.settings.app_name
                ),
            }

    def confirm_totp(self, raw_token: str, code: str) -> tuple[str, list[str]]:
        with self.session_factory() as db:
            session = self._session(db, raw_token, allowed_states={"setup", "preauth"})
            secret = self.cipher.decrypt(session.user.totp_secret_enc)
            if not pyotp.TOTP(secret).verify(code, valid_window=1):
                raise AuthError("Invalid TOTP code")
            recovery_codes: list[str] = []
            if not session.user.totp_enabled:
                recovery_codes = [secrets.token_hex(5) for _ in range(8)]
                session.user.recovery_hashes = [token_hash(item) for item in recovery_codes]
                session.user.totp_enabled = True
            csrf = secrets.token_urlsafe(32)
            session.csrf_hash = token_hash(csrf)
            session.state = "authenticated"
            session.expires_at = datetime.now(UTC) + timedelta(hours=self.settings.session_hours)
            db.add(AuditLog(event="auth.totp_verified", actor_id=session.user_id))
            db.commit()
            return csrf, recovery_codes

    def authenticated(self, raw_token: str) -> tuple[AuthSession, User]:
        with self.session_factory() as db:
            session = self._session(db, raw_token, allowed_states={"authenticated"})
            db.expunge(session.user)
            db.expunge(session)
            return session, session.user

    def validate_csrf(self, raw_token: str, csrf: str) -> User:
        with self.session_factory() as db:
            session = self._session(db, raw_token, allowed_states={"authenticated"})
            if not constant_time_matches(csrf, session.csrf_hash):
                raise AuthError("CSRF token invalid", 403)
            db.expunge(session.user)
            return session.user

    def logout(self, raw_token: str) -> None:
        with self.session_factory() as db:
            session = db.scalar(
                select(AuthSession).where(AuthSession.token_hash == token_hash(raw_token))
            )
            if session:
                db.delete(session)
                db.commit()

    def _session(self, db: Session, raw_token: str, allowed_states: set[str]) -> AuthSession:
        if not raw_token:
            raise AuthError("Authentication required")
        session = db.scalar(
            select(AuthSession).where(AuthSession.token_hash == token_hash(raw_token))
        )
        if not session or session.state not in allowed_states:
            raise AuthError("Authentication required")
        if self._aware(session.expires_at) <= datetime.now(UTC):
            db.delete(session)
            db.commit()
            raise AuthError("Session expired")
        return session

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)
