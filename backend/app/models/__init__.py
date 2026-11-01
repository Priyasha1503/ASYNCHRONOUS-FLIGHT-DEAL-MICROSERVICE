"""Import every model here so Alembic autogenerate and metadata see them."""

from app.models.base import Base
from app.models.monitoring import (
    DeliveryAttempt,
    JobFailure,
    MonitoredQuery,
    MonitoringRule,
    Notification,
    PriceObservation,
    RefreshRun,
    RuleCheck,
    SavedSearch,
)
from app.models.user import User, UserPreferences, UserSession

__all__ = [
    "Base",
    "DeliveryAttempt",
    "JobFailure",
    "MonitoredQuery",
    "MonitoringRule",
    "Notification",
    "PriceObservation",
    "RefreshRun",
    "RuleCheck",
    "SavedSearch",
    "User",
    "UserPreferences",
    "UserSession",
]
