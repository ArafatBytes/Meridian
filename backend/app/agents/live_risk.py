"""
Live Risk Agent — today's news, on the map. DEMO_PLAN.md D04, source sprint S14.

    news sitemaps ─ list_recent ─▶ relevance filter ─▶ read ─▶ raw_documents
         ─▶ extraction (Gemini, NewsExtraction) ─▶ gazetteer ─▶ risk_flags (unconfirmed)
                                                     └─▶ extracted_incidents (every
                                                          incident, published or not)

Three rules carry the design, and each is checked by a test that does not need a
database or a model (`tests/invariants/test_live_flags_are_unconfirmed.py`):

1. **Every flag this agent writes is `unconfirmed` with one source.** Verification
   is D05's Rumour Guard and nothing else; the database refuses a single-source
   `confirmed` row anyway.
2. **No place is guessed.** Locations resolve through the gazetteer only
   (`allow_llm=False`): free, deterministic, and 93.3% on D03's eval with zero
   fabrications. A location the gazetteer does not know is recorded as
   `unresolved_location` and produces no pin.
3. **The pin's text comes from `framing.py`.** The model's own words go to the audit
   trail (`extracted_incidents.summary_en`) and never to a user.

Spending the free tier carefully
--------------------------------
Gemini's free tier is a few hundred requests a day for this feature's own project.
Two filters keep the agent inside it: headlines are matched against incident
vocabulary *before* an article is fetched, and at most `MAX_EXTRACTIONS_PER_RUN`
documents are read per run. Anything left over is in the retry queue
(`raw_documents.extracted_at is null`) for the next run.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.agents import AgentContext, AgentResult, AgentStatus, BaseAgent
from app.contracts.risk import GeoResolution, IncidentKind, MobilityImpact, RawDocument
from app.geo.agent import resolve_place
from app.ingestion import store
from app.ingestion.fetcher import Fetcher
from app.ingestion.sources import SOURCES, ArticleRef, Source
from app.llm.client import FEATURE_EXTRACT, LLMUnavailable, complete
from app.llm.models import NewsExtraction, NewsIncident
from app.policy.framing import to_mobility_statement
from app.scoring.fixture import REPLAY_PATH, SEED_KEY_PREFIX
from app.scoring.kinds import defaults_for, severity_for

logger = logging.getLogger(__name__)

LIVE_KEY_PREFIX: Final = "live-"
"""Every flag this agent writes. The seeder's `seed-` rows are never touched by it."""

LOOKBACK: Final = timedelta(hours=12)
"""Older articles are skipped: a road accident's flag would be born already expired."""

MAX_READS_PER_SOURCE: Final = 8
MAX_EXTRACTIONS_PER_RUN: Final = 12
MAX_BODY_CHARS: Final = 4000
MIN_CONFIDENCE: Final = 0.5
PROMPT_VERSION: Final = "live_risk_v1"

# Sections that are never about movement inside Dhaka. Checked against the first
# URL path segment, which all three publishers use for the desk.
EXCLUDED_SECTIONS: Final = frozenset(
    {
        "international",
        "world",
        "sports",
        "entertainment",
        "lifestyle",
        "tech",
        "technology",
        "religion",
        "opinion",
        "health",
        "education",
        "economy",
        "business",
        "video",
        "photo",
        "country",
        "countries",
    }
)

# Headline vocabulary for events that change how a road can be used. Substring
# matches on the Bangla headline, so inflected forms (আগুনে, সংঘর্ষে) are caught.
# This decides which articles are worth a fetch and a model request; the model
# decides what, if anything, they actually report.
INCIDENT_WORDS: Final = (
    "আগুন",
    "অগ্নি",
    "দুর্ঘটনা",
    "সংঘর্ষ",
    "চাপায়",
    "উল্টে",
    "নিহত",
    "আহত",
    "অবরোধ",
    "অবরুদ্ধ",
    "বিক্ষোভ",
    "মিছিল",
    "সমাবেশ",
    "মানববন্ধন",
    "শোভাযাত্রা",
    "ধর্মঘট",
    "হরতাল",
    "ধাওয়া",
    "জলাবদ্ধতা",
    "জলজট",
    "পানিবন্দি",
    "বৃষ্টি",
    "যানজট",
    "সড়ক",
    "রাস্তা",
    "যান চলাচল",
    "খোঁড়াখুঁড়ি",
    "নির্মাণকাজ",
    "বিদ্যুৎ",
    "গ্যাস",
    "বিস্ফোরণ",
    "ভবন ধস",
)

