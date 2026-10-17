#!/usr/bin/env python3
"""
Force the live journey's check-in ladder to start.

    docker compose exec -T api python scripts/arm_journey_checkin.py
    docker compose exec -T api python scripts/arm_journey_checkin.py --watch

Why this is needed at all
-------------------------
Segment 4 films a phone that stops answering. On a desk it never does, and the
reason is a deliberate piece of the product rather than a bug.

`MapScreen` heartbeats every `HEARTBEAT_INTERVAL_MS` (60 s) for as long as
navigation is following, on a plain `setInterval` -- it is **not** gated on the
dot moving. Each beat runs `_HEARTBEAT`, which slides the deadline:

    deadline = least(
        greatest(deadline, now() + least(slide, coalesce(leash_seconds, slide))),
        started_at + ceiling          -- MAX_DEADLINE, six hours
    )

The shortest leash the UI offers is the `2 min` chip, so `leash_seconds` is 120
and every beat pins the deadline to `now + 120`. Beats arrive every 60 s, so the
deadline sits permanently two minutes in the future and is never reached; the
ceiling that would eventually catch it is six hours away. Measured on a real
journey: `last_heartbeat_at 18:17:53`, `deadline_at 18:19:53`,
`escalation_state normal`, indefinitely.

That is correct behaviour. A phone that is talking is not quiet, and the whole
asymmetry is "a phone in a jam talks and the clock follows it; a phone in a ditch
does not". It just means the demo premise has to be created rather than waited
for.

What this does
--------------
Shortening the leash is the obvious answer and the database refuses it:

    journeys_leash_sane CHECK (leash_seconds IS NULL
                               OR leash_seconds BETWEEN 120 AND 21600)

120 s is exactly twice the beat, so there is no legal leash that expires between
two heartbeats. Instead this backdates `deadline_at` by a second and **runs the
sweep in the same breath**, before the next beat can slide it forward again:

    update journeys set deadline_at = now() - 1s
     where ... and escalation_state = 'normal'
    await _run("journey_watch")

Doing both here is what makes it deterministic. Left to the clock, the update and
the beat race each other at the same sixty-second cadence and the first rung
lands on a coin flip.

Nothing is faked. `journey_watch` does its own real work from there -- the push,
the escalation record, the emails -- and `I'm fine` runs its true path.

**Only the first rung needs forcing.** `_HEARTBEAT` slides the deadline only
`when escalation_state = 'normal'`, so the moment the check-in is out the phone
cannot talk its way out of it, and the remaining rungs run on `CHECK_IN_WINDOW`
off the ordinary minute sweep.

Run it right after pressing Start.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass


async def main() -> int:
    import asyncpg

    from app.core.celery_app import _run
    from app.core.config import settings

    parser = argparse.ArgumentParser(
        description="Force the check-in ladder on the live journey."
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="follow the ladder until the guardian is emailed",
    )
    args = parser.parse_args()

    dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            """
            select journey_id, escalation_state, deadline_at, last_heartbeat_at,
                   guardian_contact_id
              from journeys
             where state = 'active'
             order by started_at desc
             limit 1
            """
        )
        if row is None:
            print("\n  no active journey. Press Start in Meridian first.\n")
            return 2

        short = str(row["journey_id"])[:8]
        if row["escalation_state"] != "normal":
            print(
                f"\n  journey {short} is already at '{row['escalation_state']}' "
                "- the ladder is running.\n"
            )
            return 0
        if row["guardian_contact_id"] is None:
            print(
                f"\n  journey {short} has no guardian, so nobody would be emailed.\n"
                "  Pick a contact under 'If you go quiet, tell' before Start.\n"
            )
            return 2

        await conn.execute(
            """
            update journeys
               set deadline_at = now() - interval '1 second'
             where journey_id = $1
               and escalation_state = 'normal'
            """,
            row["journey_id"],
        )
        print(f"\n  journey {short}: deadline backdated. Sweeping now...")

        result = await _run("journey_watch")
        if isinstance(result, dict):
            print(
                f"  journey_watch: {result.get('status')} - "
                f"{result.get('items_in')} in, {result.get('items_out')} out"
            )

        after = await conn.fetchrow(
            "select escalation_state from journeys where journey_id = $1",
            row["journey_id"],
        )
        print(f"  escalation_state: normal -> {after['escalation_state']}")

        if after["escalation_state"] == "normal":
            print(
                "\n  the sweep did not take it - a heartbeat probably landed first.\n"
                "  Just run it again.\n"
            )
            return 1

        print("\n  'Are you there yet?' is on the phone now. The rest runs by itself:")
        print("  ~1 min -> 'Asked twice, still no answer.'")
        print("  ~2 min -> guardian emailed, card goes red.\n")

        if not args.watch:
            return 0

        seen = after["escalation_state"]
        print("  watching. Ctrl+C to stop.\n")
        while True:
            await asyncio.sleep(5)
            now = await conn.fetchval("select now()")
            cur = await conn.fetchrow(
                "select escalation_state, answered_at from journeys where journey_id = $1",
                row["journey_id"],
            )
            if cur["answered_at"]:
                print(f"\n  answered at {cur['answered_at']:%H:%M:%S} - back to 'On your way.'\n")
                return 0
            if cur["escalation_state"] != seen:
                seen = cur["escalation_state"]
                print(f"  [{now:%H:%M:%S}] -> {seen}")
                if seen == "contacts_notified":
                    print("\n  guardian emailed. The red card is on the phone.\n")
                    return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
