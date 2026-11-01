import uuid
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import User, UserPreferences, UserSession


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def add(self, email: str, password_hash: str, display_name: str | None) -> User:
        user = User(email=email, password_hash=password_hash, display_name=display_name)
        user.preferences = UserPreferences()
        self.db.add(user)
        self.db.flush()
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)


class SessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(
        self, user_id: uuid.UUID, token_hash: str, expires_at: datetime, user_agent: str | None
    ) -> UserSession:
        s = UserSession(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at, user_agent=user_agent
        )
        self.db.add(s)
        self.db.flush()
        return s

    def get_active(self, token_hash: str, now: datetime) -> UserSession | None:
        return self.db.scalar(
            select(UserSession).where(
                UserSession.token_hash == token_hash, UserSession.expires_at > now
            )
        )

    def touch(self, session_id: uuid.UUID, now: datetime) -> None:
        self.db.execute(
            update(UserSession).where(UserSession.id == session_id).values(last_seen_at=now)
        )

    def delete_by_hash(self, token_hash: str) -> None:
        self.db.execute(delete(UserSession).where(UserSession.token_hash == token_hash))

    def delete_expired(self, now: datetime) -> int:
        result = self.db.execute(delete(UserSession).where(UserSession.expires_at <= now))
        return result.rowcount or 0  # type: ignore[attr-defined]
