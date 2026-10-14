"""
Crime Guard — four outlets reporting one robbery become one incident, not four.

The `news_crime_incidents` counterpart of `rumour_guard.py`, and a deliberately
thin one: it reuses that module's embedding, its cosine similarity, its distance
rule and its measured threshold, and changes only the three things that genuinely
differ for crime.

## Why not just call Rumour Guard

`find_duplicate` queries `risk_flags` and gates on `IncidentKind`. Neither applies
here — a different table, and a vocabulary with no `kind` in it. Generalising it
over both tables would mean parameterising the single most correctness-critical
function in the system, whose own docstring calls merging "the subtlest
correctness requirement", so that it could serve a second caller. Mirroring its
*structure* and importing its *primitives* keeps that function untouched and keeps
this file readable on its own.

## The three differences, and why each one

| | `rumour_guard` | here |
|---|---|---|
| first gate | same `kind` | same `category` |
| time window | `DEDUP_WINDOW_HOURS` (6) | `CRIME_WINDOW_HOURS` (48) |
| on no embedding | decline | decline |

**The window is the real difference.** Six hours is right for mobility: outlets
follow each other within hours and a fire a day later is a different fire. Crime
reporting does not work that way. A mugging is reported when the police confirm
it, a second outlet picks it up the next morning, and a third runs it when a
suspect is arrested two days later. A six-hour window would treat those as three
separate robberies on one corner — which is the *worse* of the two failure
directions here, because it turns one incident into a cluster of pins that looks
like a pattern. Forty-eight hours is the span over which Dhaka dailies actually
follow one another on a crime story.

The asymmetry Rumour Guard records still holds and matters more, not less:
**declining to merge costs a duplicate pin; merging wrongly costs a false claim.**
So every gate must pass, and an absent embedding model means decline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.rumour_guard import (
    cosine_similarity,
    embed,
    embeddings_available,
    within_distance,
)
from app.core.config import settings
from app.policy.independence import independent_publishers

logger = logging.getLogger(__name__)

CRIME_WINDOW_HOURS: Final[float] = 48.0
"""See the table in the module docstring. Eight times the mobility window."""

_MIN_SUMMARY_CHARS: Final[int] = 12
_MAX_CANDIDATES: Final[int] = 10


@dataclass(frozen=True, slots=True)
class CrimeMatch:
    """An existing incident judged to be the same event as the one being published."""

    incident_id: UUID
    source_ids: tuple[str, ...]
    similarity: float


_CANDIDATES: Final = text(
    """
    select incident_id,
           extensions.ST_Y(location::extensions.geometry) as lat,
           extensions.ST_X(location::extensions.geometry) as lon,
           radius_m,
           sources,
           source_count
    from public.news_crime_incidents
    where status = 'published'
      and category = :category
      and observed_at between :since and :until
      and extensions.ST_DWithin(
              location,
              extensions.ST_SetSRID(extensions.ST_MakePoint(:lon, :lat), 4326)::extensions.geography,
              :search_m)
    order by observed_at desc
    limit :limit
    """
)

_SUMMARIES: Final = text(
    """
    select summary_en
    from public.extracted_crimes
    where news_crime_id = :incident_id
    order by created_at asc
    limit 5
    """
)


async def find_duplicate(
    db: AsyncSession,
    *,
    category: str,
    lat: float,
    lon: float,
    radius_m: int,
    observed_at: datetime,
    summary_en: str,
    now: datetime,
) -> CrimeMatch | None:
    """
    The already-published incident this one is another account of, or None.

    Returns None — decline to merge — whenever the judgement cannot be made
    confidently: too short a summary to embed, no embedding model installed, no
    candidate that passes every gate. Declining costs a duplicate pin, and that is
    the cheaper mistake.
    """
    if len(summary_en.strip()) < _MIN_SUMMARY_CHARS:
        return None
    if not embeddings_available():
        logger.info("crime_guard: no embedding model; declining to merge")
        return None

    window = timedelta(hours=CRIME_WINDOW_HOURS)
    rows = (
        await db.execute(
            _CANDIDATES,
            {
                "category": category,
                "lat": lat,
                "lon": lon,
                "since": observed_at - window,
                "until": observed_at + window,
                # A generous SQL pre-filter; `within_distance` applies the real rule.
                "search_m": 3_000,
                "limit": _MAX_CANDIDATES,
            },
        )
    ).mappings().all()
    if not rows:
        return None

    candidates = [
        row
        for row in rows
        if within_distance(
            lat_a=lat,
            lon_a=lon,
            radius_a=radius_m,
            lat_b=float(row["lat"]),
            lon_b=float(row["lon"]),
            radius_b=int(row["radius_m"]),
        )
    ]
    if not candidates:
        return None

    best: CrimeMatch | None = None
    for row in candidates:
        summaries = [
            str(s)
            for (s,) in (
                await db.execute(_SUMMARIES, {"incident_id": row["incident_id"]})
            ).all()
        ]
        if not summaries:
            continue
        vectors = embed([summary_en, *summaries])
        if vectors is None:
            return None
        mine, theirs = vectors[0], vectors[1:]
        similarity = max(cosine_similarity(mine, other) for other in theirs)
        if similarity < settings.DEDUP_SIMILARITY_THRESHOLD:
            continue
        if best is None or similarity > best.similarity:
            best = CrimeMatch(
                incident_id=row["incident_id"],
                source_ids=tuple(
                    str(s.get("source_id", "")) for s in (row["sources"] or []) if s
                ),
                similarity=similarity,
            )
    return best


_MERGE: Final = text(
    """
    update public.news_crime_incidents
       set sources         = cast(:sources as jsonb),
           source_count    = :source_count,
           observed_at     = greatest(observed_at, :observed_at),
           corroborated_at = case
                                 when :source_count >= :minimum and corroborated_at is null
                                 then :now
                                 when :source_count >= :minimum
                                 then corroborated_at
                                 else null
                             end,
           statement       = :statement
     where incident_id = :incident_id
    returning incident_id
    """
)


async def merge_into(
    db: AsyncSession,
    match: CrimeMatch,
    *,
    source: dict[str, Any],
    sources: list[dict[str, Any]],
    statement: str,
    observed_at: datetime,
    now: datetime,
) -> UUID:
    """
    Add one publisher's account to an existing incident.

    The new `SourceRef` is appended **only if that publisher is not already
    cited**, so `source_count` counts publishers rather than articles and a
    same-outlet follow-up does not inflate corroboration. Identical accounting to
    `rumour_guard.merge_into`, and it has to be: both feed
    `policy/independence.py`, which collapses two mastheads of one house into one
    owner.

    The caller supplies the recomputed `statement` because this module may not
    write one — `policy/attribution.py` is the only producer, and it needs the
    publisher list that this merge decides.
    """
    await db.execute(
        _MERGE,
        {
            "incident_id": match.incident_id,
            "sources": json.dumps(sources, ensure_ascii=False),
            "source_count": len(independent_publishers(s["source_id"] for s in sources)),
            "observed_at": observed_at,
            "now": now,
            "minimum": settings.MIN_SOURCES_FOR_CONFIRMED,
            "statement": statement,
        },
    )
    logger.info(
        "crime_guard: merged %s into %s (similarity %.3f)",
        source.get("source_id"),
        match.incident_id,
        match.similarity,
    )
    return match.incident_id
