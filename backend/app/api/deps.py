from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.redis import get_redis
from app.core.security import tokens_equal
from app.models import User
from app.services.auth import AuthService
from app.services.rate_limit import RateLimiter

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]

_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def get_auth_service(db: DbSession, settings: AppSettings) -> AuthService:
    return AuthService(db, settings.session_ttl_hours)


def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_redis())


Auth = Annotated[AuthService, Depends(get_auth_service)]
Limiter = Annotated[RateLimiter, Depends(get_rate_limiter)]


def require_csrf(request: Request, settings: AppSettings) -> None:
    """Double-submit CSRF check on every unsafe method (including login, to stop login-CSRF)."""
    if request.method not in _UNSAFE:
        return
    cookie = request.cookies.get(settings.csrf_cookie_name)
    header = request.headers.get(settings.csrf_header_name)
    if not cookie or not header or not tokens_equal(cookie, header):
        raise Forbidden("Missing or invalid CSRF token")


def current_user(request: Request, auth: Auth, settings: AppSettings) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    user = auth.resolve(token) if token else None
    if user is None:
        raise Unauthorized("Authentication required")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def optional_user(request: Request, auth: Auth, settings: AppSettings) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    return auth.resolve(token) if token else None


OptionalUser = Annotated[User | None, Depends(optional_user)]
