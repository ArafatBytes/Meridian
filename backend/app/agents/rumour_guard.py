"""
Rumour Guard — four outlets reporting one fire become one confirmed flag, not four.

D05, source S15. The plan calls S15 *"the subtlest correctness requirement in the
system"*, and the reason is that both failure directions are bad in different ways:

* **Under-merging** turns one event into four flags. The map says four fires. Worse,
  each stays `unconfirmed` forever, because corroboration that arrived was counted
  as a separate claim — so reading four outlets makes the surface *less* certain
  than reading one.
* **Over-merging** folds two genuinely different events into one, and the second
  one silently stops existing. A fire in Bangshal is then "corroborating" an
  accident in Mirpur.

The gate below is therefore conservative on purpose, and when it cannot decide it
**declines to merge**. Declining costs a duplicate pin. Merging wrongly costs a
wrong claim, and a wrong claim with a `confirmed` badge on it is the single worst
output this system can produce.

---

## How two reports are judged to be one event

Four gates, **all** of which must pass. The first three are SQL and nearly free;
the fourth is the embedding, and it only ever runs on the handful of rows the first
three let through.

| Gate | Why |
|---|---|
| same `kind` | A fire and an accident on one corner are two events, however similar the prose |
| centroids within `max(radius_a, radius_b)`, capped | Two claims that do not overlap are not the same claim |
| `observed_at` within `DEDUP_WINDOW_HOURS` | Outlets follow each other within hours; a week apart is a different fire |
| cosine similarity ≥ threshold | The actual judgement: do these describe the same thing |

## What gets embedded, and why it is the English summary

`extracted_incidents.summary_en` — the extraction model's own one-line English
description. Two reasons it beats the Bangla headline:

1. **It is already normalised.** Two outlets write a headline differently on
   purpose; the extraction model describes the same event in nearly the same
   English words, which is exactly the signal wanted here.
2. **It keeps the model small.** `all-MiniLM-L6-v2` is ~90 MB and English-only. The
   multilingual alternative is ~470 MB for text we do not need to embed. If Bangla
   text ever goes through here, swap `DEDUP_MODEL` for
   `paraphrase-multilingual-MiniLM-L12-v2` and change nothing else.

There is **no embedding column and no pgvector**. Candidate summaries are re-embedded
at comparison time, which is affordable precisely because the SQL gates run first:
a typical run compares one new summary against zero to three existing ones. A vector
column would be the right answer at a thousand flags an hour; at twelve a run it
would be a schema dependency bought for nothing.

## Source accounting: one reference per publisher

When a merge happens, the new publisher's `SourceRef` is appended **only if that
publisher is not already cited**. So `source_count == len(sources) == number of
independent publishers`, which keeps all three of `risk_flags`'s constraints and
`tests/invariants/test_single_source_never_confirmed.py` true of live data for the
same reason they are true of the fixture.

A same-outlet follow-up therefore does **not** inflate corroboration. It is still
recorded in full in `extracted_incidents` — the audit trail keeps every article,
the flag keeps every *publisher*.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.risk import IncidentKind
from app.core.config import settings
from app.policy.independence import independent_publishers, is_confirmable

logger = logging.getLogger(__name__)

__all__ = [
    "DuplicateMatch",
    "MergeOutcome",
    "cosine_similarity",
    "embed",
    "embeddings_available",
    "find_duplicate",
    "merge_into",
    "within_distance",
]


# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------

DEDUP_MAX_DISTANCE_M: Final[int] = 3_000
"""
Hard cap on how far apart two reports of "one event" may be, whatever their radii.

