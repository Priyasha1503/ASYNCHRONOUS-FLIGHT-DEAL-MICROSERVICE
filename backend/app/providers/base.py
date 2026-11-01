"""Flight provider interface. Business logic depends only on this — never on a concrete provider.

Adding a provider: implement `FlightProvider` in `app/providers/<name>/`, map its responses to
`app.domain.offers.Offer`, raise the errors from `app.providers.errors`, and register a factory in
`app/providers/registry.py`. Contract tests run every registered provider through the same checks.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.domain.offers import FareSource, Offer
from app.domain.query import CabinClass, UpstreamQuery
from app.providers.errors import ProviderUnsupportedQuery


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    source: FareSource  # how this provider's prices must be labelled
    bookable: bool  # do offers link to a checkout that can honour the price?
    # How a user books: "redirect" = hand off to the airline/agency site (affiliate link),
    # "checkout" = in-app booking, "none" = not bookable (e.g. demo data).
    booking: Literal["checkout", "redirect", "none"] = "none"
    cache_ttl_s: int | None = None  # overrides SEARCH_CACHE_TTL_S for this provider
    round_trip: bool = True
    cabins: frozenset[CabinClass] = frozenset(CabinClass)
    currencies: frozenset[str] = frozenset({"USD"})
    max_passengers: int = 9
    requests_per_minute: int | None = None  # provider quota, enforced by the search service


@dataclass(slots=True)
class ProviderResult:
    provider: str
    offers: list[Offer]
    fetched_at: datetime
    latency_ms: int
    # Raw offers the adapter couldn't map into the domain model (schema-level), with reasons.
    unmappable: list[str] = field(default_factory=list)


class FlightProvider(ABC):
    name: str  # stable id, e.g. "demo", "duffel"
    display_name: str
    capabilities: ProviderCapabilities

    def check_supported(self, query: UpstreamQuery) -> None:
        caps = self.capabilities
        if query.return_date and not caps.round_trip:
            raise ProviderUnsupportedQuery(self.name, "round trips not supported")
        if query.cabin not in caps.cabins:
            raise ProviderUnsupportedQuery(self.name, f"cabin {query.cabin} not supported")
        if query.currency not in caps.currencies:
            raise ProviderUnsupportedQuery(self.name, f"currency {query.currency} not supported")
        if query.passengers.total > caps.max_passengers:
            raise ProviderUnsupportedQuery(self.name, "too many passengers")

    @abstractmethod
    def search(self, query: UpstreamQuery) -> ProviderResult:
        """Blocking search. Must enforce its own request timeout and raise ProviderError subclasses
        (never raw transport exceptions)."""
