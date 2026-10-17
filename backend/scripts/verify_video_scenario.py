#!/usr/bin/env python3
"""
Check that the video scenario is actually on the map, before filming or demoing.

    python backend/scripts/verify_video_scenario.py

Run this **immediately before** the shoot and again before the 21:00 demo. It takes
a few seconds and it is the difference between finding out now and finding out on
camera.

What it checks
--------------
Segment 3 of the video needs one route with **nothing flagged on it** and at least
one alternative that is visibly worse. That property is not guaranteed to survive
the day, for one reason:

    The fixture is ours. The live news flags are not.

`data/fixtures/video_scenario.json` was built by removing every seeded flag within
155 m of three recommended routes, so those corridors start clean. But `live_risk`
runs every fifteen minutes, and a real article about a real road can put a real flag
anywhere -- including on one of those corridors. That is the system working
correctly and the demo breaking at the same time.

So: three pairs, checked in order. The first that passes is the one to film. If a
live flag has landed on the primary corridor, the script says which flag, and you
move to the backup rather than discovering it mid-take.

Exit code is 0 if any pair passes, 1 if none do.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Final

# Windows consoles default to cp1252, and the flag statements carry Bangla place
# names and the middle dots below. Same guard as `seed_risk_flags.py`.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass

API: Final = "http://localhost:8000/api/v1/routes/calculate"

# Ordered best-first. Each was verified to give a clean recommended route against
# `video_scenario.json`; the first one has the strongest contrast by a wide margin.
PAIRS: Final = [
    ("Rampura", (23.7620, 90.4190), "Gulshan 2", (23.7925, 90.4145)),
    ("Gulshan 2", (23.7925, 90.4145), "Rampura", (23.7620, 90.4190)),
    ("Motijheel", (23.7330, 90.4170), "Kalabagan", (23.7420, 90.3840)),
    ("Dhanmondi 27", (23.7465, 90.3830), "Motijheel", (23.7330, 90.4170)),
]

# Order matters: `check` reports the first pair that passes as the one to film, and
# on 17 Oct that is no longer the first pair in this list.
#
# `Motijheel -> Kalabagan` was chosen on 16 Oct against four OSRM routes, the worst
# carrying eight flags against a clean recommendation. OSRM now returns three routes
# for that pair and the nineteen-minute one through Shahbagh and Gulistan is not
# among them, so the worst alternative carries one flag and there is no contrast
# left to film. Nothing in this repository changed to cause that; the route
# geometry did. Re-swept all 306 ordered pairs across eighteen Dhaka landmarks
# afterwards: exactly two still produce a clean recommendation with a flagged
# alternative, and both are the Gulshan 2 / Rampura corridor. Every pair with a
# wider spread carries four to seven flags on the recommendation too, which reads
# as "both are bad" -- the same saturation recorded in PLAN.md T2.
#
# This is the reason this script exists rather than a note in a document, and the
# reason it runs before both sessions.
PREFERRED: Final = "Rampura -> Gulshan 2"

# What segment 3 needs to be worth filming: a clean route, and an alternative
# carrying enough to look different on the map.
MIN_ALTERNATIVE_FLAGS: Final = 2


def routes(src: tuple[float, float], dst: tuple[float, float]) -> list[dict]:
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
        return json.load(response)


def check(name_a: str, a: tuple[float, float], name_b: str, b: tuple[float, float]) -> bool:
    label = f"{name_a} -> {name_b}"
    try:
        found = routes(a, b)
    except (urllib.error.URLError, TimeoutError) as problem:
        print(f"  {label}: cannot reach the API -- {problem}")
        return False

    if len(found) < 2:
        print(f"  {label}: FAIL -- only one route, nothing to compare")
        return False

    best, *rest = found
    on_best = best.get("flags") or []
    worst = max(rest, key=lambda r: len(r.get("flags") or []))
    on_worst = worst.get("flags") or []

    if on_best:
        print(f"  {label}: FAIL -- {len(on_best)} flag(s) on the recommended route:")
        for flag in on_best:
            # Naming it matters: a seeded flag means the fixture needs rebuilding,
            # a live one means wait for it to expire or use the next pair.
            print(
                f"      {flag['mobility_statement']} "
                f"({flag['status']}, {flag['source_count']} source(s))"
            )
        return False

    if len(on_worst) < MIN_ALTERNATIVE_FLAGS:
        print(
            f"  {label}: FAIL -- recommended route is clean, but the worst "
            f"alternative only carries {len(on_worst)} flag(s). No contrast to film."
        )
        return False

    print(f"  {label}: PASS")
    print(f"      recommended  {best['safety_score']}/100 · "
          f"{best['duration_minutes']} min · 0 flags")
    print(f"      \"{best['explanation']}\"")
    print(f"      worst option {worst['safety_score']}/100 · "
          f"{worst['duration_minutes']} min · {len(on_worst)} flags")
    for flag in on_worst[:3]:
        print(f"        - {flag['mobility_statement']}")
    if len(on_worst) > 3:
        print(f"        - ... and {len(on_worst) - 3} more")
    return True


def main() -> int:
    print("\nSegment 3 -- the routing contrast\n")
    passed = [
        f"{a} -> {b}"
        for a, pa, b, pb in PAIRS
        if check(a, pa, b, pb)
    ]

    print()
    if not passed:
        print("  NO PAIR IS FILMABLE.")
        print("  A live news flag has probably landed on every cleared corridor.")
        print("  Rebuild the fixture against today's surface, or film segment 3 last")
        print("  and re-check -- live flags expire in 8-12 hours.\n")
        return 1

    print(f"  Film: {passed[0]}")
    if len(passed) > 1:
        print(f"  Backup: {', '.join(passed[1:])}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