Without it, a chronic flag with a 12 km radius would swallow every news flag in
Dhaka. The radius test stays — this is the ceiling on it.
"""

_MIN_SUMMARY_CHARS: Final[int] = 12
"""
Below this, a summary carries no signal and the embedding is noise. Decline instead.
"""


# ---------------------------------------------------------------------------
# The embedding model, loaded once, lazily, and allowed to be absent
# ---------------------------------------------------------------------------

_MODEL: Any = None
_MODEL_FAILED = False


def embeddings_available() -> bool:
    """
    Can we embed at all? Loads the model on first call.

    A `False` here is **not** fatal and must not be: the whole ingestion run would
    otherwise die because a 90 MB download failed, and D04's offline path has no
    model at all. The caller's correct response to `False` is to publish the flag
    as its own `unconfirmed` event — which is exactly what the system did before
    this module existed.
    """
    global _MODEL, _MODEL_FAILED
    if _MODEL is not None:
        return True
    if _MODEL_FAILED:
        return False
    try:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(settings.DEDUP_MODEL)
        logger.info("rumour_guard: loaded %s", settings.DEDUP_MODEL)
        return True
    except Exception as exc:  # pragma: no cover - environment dependent
        _MODEL_FAILED = True
        logger.warning(
            "rumour_guard: no embedding model (%s: %s). Deduplication is OFF for this "
            "process: every incident becomes its own unconfirmed flag, nothing is "
            "merged and nothing is promoted. That is the safe failure, not a silent "
            "one -- a flag is never confirmed by guesswork.",
            type(exc).__name__,
            exc,
        )
        return False


def embed(texts: list[str]) -> list[list[float]] | None:
    """Unit-normalised embeddings, or None when the model is unavailable."""
    if not texts or not embeddings_available():
        return None
    vectors = _MODEL.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [[float(x) for x in row] for row in vectors]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Cosine similarity, not assuming the inputs are normalised.

    `embed()` normalises, so this is usually a dot product — but it is also called
    from tests with hand-written vectors, and a function that silently requires
    normalisation is a function that will one day be handed something else.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return 0.0 if norm == 0.0 else float(dot / norm)


# ---------------------------------------------------------------------------
# Pure geometry, so it is testable without PostGIS
# ---------------------------------------------------------------------------


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres. Mean Earth radius; good to ~0.5%."""
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return float(2 * radius * math.asin(min(1.0, math.sqrt(h))))


def within_distance(
    *,
    lat_a: float,
    lon_a: float,
    radius_a: int,
    lat_b: float,
    lon_b: float,
    radius_b: int,
) -> bool:
    """
    Do these two claims overlap enough to be the same event?

    The allowance is the **larger** of the two radii, capped at
    `DEDUP_MAX_DISTANCE_M`. Larger rather than smaller because a report located only
    to "Mirpur" (1.2 km) genuinely might be the same fire as one located to a
    specific crossing (300 m); requiring the tighter radius would refuse to merge
    precisely the vague-plus-precise pair that most needs merging.
    """
    allowance = min(DEDUP_MAX_DISTANCE_M, max(radius_a, radius_b))
    return _haversine_m(lat_a, lon_a, lat_b, lon_b) <= allowance


# ---------------------------------------------------------------------------
# Candidate lookup
# ---------------------------------------------------------------------------

_CANDIDATES: Final = text(
    """
    select f.flag_id,
           f.event_key,
           f.status,
           f.source_count,
           f.sources::text as sources_json,
           f.radius_m,
           f.observed_at,
           extensions.ST_Y(f.location::extensions.geometry) as lat,
           extensions.ST_X(f.location::extensions.geometry) as lon,
           coalesce(
               (select string_agg(e.summary_en, ' | ' order by e.created_at)
                  from public.extracted_incidents e
                 where e.flag_id = f.flag_id and e.summary_en is not null),
               ''
           ) as summaries
      from public.risk_flags f
     where f.kind = :kind
       and f.status in ('unconfirmed', 'confirmed')
       and f.expires_at > :now
       and f.observed_at between :since and :until
       and extensions.ST_DWithin(
               f.location,
               extensions.ST_SetSRID(
                   extensions.ST_MakePoint(:lon, :lat), 4326
               )::extensions.geography,
               :max_distance_m
           )
     order by f.observed_at desc
     limit :limit
    """
)

