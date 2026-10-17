#!/usr/bin/env python3
"""
Drive the phone's location along a GPX track, over adb. No app to install.

    python backend/scripts/play_mock_track.py
    python backend/scripts/play_mock_track.py --speed-kmh 40
    python backend/scripts/play_mock_track.py --gpx backend/data/video/Gulshan2-to-Rampura.gpx
    python backend/scripts/play_mock_track.py --teardown

Segment 4 films a journey that has to arrive: `ARRIVAL_M` is 30 m, so the dot has
to get genuinely close before navigation ends by itself. Walking the route is not
an option and the usual answer -- a GPX player from the Play Store designated under
*Developer options -> Select mock location app* -- means trusting a free app to
replay at a sane rate on the one evening it matters.

Android 11+ ships the same capability in the shell, so this uses that instead:

    cmd location providers add-test-provider fused
    cmd location providers set-test-provider-enabled fused true
    cmd location providers set-test-provider-location fused --location <lat>,<lon>

The app does nothing to resist. There is no `isFromMockProvider` check anywhere in
the codebase, so an injected fix is treated exactly like a real one -- which is
the point: Journey Guardian, the moving dot, the arrival and the emails all run
their real code paths.

Why it resamples instead of replaying the points
------------------------------------------------
`export_route_track.py` writes OSRM's own geometry, and OSRM spaces points by
turns, not by time: on this track they run from 3 m to 195 m apart. Pushing them
one per tick makes the dot crawl through junctions and leap across flyovers. So
the track is resampled to a constant `speed_kmh`, which is also what makes the
arrival predictable -- the run takes distance/speed, and you can check that
against the check-in ladder before you start filming.

Leaving the phone clean
-----------------------
The test provider outlives this process, so the phone keeps reporting the last
injected fix until it is removed. Ctrl+C and normal exit both tear it down.
`--teardown` does it by hand if a run was killed.
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import threading
import sys
import time
from pathlib import Path
from typing import Final

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass

BACKEND_DIR: Final = Path(__file__).resolve().parent.parent
DEFAULT_GPX: Final = BACKEND_DIR / "data" / "video" / "FILM-Rampura-to-Gulshan2.gpx"

DEFAULT_PROVIDERS: Final = ("fused", "gps", "network")
"""
All three, and that is the whole trick.

`expo-location` asks Play Services' fused client, which *blends* the platform
providers rather than reading one. Mocking `fused` alone leaves `network` still
reporting the real phone -- actively, every few seconds -- and the first fix the
app receives on `watchPositionAsync` can be that one. Navigation then starts
kilometres off its own route, `locate()` snaps to the nearest point on the line,
the off-route timer trips, and it reroutes from where the phone really is. On
camera that reads as the dot teleporting mid-journey and sticking there.

So every provider the blend can see has to tell the same story.
"""
DEFAULT_SPEED_KMH: Final = 25.0
DEFAULT_INTERVAL_S: Final = 1.0

# Matches `export_route_track.py`'s output and any ordinary GPX: attribute order
# is lat then lon, which is what that writer emits and what every player expects.
_TRKPT: Final = re.compile(r'lat="([-\d.]+)"\s+lon="([-\d.]+)"')


def adb(*args: str, check: bool = True) -> str:
    """One adb shell call. Returns stdout; raises on a non-zero exit if `check`."""
    done = subprocess.run(
        ["adb", "shell", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and done.returncode != 0:
        raise SystemExit(f"  adb failed: {' '.join(args)}\n  {done.stderr.strip()}")
    return (done.stdout or "") + (done.stderr or "")


def metres_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Haversine, in metres. Good to a fraction of a percent at city scale."""
    radius = 6_371_000.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def read_track(path: Path) -> list[tuple[float, float]]:
    if not path.exists():
        raise SystemExit(
            f"\n  no such track: {path}\n"
            "  export one first:  python backend/scripts/export_route_track.py\n"
        )
    points = [(float(a), float(b)) for a, b in _TRKPT.findall(path.read_text(encoding="utf-8"))]
    if len(points) < 2:
        raise SystemExit(f"\n  {path} has fewer than two track points\n")
    return points


def resample(
    points: list[tuple[float, float]], *, step_m: float
) -> list[tuple[float, float]]:
    """
    The track at a constant spacing, so one tick is one `step_m` of travel.

    Walks the polyline accumulating distance and emits a linearly interpolated
    point every `step_m`. Linear interpolation between two fixes a few tens of
    metres apart is indistinguishable from the great circle at this scale, and
    the dot is drawn on the same polyline anyway.
    """
    out: list[tuple[float, float]] = [points[0]]
    carry = 0.0
    for index in range(1, len(points)):
        start, end = points[index - 1], points[index]
        leg = metres_between(start, end)
        if leg <= 0:
            continue
        travelled = step_m - carry
        while travelled <= leg:
            fraction = travelled / leg
            out.append(
                (
                    start[0] + (end[0] - start[0]) * fraction,
                    start[1] + (end[1] - start[1]) * fraction,
                )
            )
            travelled += step_m
        carry = leg - (travelled - step_m)
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


