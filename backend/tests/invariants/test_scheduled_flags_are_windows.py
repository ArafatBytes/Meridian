"""
Invariants for the Scheduled Risk Agent (D09). No database, no network, no model.

A forward-dated flag is a claim about a *window*, and every way this agent can go
wrong is a way of losing that window:

1. **Every published flag carries both ends of it.** A scheduled flag with a null
   `valid_from` is served from the moment it is written, which puts tomorrow's
   procession on tonight's map.
2. **A window that has already closed is not published.** Reading yesterday's
   paper is normal; acting on it is not.
3. **The model is never asked for an instant.** It answers a three-way day and an
   integer hour, and the arithmetic happens here, from the article's own
   publication date.
4. **Nothing is served before its window opens** — the floor in `decay.is_live`
   and in `surface_db._LIVE_PREDICATE`, which have to keep agreeing.
5. **The usual two**, inherited from D04 and re-asserted because this agent writes
   to the same table: one article is one source, and the pin's text comes from
   `framing.py`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.agents import scheduled_risk
from app.agents.scheduled_risk import (
    SCHEDULED_KEY_PREFIX,
    _window,
    discard_reason,
    flag_row,
    is_announcement,
)
from app.contracts.risk import GeoResolution, IncidentKind, MobilityImpact, RawDocument
from app.ingestion.sources import ArticleRef
from app.ingestion.sources.base import DHAKA_TZ
from app.llm.models import ScheduledEvent
from app.policy.framing import assert_mobility_safe
from app.scoring.decay import is_live

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def event(**overrides) -> ScheduledEvent:
    return ScheduledEvent(
        **{
            "kind": "procession",
            "location_text": "শাহবাগ",
            "mobility_impact": MobilityImpact.HEAVY_CROWD,
            "day": "tomorrow",
            "start_hour": 10,
            "end_hour": None,
            "severity_hint": "medium",
            "summary_en": "A rally is called at Shahbagh tomorrow morning.",
            "confidence": 0.8,
            **overrides,
        }
    )


def document(published_at: datetime = NOW) -> RawDocument:
    return RawDocument(
        doc_id="a" * 64,
        source_id="prothom_alo",
        url="https://example.test/announcement",
        fetched_at=published_at,
        published_at=published_at,
        language="bn",
        title="আগামীকাল শাহবাগে সমাবেশের ডাক",
        body="…",
    )


def resolved() -> GeoResolution:
    return GeoResolution(
        lat=23.7389,
        lon=90.3958,
        radius_m=600,
        resolved_name="Shahbagh",
        method="gazetteer",
        confidence=1.0,
    )


def unresolved() -> GeoResolution:
    # `radius_m` must be positive and `resolved_name` is required even here; what
    # makes it unresolved is `method`, which is the field `discard_reason` reads.
    return GeoResolution(
        lat=0.0, lon=0.0, radius_m=1, resolved_name="x", method="unresolved", confidence=0.0
    )


# ---------------------------------------------------------------------------
# 1. Every published flag carries a window
# ---------------------------------------------------------------------------


def test_a_published_flag_always_has_both_ends_of_its_window():
    start, end = _window(event(), NOW)
    row = flag_row(
        doc=document(), index=0, event=event(), place=resolved(), valid_from=start, valid_to=end
    )
    assert row["valid_from"] is not None
    assert row["valid_to"] is not None
    assert row["valid_to"] > row["valid_from"]


def test_the_flag_is_keyed_as_scheduled_so_it_is_never_mistaken_for_live_news():
    start, end = _window(event(), NOW)
    row = flag_row(
        doc=document(), index=0, event=event(), place=resolved(), valid_from=start, valid_to=end
    )
    assert row["event_key"].startswith(SCHEDULED_KEY_PREFIX)


def test_observed_at_is_when_it_was_announced_not_when_the_window_opens():
    """
    Nothing was observed. `observed_at` is the article's publication time, which is
    what the flag sheet labels "Announced" — and `decay.decay_anchor` is what makes
    decay start at `valid_from` instead, so the flag does not arrive half-faded.
    """
    published = NOW - timedelta(hours=5)
    start, end = _window(event(), published)
    row = flag_row(
        doc=document(published),
        index=0,
        event=event(),
        place=resolved(),
        valid_from=start,
        valid_to=end,
    )
    assert row["observed_at"] == published
    assert row["valid_from"] > row["observed_at"]


# ---------------------------------------------------------------------------
# 2. A closed window is not published
# ---------------------------------------------------------------------------


def test_an_event_whose_window_has_already_closed_is_rejected():
    yesterday = NOW - timedelta(days=1)
    start, end = _window(event(day="today", start_hour=9), yesterday)
    assert end < NOW
    assert discard_reason(event(), resolved(), end, NOW) == "rejected"


def test_an_event_still_to_come_is_published():
    start, end = _window(event(), NOW)
    assert discard_reason(event(), resolved(), end, NOW) is None


def test_an_event_with_no_road_impact_is_rejected():
    start, end = _window(event(), NOW)
    assert (
        discard_reason(event(mobility_impact=MobilityImpact.NONE), resolved(), end, NOW)
        == "rejected"
    )


def test_a_place_the_gazetteer_does_not_know_produces_no_flag():
    start, end = _window(event(), NOW)
    assert discard_reason(event(), unresolved(), end, NOW) == "unresolved_location"


def test_a_low_confidence_reading_produces_no_flag():
    start, end = _window(event(), NOW)
    assert discard_reason(event(confidence=0.2), resolved(), end, NOW) == "low_confidence"


# ---------------------------------------------------------------------------
# 3. The window is computed here, from the publication date
# ---------------------------------------------------------------------------


def test_tomorrow_means_the_day_after_the_article_in_dhaka_time():
    # Published 18:00 Dhaka on the 10th; "tomorrow at 10" is the 11th at 10:00 Dhaka.
    published = datetime(2026, 10, 10, 18, 0, tzinfo=DHAKA_TZ).astimezone(UTC)
    start, _ = _window(event(day="tomorrow", start_hour=10), published)
    local = start.astimezone(DHAKA_TZ)
    assert (local.year, local.month, local.day, local.hour) == (2026, 10, 11, 10)


def test_an_article_published_late_evening_utc_still_resolves_to_the_right_dhaka_day():
    """
    Dhaka is UTC+6, so 20:00 UTC on the 10th is already 02:00 on the 11th locally.
    "Tomorrow" has to mean the 12th. Reading the date in UTC would say the 11th —
    a whole day early, and the flag would be served a day before the event.
    """
    published = datetime(2026, 10, 10, 20, 0, tzinfo=UTC)
    start, _ = _window(event(day="tomorrow", start_hour=9), published)
    local = start.astimezone(DHAKA_TZ)
    assert (local.month, local.day, local.hour) == (10, 12, 9)


def test_a_stated_end_hour_is_used():
    start, end = _window(event(start_hour=10, end_hour=16), NOW)
    assert (end - start) == timedelta(hours=6)


def test_an_absent_end_hour_falls_back_to_the_kinds_own_duration():
    start, end = _window(event(kind="procession", end_hour=None), NOW)
    assert (end - start) == timedelta(hours=scheduled_risk.DEFAULT_DURATION_HOURS[
        IncidentKind.PROCESSION
    ])


def test_an_end_hour_at_or_before_the_start_does_not_produce_a_backwards_window():
    """
    `22:00 to 02:00` crosses midnight and `14:00 to 14:00` is a misreading, and one
    integer cannot tell them apart. Either way the window must come out forwards.
    """
    for end_hour in (2, 10):
        start, end = _window(event(start_hour=10, end_hour=end_hour), NOW)
        assert end > start


def test_the_model_is_never_asked_for_a_date_or_a_timestamp():
    """
    `ScheduledEvent` offers a three-way day and two integer hours. A field that took
    an instant would reintroduce exactly the digit-copying failure D08 measured.
    """
    fields = ScheduledEvent.model_fields
    assert set(fields) >= {"day", "start_hour", "end_hour"}
    for name, field in fields.items():
        assert "datetime" not in str(field.annotation), (
            f"{name} accepts a datetime; the model must not be asked for an instant"
        )
    assert set(scheduled_risk.DAY_OFFSET) == {"today", "tomorrow", "day_after"}


# ---------------------------------------------------------------------------
# 4. Nothing is served before its window opens
# ---------------------------------------------------------------------------


def test_a_flag_is_not_live_before_its_window_opens():
    start, end = _window(event(), NOW)
    # expires_at well past the window, which is what the trigger derives.
    expires = end + timedelta(hours=2)
    assert not is_live(at=NOW, expires_at=expires, valid_from=start, valid_to=end)
    assert is_live(at=start, expires_at=expires, valid_from=start, valid_to=end)
    assert not is_live(at=end, expires_at=expires, valid_from=start, valid_to=end)


def test_the_sql_predicate_and_the_python_one_both_test_valid_from():
    """
    `decay.is_live` and `surface_db._LIVE_PREDICATE` are two statements of one rule,
    and the seeded and database surfaces each use one of them. A floor added to only
    one would make the offline demo and the live backend disagree about whether
    tomorrow is visible today.
    """
    from app.scoring import surface_db

    assert "valid_from IS NULL OR valid_from <= :at" in surface_db._LIVE_PREDICATE
    source = Path(surface_db.__file__).with_name("surface_seeded.py").read_text(encoding="utf-8")
    assert "valid_from=flag.valid_from" in source


def test_an_ordinary_flag_with_no_window_is_unaffected():
    expires = NOW + timedelta(hours=3)
    assert is_live(at=NOW, expires_at=expires, valid_from=None, valid_to=None)


# ---------------------------------------------------------------------------
# 5. Inherited from D04
# ---------------------------------------------------------------------------


def test_one_article_is_one_unconfirmed_source():
    start, end = _window(event(), NOW)
    row = flag_row(
        doc=document(), index=0, event=event(), place=resolved(), valid_from=start, valid_to=end
    )
    assert row["status"] == "unconfirmed"
    assert row["source_count"] == 1
    assert len(row["sources"]) == 1


def test_the_pin_text_comes_from_framing_and_not_from_the_model():
    start, end = _window(event(), NOW)
    row = flag_row(
        doc=document(),
        index=0,
        event=event(summary_en="Violent mob to attack Shahbagh, very dangerous"),
        place=resolved(),
        valid_from=start,
        valid_to=end,
    )
    assert_mobility_safe(row["mobility_statement"])
    assert "dangerous" not in row["mobility_statement"].lower()
    assert "mob" not in row["mobility_statement"].lower()


def test_the_agent_never_writes_a_mobility_statement_itself():
    """
    `framing.to_mobility_statement` is the only writer of that field. A template in
    this module, however careful, is the start of a second one.
    """
    source = Path(scheduled_risk.__file__).read_text(encoding="utf-8")
    body = source[source.index('"""', source.index('"""') + 3) :]
    assert body.count("to_mobility_statement") >= 1
    assert not re.search(r'"mobility_statement":\s*f?"', body)


# ---------------------------------------------------------------------------
# The announcement filter
# ---------------------------------------------------------------------------


def ref(title: str, section: str = "capital", hours_ago: float = 1.0) -> ArticleRef:
    # `section` is a property derived from the first path segment, not a field, so
    # it is set by building a URL that has it.
    return ArticleRef(
        url=f"https://example.test/{section}/{abs(hash(title))}",
        title=title,
        published_at=NOW - timedelta(hours=hours_ago),
    )


@pytest.mark.parametrize(
    "title",
    [
        "আগামীকাল শাহবাগে সমাবেশের ডাক",
        "আগামী রোববার সারাদেশে হরতাল ঘোষণা",
        "কাল থেকে মিরপুর সড়কে নির্মাণকাজ শুরু",
    ],
)
def test_an_announcement_of_a_road_event_is_fetched(title: str):
    assert is_announcement(ref(title), NOW)


@pytest.mark.parametrize(
    "title",
    [
        # A future marker with no road event: tomorrow's weather, tomorrow's match.
        "আগামীকাল বৃষ্টির সম্ভাবনা",
        "আগামীকাল বাংলাদেশের ম্যাচ",
        # A road event with no future marker: this is D04's article, not ours.
        "শাহবাগে মিছিল, যান চলাচল বন্ধ",
    ],
)
def test_an_article_that_is_only_half_an_announcement_is_skipped(title: str):
    assert not is_announcement(ref(title), NOW)


def test_an_excluded_desk_is_skipped_even_when_the_headline_matches():
    assert not is_announcement(ref("আগামীকাল হরতাল ঘোষণা", section="sports"), NOW)


def test_an_old_article_is_skipped():
    assert not is_announcement(ref("আগামীকাল শাহবাগে সমাবেশের ডাক", hours_ago=40), NOW)
