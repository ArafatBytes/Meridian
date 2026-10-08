"""
The scripted promotion, for the stage.

    python -m app.agents promote-demo                 promote one unconfirmed flag
    python -m app.agents promote-demo --dry-run       say what it would do
    python -m app.agents promote-demo --reset         put it back to unconfirmed

D05 asks for *"a scripted replay that performs the promotion on demand, for the
stage"*, and this is it. Demo beat 2 is the concept document's 14:26 → 14:31
transition: a flag that was one outlet's claim becomes a corroborated one while the
audience watches.

---

## Why this exists rather than waiting for real corroboration

Because real corroboration cannot be scheduled, and measurement says it is missed
about half the time anyway.

`scripts/eval_dedup.py` puts recall at ~56% on the labelled set at the configured
threshold — true duplicates and genuinely different events in one neighbourhood are
not separable on a one-line summary (the Mohakhali pair and the worst false pair both
score 0.718). The guard is therefore tuned for **precision**: it declines when it
cannot tell. The consequence is that a promotion may simply not happen during a
nine-minute demo, and "wait for a second outlet to phrase a fire the same way" is not
a stage plan.

So this command makes the transition **deterministic and repeatable**, and it does it
*through the real code path*: `rumour_guard.merge_into()`, the same function live
ingestion calls, with the same independence rules and the same database constraints.
Nothing here writes `status = 'confirmed'` directly.

## What is honest about it, and what to say out loud

The second source is **synthetic, and labelled as such**: `source_id` is
`demo_second_source` and its URL points at this file, so it can never be mistaken for
a real outlet in the flag sheet or the source strip. On stage the honest sentence is:

> *"I'm injecting a second source here so you can watch the transition on demand.
> The logic that promotes it is the same code that runs against live news — what I
> cannot schedule is a second newspaper publishing in the next ninety seconds."*

`--reset` returns the flag to `unconfirmed` and drops the synthetic source, so the
demo can be rehearsed repeatedly. It only ever removes `demo_second_source`, so it
cannot damage real provenance.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.rumour_guard import DuplicateMatch, merge_into
from app.policy.independence import independent_publishers

logger = logging.getLogger(__name__)

DEMO_SOURCE_ID: Final[str] = "demo_second_source"
"""
Deliberately not the id of any real outlet.