def setup(providers: tuple[str, ...]) -> None:
    # `cmd location` runs as the shell, so the shell is what needs the appop.
    # Harmless to re-apply, and re-applying is the common case: the provider is
    # removed on exit but the appop is left, being a permission rather than state.
    adb("appops", "set", "com.android.shell", "android:mock_location", "allow", check=False)
    for provider in providers:
        # Remove before adding: a provider left behind by a killed run cannot be
        # added twice, and the failure message is obscure.
        adb("cmd", "location", "providers", "remove-test-provider", provider, check=False)
        adb("cmd", "location", "providers", "add-test-provider", provider,
            "--supportsSpeed", "--supportsBearing")
        adb("cmd", "location", "providers", "set-test-provider-enabled", provider, "true")


def teardown(providers: tuple[str, ...]) -> None:
    for provider in providers:
        adb("cmd", "location", "providers", "set-test-provider-enabled", provider, "false",
            check=False)
        adb("cmd", "location", "providers", "remove-test-provider", provider, check=False)


def push(providers: tuple[str, ...], lat: float, lon: float) -> None:
    """
    One fix to every provider, in a single adb call, re-asserting the test
    provider each time.

    The re-assert is the part that matters. On a Pixel the `fused` provider
    belongs to Play Services --

        identity=10133/com.google.android.gms[fused_location_provider]

    -- and Play Services re-registers it on its own schedule, roughly every two
    minutes under observation. That silently drops the test override: `gps` and
    `network` stay mocked, `fused` quietly goes back to the real phone, and since
    `expo-location` reads the Play Services client, the app starts getting true
    positions again. The symptom is a run that "worked for a bit" and then put the
    dot back on the real location mid-journey.

    Re-adding a provider that is already a test provider is a no-op -- verified,
    it neither errors nor clears the last fix -- so the cheap and reliable answer
    is to assert it on every tick rather than detect the reclaim. Worst case the
    real position is live for one interval, and `advance()` is windowed and
    monotonic, so a single stray fix cannot move progress.

    Batched with `;` because a round trip is ~100 ms and nine of them per tick
    would eat the interval -- and worse, stagger the providers, which is the
    disagreement this exists to prevent.
    """
    where = f"{lat:.7f},{lon:.7f}"
    parts: list[str] = []
    for provider in providers:
        parts.append(
            f"cmd location providers add-test-provider {provider} "
            "--supportsSpeed --supportsBearing"
        )
        parts.append(f"cmd location providers set-test-provider-enabled {provider} true")
        parts.append(
            f"cmd location providers set-test-provider-location {provider} "
            f"--location {where} --accuracy 5"
        )
    adb("; ".join(parts), check=False)


def still_mocked(providers: tuple[str, ...]) -> list[str]:
    """Which of `providers` are NOT currently reporting a mock fix."""
    out = adb("dumpsys location", check=False)
    bad = []
    for provider in providers:
        marker = f"last location=Location[{provider} "
        line = next((l for l in out.splitlines() if marker in l), None)
        if line is None or "mock" not in line:
            bad.append(provider)
    return bad