# Words that wrap a place name in news copy without being part of it. D03's
# gazetteer resolves "মিরপুর ১০ গোলচত্বর" and "কড়াইল" but not
# "রাজধানীর মিরপুর ১০ নম্বর গোলচত্বর এলাকায়" or "কড়াইল বস্তি" (measured
# 2026-10-08). Removing these is deterministic and adds no information: the result
# is still a place the article named, never a different one.
PLACE_FILLER: Final = frozenset(
    {
        "রাজধানীর",
        "রাজধানী",
        "ঢাকার",
        "মহানগরীর",
        "এলাকায়",
        "এলাকার",
        "এলাকা",
        "নম্বর",
        "নং",
        "সংলগ্ন",
        "সামনে",
        "কাছে",
        "পাশে",
        "বস্তি",
        "বস্তিতে",
        "থানা",
        "থানার",
        "থানায়",
        "মহল্লা",
        "মহল্লায়",
    }
)

# Generic place-*type* nouns that trail a specific name in Bangla news copy, with
# the case suffixes the copy actually uses. Stripped from the END only, because
# Bangla puts the specific name first: মহাখালী বাস টার্মিনালে is Mohakhali + "bus
# terminal", so the head is the identity and the tail is the category.
#
# Why this exists: the Live Risk Agent asks the model for "the most specific place
# name", and on 2026-10-08 it correctly answered মহাখালী বাস টার্মিনালে for a real
# bus fire. The gazetteer resolves মহাখালী at confidence 1.00 and that phrase at
# nothing, so the most specific answer was the least resolvable one and a genuine
# Dhaka road event was discarded as unresolved_location. Filler removal did not
# help: বাস and টার্মিনালে are part of the place's name, not wrapping around it.
#
# This stays on the right side of "discarded, never guessed" for the same reason
# PLACE_FILLER does — the result is a prefix of what the article said, never a
# different name. The protection against it becoming a *vaguer* name than the
# article supports is D03's number-identity rule: গুলশান ৯৭ গোলচত্বর reduces to
# গুলশান ৯৭, which no entry matches, so a fabricated sub-location is still
# refused rather than being rounded up to Gulshan. Do not add bare numbers here.
PLACE_GENERIC_TAIL: Final = (
    # multi-word first; matching is longest-first so these strip as a unit
    "বাস টার্মিনালে",
    "বাস টার্মিনাল",
    "বাস স্ট্যান্ডে",
    "বাস স্ট্যান্ড",
    "বাসস্ট্যান্ডে",
    "বাসস্ট্যান্ড",
    "রেল স্টেশনে",
    "রেল স্টেশন",
    # single tokens
    "টার্মিনালে",
    "টার্মিনাল",
    "স্ট্যান্ডে",
    "স্ট্যান্ড",
    "স্টেশনে",
    "স্টেশন",
    "গোলচত্বরে",
    "গোলচত্বর",
    "চত্বরে",
    "চত্বর",
    "চৌরাস্তায়",
    "চৌরাস্তা",
    "মোড়ে",
    "মোড়",
    "ক্রসিংয়ে",
    "ক্রসিং",
    "রেলগেটে",
    "রেলগেট",
    "ফ্লাইওভারে",
    "ফ্লাইওভার",
    "ওভারব্রিজে",
    "ওভারব্রিজ",
    "ব্রিজে",
    "ব্রিজ",
    "সেতুতে",
    "সেতু",
    "বাজারে",
    "বাজার",
    "সড়কে",
    "সড়ক",
    "রোডে",
    "রোড",
    "রাস্তায়",
    "রাস্তা",
)

SYSTEM_PROMPT: Final = (
    "You read Bangla news articles for a navigation app in Dhaka, Bangladesh. "
    "List only events that affect movement on roads inside Dhaka city today: road "
    "accidents, fires, clashes, road blockades, processions or rallies, waterlogging, "
    "road construction, utility works. "
    "For each, give location_text: the most specific place name, copied from the "
    "article in its own script, without words like রাজধানীর, এলাকায় or নম্বর "
    "(write মিরপুর ১০ গোলচত্বর, not রাজধানীর মিরপুর ১০ নম্বর গোলচত্বর এলাকায়). "
    "mobility_impact is road_blocked, heavy_crowd, delay_likely, lane_closed, "
    "impassable, or none if traffic is not affected. "
    "Ignore events outside Dhaka city, events more than a day old, court cases, "
    "arrests, statements and announcements. Most articles report no such event: "
    "then return an empty list. Never invent a place the article does not name."
)