`SOURCES` in `app/ingestion/sources/` holds `ekattor_tv`, `independent_tv` and
`channel24`. A synthetic corroboration must be distinguishable from all of them in
the UI without anyone having to remember that it is synthetic — the flag sheet shows
the raw id, so this string is the disclosure.
"""


def demo_source(now: datetime) -> dict[str, Any]:
    """The synthetic second account. Self-describing on purpose."""
    return {
        "source_id": DEMO_SOURCE_ID,
        "url": "https://meridian.invalid/demo/scripted-promotion",
        "title": "Scripted second source (D05 promotion demo)",
        "published_at": now.isoformat(),
        "snippet": "Injected by `python -m app.agents promote-demo` to make demo beat 2 "
        "repeatable. Not a real publisher.",
    }


# Prefer a flag that already cites a real outlet and is still well clear of expiry:
# promoting something about to vanish gives the audience nothing to look at, and
# promoting a fixture flag would be a demo of the fixture rather than of the guard.
_PICK: Final = text(
    """
    select f.flag_id,
           f.event_key,
           f.status,
           f.sources::text as sources_json
      from public.risk_flags f
     where f.status = 'unconfirmed'
       -- cast(:now as timestamptz) explicitly: asyncpg sends the parameter with an
       -- unresolved type, and Postgres then reads `$1 + interval '30 minutes'` as
       -- interval arithmetic, so the comparison becomes timestamptz > interval and
       -- fails with `operator does not exist`.
       and f.expires_at > cast(:now as timestamptz) + interval '30 minutes'
       and f.sources::text not like :demo_like
     order by (f.event_key like :live_prefix) desc,   -- real news first
              f.severity_0 desc
     limit 1
    """
)

_RESET: Final = text(
    """
    update public.risk_flags
       set sources = (
               select coalesce(jsonb_agg(s), '[]'::jsonb)
                 from jsonb_array_elements(sources) as s
                where s->>'source_id' <> :demo_id
           ),
           source_count = greatest(1, (
               select count(distinct s->>'source_id')
                 from jsonb_array_elements(sources) as s
                where s->>'source_id' <> :demo_id
           )),
           -- Conditional, not unconditional. If a flag picked up a REAL second
           -- publisher after the scripted promotion, removing the synthetic source
           -- still leaves it genuinely corroborated, and demoting it would be this
           -- command destroying real provenance. Only drop to unconfirmed when what
           -- remains cannot sustain `confirmed`.
           status = case
                      when (select count(distinct s->>'source_id')
                              from jsonb_array_elements(sources) as s
                             where s->>'source_id' <> :demo_id) >= 2
                      then status
                      else 'unconfirmed'
                    end,
           confirmed_at = case
                            when (select count(distinct s->>'source_id')
                                    from jsonb_array_elements(sources) as s
                                   where s->>'source_id' <> :demo_id) >= 2
                            then confirmed_at
                            else null
                          end,
           updated_at = now()
     where sources::text like :demo_like
    returning event_key
    """
)


@dataclass(frozen=True)
class PromotionDemo:
    """What the scripted promotion did, for the CLI to print."""

    event_key: str
    flag_id: UUID
    status: str
    source_count: int
    promoted: bool


async def pick_target(db: AsyncSession, now: datetime) -> dict[str, Any] | None:
    """The unconfirmed flag worth promoting on stage, or None if there is none."""
    row = (
        await db.execute(
            _PICK,
            {
                "now": now,
                "demo_like": f"%{DEMO_SOURCE_ID}%",
                "live_prefix": "live-%",
            },
        )
    ).mappings().first()
    return dict(row) if row is not None else None


async def promote_one(
    db: AsyncSession, now: datetime, *, dry_run: bool = False
) -> PromotionDemo | None:
    """
    Add the synthetic second source to one unconfirmed flag, through the real guard.

    Returns None when there is nothing to promote — every served flag is already
    confirmed, or already carries the demo source. That is a legitimate state, not an
    error, and `--reset` is how you get back to a demoable one.
    """
    target = await pick_target(db, now)
    if target is None:
        return None

    existing = json.loads(target["sources_json"] or "[]")
    source_ids = frozenset(str(s.get("source_id", "")) for s in existing)

    if dry_run:
        projected = independent_publishers({*source_ids, DEMO_SOURCE_ID})
        return PromotionDemo(
            event_key=str(target["event_key"]),
            flag_id=UUID(str(target["flag_id"])),
            status="confirmed" if len(projected) >= 2 else "unconfirmed",
            source_count=len(projected),
            promoted=len(projected) >= 2,
        )

    # Hand-built rather than returned by `find_duplicate()`: we are not asking whether
    # two articles describe one event, we are asserting that this synthetic account
    # belongs to a flag we chose. Everything after this point is the production path.
    match = DuplicateMatch(
        flag_id=UUID(str(target["flag_id"])),
        event_key=str(target["event_key"]),
        similarity=1.0,
        status=str(target["status"]),
        source_ids=source_ids,
    )
    outcome = await merge_into(db, match, source=demo_source(now), now=now)
    await db.commit()

    return PromotionDemo(
        event_key=outcome.event_key,
        flag_id=outcome.flag_id,
        status=outcome.status,
        source_count=outcome.source_count,
        promoted=outcome.promoted,
    )


async def reset(db: AsyncSession) -> list[str]:
    """
    Undo every scripted promotion, so the demo can be rehearsed again.

    Removes only `demo_second_source` refs and recomputes `source_count` from what is
    left, so a flag that genuinely had two real publishers keeps them — this cannot
    strip real provenance even if it is run on the wrong database.

    `status` goes back to `unconfirmed` and `confirmed_at` to null. That is right for
    the demo flags, and it is why the pick query avoids anything already confirmed:
    nothing here should be able to demote a flag that two real outlets corroborated.
    """
    rows = (await db.execute(_RESET, {"demo_id": DEMO_SOURCE_ID, "demo_like": f"%{DEMO_SOURCE_ID}%"})).all()
    await db.commit()
    return [str(r[0]) for r in rows]
