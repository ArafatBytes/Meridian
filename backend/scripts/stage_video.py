#!/usr/bin/env python3
"""
Put the whole video scenario on the map, and say what still needs a human.

    python backend/scripts/stage_video.py

Run it before the shoot and again before the 21:00 demo. It does three things:

1. **Seeds `video_scenario.json`** -- the curated surface. 193 flags, with three
   route corridors deliberately cleared so segment 3 has a clean route to
   recommend. Offsets are relative to `now`, so running it at 09:00 and at 20:55
   gives the same scenario at both.
2. **Lists the real news flags**, so you know which one segment 2 taps before the
   camera is rolling. Two kinds, both from real articles with an openable URL:
   `live-%`, which this database's own agent published and which expires in 8-12
   hours, and `seed-live-%`, captured from a real article by
   `capture_video_news.py` and re-laid against the current clock. Printed fresh
   each run rather than written into the script, because which ones exist changes.
3. **Verifies the routing contrast** and names the pair to film.

What it deliberately does not do: anything to the phone. Hot words, mock
location, the inbox and Do Not Disturb are listed at the end as manual steps,
because none of them can be set from here.

See `docs/video/PLAN.md` and `docs/video/SCENARIOS.md`.
"""

from __future__ import annotations

import asyncio
import subprocess
import os
import sys
from pathlib import Path
from typing import Final

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass

BACKEND_DIR: Final = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Run as though launched from `backend/`, whatever directory was actually used.
#
# `Settings.Config.env_file = ".env"` is **relative to the working directory**, so
# importing `app.core.config` from anywhere else raises
# `ValidationError: DATABASE_URL Field required` -- which reads as a missing
# setting rather than a wrong cwd. Step 1 still worked from the repository root,
# because it is a subprocess that resolves its own paths, so the failure landed on
# step 2 and looked like a database problem.
#
# Done here rather than by fixing `env_file`: that path is load-bearing for the
# server and every other script, and a shoot-day tool is the wrong place to change
# how the application finds its configuration. `--fixture` is unaffected, because
# `seed_risk_flags.py` resolves relative fixture paths against `BACKEND_DIR`.
os.chdir(BACKEND_DIR)

FIXTURE: Final = "data/fixtures/video_scenario.json"


def run(*args: str) -> int:
    """
    Run one of the sibling scripts with this same interpreter.

    The flush is not optional: the child writes straight to the terminal while our
    own prints sit in a buffer, so without it every section header appears *after*
    the output it introduces, and the report reads as though the steps ran out of
    order.
    """
    sys.stdout.flush()
    code = subprocess.call(
        [sys.executable, str(BACKEND_DIR / "scripts" / args[0]), *args[1:]]
    )
    sys.stdout.flush()
    return code


async def live_flags() -> list[tuple[str, str, int, str, bool]]:
    """
    The agent-produced flags, with the publisher that produced each one.

    Segment 2 taps one of these and opens its source article, so the statement and
    the outlet both matter. Returns empty rather than raising when there is no
    database -- the seeding step will already have failed loudly in that case.
    """
    import logging

    from sqlalchemy import text

    from app.core.database import AsyncSessionLocal, engine

    # The app engine is built with `echo=True`, which buries the three lines this
    # function exists to print under a connection handshake.
    #
    # Raising the log level does not silence it, on the parent logger or the
    # child: echo routes through SQLAlchemy's `InstanceLogger`, which consults the
    # engine's own `echo` flag and emits whatever the logger level says. The flag
    # is the only thing that works, and on an `AsyncEngine` it lives on the
    # wrapped sync engine.
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.ERROR)
    try:
        engine.sync_engine.echo = False
    except AttributeError:  # pragma: no cover - a plain Engine, or a future rename
        engine.echo = False  # type: ignore[attr-defined]

    # Both prefixes. `live-%` is a flag the agent published in this database;
    # `seed-live-%` is one captured from a real article by
    # `capture_video_news.py` and re-laid against the current clock. The second
    # exists because on 17 Oct the first set was empty -- not through any failure,
    # but because the day's road news was all outside Dhaka and so resolved to no
    # location. Both are real reporting with an openable URL, which is what
    # segment 2 needs; the distinction that matters here is only that a `live-%`
    # row will expire on its own and a `seed-live-%` row is re-laid every run.
    query = text(
        "select mobility_statement, status, source_count, "
        "       coalesce(("
        "         select string_agg(distinct s->>'source_id', ', ')"
        "         from jsonb_array_elements(sources) s"
        "       ), '-') as publishers, "
        "       event_key like 'seed-live-%' as replayed "
        "from public.risk_flags "
        "where expires_at > now() "
        "  and (event_key like 'live-%' or event_key like 'seed-live-%') "
        "order by observed_at desc"
    )
    try:
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(query)).fetchall()
            await session.rollback()
    except Exception as problem:  # pragma: no cover - diagnostics only
        print(f"  could not read live flags: {type(problem).__name__}: {problem}")
        return []
    return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]