# ---------------------------------------------------------------------------
# Pure decisions — tested without a database or a model
# ---------------------------------------------------------------------------


def is_relevant(ref: ArticleRef, now: datetime) -> bool:
    """Worth fetching? Recent, not from an excluded desk, headline names an incident."""
    if ref.section in EXCLUDED_SECTIONS:
        return False
    if ref.published_at is not None and ref.published_at < now - LOOKBACK:
        return False
    return any(word in ref.title for word in INCIDENT_WORDS)


def _without_generic_tail(text: str) -> str:
    """
    Drop trailing generic place-type nouns, longest match first, repeatedly.

    `মহাখালী বাস টার্মিনালে` -> `মহাখালী`. Returns `text` unchanged when nothing
    matches, and never returns an empty string — a bare category word like
    `বাজারে` with no name in front of it is left alone to be refused, because on
    its own it identifies nowhere.
    """
    current = text
    while True:
        for tail in sorted(PLACE_GENERIC_TAIL, key=len, reverse=True):
            if current == tail:
                return current  # nothing but a category; let it fail to resolve
            if current.endswith(" " + tail):
                current = current[: len(current) - len(tail)].strip()
                break
        else:
            return current


def place_candidates(location_text: str) -> list[str]:
    """
    As written, then without filler, then without a trailing place-type noun.
    Never a shorter *different* name.

    Every candidate is built by **removing** words — those in `PLACE_FILLER`, then
    those in `PLACE_GENERIC_TAIL` from the end — so each one is a sub-phrase of
    what the article said. That is what keeps this on the right side of
    "discarded, never guessed": it can make a match possible, it cannot make one
    up. Order matters: the most specific form is tried first, so a place the
    gazetteer knows in full (`যাত্রাবাড়ী চৌরাস্তা`, `কারওয়ান বাজারে`) resolves to
    itself and never to its own prefix.
    """
    original = " ".join(location_text.split())
    cleaned = " ".join(w for w in original.replace("-", " ").split() if w not in PLACE_FILLER)
    trimmed = _without_generic_tail(cleaned)
    return [c for c in dict.fromkeys((original, cleaned, trimmed)) if c]


async def resolve_news_place(location_text: str) -> GeoResolution:
    """The first candidate the gazetteer knows, or the unresolved answer. No LLM tier."""
    resolution: GeoResolution | None = None
    for candidate in place_candidates(location_text):
        resolution = await resolve_place(candidate, allow_llm=False)
        if resolution.method != "unresolved":
            return resolution
    return resolution or await resolve_place(location_text, allow_llm=False)


def discard_reason(incident: NewsIncident, place: GeoResolution) -> str | None:
    """Why an extracted incident must not become a flag, or None if it may."""
    if incident.confidence < MIN_CONFIDENCE:
        return "low_confidence"
    if place.method == "unresolved":
        return "unresolved_location"
    if incident.mobility_impact == MobilityImpact.NONE:
        return "rejected"  # real, located, and irrelevant to getting through it
    return None


