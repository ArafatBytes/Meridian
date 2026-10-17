#!/usr/bin/env python3
"""
Write the recommended route's own geometry as a GPX track, for mock location.

    python backend/scripts/export_route_track.py
    python backend/scripts/export_route_track.py --pair "Motijheel -> Kalabagan"
    python backend/scripts/export_route_track.py --speed-kmh 30 --out track.gpx

Segment 4 films a journey that has to arrive. Walking it is not an option -- the
Gulshan 2 to Rampura route is 23 minutes by car -- and `ARRIVAL_M` is 30 m, so the
dot has to get genuinely close to the destination before navigation ends by itself.
Mock location solves it indoors, and the app does nothing to resist: there is no
`isFromMockProvider` check anywhere in the codebase, so an injected fix is treated
exactly like a real one.

**The track is the route the app itself recommends**, fetched live from
`/routes/calculate` rather than drawn by hand. That matters for the shot: the blue
line and the moving dot come from the same geometry, so the dot stays on the line
through every turn instead of cutting corners and snapping back.

Timestamps
----------
Each point gets a `<time>`, spaced from the distance to the previous point at
`--speed-kmh`. Most mock-location apps will replay a track at their own rate and
ignore these; the ones that honour them need them monotonic and plausible, and a
track with no times at all is rejected by some. 25 km/h is roughly what OSRM's
driving profile means in central Dhaka once `OSRM_DRIVING_FACTOR` is applied.

Loading it on the phone
-----------------------
1. Settings -> About phone -> tap Build number seven times (developer options).
2. Settings -> System -> Developer options -> **Select mock location app** ->
   whichever GPX player you installed.
3. Copy the GPX to the phone and open it in that app.
4. Start playback, then start the journey in Meridian. Playback first: the journey
   takes its start point from wherever the device says it is.

Any player that reads GPX works. The file is ordinary `<trkpt>` with `<time>`, no
extensions.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final
from xml.sax.saxutils import escape

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass

BACKEND_DIR: Final = Path(__file__).resolve().parent.parent

API: Final = "http://localhost:8000/api/v1/routes/calculate"

# The same landmarks `verify_video_scenario.py` checks, so the two scripts cannot
# disagree about where a pair is. Keyed by the label the verifier prints, which is
# what you will have just read when you come here.
PAIRS: Final[dict[str, tuple[tuple[float, float], tuple[float, float]]]] = {
    "Gulshan 2 -> Rampura": ((23.7925, 90.4145), (23.7620, 90.4190)),
    "Rampura -> Gulshan 2": ((23.7620, 90.4190), (23.7925, 90.4145)),
    "Motijheel -> Kalabagan": ((23.7330, 90.4170), (23.7420, 90.3840)),
    "Dhanmondi 27 -> Motijheel": ((23.7465, 90.3830), (23.7330, 90.4170)),
    # ---- the pairs to film with -------------------------------------------
    #
    # The four above are the verifier's landmark centroids, typed by hand. The
    # app never uses them: a person types "Rampura", taps the first suggestion,
    # and the screen binds whatever `/geo/search` returned. Those are different
    # points -- Rampura by 17 m, Gulshan 2 by 25 m -- and that is enough to
    # change which OSRM alternatives come back. On 17 Oct the hand-typed pair
    # produced three routes at 5.1 km and the geocoded pair produced two at
    # 5.5 km.
    #
    # For segment 4 that gap is the whole problem: the GPX has to be the line
    # the app actually drew, or the dot walks beside the blue route instead of
    # along it. So these entries hold the geocoder's own answer, and they are
    # what the filming track is exported from.
    "Rampura -> Gulshan 2 (geocoded)": (
        (23.7626126, 90.4205675),
        (23.7947191, 90.4136986),
    ),
    "Gulshan 2 -> Rampura (geocoded)": (
        (23.7947191, 90.4136986),
        (23.7626126, 90.4205675),
    ),
}

DEFAULT_PAIR: Final = "Rampura -> Gulshan 2 (geocoded)"
DEFAULT_SPEED_KMH: Final = 25.0


def metres_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Haversine, in metres. Good to a fraction of a percent at city scale."""
    radius = 6_371_000.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def fetch_recommended(
    src: tuple[float, float], dst: tuple[float, float]
) -> dict[str, Any]:
    """
    The first route the API returns, which is the recommended one.

    Deliberately the same request shape as `verify_video_scenario.py`, so that the
    track exported here is the route that script just said was clean. Taking any
    other element would film a journey along a corridor the app did not recommend.
    """
    body = json.dumps(
        {
            "source": {"latitude": src[0], "longitude": src[1]},
            "destination": {"latitude": dst[0], "longitude": dst[1]},
            "profile": "driving",
        }
    ).encode()
    request = urllib.request.Request(
        API, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        routes = json.load(response)
    if not routes:
        raise SystemExit("  the API returned no routes")
    return routes[0]


def gpx(points: list[tuple[float, float]], *, name: str, speed_kmh: float) -> str:
    start = datetime.now(UTC)
    metres_per_second = speed_kmh * 1000 / 3600

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Meridian export_route_track.py" '
        'xmlns="http://www.topografix.com/GPX/1/1">',
        "  <trk>",
        f"    <name>{escape(name)}</name>",
        "    <trkseg>",
    ]

    elapsed = 0.0
    for index, (lat, lon) in enumerate(points):
        if index:
            elapsed += metres_between(points[index - 1], (lat, lon)) / metres_per_second
        stamp = (start + timedelta(seconds=elapsed)).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines.append(f'      <trkpt lat="{lat:.6f}" lon="{lon:.6f}">')
        lines.append(f"        <time>{stamp}</time>")
        lines.append("      </trkpt>")

    lines += ["    </trkseg>", "  </trk>", "</gpx>", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a route as a GPX track.")
    parser.add_argument(
        "--pair",
        default=DEFAULT_PAIR,
        choices=sorted(PAIRS),
        help=f"which pair to export (default: {DEFAULT_PAIR!r})",
    )
    parser.add_argument(
        "--speed-kmh",
        type=float,
        default=DEFAULT_SPEED_KMH,
        help=(
            f"playback speed used to space the timestamps (default {DEFAULT_SPEED_KMH}). "
            "Raise it to shorten the wait on camera, but keep the journey longer than "
            "the check-in ladder or the dot arrives before the escalation finishes."
        ),
    )
    parser.add_argument("--out", metavar="PATH", help="where to write (default: data/video/)")
    args = parser.parse_args()

    src, dst = PAIRS[args.pair]
    try:
        route = fetch_recommended(src, dst)
    except (urllib.error.URLError, TimeoutError) as problem:
        print(f"\n  cannot reach the API -- {problem}")
        print("  start the backend first; this reads the route it recommends.\n")
        return 2

    # `path`, not `segments`. The response field is `path` and reaching for the
    # wrong name returns an empty track that looks like a routing failure.
    path = [(float(p["latitude"]), float(p["longitude"])) for p in route.get("path") or []]
    if len(path) < 2:
        print("\n  the recommended route came back with no geometry\n")
        return 2

    flags = route.get("flags") or []
    total_m = sum(metres_between(path[i - 1], path[i]) for i in range(1, len(path)))
    minutes = total_m / (args.speed_kmh * 1000 / 60)

    out = Path(args.out) if args.out else BACKEND_DIR / "data" / "video" / (
        args.pair.replace(" -> ", "-to-").replace(" ", "") + ".gpx"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(gpx(path, name=args.pair, speed_kmh=args.speed_kmh), encoding="utf-8")

    print(f"\n  {args.pair}")
    print(f"      {len(path)} points · {total_m / 1000:.1f} km")
    print(f"      safety {route.get('safety_score')}/100 · {route.get('duration_minutes')} min"
          f" · {len(flags)} flag(s) on this route")
    if flags:
        # Worth saying loudly: the whole point of segment 3 is that the route the
        # journey follows is the clean one.
        print("      WARNING -- the recommended route is not clean. Re-run")
        print("      verify_video_scenario.py before filming segment 3.")
    print(f"      replays in about {minutes:.0f} min at {args.speed_kmh:g} km/h")
    print(f"\n  wrote {out}\n")
    print("  On the phone: Developer options -> Select mock location app -> your GPX")
    print("  player, then start playback BEFORE starting the journey in Meridian.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
