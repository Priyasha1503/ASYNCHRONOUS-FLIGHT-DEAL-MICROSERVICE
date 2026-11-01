import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, StringConstraints


def _upper(v: object) -> object:
    return v.strip().upper() if isinstance(v, str) else v


# Upper-case *before* the pattern check so "eur"/"lhr" are accepted and normalized.
Iata = Annotated[str, BeforeValidator(_upper), StringConstraints(pattern=r"^[A-Z]{3}$")]
Currency = Annotated[str, BeforeValidator(_upper), StringConstraints(pattern=r"^[A-Z]{3}$")]
Password = Annotated[str, StringConstraints(min_length=10, max_length=128)]


class RegisterIn(BaseModel):
    email: EmailStr
    password: Password
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = (
        None
    )


class LoginIn(BaseModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class DeleteAccountIn(BaseModel):
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class PreferencesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency: str
    home_airport: str | None
    timezone: str
    email_notifications: bool
    inapp_notifications: bool


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: Currency | None = None
    home_airport: Iata | None = None
    timezone: Annotated[str, StringConstraints(min_length=1, max_length=64)] | None = None
    email_notifications: bool | None = None
    inapp_notifications: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    created_at: datetime
    preferences: PreferencesOut


class SessionOut(BaseModel):
    user: UserOut | None = Field(description="null when the caller is not signed in")


class CsrfOut(BaseModel):
    csrf_token: str = Field(description="Echo this in the X-CSRF-Token header on unsafe requests")