def flag_row(
    *, doc: RawDocument, index: int, incident: NewsIncident, place: GeoResolution
) -> dict[str, Any]:
    """
    One incident as an insert-shaped `risk_flags` row.

    Same shape as `app/scoring/fixture.py`'s rows. `expires_at` is absent because the
    database trigger derives it; `status` is `unconfirmed` and `source_count` is 1
    whatever the input, because this agent has exactly one source per flag.
    """
    kind = IncidentKind(incident.kind)
    defaults = defaults_for(kind)
    observed_at = doc.published_at or doc.fetched_at
    return {
        "event_key": f"{LIVE_KEY_PREFIX}{doc.doc_id[:16]}-{index}",
        "kind": kind.value,
        "status": "unconfirmed",
        "lat": place.lat,
        "lon": place.lon,
        # The wider of the event's reach and our uncertainty about where it is: a
        # fire resolved only to "Mirpur" is claimed over Mirpur, not over 400 m of it.
        "radius_m": min(20_000, max(defaults.radius_m, place.radius_m)),
        "severity_0": severity_for(kind, incident.severity_hint),
        "half_life_hours": defaults.half_life_hours,
        "observed_at": observed_at,
        "valid_from": None,
        "valid_to": None,
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
            kind=kind, impact=incident.mobility_impact, place=place.resolved_name
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
    db: AsyncSession, doc: RawDocument, index: int, incident: NewsIncident, dry_run: bool
) -> tuple[bool, str | None]:
    """Write one incident and, if it qualifies, its flag. Returns (published, reason)."""
    place = await resolve_news_place(incident.location_text)
    reason = discard_reason(incident, place)
    logger.info(
        "%s #%d %s at %r -> %s",
        doc.source_id,
        index,
        incident.kind,
        incident.location_text,
        reason or f"flag near {place.resolved_name}",
    )
    if dry_run:
        return reason is None, reason

    flag_id: UUID | None = None
    if reason is None:
        row = flag_row(doc=doc, index=index, incident=incident, place=place)
        result = await db.execute(
            _INSERT_FLAG, {**row, "sources": json.dumps(row["sources"], ensure_ascii=False)}
        )
        flag_id = result.scalar_one()

    source = {
        "source_id": doc.source_id,
        "url": doc.url,
        "title": doc.title,
        "published_at": doc.published_at.isoformat() if doc.published_at else None,
    }
    await db.execute(
        _INSERT_INCIDENT,
        {
            "doc_id": doc.doc_id,
            "kind": incident.kind,
            "summary_en": incident.summary_en,
            "location_text": incident.location_text,
            "severity_hint": incident.severity_hint,
            "mobility_impact": incident.mobility_impact.value,
            "confidence": incident.confidence,
            "source": json.dumps(source, ensure_ascii=False),
            "flag_id": flag_id,
            "discarded_reason": reason,
        },
    )
    return reason is None, reason


# ---------------------------------------------------------------------------
# The agent
# ---------------------------------------------------------------------------


class LiveRiskAgent(BaseAgent):
    name = "live_risk"
    cron = "*/15 * * * *"

    async def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.db is None:
            raise RuntimeError("live_risk needs ctx.db; the runner provides it")
        db = ctx.db
        errors: list[str] = []
        metrics: dict[str, float] = dict.fromkeys(
            (
                "listed",
                "relevant",
                "fetched",
                "documents_read",
                "incidents",
                "published",
                "low_confidence",
                "unresolved_location",
                "rejected",
            ),
            0.0,
        )

        fresh: list[RawDocument] = []
        async with Fetcher() as fetcher:
            for source in SOURCES:
                try:
                    fresh += await self._ingest(source, fetcher, db, ctx, metrics, errors)
                    if not ctx.dry_run:
                        await db.commit()
                except Exception as problem:  # noqa: BLE001 - one publisher must not stop the rest
                    await db.rollback()
                    errors.append(f"{source.source_id}: {type(problem).__name__}: {problem}")

        fresh_ids = {doc.doc_id for doc in fresh}
        retry = await store.unextracted(db, since=ctx.now - LOOKBACK, limit=MAX_EXTRACTIONS_PER_RUN)
        queue = (fresh + [doc for doc in retry if doc.doc_id not in fresh_ids])[
            :MAX_EXTRACTIONS_PER_RUN
        ]

        consecutive_misses = 0
        for doc in queue:
            try:
                extraction = await complete(
                    SYSTEM_PROMPT,
                    user_prompt(doc),
                    NewsExtraction,
                    feature=FEATURE_EXTRACT,
                    max_tokens=1024,
                )
            except LLMUnavailable as problem:
                errors.append(f"extract {doc.doc_id[:12]}: {problem}")
                consecutive_misses += 1
                if consecutive_misses >= 2:
                    break  # rate limited or out of quota; the queue waits for the next run
                continue
            consecutive_misses = 0
            metrics["documents_read"] += 1
            try:
                for index, incident in enumerate(extraction.incidents):
                    metrics["incidents"] += 1
                    published, reason = await _publish(db, doc, index, incident, ctx.dry_run)
                    metrics["published" if published else str(reason)] += 1
                if not ctx.dry_run:
                    await store.mark_extracted(db, doc.doc_id, ctx.now)
                    await db.commit()
            except Exception as problem:  # noqa: BLE001 - the document stays in the retry queue
                await db.rollback()
                errors.append(f"publish {doc.doc_id[:12]}: {type(problem).__name__}: {problem}")

        status: AgentStatus = "ok"
        if errors:
            nothing_worked = not fresh and metrics["documents_read"] == 0
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
        """List, filter, read and store one publisher's new articles."""
        refs = await source.list_recent(fetcher, ctx.now)
        relevant = [ref for ref in refs if is_relevant(ref, ctx.now)]
        known = await store.known_urls(db, [ref.url for ref in relevant])
        to_read = [ref for ref in relevant if ref.url not in known][:MAX_READS_PER_SOURCE]
        metrics["listed"] += len(refs)
        metrics["relevant"] += len(relevant)

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


