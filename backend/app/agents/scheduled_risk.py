"""
Scheduled Risk Agent — tomorrow's map. DEMO_PLAN.md D09, source sprint S26.

    news sitemaps ─ list_recent ─▶ announcement filter ─▶ read ─▶ raw_documents
         ─▶ extraction (ScheduledExtraction) ─▶ gazetteer
              ─▶ risk_flags with valid_from / valid_to  (forward-dated)
              └─▶ extracted_incidents (every event, published or not)

This is the Live Risk Agent's complement, and the split is in the prompts. D04's
tells the model to *ignore* "court cases, arrests, statements and announcements"
and report only what is happening today. That instruction throws away a whole
class of article Dhaka papers are full of: a procession called for tomorrow
morning, a hartal announced for Sunday, drainage work starting at ten. Those are
the only articles this agent reads.

**Why forward-dating is worth an agent of its own.** Every competing product can
tell you a road is blocked once it is blocked. None of them can tell you at
dinner tonight that it will be blocked when you leave in the morning, because
none of them read the announcement. The data to do it is published, in Bangla, in
public, hours ahead.

Four rules carry the design, all checked without a database or a model in
`tests/invariants/test_scheduled_flags_are_windows.py`:

1. **Every flag carries a window.** `valid_from` and `valid_to` are never null on
   this agent's output; a scheduled flag with no window is just a flag with a
   wrong time, and the surface serves it from the moment it is written.
2. **A window in the past is not published.** By the time a run reads an article
   the event may be over. That is `rejected`, with the row kept.
3. **No place is guessed**, and the gazetteer-only path is shared verbatim with
   D04 — same `resolve_news_place`, same `allow_llm=False`, same
   `unresolved_location` outcome.
4. **The model is never asked for an instant.** It answers a three-way day and an
   integer hour; `_window()` does the arithmetic from the article's publication
   date. See `ScheduledDay` for the measurement behind that.

## What this agent deliberately does not do

**No retry queue.** D04 keeps unextracted documents and picks them up next run,
because a road accident is worth catching late. An announcement read six hours
late is usually an announcement about an event that has already started, and the
window test would discard it anyway. Each run extracts only what it fetched.

**No separate LLM feature key.** It reads news, exactly as D04 does, so it spends
`LLM_CHAIN_EXTRACT` and `FEATURE_EXTRACT`. A second key would be a second thing to
provision and rotate for no behavioural difference.

**No new framing.** `to_mobility_statement` produces present-tense text — "Road
blocked near Shahbagh" — and that is correct here rather than a gap, because a
scheduled flag is only ever *served* at an instant inside its own window. The
tense matches the moment you are looking at. The UI, not the statement, is what
says "Scheduled" and shows the window.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.live_risk import (
    EXCLUDED_SECTIONS,
    MAX_BODY_CHARS,
    MIN_CONFIDENCE,
    boundary_pattern,
    interleave,
    resolve_news_place,
)
from app.contracts.agents import AgentContext, AgentResult, AgentStatus, BaseAgent
from app.contracts.risk import GeoResolution, IncidentKind, MobilityImpact, RawDocument
from app.ingestion import store
from app.ingestion.fetcher import Fetcher
from app.ingestion.sources import SOURCES, ArticleRef, Source
from app.ingestion.sources.base import DHAKA_TZ
from app.llm.client import FEATURE_EXTRACT, LLMUnavailable, complete
from app.llm.models import ScheduledEvent, ScheduledExtraction
from app.policy.framing import to_mobility_statement
from app.scoring.kinds import defaults_for, severity_for

logger = logging.getLogger(__name__)

SCHEDULED_KEY_PREFIX: Final = "sched-"
"""Every flag this agent writes. Distinct from D04's `live-` and the seeder's `seed-`."""

LOOKBACK: Final = timedelta(hours=18)
"""
How far back to look for announcements, against D04's 12.

