"""Money helpers. Amounts are always `Decimal` with an explicit ISO-4217 currency — never floats."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated

from pydantic import AfterValidator, PlainSerializer

# Currencies the product supports for search/display. Providers may support fewer.
SUPPORTED_CURRENCIES: frozenset[str] = frozenset(
    {"USD", "EUR", "GBP", "INR", "AUD", "CAD", "SGD", "AED", "JPY", "CHF"}
)
# ISO-4217 minor units for the supported set (JPY has none).
MINOR_UNITS: dict[str, int] = {c: 2 for c in SUPPORTED_CURRENCIES} | {"JPY": 0}

CENT = Decimal("0.01")


def quantize(amount: Decimal, currency: str) -> Decimal:
    exp = Decimal(1).scaleb(-MINOR_UNITS.get(currency, 2))
    return amount.quantize(exp, rounding=ROUND_HALF_UP)


def to_decimal(value: object) -> Decimal:
    """Parse a provider amount (str/int/Decimal; floats are rejected as lossy)."""
    if isinstance(value, float):
        raise ValueError("float amounts are not accepted; pass a string")
    try:
        d = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount: {value!r}") from exc
    if not d.is_finite():
        raise ValueError(f"non-finite amount: {value!r}")
    return d


def _check_currency(code: str) -> str:
    code = code.strip().upper()
    if code not in SUPPORTED_CURRENCIES:
        raise ValueError(f"unsupported currency {code!r}")
    return code


Currency = Annotated[str, AfterValidator(_check_currency)]

# Serialized as a string in JSON so no client ever round-trips money through a float.
Amount = Annotated[Decimal, PlainSerializer(lambda d: str(d), return_type=str, when_used="json")]