MANUAL: Final = [
    "Hot word is set to 'Help' (17 Oct). It works, but `phraseWasSaid` matches it as "
    "a whole word, so it fires on the bare word in ordinary speech -- including "
    "'this will help you' while narrating. Consider a two-or-three word phrase "
    "instead: the matcher needs the whole sequence, so 'help me now' cannot "
    "false-fire on 'help'. Profile -> SOS hot words. Once, not per session.",
    "Inbox open on a laptop, as a cutaway. First email already marked Not spam.",
    "Mock location app loaded with data/video/Rampura-to-Gulshan2.gpx -- and playback "
    "started, then paused at the start, BEFORE route mode is opened. The journey's "
    "origin is read from wherever the phone says it is at that moment. Rebuild the "
    "track with: backend\\venv\\Scripts\\python.exe backend\\scripts\\export_route_track.py",
    "Phone on Do Not Disturb, Meridian excepted.",
    "Staged photo for segment 6 on the phone's gallery.",
]


VENV_PYTHON: Final = BACKEND_DIR / "venv" / "Scripts" / "python.exe"


def wrong_interpreter() -> bool:
    """
    True, loudly, if this Python cannot reach the database.

    Checked before anything runs rather than left to fail inside the seeder. A bare
    `python backend/scripts/stage_video.py` picks up whatever is first on PATH --
    on this machine the base conda environment -- which has no `asyncpg`. The
    seeder's own message says "install the backend dependencies", which is the
    right message for a missing dependency and the wrong one here: nothing is
    missing, the wrong interpreter was used.

    Worth the twelve lines because of when this gets run: 09:00 on a shoot day and
    20:55 before a judge demo, from a fresh shell, by someone who is not thinking
    about virtualenvs.
    """
    try:
        import asyncpg  # noqa: F401
    except ImportError:
        print("\n" + "=" * 72)
        print("  Wrong interpreter -- this Python has no asyncpg")
        print("=" * 72)
        print(f"\n  running as: {sys.executable}")
        print("\n  Nothing is missing; the backend venv was not used. Run:\n")
        if VENV_PYTHON.is_file():
            print(f"      {VENV_PYTHON} {Path(__file__).resolve()}")
            print("\n  or, from the repository root:\n")
            print("      backend\\venv\\Scripts\\python.exe backend\\scripts\\stage_video.py")
        else:
            print("      backend\\venv\\Scripts\\python.exe backend\\scripts\\stage_video.py")
            print(f"\n  ...though there is no venv at {VENV_PYTHON}, so create one first.")
        print()
        return True
    return False


def main() -> int:
    # `run` launches the sibling scripts with `sys.executable`, so getting this
    # right once fixes it for every step rather than each one failing in turn.
    if wrong_interpreter():
        return 2

    print("\n" + "=" * 72)
    print("  1. Seeding the video surface")
    print("=" * 72)
    if run("seed_risk_flags.py", "--fixture", FIXTURE, "--replay") != 0:
        print("\n  seeding failed -- stopping. Nothing else will be meaningful.\n")
        return 2

    print("=" * 72)
    print("  2. Real news flags -- segment 2 taps one of these")
    print("=" * 72)
    flags = asyncio.run(live_flags())
    if not flags:
        print("\n  NONE -- and this is the one thing that cannot be filmed around.")
        print("  Segments 1 and 2 need at least one real flag; they are the most")
        print("  persuasive part of the video and should not be faked.")
        print()
        print("  `live_risk` runs every 15 minutes, so first give it a cycle. If it")
        print("  still publishes nothing, the day's road news is probably all outside")
        print("  Dhaka, which is what happened on 17 Oct -- the agent is working and")
        print("  there is simply nothing in the city to flag. In that case replay a")
        print("  real article from an earlier day:")
        print()
        print("      python backend/scripts/capture_video_news.py --list")
        print("      python backend/scripts/capture_video_news.py")
        print()
        print("  then run this script again. See docs/video/PLAN.md T10.\n")
    else:
        for statement, status, count, publishers, replayed in flags:
            print(f"\n  {statement}")
            origin = "replayed" if replayed else "published here"
            print(f"      {status} · {count} source(s) · {publishers} · {origin}")
        print()

    print("=" * 72)
    print("  3. Segment 3 -- the routing contrast")
    print("=" * 72)
    routing_ok = run("verify_video_scenario.py") == 0

    print("=" * 72)
    print("  Still needs a human")
    print("=" * 72)
    for item in MANUAL:
        print(f"  [ ] {item}")

    print("\n" + "=" * 72)
    ready = routing_ok and bool(flags)
    print(f"  {'READY TO FILM' if ready else 'NOT READY'}")
    if not routing_ok:
        print("  Segment 3 has no filmable pair. See the failure above.")
    if not flags:
        print("  Segments 1 and 2 have no real flag to show.")
    print("=" * 72 + "\n")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
