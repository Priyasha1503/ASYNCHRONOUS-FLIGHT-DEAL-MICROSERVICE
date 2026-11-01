"""Developer CLI: run a search through the full domain pipeline without the API.

uv run python -m app.cli search LHR JFK 2026-12-10 --return 2026-12-17 --budget 900 --max-stops 1
"""

import argparse
from datetime import UTC, date, datetime
from decimal import Decimal

from app.core.config import get_settings
from app.domain.offers import Offer
from app.domain.pipeline import evaluate
from app.domain.query import CabinClass, Passengers, Preferences, UpstreamQuery
from app.domain.ranking import Pick, fmt_minutes, fmt_money
from app.providers.errors import ProviderError
from app.providers.registry import build_providers


def _describe(o: Offer) -> str:
    parts = []
    for s in o.slices:
        route = " → ".join([s.origin] + [seg.destination for seg in s.segments])
        dep = s.departure_at.strftime("%a %d %b %H:%M")
        arr = s.arrival_at.strftime("%H:%M")
        stops = "nonstop" if s.stops == 0 else f"{s.stops} stop{'s' if s.stops > 1 else ''}"
        carriers = ", ".join(sorted({seg.carrier_name for seg in s.segments}))
        parts.append(
            f"{route}  {dep} → {arr}  {fmt_minutes(s.duration_minutes)}, {stops}  [{carriers}]"
        )
    bags = o.baggage.checked_bags
    bag = "bag: unconfirmed" if bags is None else f"checked bags: {bags}"
    head = f"{fmt_money(o.total_amount, o.currency)}  ·  {o.fare_brand or 'fare'}  ·  {bag}"
    return head + "\n      " + "\n      ".join(parts)


def _pick(title: str, p: Pick | None) -> None:
    if p is None:
        return
    print(f"\n■ {title}  (score {p.scored.score:g})")
    print("    " + _describe(p.scored.offer))
    for r in p.reasons:
        print(f"    • {r}")


def search(args: argparse.Namespace) -> int:
    query = UpstreamQuery(
        origin=args.origin,
        destination=args.destination,
        depart_date=date.fromisoformat(args.depart),
        return_date=date.fromisoformat(args.ret) if args.ret else None,
        passengers=Passengers(adults=args.adults, children=args.children),
        cabin=CabinClass(args.cabin),
        currency=args.currency,
    )
    query.check_dates(datetime.now(UTC).date())
    prefs = Preferences(
        max_price=Decimal(args.budget) if args.budget else None,
        max_stops=args.max_stops,
        require_checked_bag=args.bag,
    )

    offers: list[Offer] = []
    for provider in build_providers(get_settings()):
        try:
            result = provider.search(query)
        except ProviderError as exc:
            print(f"! {provider.name}: {exc.code} — {exc}")
            continue
        label = provider.capabilities.source.value.upper()
        print(f"✓ {provider.display_name}: {len(result.offers)} offers [{label}]")
        offers += result.offers

    out = evaluate(query, prefs, offers, include_nearby=args.nearby)
    if any(o.source.value == "demo" for o in offers):
        print("\n*** DEMO DATA — synthetic fares from fictional airlines, not real prices ***")
    print(
        f"\n{out.received} received · {len(out.dropped)} invalid · "
        f"{out.constraints.qualifying} of {out.constraints.total} meet your requirements"
    )

    recs = out.recommendations
    if not out.has_results:
        print("\nNo offers meet all your requirements.")
        for c, n in out.constraints.failed_by.items():
            print(f"  • {c.value}: excluded {n}")
        for r in out.constraints.relaxations:
            extra = f" (needs {r.needed_value})" if r.needed_value is not None else ""
            print(f"  → relaxing {r.constraint.value} alone would add {r.unlocks} offer(s){extra}")
        return 1

    _pick("CHEAPEST QUALIFYING", recs.cheapest)
    _pick("BEST OVERALL MATCH", recs.best_match)
    for alt in recs.alternatives:
        _pick(f"ALTERNATIVE · {alt.kind.value.replace('_', ' ')}", alt)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("search", help="search flights and print recommendations")
    s.add_argument("origin")
    s.add_argument("destination")
    s.add_argument("depart", help="YYYY-MM-DD")
    s.add_argument("--return", dest="ret", help="YYYY-MM-DD")
    s.add_argument("--adults", type=int, default=1)
    s.add_argument("--children", type=int, default=0)
    s.add_argument("--cabin", default="economy", choices=[c.value for c in CabinClass])
    s.add_argument("--currency", default="USD")
    s.add_argument("--budget")
    s.add_argument("--max-stops", type=int)
    s.add_argument("--bag", action="store_true", help="require a confirmed checked bag")
    s.add_argument("--nearby", action="store_true", help="include nearby airports")
    args = parser.parse_args()
    return search(args)


if __name__ == "__main__":
    raise SystemExit(main())
