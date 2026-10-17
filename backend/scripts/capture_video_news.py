#!/usr/bin/env python3
"""
Rebuild `data/fixtures/live_replay.json` from named real news flags.

    python backend/scripts/capture_video_news.py
    python backend/scripts/capture_video_news.py --list

Why this exists and `python -m app.agents export-replay` does not do
-------------------------------------------------------------------
`export_replay` captures the flags *being served right now*, which is the right
behaviour for the offline demo: whatever the agent found today is what the
offline surface should replay.

On 17 Oct that set was empty. Not because anything failed -- `live_risk` reads
every publisher every five minutes and marked ~52 articles relevant per run --
but because the day's road news happened to be Rajbari, Sitakunda, Bandarban and
Jhalokathi. None of it resolves to a Dhaka location, so none of it published, and
the last real flag (16 Oct 06:45 UTC) had expired. A video about reading the news
cannot open on a map with no news on it, and the honest number on **What we read**
would have been *0 real*.

So this script captures by **event key**, ignoring expiry, and re-anchors each
flag to a chosen recent offset. Everything that makes the flag real survives:

* the publisher, taken from the row
* the article URL, which opens, because it is the one the agent fetched
* the Bangla headline, as the publisher wrote it
* the coordinates and `location_text` the extractor resolved
* `severity_0`, `half_life_hours`, `radius_m` and `mobility_impact` as published

What does not survive is the clock. `observed_offset_hours` is reassigned from
`OFFSETS` below rather than measured, which is the one liberty taken and the same
one every other fixture here takes: times are relative to `now`, so the surface
is correct whenever it is laid down. See `docs/video/PLAN.md` T10.

`mobility_statement` is *not* captured. `framing.py` re-derives it at load, as for
every fixture, so the replayed flag's text has passed the framing guard rather
than being copied around it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass

BACKEND_DIR: Final = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Before the `app` imports below, and for the same reason as in `stage_video.py`:
# `Settings.Config.env_file = ".env"` is resolved against the working directory, so
# importing `app.core.config` from anywhere but `backend/` fails with
# `DATABASE_URL Field required` -- a wrong-cwd error wearing a missing-setting
# message.
os.chdir(BACKEND_DIR)

from sqlalchemy import text  # noqa: E402

from app.agents.live_risk import REPLAY_PATH, resolve_news_place, write_replay  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.policy.independence import is_confirmable  # noqa: E402
from app.scoring.fixture import SEED_KEY_PREFIX  # noqa: E402


# The flags to replay, newest first, with the age each should have when laid down.
#
# Five publishers and five places, chosen over the fuller candidate list for three
# reasons. Distinct publishers, so the **Today** list on *What we read* reads as a
# sweep of the press rather than one outlet's feed. Distinct places, so no two
# cards describe the same event. And an English statement that reads cleanly --
# which ruled out the Jagannath University procession, whose statement comes out as
# *"Heavy crowd near জগন্নাথ বিশ্ববিদ্যালয়"* because the gazetteer had no
# transliteration, and the Dhaka Tribune Tongi factory fire, which resolved to
# *Tejgaon Industrial Area* and is simply wrong.
#
# Offsets are hours before load and are kept well inside each flag's half-life, so
# `severity_now` stays far above `SERVE_THRESHOLD = 5.0` whether the surface is laid
# down at 09:00 or at 20:55. The spread also fixes the order of the Today list,
# which sorts newest first.
OFFSETS: Final[dict[str, float]] = {
    "live-5440969e00a52fda-0": -1.0,  # Jugantor      · Bangla Motor
    "live-c1034e8ae66c3604-0": -1.5,  # Prothom Alo   · Mohammadpur Beribadh
    "live-5e1577b839dbda42-0": -2.0,  # Samakal       · Azampur
    "live-4d14607e489c7ae7-0": -2.5,  # Ittefaq       · Tongi Junction
    "live-7090aab560a1c135-1": -3.0,  # Dhaka Tribune · Raj Laxmi
}

SELECT: Final = """
    select f.event_key, f.kind, f.radius_m, f.severity_0, f.half_life_hours,
           f.observed_at, f.status, f.sources::text as sources_json,
           extensions.ST_Y(f.location::extensions.geometry) as lat,
           extensions.ST_X(f.location::extensions.geometry) as lon,
           e.mobility_impact, e.location_text
    from public.risk_flags f
    join public.extracted_incidents e on e.flag_id = f.flag_id
    where f.event_key = any(:keys)
"""

# Candidates, for `--list`: every real flag with an extraction behind it, so a
# replacement can be picked when one of the five above is no longer in the table.
CANDIDATES: Final = """
    select f.event_key, f.status, f.observed_at, f.mobility_statement,
           f.severity_0, f.half_life_hours,
           (select string_agg(distinct s->>'source_id', ', ')
              from jsonb_array_elements(f.sources) s) as publishers
    from public.risk_flags f
    join public.extracted_incidents e on e.flag_id = f.flag_id
    where f.event_key like 'live-%'
    order by f.observed_at desc
    limit 40
