#!/usr/bin/env python3
"""
Put the whole video scenario on the map, and say what still needs a human.

    python backend/scripts/stage_video.py

Run it before the shoot and again before the 21:00 demo. It does three things:

1. **Seeds `video_scenario.json`** -- the curated surface. 193 flags, with three
   route corridors deliberately cleared so segment 3 has a clean route to
   recommend. Offsets are relative to `now`, so running it at 09:00 and at 20:55
   gives the same scenario at both.
2. **Lists the live news flags**, so you know which one segment 2 taps before the
   camera is rolling. These are agent-produced, from real articles, and they
   expire in 8-12 hours -- which is why this is printed fresh each run rather
   than written into the script.
3. **Verifies the routing contrast** and names the pair to film.

What it deliberately does not do: anything to the phone. Hot words, mock
location, the inbox and Do Not Disturb are listed at the end as manual steps,
because none of them can be set from here.

See `docs/video/PLAN.md` and `docs/video/SCENARIOS.md`.
"""

from __future__ import annotations

import asyncio
import subprocess
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


async def live_flags() -> list[tuple[str, str, int, str]]:
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

    query = text(
        "select mobility_statement, status, source_count, "
        "       coalesce(("
        "         select string_agg(distinct s->>'source_id', ', ')"
        "         from jsonb_array_elements(sources) s"
        "       ), '-') as publishers "
        "from public.risk_flags "
        "where expires_at > now() and event_key like 'live-%' "
        "order by observed_at desc"
    )
    try:
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(query)).fetchall()
            await session.rollback()
    except Exception as problem:  # pragma: no cover - diagnostics only
        print(f"  could not read live flags: {type(problem).__name__}: {problem}")
        return []
    return [(r[0], r[1], r[2], r[3]) for r in rows]


MANUAL: Final = [
    "Hot words: both stored phrases are 'Hello'. Replace with one distinctive "
    "phrase (Profile -> SOS hot words) and practise saying it. Once, not per session.",
    "Inbox open on a laptop, as a cutaway. First email already marked Not spam.",
    "Mock location app loaded with the Motijheel -> Kalabagan track.",
    "Phone on Do Not Disturb, Meridian excepted.",
    "Staged photo for segment 6 on the phone's gallery.",
]


def main() -> int:
    print("\n" + "=" * 72)
    print("  1. Seeding the video surface")
    print("=" * 72)
    if run("seed_risk_flags.py", "--fixture", FIXTURE) != 0:
        print("\n  seeding failed -- stopping. Nothing else will be meaningful.\n")
        return 2

    print("=" * 72)
    print("  2. Live news flags -- segment 2 taps one of these")
    print("=" * 72)
    flags = asyncio.run(live_flags())
    if not flags:
        print("\n  NONE. `live_risk` runs every 15 minutes; give it a cycle.")
        print("  Segment 1 and 2 need at least one real flag -- they are the")
        print("  most persuasive part of the video and should not be faked.\n")
    else:
        for statement, status, count, publishers in flags:
            print(f"\n  {statement}")
            print(f"      {status} · {count} source(s) · {publishers}")
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