_MAX_CANDIDATES: Final[int] = 10


@dataclass(frozen=True)
class DuplicateMatch:
    """An existing flag judged to be the same event as the incoming incident."""

    flag_id: UUID
    event_key: str
    similarity: float
    status: str
    source_ids: frozenset[str]


async def find_duplicate(
    db: AsyncSession,
    *,
    kind: IncidentKind,
    lat: float,
    lon: float,
    radius_m: int,
    observed_at: datetime,
    summary_en: str | None,
    now: datetime,
) -> DuplicateMatch | None:
    """
    The existing flag this incident is another account of, or None.

    Returns None — decline to merge — whenever the judgement cannot be made
    confidently: no usable summary, no embedding model, no candidate inside the
    spatial and temporal gates, or nothing above the similarity threshold. Every one
    of those is a vote for "publish it separately as unconfirmed", which is the
    failure that costs a duplicate pin rather than a wrong claim.
    """
    summary = (summary_en or "").strip()
    if len(summary) < _MIN_SUMMARY_CHARS:
        logger.info("rumour_guard: no usable summary to compare; not merging")
        return None

    window = timedelta(hours=settings.DEDUP_WINDOW_HOURS)
    rows = (
        await db.execute(
            _CANDIDATES,
            {
                "kind": kind.value,
                "now": now,
                "since": observed_at - window,
                "until": observed_at + window,
                "lat": lat,
                "lon": lon,
                "max_distance_m": DEDUP_MAX_DISTANCE_M,
                "limit": _MAX_CANDIDATES,
            },
        )
    ).mappings().all()

    candidates = [
        row
        for row in rows
        if (row["summaries"] or "").strip()
        and within_distance(
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

    vectors = embed([summary] + [str(row["summaries"]) for row in candidates])
    if vectors is None:
        return None  # model unavailable — see embeddings_available()

    incoming, existing = vectors[0], vectors[1:]
    scored = [
        (cosine_similarity(incoming, vec), row) for vec, row in zip(existing, candidates, strict=True)
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    best_similarity, best = scored[0]

    if best_similarity < settings.DEDUP_SIMILARITY_THRESHOLD:
        logger.info(
            "rumour_guard: closest candidate %s scored %.3f, below %.2f -- treating as a "
            "new event",
            best["event_key"],
            best_similarity,
            settings.DEDUP_SIMILARITY_THRESHOLD,
        )
        return None

    source_ids = frozenset(
        s.get("source_id", "") for s in json.loads(best["sources_json"] or "[]")
    )
    logger.info(
        "rumour_guard: same event as %s (similarity %.3f, publishers %s)",
        best["event_key"],
        best_similarity,
        sorted(source_ids),
    )
    return DuplicateMatch(
        flag_id=best["flag_id"]
        if isinstance(best["flag_id"], UUID)
        else UUID(str(best["flag_id"])),
        event_key=str(best["event_key"]),
        similarity=best_similarity,
        status=str(best["status"]),
        source_ids=source_ids,
    )


# ---------------------------------------------------------------------------
# Merge and promote
# ---------------------------------------------------------------------------

_MERGE: Final = text(
    """
    update public.risk_flags
       set sources      = cast(:sources as jsonb),
           source_count = :source_count,
           status       = :status,
           -- coalesce, not assignment: passing null must PRESERVE an existing
           -- confirmation time, not erase it. A flag confirmed at 14:31 that picks
           -- up a third publisher at 16:02 was still confirmed at 14:31.
           confirmed_at = coalesce(:confirmed_at, confirmed_at),
           updated_at   = now()
     where flag_id = :flag_id
    """
)


@dataclass(frozen=True)
class MergeOutcome:
    """What a merge did. `promoted` is the thing demo beat 2 is about."""

    flag_id: UUID
    event_key: str
    source_count: int
    status: str
    promoted: bool
    already_cited: bool


async def merge_into(
    db: AsyncSession,
    match: DuplicateMatch,
    *,
    source: dict[str, Any],
    now: datetime,
) -> MergeOutcome:
    """
    Add this publisher's account to an existing flag, promoting it if that earns it.

    Three things happen here and the order is not interesting, but the rules are:

    1. **The reference is appended only if the publisher is not already cited.** One
       `SourceRef` per publisher — see the module docstring. A second article from an
       outlet already on the flag changes nothing about the flag.
    2. `source_count` is recomputed as the number of **independent** publishers via
       `policy.independence`, never incremented. Incrementing is how a count drifts
       away from the list it is supposed to summarise.
    3. Promotion to `confirmed` happens only when that count reaches
       `MIN_SOURCES_FOR_CONFIRMED`, and `confirmed_at` is stamped exactly once — on
       the transition. A flag already confirmed keeps its original confirmation time,
       because that is when we decided to believe it.

    Note what is **not** updated: `observed_at`, `severity_0` and `mobility_statement`
    stay as the first report left them. The event did not move or change because
    somebody else wrote about it, and re-framing the statement from a second article
    would mean two publishers' phrasings fighting over one string.
    """
    source_id = str(source.get("source_id", ""))
    already_cited = source_id in match.source_ids

    existing_refs: list[dict[str, Any]] = []
    rows = (
        await db.execute(
            text("select sources::text as sources_json from public.risk_flags where flag_id = :id"),
            {"id": str(match.flag_id)},
        )
    ).mappings().first()
    if rows is not None:
        existing_refs = json.loads(rows["sources_json"] or "[]")

    refs = existing_refs if already_cited else [*existing_refs, source]
    publishers = independent_publishers(
        str(ref.get("source_id", "")) for ref in refs if ref.get("source_id")
    )
    source_count = max(1, len(publishers))

    was_confirmed = match.status == "confirmed"
    # `is_confirmable` rather than a bare count since 2026-10-16: one vetted
    # publisher is enough, and corroboration remains the route for anything
    # that is not on that list. Never demotes -- `was_confirmed` wins -- because
    # a flag that was confirmed does not become doubtful when another outlet
    # agrees with it.
    confirmed = was_confirmed or is_confirmable(
        (str(ref.get("source_id", "")) for ref in refs if ref.get("source_id")),
        minimum=settings.MIN_SOURCES_FOR_CONFIRMED,
    )
    status = "confirmed" if confirmed else "unconfirmed"
    promoted = confirmed and not was_confirmed

    await db.execute(
        _MERGE,
        {
            "flag_id": str(match.flag_id),
            "sources": json.dumps(refs, ensure_ascii=False),
            "source_count": source_count,
            "status": status,
            # Non-null only on the transition. The `coalesce` in _MERGE means a flag
            # that was already confirmed keeps the time it was first confirmed, so
            # re-reading a third article does not keep moving the moment we decided
            # to believe it.
            "confirmed_at": now if promoted else None,
        },
    )

    if promoted:
        logger.info(
            "rumour_guard: PROMOTED %s to confirmed on %d independent publishers (%s)",
            match.event_key,
            source_count,
            sorted(publishers),
        )
    elif already_cited:
        logger.info(
            "rumour_guard: %s already cites %s -- a second article from one outlet is "
            "not corroboration",
            match.event_key,
            source_id,
        )
    else:
        logger.info(
            "rumour_guard: merged %s into %s, now %d publisher(s), still %s",
            source_id,
            match.event_key,
            source_count,
            status,
        )

    return MergeOutcome(
        flag_id=match.flag_id,
        event_key=match.event_key,
        source_count=source_count,
        status=status,
        promoted=promoted,
        already_cited=already_cited,
    )
