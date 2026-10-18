"""
The Nominatim proxy. Defect 10.

Four screens in the app were calling `nominatim.openstreetmap.org` directly, from the
device, with React Native's default `User-Agent`. Three things wrong with that, in
increasing order of how much they cost:

1. **It violates Nominatim's usage policy**, which requires a genuine identifying
   User-Agent and no more than one request per second. Being blocked is not a hypothetical
   — it is the documented consequence, and it would arrive without warning.
2. **No caching.** The reverse-geocode on `AddReportScreen` fires on every map drag, so
   one person picking a location could issue dozens of identical requests.
3. **Every device is a separate offender.** Rate limits are per-IP, so the policy budget
   is spent independently by each phone, and nothing on the server can see it happening.

Routing it through here fixes all three at once: one `User-Agent` we own, one Redis cache
shared by every client, and one place to see the traffic.

---

## Why this is not in `app/geo/agent.py`

`agent.py` answers *"where is this place in Dhaka, and do we trust the answer?"* — a
gazetteer first, an LLM second, a refusal third, with the discard invariant on top. This
answers *"what does OpenStreetMap say about this string?"* and has no opinion about
whether the answer is good enough to draw a pin for.

Keeping them apart matters because of D03's hard-won lesson: the LLM tier was overturning
the gazetteer's deliberate ambiguity refusals. A geocoder that answers *everything* must
not be able to leak into the path that is allowed to say no. `method="nominatim"` exists in
the `GeoResolution` contract and is **not** produced by `resolve_place`; it is produced
here, for the search and reverse-geocode features that genuinely want a general geocoder.

## Caching, and what the TTL means

24 hours, keyed on the normalised query. Place names do not move. The cache is the thing
that makes the politeness guarantee achievable rather than aspirational — without it, one
screen's drag handler can exceed one request per second by itself.

A Redis failure is **not** an error: the request goes to Nominatim and the answer is simply
not cached. A geocoder that stops working because a cache is down would be a worse outage
than the one it was protecting against.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Final

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

__all__ = ["NominatimUnavailable", "reverse", "search"]

_TIMEOUT_SECONDS: Final[float] = 6.0
_CACHE_PREFIX: Final[str] = "nominatim:v1:"
_MAX_RESULTS: Final[int] = 5

_REVERSE_PRECISION: Final[int] = 4

_COUNTRY_CODES: Final[str] = "bd"
"""
Bangladesh only, on every forward geocode.

Without it `search` is a world query. Typing *Rampura* offered **Rampura, India**
above Rampura in Dhaka, because the Indian one is the larger place and Nominatim
ranks by prominence when nothing says otherwise. The same thing put *Seoul* in the
destination box, recorded in `features/search/suggest.ts`.

This is not a display preference. The route box feeds a destination straight into
`/routes/calculate`, which scores a path against the Dhaka risk surface; a
destination in another country produces a route with no flags on it for the wrong
reason entirely. The app is a Bangladesh product and there is no case where a
destination outside the country is the answer, so the restriction is on the request
rather than on the ranking.
"""

_DHAKA_VIEWBOX: Final[str] = "90.30,23.66,90.52,23.92"
"""
`lon_min,lat_min,lon_max,lat_max` around greater Dhaka, used **unbounded**.

With `bounded=0` this is a preference, not a filter: Nominatim boosts results
inside the box and still returns Chattogram or Sylhet when that is what was asked
for. Bounded would have been wrong -- a user travelling outside Dhaka is a real
case, and silently returning nothing for Cox's Bazar is a worse failure than
ranking it second.

Covers roughly Tongi and Uttara in the north to Jatrabari and Keraniganj in the
south, which is the area the risk surface has flags for.
"""
"""
Decimal places a reverse-geocode coordinate is rounded to for the cache key.

Four places is about 11 m at Dhaka's latitude — finer than any street address Nominatim
will return, and coarse enough that a map drag producing hundreds of near-identical
coordinates collapses onto a handful of cache keys. Without this the cache would miss on
almost every request and defect 10 would be only half fixed.
"""


class NominatimUnavailable(RuntimeError):
    """Nominatim did not answer. The caller decides whether that is fatal."""


async def _cached(key: str) -> Any | None:
    """A cached payload, or None. Never raises — a cache miss and a dead cache are the same."""
    try:
        from app.core.redis import redis_client

        raw = await redis_client.get(_CACHE_PREFIX + key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.debug("nominatim cache read skipped (%s: %s)", type(exc).__name__, exc)
        return None


async def _store(key: str, payload: Any) -> None:
    try:
        from app.core.redis import redis_client

        await redis_client.setex(
            _CACHE_PREFIX + key,
            settings.NOMINATIM_CACHE_TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False),
        )
    except Exception as exc:
        logger.debug("nominatim cache write skipped (%s: %s)", type(exc).__name__, exc)


async def _get(path: str, params: dict[str, Any], cache_key: str) -> Any:
    cached = await _cached(cache_key)
    if cached is not None:
        return cached

    url = f"{settings.NOMINATIM_BASE_URL.rstrip('/')}/{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(
                url,
                params={**params, "format": "json"},
                headers={
                    # The policy requirement, and the whole point of the proxy. A real
                    # contact address means a problem reaches us as an email rather than
                    # as a block.
                    "User-Agent": settings.NOMINATIM_USER_AGENT,
                    "Accept-Language": "en,bn",
                },
            )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise NominatimUnavailable(f"{type(exc).__name__}: {exc}") from exc

    await _store(cache_key, payload)
    return payload


async def search(query: str) -> list[dict[str, Any]]:
    """
    Forward geocode: a string to candidate places.

    Returns Nominatim's own shape, trimmed to the fields the app uses. Deliberately not
    converted to `GeoResolution`: that contract carries a `method` and a `confidence` which
    imply a judgement this function does not make. The caller decides what a result is
    worth.
    """
    normalised = " ".join(query.split()).lower()
    if not normalised:
        return []

    payload = await _get(
        "search",
        {
            "q": normalised,
            "limit": _MAX_RESULTS,
            "addressdetails": 1,
            "countrycodes": _COUNTRY_CODES,
            "viewbox": _DHAKA_VIEWBOX,
            # Prefer Dhaka, do not require it. See `_DHAKA_VIEWBOX`.
            "bounded": 0,
        },
        # The cache key carries the bias, so entries written before it existed are
        # not served back. They hold world results for a Bangladesh query and
        # would outlive this change by `NOMINATIM_CACHE_TTL_SECONDS` otherwise.
        f"search:bd:{normalised}",
    )
    if not isinstance(payload, list):
        return []
    return [
        {
            "display_name": item.get("display_name"),
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
            "type": item.get("type"),
        }
        for item in payload
        if item.get("lat") and item.get("lon")
    ]


async def reverse(lat: float, lon: float) -> dict[str, Any] | None:
    """Reverse geocode: a coordinate to an address, or None if Nominatim has no name for it."""
    key = f"reverse:{round(lat, _REVERSE_PRECISION)},{round(lon, _REVERSE_PRECISION)}"
    payload = await _get("reverse", {"lat": lat, "lon": lon, "zoom": 18}, key)
    if not isinstance(payload, dict) or not payload.get("display_name"):
        return None
    return {
        "display_name": payload["display_name"],
        "address": payload.get("address", {}),
    }