def device_attached() -> bool:
    done = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = [ln for ln in done.stdout.splitlines()[1:] if ln.strip().endswith("device")]
    return bool(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay a GPX track as the phone's location, over adb."
    )
    parser.add_argument("--gpx", type=Path, default=DEFAULT_GPX, help="track to replay")
    parser.add_argument(
        "--speed-kmh", type=float, default=DEFAULT_SPEED_KMH,
        help=(
            f"travel speed (default {DEFAULT_SPEED_KMH:g}). Keep the run longer than the "
            "check-in ladder or the dot arrives before the escalation finishes."
        ),
    )
    parser.add_argument(
        "--interval", type=float, default=DEFAULT_INTERVAL_S,
        help=f"seconds between fixes (default {DEFAULT_INTERVAL_S})",
    )
    parser.add_argument(
        "--providers", default=",".join(DEFAULT_PROVIDERS),
        help=("comma-separated providers to drive (default "
              f"{','.join(DEFAULT_PROVIDERS)}) -- all of them, unless debugging"),
    )
    parser.add_argument(
        "--hold", type=float, default=0.0,
        help=(
            "seconds to sit still at the first point before moving. The default, 0, waits "
            "for Enter instead, which is better on camera: the journey has to be started "
            "while the phone is already at the start point, and that takes as long as it takes"
        ),
    )
    parser.add_argument(
        "--stop-after", type=float, metavar="MIN",
        help="freeze the dot after this many minutes and keep reporting that fix, "
             "which is what makes the phone look like it stopped answering",
    )
    parser.add_argument(
        "--teardown", action="store_true",
        help="remove the test provider and exit (for a run that was killed)",
    )
    args = parser.parse_args()
    providers = tuple(x.strip() for x in args.providers.split(",") if x.strip())

    if not device_attached():
        print("\n  no device. Plug the phone in, unlock it, and check `adb devices`.\n")
        return 2

    if args.teardown:
        teardown(providers)
        print(f"\n  removed test providers: {', '.join(providers)}. Phone is back on its own GPS.\n")
        return 0

    points = read_track(args.gpx)
    total_m = sum(metres_between(points[i - 1], points[i]) for i in range(1, len(points)))
    metres_per_second = args.speed_kmh * 1000 / 3600
    step_m = metres_per_second * args.interval
    fixes = resample(points, step_m=step_m)
    run_s = len(fixes) * args.interval

    print(f"\n  {args.gpx.name}")
    print(f"      {len(points)} track points · {total_m / 1000:.2f} km")
    print(f"      {len(fixes)} fixes · one every {args.interval:g}s · {args.speed_kmh:g} km/h")
    print(f"      runs for {run_s / 60:.1f} min")
    if args.stop_after:
        print(f"      freezes at {args.stop_after:g} min, then holds that fix")
    print()

    setup(providers)
    push(providers, *fixes[0])
    print(f"  providers {', '.join(providers)} are live; phone is at the start point.")

    # The park is an ACTIVE hold, not a wait.
    #
    # This is where the whole thing used to come apart. Parking used to push one
    # fix and then block on input(), and a single fix is not enough: the moment
    # Meridian calls `watchPositionAsync` with `Accuracy.High` -- which is the
    # moment Start is pressed -- Play Services spins its fused engine up, the
    # platform provider goes from `ProviderRequest[OFF]` to on, and re-registering
    # it drops the test override. Nothing then restored it until Enter was
    # pressed, so the app read the real phone, decided it was kilometres off its
    # own route, announced "off route, recalibrating" and rerouted from reality.
    #
    # Idle, the override survives untouched -- measured, 45 s with no re-assert
    # and no flip. It is the act of requesting location that steals it. So the
    # park has to keep pushing, at the same cadence as the run, for exactly as
    # long as the phone is sitting at the start point.
    if args.hold:
        print(f"  holding {args.hold:g}s — press Start in Meridian now.")
        deadline = time.monotonic() + args.hold
        while time.monotonic() < deadline:
            push(providers, *fixes[0])
            time.sleep(args.interval)
    else:
        print("  the phone is parked at the start point and is being held there.")
        print("  plan the route, set the deadline, pick the contact, press Start in Meridian,")
        print("  then come back here and press Enter to start moving.\n")

        released = threading.Event()
        saw_eof = threading.Event()

        def wait_for_enter() -> None:
            try:
                input()
            except EOFError:
                saw_eof.set()
            released.set()

        threading.Thread(target=wait_for_enter, daemon=True).start()

        ticks = 0
        while not released.is_set():
            push(providers, *fixes[0])
            ticks += 1
            if ticks % 20 == 0:
                bad = still_mocked(providers)
                note = "holding at the start point"
                if bad:
                    note = f"recovered {', '.join(bad)} — Play Services took it back"
                print(f"  [parked {ticks * args.interval:5.0f}s] {note}")
            time.sleep(args.interval)

        if saw_eof.is_set():
            # Moving without the cue would start the journey mid-route.
            teardown(providers)
            print("\n  stdin is not readable, so there is nothing to press Enter on.")
            print("  Run this from a real terminal, or give it a fixed wait instead:")
            print("      ... play_mock_track.py --hold 120\n")
            return 2

    print("  moving. Ctrl+C stops and cleans up.\n")
    started = time.monotonic()
    frozen = False
    try:
        for index, (lat, lon) in enumerate(fixes):
            elapsed_min = (time.monotonic() - started) / 60
            if args.stop_after and elapsed_min >= args.stop_after:
                if not frozen:
                    print(f"\n  [{elapsed_min:4.1f} min] FROZEN — holding this fix. "
                          "The ladder starts from here.\n")
                    frozen = True
                push(providers, lat, lon)
                time.sleep(args.interval)
                continue

            push(providers, lat, lon)
            if index % 15 == 0 or index == len(fixes) - 1:
                remaining = metres_between((lat, lon), points[-1])
                # Cheap enough every fifteenth tick, and it is the one thing worth
                # knowing while filming: a provider Play Services took back shows
                # up here before it shows up as the dot leaving the route.
                bad = still_mocked(providers)
                flag = "" if not bad else f"   <-- REAL LOCATION ON: {', '.join(bad)}"
                print(f"  [{elapsed_min:4.1f} min] {index + 1:4d}/{len(fixes)}  "
                      f"{lat:.5f},{lon:.5f}  {remaining:6.0f} m to go{flag}")
            time.sleep(args.interval)

        print("\n  reached the last point. Navigation should have ended by itself.")
        print("  holding the final fix for 60s so arrival registers.")
        for _ in range(60):
            push(providers, *fixes[-1])
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n  stopped.")
    finally:
        teardown(providers)
        print(f"  removed test providers: {', '.join(providers)}. Phone is back on its own GPS.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