"""


def quiet_engine() -> None:
    """
    Silence the app engine's `echo=True`, which otherwise buries this script's
    output under the connection handshake. Raising the logger level does not work:
    echo routes through SQLAlchemy's `InstanceLogger`, which consults the engine's
    own flag, and on an `AsyncEngine` that flag lives on the wrapped sync engine.
    """
    import logging

    from app.core.database import engine

    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.ERROR)
    try:
        engine.sync_engine.echo = False
    except AttributeError:  # pragma: no cover - a plain Engine, or a future rename
        engine.echo = False  # type: ignore[attr-defined]


async def list_candidates() -> int:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(text(CANDIDATES))).fetchall()
        await session.rollback()

    if not rows:
        print("\n  no real flags with an extraction behind them. Nothing to replay.\n")
        return 1

    print(f"\n  {len(rows)} real flag(s) available to replay:\n")
    for row in rows:
        chosen = "*" if row.event_key in OFFSETS else " "
        print(f"  {chosen} {row.event_key:26} {str(row.observed_at)[:16]}  {row.publishers}")
        print(f"      {row.mobility_statement}")
        print(f"      severity {row.severity_0} · half-life {row.half_life_hours}h · {row.status}")
    print("\n  (* = currently in OFFSETS)\n")
    return 0


async def capture() -> int:
    from app.core.database import AsyncSessionLocal

    keys = list(OFFSETS)
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(text(SELECT), {"keys": keys})).fetchall()
        await session.rollback()

    found = {row.event_key for row in rows}
    missing = [key for key in keys if key not in found]
    if missing:
        # Never write a partial file: the seeder would lay down three flags and the
        # shoot would be short two without anything saying so.
        print("\n  these flags are no longer in the table:")
        for key in missing:
            print(f"    {key}")
        print("\n  run with --list to see what is available, then edit OFFSETS.\n")
        return 2

    now = datetime.now(UTC)
    entries: list[dict[str, Any]] = []

    # Written in OFFSETS order rather than query order, so the file reads newest
    # first and a human can see at a glance what the Today list will look like.
    by_key = {row.event_key: row for row in rows}
    for key in sorted(keys, key=lambda k: OFFSETS[k], reverse=True):
        row = by_key[key]
        observed_offset = OFFSETS[key]
        place = await resolve_news_place(row.location_text)
        sources = json.loads(row.sources_json)

        # Asked of the policy, not defaulted.
        #
        # `_row_from_entry` defaults `status` to `unconfirmed`, which predates the
        # 2026-10-16 rule: since then one vetted newsroom is enough on its own, and
        # `unconfirmed` means a community report with no newsroom behind it. Every
        # flag replayed here was built from an article by a publisher in
        # `VETTED_PUBLISHERS`, so leaving it to the default drew five real newspaper
        # reports as hollow question marks -- the opposite of what the badge now
        # means. `is_confirmable` is the same call `live_risk.flag_row` makes, so the
        # replayed flag gets the badge the original carried.
        status = (
            "confirmed"
            if is_confirmable(
                [s["source_id"] for s in sources],
                minimum=settings.MIN_SOURCES_FOR_CONFIRMED,
            )
            else "unconfirmed"
        )

        entries.append(
            {
                "event_key": SEED_KEY_PREFIX + row.event_key,
                "kind": row.kind,
                "status": status,
                "lat": float(row.lat),
                "lon": float(row.lon),
                "radius_m": int(row.radius_m),
                "severity_0": float(row.severity_0),
                "half_life_hours": float(row.half_life_hours),
                "mobility_impact": row.mobility_impact,
                "place": place.resolved_name if place.method != "unresolved" else None,
                "observed_offset_hours": observed_offset,
                # Stated, not assumed. `export_replay` hard-codes 1 here, which is
                # wrong for any flag Rumour Guard merged -- `check_rows` rejects a
                # row listing more sources than it counts.
                "source_count": len(sources),
                "sources": [
                    {
                        "source_id": source["source_id"],
                        "url": source["url"],
                        "title": source.get("title"),
                        # Reported just after it happened, which is the real
                        # ordering, and never in the future relative to load.
                        "published_offset_hours": min(observed_offset + 0.05, -0.05),
                    }
                    for source in sources
                ],
            }
        )

        statement_place = place.resolved_name if place.method != "unresolved" else "?"
        publishers = ", ".join(sorted({s["source_id"] for s in sources}))
        print(f"  {observed_offset:+5.1f}h  {statement_place:38} {status:12} {publishers}")

    write_replay(entries, now, REPLAY_PATH)
    print(f"\n  wrote {len(entries)} flag(s) to {REPLAY_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list",
        action="store_true",
        help="show the real flags available to replay instead of capturing",
    )
    args = parser.parse_args()

    # Same trap as `stage_video.py`: a bare `python` is whatever is first on PATH,
    # and the base conda environment here has no asyncpg. Said plainly, because the
    # failure that follows otherwise reads as a missing dependency.
    try:
        import asyncpg  # noqa: F401
    except ImportError:
        venv = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
        print(f"\n  wrong interpreter -- {sys.executable} has no asyncpg.")
        print("  Nothing is missing; the backend venv was not used. Run:\n")
        print(f"      {venv} {Path(__file__).resolve()}\n")
        return 2

    quiet_engine()
    if args.list:
        return asyncio.run(list_candidates())

    print("\n  capturing real news flags into the replay fixture\n")
    return asyncio.run(capture())


if __name__ == "__main__":
    raise SystemExit(main())