Longer because an announcement is useful for as long as the event it announces has
not happened: an article published yesterday evening about tomorrow morning is
exactly what this agent is for. It is not much longer, because the window test
below is what actually decides, and listing a day of articles costs requests.
"""

MAX_READS_PER_SOURCE: Final = 6
MAX_EXTRACTIONS_PER_RUN: Final = 8

DAY_OFFSET: Final[dict[str, int]] = {"today": 0, "tomorrow": 1, "day_after": 2}

DEFAULT_DURATION_HOURS: Final[dict[IncidentKind, float]] = {
    # A procession or rally occupies a road for an afternoon, not a day.
    IncidentKind.PROCESSION: 4.0,
    # A called hartal or blockade is announced by the day, dawn to dusk.
    IncidentKind.BLOCKADE: 12.0,
    # Works run a shift, and are usually re-announced if they continue.
    IncidentKind.CONSTRUCTION: 10.0,
    IncidentKind.UTILITY_OUTAGE: 8.0,
}
"""
How long an event lasts when the article does not say — which is most of the time,
because Bangla copy announces a start and leaves the end to the reader.

A default rather than an open-ended window: `valid_to` is what retires a scheduled
flag, so a null end date would leave a procession on the map until its decay curve
expired, which for `construction` is thirty days. Four hours of wrongly-claimed
road beats a month of it.
"""

FALLBACK_DURATION_HOURS: Final = 6.0

# Headline vocabulary for a *future* event. Deliberately different from D04's
# INCIDENT_WORDS, which match the event itself: these match the announcement of
# one. An article has to contain a future marker (আগামীকাল, আগামী, কর্মসূচি) AND
# an event word, or every weather forecast and cricket fixture in the paper gets
# fetched.
FUTURE_WORDS: Final = (
    "আগামীকাল",
    "আগামী",
    "কাল",
    "পরশু",
    "আজ",
    "ঘোষণা",
    "ডাক",
    "ডেকেছে",
    "কর্মসূচি",
    "কর্মসূচী",
    "হবে",
    "চলবে",
    "শুরু",
    "অনুষ্ঠিত",
    "পালিত",
    "নির্ধারিত",
    "বন্ধ থাকবে",
)

# Events worth a pin when they are announced. A shorter list than D04's, because an
# announcement of an accident is not a thing — nobody schedules a collision.
EVENT_WORDS: Final = (
    "হরতাল",
    "অবরোধ",
    "ধর্মঘট",
    "মিছিল",
    "সমাবেশ",
    "মানববন্ধন",
    "শোভাযাত্রা",
    "বিক্ষোভ",
    "গণজমায়েত",
    "জমায়েত",
    "কর্মবিরতি",
    "পরীক্ষা",
    "ভর্তি পরীক্ষা",
    "সংস্কার",
    "খোঁড়াখুঁড়ি",
    "নির্মাণকাজ",
    "মেট্রোরেল",
    "সড়ক বন্ধ",
    "যান চলাচল বন্ধ",
    "ডাইভারশন",
    "রুট পরিবর্তন",
    "বিদ্যুৎ বন্ধ",
    "গ্যাস সরবরাহ",
    "পানি সরবরাহ",
)

# The English halves, for Dhaka Tribune (added 2026-10-14). Matched between word
# boundaries, with every inflection spelled out, for the reason recorded at
# `live_risk.INCIDENT_WORDS_EN` — a suffix wildcard reintroduces exactly the false
# positives the boundary exists to stop.
#
# Both halves are still required, which is what keeps these broad lists cheap:
# `tomorrow` alone is every weather forecast, `rally` alone is this afternoon's
# procession, and only their conjunction is an announcement of a road event.
FUTURE_WORDS_EN: Final = (
    "tomorrow",
    "today",
    "tonight",
    "next",
    "upcoming",
    "announce",
    "announces",
    "announced",
    "announcement",
    "call",
    "calls",
    "called",
    "programme",
    "program",
    "schedule",
    "scheduled",
    "will",
    "to be held",
    "begins",
    "begin",
    "start",
    "starts",
    "starting",
    "ahead of",
    "observe",
)

EVENT_WORDS_EN: Final = (
    "hartal",
    "blockade",
    "blockades",
    "strike",
    "strikes",
    "procession",
    "processions",
    "rally",
    "rallies",
    "gathering",
    "human chain",
    "protest",
    "protests",
    "demonstration",
    "demonstrations",
    "march",
    "siege",
    "gherao",
    "exam",
    "exams",
    "admission test",
    "repair",
    "repairs",
    "digging",
    "construction",
    "metro rail",
    "road closure",
    "road closed",
    "diversion",
    "route change",
    "power outage",
    "gas supply",
    "water supply",
    "shutdown",
)


_FUTURE_PATTERN_EN: Final = boundary_pattern(FUTURE_WORDS_EN)
_EVENT_PATTERN_EN: Final = boundary_pattern(EVENT_WORDS_EN)

SYSTEM_PROMPT: Final = (
    "You read Bangla and English news articles for a navigation app in Dhaka, "
    "Bangladesh. "
    "List only events that have NOT HAPPENED YET and will affect movement on roads "
    "inside Dhaka city: announced processions, rallies, hartals, blockades, "
    "strikes, large gatherings, exam days, scheduled road works, and announced "
    "closures of a road or a utility. "
    "An event that is already happening or already over is NOT one of these — "
    "return nothing for it. "
    "For each, give location_text: the most specific place name, copied from the "
    "article in its own script, without words like রাজধানীর, এলাকায় or নম্বর "
    "(write শাহবাগ মোড়, not রাজধানীর শাহবাগ মোড় এলাকায়). "
    "In an English article, copy the romanised name the same way: write "
    "Shahbagh intersection, not the capital's Shahbagh intersection area. Keep any "
    "number that is part of the name. "
    # See the same clause in live_risk.py for why this is phrased as permission.
    # It matters more here: this agent has no retry queue, so an announcement it
    # locates to a road the gazetteer cannot place is the only chance to publish
    # that event before it happens.
    "A road name is a place name: write সাতমসজিদ রোড or Satmasjid Road when that "
    "is the most specific place the article names. "
    "day is today, tomorrow or day_after, relative to THIS ARTICLE's date. "
    "start_hour is the hour it begins, 0-23, Bangladesh time. Set end_hour only if "
    "the article states when it ends; otherwise leave it null. Never guess a time: "
    "if the article gives no hour at all, do not list the event. "
    "mobility_impact is road_blocked, heavy_crowd, delay_likely, lane_closed, "
    "impassable, or none if traffic is not affected. "
    "Ignore events outside Dhaka city, court dates, political statements with no "
    "street event, and anything already in the past. Most articles announce no "
    "such event: then return an empty list. "
    "Never invent a place or a time the article does not give."
)


# ---------------------------------------------------------------------------
# Pure decisions — tested without a database or a model
# ---------------------------------------------------------------------------


def is_announcement(ref: ArticleRef, now: datetime) -> bool:
    """
    Worth fetching? Recent, not from an excluded desk, and the headline reads like
    an announcement of a road event.

    Both halves are required. `আগামীকাল` alone matches tomorrow's weather and
    tomorrow's match; `মিছিল` alone matches the procession that happened this
    afternoon, which is D04's article and not ours.

    The two halves may be satisfied in **different languages**, which is not an
    oversight: Dhaka English copy writes "hartal called for tomorrow", where the
    event word is a loan from Bangla and the future marker is English.
    """
    if ref.section in EXCLUDED_SECTIONS:
        return False
    if ref.published_at is not None and ref.published_at < now - LOOKBACK:
        return False
    has_future = any(w in ref.title for w in FUTURE_WORDS) or bool(
        _FUTURE_PATTERN_EN.search(ref.title)
    )
    has_event = any(w in ref.title for w in EVENT_WORDS) or bool(
        _EVENT_PATTERN_EN.search(ref.title)
    )
    return has_future and has_event


def _window(event: ScheduledEvent, published_at: datetime) -> tuple[datetime, datetime]:
    """
    The event's `valid_from` and `valid_to`, in UTC.

    Built from the article's own publication date — which we know — plus the day and
    hour the model read out of the copy. The model is never asked for an instant;
    see `ScheduledDay`.

    Two edge cases, both resolved towards a shorter window rather than a longer one:

    * **`end_hour` at or before `start_hour`.** Either the event crosses midnight or
      the model misread, and there is no way to tell which from one integer. The
      per-kind default duration is used instead, because a window that is wrong by
      a few hours costs less than one that is wrong by a day.
    * **No `end_hour` at all**, which is the common case: same default.
    """
    local_date = published_at.astimezone(DHAKA_TZ).date()
    day = local_date + timedelta(days=DAY_OFFSET[event.day])
    start = datetime(
        day.year, day.month, day.day, event.start_hour, tzinfo=DHAKA_TZ
    ).astimezone(UTC)

    if event.end_hour is not None and event.end_hour > event.start_hour:
        end = datetime(
            day.year, day.month, day.day, event.end_hour, tzinfo=DHAKA_TZ
        ).astimezone(UTC)
    else:
        kind = IncidentKind(event.kind)
        hours = DEFAULT_DURATION_HOURS.get(kind, FALLBACK_DURATION_HOURS)
        end = start + timedelta(hours=hours)

    return start, end


def discard_reason(
    event: ScheduledEvent, place: GeoResolution, valid_to: datetime, now: datetime
) -> str | None:
    """
    Why an announced event must not become a flag, or None if it may.

    The order matters only for which reason gets recorded; all four are terminal.
    `rejected` carries two different situations — no road impact, and a window that
    has already closed — because `extracted_incidents.discarded_reason` has a CHECK
    constraint listing four values and neither of these is worth a migration to
    name separately. The log line says which.
    """
    if event.confidence < MIN_CONFIDENCE:
        return "low_confidence"
    if place.method == "unresolved":
        return "unresolved_location"
    if event.mobility_impact == MobilityImpact.NONE:
        return "rejected"
    if valid_to <= now:
        # Announced for a window that has already closed. Reading yesterday's paper
        # about yesterday afternoon is normal and is not an error.
        return "rejected"
    return None


def flag_row(
    *,
    doc: RawDocument,
    index: int,
    event: ScheduledEvent,
    place: GeoResolution,
    valid_from: datetime,
    valid_to: datetime,
) -> dict[str, Any]:
    """
    One announced event as an insert-shaped `risk_flags` row.

    Three fields differ from D04's `flag_row`, and they are the whole point:

    * `valid_from` / `valid_to` are set, so the surface serves this only inside the
      window and `decay.decay_anchor` measures decay from the start of the event
      rather than from when it was announced.
    * `observed_at` is the announcement's publication time. That is honest —
      nothing was observed — and it is what the flag sheet labels "Announced".
    * `event_key` carries `sched-`, so this agent's rows can be told apart from
      D04's and the seeder's without parsing anything.

    `status` is `unconfirmed` with one source, for exactly D04's reason: this agent
    does not verify. Rumour Guard does, and the database refuses a single-source
    `confirmed` row in any case.
    """
    kind = IncidentKind(event.kind)
    defaults = defaults_for(kind)
    observed_at = doc.published_at or doc.fetched_at
    return {
        "event_key": f"{SCHEDULED_KEY_PREFIX}{doc.doc_id[:16]}-{index}",
        "kind": kind.value,
        "status": "unconfirmed",
        "lat": place.lat,
        "lon": place.lon,
        "radius_m": min(20_000, max(defaults.radius_m, place.radius_m)),
        "severity_0": severity_for(kind, event.severity_hint),
        "half_life_hours": defaults.half_life_hours,
        "observed_at": observed_at,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "source_count": 1,
        "sources": [
            {
                "source_id": doc.source_id,
                "url": doc.url,
                "published_at": observed_at.isoformat(),
                "title": doc.title,
                "snippet": None,
            }
        ],
        "mobility_statement": to_mobility_statement(
            kind=kind, impact=event.mobility_impact, place=place.resolved_name
        ),
    }


def user_prompt(doc: RawDocument) -> str:
    published = doc.published_at.isoformat() if doc.published_at else "unknown"
    return f"Headline: {doc.title}\nPublished: {published}\n\n{doc.body[:MAX_BODY_CHARS]}"


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

_INSERT_FLAG: Final = text(
    """
    insert into public.risk_flags
        (event_key, kind, status, location, radius_m, severity_0, half_life_hours,
         observed_at, valid_from, valid_to, source_count, sources, mobility_statement)
    values
        (:event_key, :kind, :status,
         extensions.ST_SetSRID(extensions.ST_MakePoint(:lon, :lat), 4326)::extensions.geography,
         :radius_m, :severity_0, :half_life_hours, :observed_at, :valid_from, :valid_to,
         :source_count, cast(:sources as jsonb), :mobility_statement)
    returning flag_id
    """
)
"""
A plain insert, exactly as D04 does, and **no `on conflict`**: `event_key` is
indexed on `risk_flags` but deliberately not unique, because four outlets reporting
one fire are meant to share one. There is no unique constraint for an upsert to
target.

