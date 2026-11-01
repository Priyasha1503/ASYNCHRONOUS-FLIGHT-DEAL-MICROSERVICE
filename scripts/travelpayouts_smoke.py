"""Live check of the Travelpayouts integration — run once your token and marker are in .env.

    uv run --project backend python scripts/travelpayouts_smoke.py LHR JFK 2026-12-10 2026-12-17

It (1) calls the real API through the adapter, (2) prints what was mapped and what wasn't,
(3) shows one booking link so you can confirm in a browser that it opens Aviasales with your
marker, and (4) saves the raw response to backend/tests/fixtures/travelpayouts_recorded.json so the
contract-test fixture can be replaced with ground truth. The token is never printed or saved.
"""

import json
import sys
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.domain.query import UpstreamQuery  # noqa: E402
from app.providers.errors import ProviderError  # noqa: E402
from app.providers.travelpayouts import PATH, TravelpayoutsProvider  # noqa: E402


def main(origin: str, destination: str, depart: str, ret: str | None) -> int:
    s = get_settings()
    if not (s.travelpayouts_token and s.travelpayouts_marker):
        print("Set TRAVELPAYOUTS_TOKEN and TRAVELPAYOUTS_MARKER in .env first.")
        return 2
    query = UpstreamQuery(
        origin=origin,
        destination=destination,
        depart_date=date.fromisoformat(depart),
        return_date=date.fromisoformat(ret) if ret else None,
    )
    raw: dict[str, object] = {}

    def recording(request: httpx.Request) -> httpx.Response:
        with httpx.Client(timeout=15) as c:
            resp = c.send(request)
        raw["status"] = resp.status_code
        raw["rate_limit_remaining"] = resp.headers.get("X-Rate-Limit-Remaining")
        raw["body"] = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:500]
        return httpx.Response(resp.status_code, content=resp.content, headers=resp.headers)

    p = TravelpayoutsProvider(
        token=s.travelpayouts_token.get_secret_value(),
        marker=s.travelpayouts_marker,
        base_url=s.travelpayouts_base_url,
        link_host=s.travelpayouts_link_host,
        transport=httpx.MockTransport(recording),
    )
    try:
        result = p.search(query)
    except ProviderError as exc:
        print(f"FAILED: {exc.code}: {exc}  (HTTP {raw.get('status')})")
        return 1
    finally:
        if raw:
            out = ROOT / "backend" / "tests" / "fixtures" / "travelpayouts_recorded.json"
            out.write_text(json.dumps({"_recorded_from": PATH, "_query": query.model_dump(mode="json"), **raw}, indent=2))
            print(f"raw response saved to {out.relative_to(ROOT)}")

    print(f"HTTP {raw.get('status')} · {len(result.offers)} offers mapped · {len(result.unmappable)} unmappable "
          f"· rate-limit remaining {raw.get('rate_limit_remaining')}")
    for line in result.unmappable[:5]:
        print("  unmappable:", line)
    for o in sorted(result.offers, key=lambda o: o.total_amount)[:5]:
        s0 = o.slices[0]
        print(f"  {o.total_amount} {o.currency}  {s0.origin}->{s0.destination} {s0.departure_at:%d %b %H:%M} "
              f"{s0.stops} stop(s)  {','.join(sorted(o.carriers))}")
    if result.offers:
        print("\nOpen this in a browser and confirm it lands on Aviasales with your marker:")
        print(" ", result.offers[0].booking_url)
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) not in (3, 4):
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(*args[:3], args[3] if len(args) == 4 else None))
