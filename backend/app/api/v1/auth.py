import logging
from zoneinfo import available_timezones

from fastapi import APIRouter, Request, Response, status

from app.api.deps import AppSettings, Auth, CurrentUser, DbSession, Limiter
from app.api.v1.schemas.auth import (
    CsrfOut,
    DeleteAccountIn,
    LoginIn,
    PreferencesUpdate,
    RegisterIn,
    SessionOut,
    UserOut,
)
from app.core.config import Settings
from app.core.errors import AppError, Unauthorized
from app.core.security import new_token, verify_password
from app.services.auth import AuthService, IssuedSession
from app.services.notifications import create_account_notification

router = APIRouter(tags=["auth"])
log = logging.getLogger(__name__)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_csrf(response: Response, settings: Settings) -> str:
    token = new_token()
    response.set_cookie(
        settings.csrf_cookie_name,
        token,
        httponly=False,  # must be readable by the frontend to echo in the header
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return token


def _set_session(response: Response, settings: Settings, issued: IssuedSession) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        issued.token,
        max_age=issued.max_age_s,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    _set_csrf(response, settings)  # rotate CSRF token on privilege change


def _queue_account_email(
    auth: AuthService, issued: IssuedSession, kind: str, user_agent: str | None
) -> None:
    """Welcome / new-sign-in email. Never blocks or fails sign-in if email or the queue is down."""
    try:
        nid = create_account_notification(auth.db, issued.user, kind, user_agent)
        from app.workers.tasks import send_notification_email  # Celery only when needed

        send_notification_email.delay(str(nid))
    except Exception:
        auth.db.rollback()
        log.warning("could not queue account email", extra={"kind": kind})


@router.get("/auth/csrf", response_model=CsrfOut)
def csrf(response: Response, settings: AppSettings) -> CsrfOut:
    return CsrfOut(csrf_token=_set_csrf(response, settings))


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterIn,
    request: Request,
    response: Response,
    auth: Auth,
    settings: AppSettings,
    limiter: Limiter,
) -> UserOut:
    limiter.hit(f"register:{_client_ip(request)}", settings.auth_rate_limit_per_minute)
    issued = auth.register(
        body.email, body.password, body.display_name or None, request.headers.get("user-agent")
    )
    _set_session(response, settings, issued)
    out = UserOut.model_validate(issued.user)
    _queue_account_email(auth, issued, "welcome", request.headers.get("user-agent"))
    return out


@router.post("/auth/login", response_model=UserOut)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    auth: Auth,
    settings: AppSettings,
    limiter: Limiter,
) -> UserOut:
    limiter.hit(f"login:{_client_ip(request)}", settings.auth_rate_limit_per_minute)
    limiter.hit(f"login-email:{body.email.lower()}", settings.auth_rate_limit_per_minute)
    issued = auth.login(body.email, body.password, request.headers.get("user-agent"))
    _set_session(response, settings, issued)
    out = UserOut.model_validate(issued.user)
    _queue_account_email(auth, issued, "sign_in", request.headers.get("user-agent"))
    return out


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, auth: Auth, settings: AppSettings) -> Response:
    if token := request.cookies.get(settings.session_cookie_name):
        auth.logout(token)
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response


@router.get("/auth/session", response_model=SessionOut)
def session(request: Request, auth: Auth, settings: AppSettings) -> SessionOut:
    """Who am I, without treating "signed out" as an error (the UI probes this on every page)."""
    token = request.cookies.get(settings.session_cookie_name)
    user = auth.resolve(token) if token else None
    return SessionOut(user=UserOut.model_validate(user) if user else None)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me/preferences", response_model=UserOut)
def update_preferences(body: PreferencesUpdate, user: CurrentUser, db: DbSession) -> UserOut:
    changes = body.model_dump(exclude_unset=True)
    if "timezone" in changes and changes["timezone"] not in available_timezones():
        raise AppError("Unknown timezone", details={"field": "timezone"})
    for field in ("currency", "timezone", "email_notifications", "inapp_notifications"):
        if field in changes and changes[field] is None:
            raise AppError(f"{field} cannot be null", details={"field": field})
    for key, value in changes.items():
        setattr(user.preferences, key, value)
    db.commit()
    return UserOut.model_validate(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    body: DeleteAccountIn,
    user: CurrentUser,
    auth: Auth,
    response: Response,
    settings: AppSettings,
) -> Response:
    if not verify_password(user.password_hash, body.password):
        raise Unauthorized("Password confirmation failed")
    auth.delete_account(user)
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response
