"""Notification delivery. In-app notifications are the database rows themselves; email is a
channel with explicit, honest delivery records.

Delivery status semantics (never overstated):
  queued     attempt recorded, transport not yet called
  sent       the SMTP server accepted the message — *not* proof it reached the inbox
  failed     the transport raised; `error` says why
  simulated  console backend (development): the email was only written to the log
"""

import logging
import smtplib
import ssl
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.metrics import NOTIFICATION_DELIVERIES
from app.models import DeliveryAttempt, Notification, User
from app.models.base import utcnow

log = logging.getLogger(__name__)


class EmailError(Exception):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class Email:
    to: str
    subject: str
    text: str


class EmailBackend(Protocol):
    name: str
    delivered_status: str  # status recorded when send() returns normally

    def send(self, email: Email) -> None: ...


class ConsoleEmailBackend:
    name = "console"
    delivered_status = "simulated"

    def send(self, email: Email) -> None:
        # Log subject + body only; the recipient address is personal data and isn't needed here.
        log.info(
            "email (console backend, not sent)",
            extra={"subject": email.subject, "body": email.text},
        )


class SmtpEmailBackend:
    name = "smtp"
    delivered_status = "sent"

    def __init__(self, s: Settings) -> None:
        if not s.smtp_host:
            raise ValueError("SMTP_HOST is required for the smtp email backend")
        self.s = s

    def send(self, email: Email) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.s.smtp_from, email.to, email.subject
        msg.set_content(email.text)
        try:
            with smtplib.SMTP(
                self.s.smtp_host or "", self.s.smtp_port, timeout=self.s.smtp_timeout_s
            ) as smtp:
                if self.s.smtp_starttls:
                    smtp.starttls(context=ssl.create_default_context())
                if self.s.smtp_username and self.s.smtp_password:
                    smtp.login(self.s.smtp_username, self.s.smtp_password.get_secret_value())
                smtp.send_message(msg)
        except smtplib.SMTPRecipientsRefused as exc:
            raise EmailError("recipient refused", retryable=False) from exc
        except smtplib.SMTPAuthenticationError as exc:
            raise EmailError("SMTP authentication failed", retryable=False) from exc
        except (smtplib.SMTPException, OSError) as exc:  # timeouts, connection errors, 4xx
            raise EmailError(f"{type(exc).__name__}: {exc}", retryable=True) from exc


def email_backend(s: Settings) -> EmailBackend:
    return SmtpEmailBackend(s) if s.email_backend == "smtp" else ConsoleEmailBackend()


ACCOUNT_KINDS = frozenset({"welcome", "sign_in"})


def create_account_notification(
    db: Session, user: User, kind: str, user_agent: str | None
) -> uuid.UUID:
    """Account emails (welcome / new sign-in) are recorded like alerts so delivery is tracked the
    same honest way. Sign-in notices are created already read so they don't light up the bell."""
    now = utcnow()
    if kind == "welcome":
        title = "Welcome to SkyScout"
        body = (
            f"Hi {user.display_name or 'there'}, your SkyScout account is ready.\n\n"
            "Search a trip, choose 'Monitor this trip' and set a target price: we'll email you the "
            "first time a flight meeting your requirements reaches it."
        )
    else:
        device = (user_agent or "unknown device")[:120]
        title = "New sign-in to your SkyScout account"
        body = (
            f"Your account was signed in at {now:%d %b %Y %H:%M} UTC from: {device}.\n\n"
            "If this wasn't you, change your password straight away."
        )
    n = Notification(
        user_id=user.id,
        rule_id=None,
        kind=kind,
        dedup_key=f"{kind}:{uuid.uuid4().hex}",
        title=title,
        body=body,
        data={"email": True},
        created_at=now,
        read_at=now if kind == "sign_in" else None,
    )
    db.add(n)
    db.commit()
    return n.id


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    status: str  # sent | simulated | failed | skipped
    retry: bool = False


def deliver_email(
    db: Session, notification_id: uuid.UUID, backend: EmailBackend, settings: Settings
) -> DeliveryResult:
    """One delivery attempt. Idempotent: if an earlier attempt succeeded, nothing is sent again."""
    n = db.get(Notification, notification_id)
    if n is None or (n.data or {}).get("email") is False:  # in-app only by design
        return DeliveryResult("skipped")
    user = db.get(User, n.user_id)
    if user is None or not user.is_active or not user.preferences.email_notifications:
        return DeliveryResult("skipped")
    done = db.scalar(
        select(DeliveryAttempt.id).where(
            DeliveryAttempt.notification_id == n.id,
            DeliveryAttempt.channel == "email",
            DeliveryAttempt.status.in_(("sent", "simulated")),
        )
    )
    if done is not None:
        return DeliveryResult("skipped")

    attempt_no = (
        db.scalar(
            select(func.max(DeliveryAttempt.attempt)).where(
                DeliveryAttempt.notification_id == n.id, DeliveryAttempt.channel == "email"
            )
        )
        or 0
    ) + 1
    attempt = DeliveryAttempt(
        notification_id=n.id,
        channel="email",
        attempt=attempt_no,
        status="queued",
        backend=backend.name,
    )
    db.add(attempt)
    db.commit()  # the "queued" record exists before we touch the network

    if n.kind in ACCOUNT_KINDS:
        email = Email(
            to=user.email,
            subject=f"SkyScout: {n.title}",
            text=f"{n.body}\n\nYour account: {settings.app_base_url}/account\n"
            "You can turn off SkyScout emails in your account settings.",
        )
    else:
        link = f"{settings.app_base_url}/monitors"
        if n.rule_id:
            link = f"{settings.app_base_url}/monitors/{n.rule_id}"
        email = Email(
            to=user.email,
            subject=f"SkyScout: {n.title}",
            text=f"{n.body}\n\nOpen in SkyScout: {link}\n\n"
            "Prices are search results, not guaranteed checkout prices.\n"
            "Change alert settings at " + f"{settings.app_base_url}/account",
        )
    try:
        backend.send(email)
    except EmailError as exc:
        attempt.status, attempt.error, attempt.finished_at = "failed", str(exc)[:1000], utcnow()
        db.commit()
        NOTIFICATION_DELIVERIES.labels("email", "failed").inc()
        retry = exc.retryable and attempt_no < settings.email_max_attempts
        return DeliveryResult("failed", retry=retry)
    attempt.status, attempt.finished_at = backend.delivered_status, utcnow()
    db.commit()
    NOTIFICATION_DELIVERIES.labels("email", backend.delivered_status).inc()
    return DeliveryResult(backend.delivered_status)