AGENT = LiveRiskAgent()


# ---------------------------------------------------------------------------
# The offline replay — DEMO_PLAN.md D04's "passes again with the network off"
# ---------------------------------------------------------------------------


async def export_replay(db: AsyncSession, now: datetime) -> int:
    """
    Write the live flags served right now to `data/fixtures/live_replay.json`.

    The offline demo has no database, no model and no publisher, so replaying
    `raw_documents` (which lives in Supabase) cannot work. What can: the fixture
    mechanism D02 already built. Each live flag becomes a fixture entry — structured
    fields only, times relative to the export — and `SeededRiskSurface` serves those
    entries beside the hand-built ones, re-anchored to whenever the process starts.
    So a run captured on the 14th still shows fresh, decaying news flags with their
    real headlines on the 24th.

    `place` is re-resolved from the stored `location_text` through the same
    deterministic gazetteer path the agent used, and the statement is re-derived by
    `framing.py` at load — the replay file holds no flag prose, like every fixture.
    """
    result = await db.execute(
        text(
            """
            select f.event_key, f.kind, f.radius_m, f.severity_0, f.half_life_hours,
                   f.observed_at, f.sources::text as sources_json,
                   extensions.ST_Y(f.location::extensions.geometry) as lat,
                   extensions.ST_X(f.location::extensions.geometry) as lon,
                   e.mobility_impact, e.location_text
            from public.risk_flags f
            join public.extracted_incidents e on e.flag_id = f.flag_id
            where f.event_key like :prefix
              and f.status in ('unconfirmed', 'confirmed')
              and f.expires_at > :now
            order by f.observed_at desc
            """
        ),
        {"prefix": LIVE_KEY_PREFIX + "%", "now": now},
    )

    def hours_from_now(at: datetime) -> float:
        return round((at - now).total_seconds() / 3600, 3)

    entries: list[dict[str, Any]] = []
    for row in result:
        place = await resolve_news_place(row.location_text)
        entries.append(
            {
                "event_key": SEED_KEY_PREFIX + row.event_key,
                "kind": row.kind,
                "lat": float(row.lat),
                "lon": float(row.lon),
                "radius_m": int(row.radius_m),
                "severity_0": float(row.severity_0),
                "half_life_hours": float(row.half_life_hours),
                "mobility_impact": row.mobility_impact,
                "place": place.resolved_name if place.method != "unresolved" else None,
                "observed_offset_hours": hours_from_now(row.observed_at),
                "source_count": 1,
                "sources": [
                    {
                        "source_id": s["source_id"],
                        "url": s["url"],
                        "title": s.get("title"),
                        "published_offset_hours": hours_from_now(
                            datetime.fromisoformat(s["published_at"])
                            if s.get("published_at")
                            else row.observed_at
                        ),
                    }
                    for s in json.loads(row.sources_json)
                ],
            }
        )

    write_replay(entries, now, REPLAY_PATH)
    return len(entries)


def write_replay(entries: list[dict[str, Any]], now: datetime, path: Path) -> None:
    document = {
        "_README": (
            "Captured live news flags, replayed by SeededRiskSurface when "
            "RISK_SURFACE_IMPL=seeded. Written by `python -m app.agents export-replay`; "
            "do not edit by hand. Times are hours relative to `exported_at` and are "
            "re-anchored to the moment the backend starts. No mobility_statement: "
            "framing.py derives it at load, as for every fixture."
        ),
        "exported_at": now.isoformat(),
        "flags": entries,
    }
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
