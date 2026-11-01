"""Authentication use cases. Framework-free: takes a SQLAlchemy Session, returns domain results."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import security
from app.core.errors import Conflict, Unauthorized
from app.core.metrics import AUTH_EVENTS
from app.models import User
from app.models.base import utcnow
from app.repositories.users import SessionRepository, UserRepository

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class IssuedSession:
    user: User
    token: str  # raw token: goes into the cookie, never persisted
    max_age_s: int


class AuthService:
    def __init__(self, db: Session, session_ttl_hours: int) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)
        self.ttl = timedelta(hours=session_ttl_hours)

    def register(
        self, email: str, password: str, display_name: str | None, user_agent: str | None
    ) -> IssuedSession:
        email = email.strip().lower()
        if self.users.get_by_email(email):
            AUTH_EVENTS.labels("register", "duplicate").inc()
            raise Conflict("An account with this email already exists")
        try:
            user = self.users.add(email, security.hash_password(password), display_name)
            issued = self._issue(user, user_agent)
            self.db.commit()
        except IntegrityError as exc:  # concurrent registration with the same email
            self.db.rollback()
            AUTH_EVENTS.labels("register", "duplicate").inc()
            raise Conflict("An account with this email already exists") from exc
        AUTH_EVENTS.labels("register", "ok").inc()
        log.info("user registered", extra={"user_id": str(user.id)})
        return issued

    def login(self, email: str, password: str, user_agent: str | None) -> IssuedSession:
        user = self.users.get_by_email(email.strip().lower())
        ok = security.verify_password(user.password_hash if user else None, password)
        if not user or not ok or not user.is_active:
            AUTH_EVENTS.labels("login", "failed").inc()
            raise Unauthorized("Invalid email or password")
        if security.needs_rehash(user.password_hash):
            user.password_hash = security.hash_password(password)
        user.last_login_at = utcnow()
        issued = self._issue(user, user_agent)
        self.db.commit()
        AUTH_EVENTS.labels("login", "ok").inc()
        return issued

    def logout(self, token: str) -> None:
        self.sessions.delete_by_hash(security.hash_token(token))
        self.db.commit()

    def resolve(self, token: str) -> User | None:
        now = utcnow()
        s = self.sessions.get_active(security.hash_token(token), now)
        if not s or not s.user.is_active:
            return None
        # Throttle last_seen writes to avoid a DB write on every request.
        if now - s.last_seen_at > timedelta(minutes=5):
            self.sessions.touch(s.id, now)
            self.db.commit()
        return s.user

    def delete_account(self, user: User) -> None:
        self.users.delete(user)
        self.db.commit()
        log.info("user deleted", extra={"user_id": str(user.id)})

    def _issue(self, user: User, user_agent: str | None) -> IssuedSession:
        token = security.new_token()
        self.sessions.add(
            user.id, security.hash_token(token), utcnow() + self.ttl, (user_agent or "")[:255]
        )
        return IssuedSession(user=user, token=token, max_age_s=int(self.ttl.total_seconds()))