**Cross-article corroboration is deliberately not wired in here.** The same
procession announced by two outlets produces two pins, because `rumour_guard`'s
`find_duplicate` compares events by location, kind and *observed time*, and for a
scheduled flag `observed_at` is when the announcement was published — two papers
can carry the same call a day apart. Running it anyway risks merging two different
events into one `confirmed` claim, and the project's stated asymmetry applies: a
duplicate pin is a cosmetic cost, a wrongly confirmed flag is not. Matching
announcements on their *window* instead is the right fix and it is not a D09-sized
one.
"""

_INSERT_INCIDENT: Final = text(
    """
    insert into public.extracted_incidents
        (doc_id, kind, summary_en, location_text, severity_hint, mobility_impact,
         extraction_confidence, source, flag_id, discarded_reason)
    values
        (:doc_id, :kind, :summary_en, :location_text, :severity_hint, :mobility_impact,
         :confidence, cast(:source as jsonb), :flag_id, :discarded_reason)
    """
)


async def _publish(
    db: AsyncSession, doc: RawDocument, index: int, event: ScheduledEvent, ctx: AgentContext
) -> tuple[bool, str | None]:
    """Write one announced event and, if it qualifies, its forward-dated flag."""
    place = await resolve_news_place(event.location_text)
    published_at = doc.published_at or doc.fetched_at
    valid_from, valid_to = _window(event, published_at)
    reason = discard_reason(event, place, valid_to, ctx.now)

    logger.info(
        "%s #%d %s at %r for %s %02d:00 -> %s",
        doc.source_id,
        index,
        event.kind,
        event.location_text,
        event.day,
        event.start_hour,
        reason or f"scheduled flag near {place.resolved_name} "
        f"({valid_from.isoformat()} .. {valid_to.isoformat()})",
    )
    if ctx.dry_run:
        return reason is None, reason

    source = {
        "source_id": doc.source_id,
        "url": doc.url,
        "title": doc.title,
        "published_at": published_at.isoformat(),
    }

    flag_id = None
    if reason is None:
        row = flag_row(
            doc=doc,
            index=index,
            event=event,
            place=place,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        result = await db.execute(
            _INSERT_FLAG, {**row, "sources": json.dumps(row["sources"], ensure_ascii=False)}
        )
        flag_id = result.scalar_one()

    await db.execute(
        _INSERT_INCIDENT,
        {
            "doc_id": doc.doc_id,
            "kind": event.kind,
            "summary_en": event.summary_en,
            "location_text": event.location_text,
            "severity_hint": event.severity_hint,
            "mobility_impact": event.mobility_impact.value,
            "confidence": event.confidence,
            "source": json.dumps(source, ensure_ascii=False),
            "flag_id": flag_id,
            "discarded_reason": reason,
        },
    )
    return reason is None, reason


# ---------------------------------------------------------------------------
# The agent
# ---------------------------------------------------------------------------


class ScheduledRiskAgent(BaseAgent):
    name = "scheduled_risk"
    cron = "20 * * * *"
    """
    Hourly, at twenty past — not D04's every fifteen minutes.

    An announcement does not get more urgent while you wait, and it stays true for
    hours. Offset from the hour so it does not contend with the live agent's
    on-the-hour run for the same free-tier quota.
    """

    async def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.db is None:
            raise RuntimeError("scheduled_risk needs ctx.db; the runner provides it")
        db = ctx.db
        errors: list[str] = []
        metrics: dict[str, float] = dict.fromkeys(
            (
                "listed",
                "announcements",
                "fetched",
                "documents_read",
                "events",
                "published",
                "low_confidence",
                "unresolved_location",
                "rejected",
            ),
            0.0,
        )

        by_source: list[list[RawDocument]] = []
        async with Fetcher() as fetcher:
            for source in SOURCES:
                try:
                    by_source.append(await self._ingest(source, fetcher, db, ctx, metrics, errors))
                    if not ctx.dry_run:
                        await db.commit()
                except Exception as problem:  # noqa: BLE001 - one publisher must not stop the rest
                    await db.rollback()
                    errors.append(f"{source.source_id}: {type(problem).__name__}: {problem}")

        # No retry queue, deliberately. See the module docstring — which is exactly
        # why the round-robin matters more here than in D04: a document this agent
        # does not extract in the run that fetched it is not deferred, it is gone,
        # and with it the only chance to publish an event *before* it happens. Under
        # the old concatenate-then-truncate, every publisher after the second in
        # `SOURCES` would have had its announcements silently dropped, for ever.
        queue = interleave(by_source)[:MAX_EXTRACTIONS_PER_RUN]

        consecutive_misses = 0
        for doc in queue:
            try:
                extraction = await complete(
                    SYSTEM_PROMPT,
                    user_prompt(doc),
                    ScheduledExtraction,
                    feature=FEATURE_EXTRACT,
                    max_tokens=1024,
                )
            except LLMUnavailable as problem:
                errors.append(f"extract {doc.doc_id[:12]}: {problem}")
                consecutive_misses += 1
                if consecutive_misses >= 2:
                    break  # rate limited or out of quota; next run tries again
                continue
            consecutive_misses = 0
            metrics["documents_read"] += 1
            try:
                for index, event in enumerate(extraction.events):
                    metrics["events"] += 1
                    published, reason = await _publish(db, doc, index, event, ctx)
                    metrics["published" if published else str(reason)] += 1
                if not ctx.dry_run:
                    await store.mark_extracted(db, doc.doc_id, ctx.now)
                    await db.commit()
            except Exception as problem:  # noqa: BLE001 - recorded, and the run continues
                await db.rollback()
                errors.append(f"publish {doc.doc_id[:12]}: {type(problem).__name__}: {problem}")

        status: AgentStatus = "ok"
        if errors:
            # `any(by_source)` is "did any publisher yield a document at all".
            # It used to read `not fresh`, against a flat list of every document
            # ingested; S30's round-robin replaced that list with one list per
            # publisher and missed this reference, leaving a `NameError` on a
            # path that only runs when something else has already gone wrong.
            nothing_worked = not any(by_source) and metrics["documents_read"] == 0
            status = "failed" if nothing_worked else "partial"
        return AgentResult(
            agent=self.name,
            run_id=ctx.run_id,
            started_at=ctx.now,
            finished_at=datetime.now(UTC),
            status=status,
            items_in=len(queue),
            items_out=int(metrics["published"]),
            errors=errors,
            metrics=metrics,
        )

    async def _ingest(
        self,
        source: Source,
        fetcher: Fetcher,
        db: AsyncSession,
        ctx: AgentContext,
        metrics: dict[str, float],
        errors: list[str],
    ) -> list[RawDocument]:
        """
        List, filter, read and store one publisher's new announcement articles.

        `known_urls` is what keeps the two news agents off each other: whichever
        stores a document first owns it, and the other skips it. Where that costs
        us an article it costs us one whose headline matched both filters, which is
        rare — D04's match the event, these match the announcement of one.
        """
        refs = await source.list_recent(fetcher, ctx.now)
        announcements = [ref for ref in refs if is_announcement(ref, ctx.now)]
        known = await store.known_urls(db, [ref.url for ref in announcements])
        to_read = [ref for ref in announcements if ref.url not in known][:MAX_READS_PER_SOURCE]
        metrics["listed"] += len(refs)
        metrics["announcements"] += len(announcements)

        stored: list[RawDocument] = []
        for ref in to_read:
            try:
                doc = await source.read(fetcher, ref, ctx.now)
            except Exception as problem:  # noqa: BLE001 - one article must not stop its source
                errors.append(f"{source.source_id} read {ref.url[-40:]}: {type(problem).__name__}")
                continue
            if doc is None:
                continue
            metrics["fetched"] += 1
            if ctx.dry_run or await store.save(db, doc):
                stored.append(doc)
        return stored


AGENT = ScheduledRiskAgent()
