import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    # Stored lower-cased; uniqueness enforced on the normalized value.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_login_at: Mapped[datetime | None]

    preferences: Mapped["UserPreferences"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )

    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)


class UserPreferences(Timestamps, Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    currency: Mapped[str] = mapped_column(CHAR(3), default="USD", server_default="USD")
    home_airport: Mapped[str | None] = mapped_column(CHAR(3))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    inapp_notifications: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    user: Mapped[User] = relationship(back_populates="preferences")

    __table_args__ = (
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_iso4217"),
        CheckConstraint("home_airport IS NULL OR home_airport ~ '^[A-Z]{3}$'", name="home_iata"),
    )


class UserSession(UUIDPk, Base):
    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(CHAR(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    user_agent: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )
