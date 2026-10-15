"""
B11a — the first source that is not a newspaper.

DMP News is the Dhaka Metropolitan Police's own outlet and the only one of four
institutional bodies that publishes anything machine-readable. The survey behind
that claim is in `app/ingestion/sources/dmp_news.py`; what is tested here is the
parsing, because the feed differs from every other source in two ways that each
broke something during the build:

* **`pubDate` is RFC 822, not ISO 8601.** `base.parse_time` reads sitemap dates
  and returns None for `Wed, 14 Oct 2026 09:17:34 +0000`. An undated ref is
  treated by `is_relevant` as "unknown, let it through", so getting this wrong
  would not fail loudly -- it would quietly disable the lookback for this source.
* **The body arrives in the feed.** `content:encoded` carries the article, so
  `read` consumes what `list_recent` kept and makes no second request. That
  halves the requests against a government host, and it is the only source here
  where `read` can legitimately not fetch.

No network: every test drives a fake fetcher, which is also how the
"did it fetch?" assertions are possible at all.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.ingestion.sources.dmp_news import DmpNewsSource, _published

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>DMP News</title>
    <item>
      <title>উত্তরায় দুই ছিনতাইকারী গ্রেফতার</title>
      <link>https://dmpnews.org/uttara-mugging/</link>
      <pubDate>Wed, 14 Oct 2026 09:17:34 +0000</pubDate>
      <content:encoded><![CDATA[<p>উত্তরা পশ্চিম থানা পুলিশ দুইজনকে গ্রেফতার করেছে।</p>
      <p>ছিনতাইয়ে ব্যবহৃত অটোরিকশা উদ্ধার করা হয়েছে।</p>]]></content:encoded>
    </item>
    <item>
      <title>যাত্রাবাড়ী থানার বিশেষ অভিযানে গ্রেফতার ১৭</title>
      <link>https://dmpnews.org/jatrabari-drive/</link>
      <pubDate>Wed, 14 Oct 2026 07:32:46 +0000</pubDate>
    </item>
  </channel>
</rss>
"""


class FakeFetcher:
    """Records what was asked for, so a test can assert that nothing was."""

    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    async def text(self, url: str) -> str:
        self.requested.append(url)
        return self.pages[url]


def feed_fetcher(**extra: str) -> FakeFetcher:
    return FakeFetcher({DmpNewsSource().feed_url: FEED, **extra})


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------


def test_an_rfc822_pubdate_is_read() -> None:
    parsed = _published("Wed, 14 Oct 2026 09:17:34 +0000")
    assert parsed == datetime(2026, 10, 14, 9, 17, 34, tzinfo=UTC)


def test_the_sitemap_date_parser_could_not_have_read_it() -> None:
    """
    Why `_published` exists rather than reusing `base.parse_time`.

    This is the quiet failure the module docstring warns about: `parse_time`
    returns None instead of raising, `is_relevant` lets an undated ref through, and
    the 12-hour lookback would simply stop applying to this one source.
    """
    from app.ingestion.sources.base import parse_time

    assert parse_time("Wed, 14 Oct 2026 09:17:34 +0000") is None


@pytest.mark.parametrize("raw", ["", "   ", None, "not a date", "14/10/2026"])
def test_an_unreadable_date_is_none_not_an_exception(raw: str | None) -> None:
    """One malformed date must not take out the listing it arrived in."""
    assert _published(raw) is None


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


async def test_listing_yields_refs_and_keeps_the_bodies() -> None:
    source = DmpNewsSource()
    refs = await source.list_recent(feed_fetcher(), NOW)

    assert [r.url for r in refs] == [
        "https://dmpnews.org/uttara-mugging/",
        "https://dmpnews.org/jatrabari-drive/",
    ]
    assert refs[0].title == "উত্তরায় দুই ছিনতাইকারী গ্রেফতার"
    assert refs[0].published_at == datetime(2026, 10, 14, 9, 17, 34, tzinfo=UTC)
    # Only the first item carries content:encoded.
    assert set(source._bodies) == {"https://dmpnews.org/uttara-mugging/"}


async def test_a_malformed_feed_returns_nothing_rather_than_raising() -> None:
    """
    `live_risk` catches per-source exceptions, so this is not about crashing — it is
    about the other nine publishers' error logs staying readable when a government
    host serves an error page with a 200.
    """
    source = DmpNewsSource()
    fetcher = FakeFetcher({source.feed_url: "<html>502 Bad Gateway</html>"})
    assert await source.list_recent(fetcher, NOW) == []


async def test_an_item_without_a_link_is_skipped() -> None:
    source = DmpNewsSource()
    feed = FEED.replace("<link>https://dmpnews.org/jatrabari-drive/</link>", "")
    fetcher = FakeFetcher({source.feed_url: feed})
    refs = await source.list_recent(fetcher, NOW)
    assert [r.url for r in refs] == ["https://dmpnews.org/uttara-mugging/"]


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


async def test_read_uses_the_feed_body_and_makes_no_request() -> None:
    """The point of caching at all: one request per listing, not one per article."""
    source = DmpNewsSource()
    fetcher = feed_fetcher()
    refs = await source.list_recent(fetcher, NOW)
    fetcher.requested.clear()

    doc = await source.read(fetcher, refs[0], NOW)

    assert fetcher.requested == [], "read() fetched a page whose body the feed had already given"
    assert doc is not None
    assert "অটোরিকশা" in doc.body
    assert doc.source_id == "dmp_news"
    assert doc.language == "bn"
    assert doc.published_at == refs[0].published_at


async def test_read_falls_back_to_fetching_when_the_feed_carried_no_body() -> None:
    """
    A feed that stops carrying bodies must degrade, not return nothing. The second
    item has no `content:encoded`.
    """
    source = DmpNewsSource()
    page = "<html><body><p>যাত্রাবাড়ী থানা পুলিশ ১৭ জনকে গ্রেফতার করেছে।</p></body></html>"
    fetcher = feed_fetcher(**{"https://dmpnews.org/jatrabari-drive/": page})
    refs = await source.list_recent(fetcher, NOW)
    fetcher.requested.clear()

    doc = await source.read(fetcher, refs[1], NOW)

    assert fetcher.requested == ["https://dmpnews.org/jatrabari-drive/"]
    assert doc is not None and "গ্রেফতার" in doc.body


async def test_a_second_listing_replaces_the_cache_rather_than_growing_it() -> None:
    """
    `SOURCES` holds one instance for the life of the worker process, so a dict fed
    by a remote server and never cleared is a slow leak rather than a cache.
    """
    source = DmpNewsSource()
    await source.list_recent(feed_fetcher(), NOW)

    other = FEED.replace("uttara-mugging", "later-story")
    await source.list_recent(FakeFetcher({source.feed_url: other}), NOW)

    assert set(source._bodies) == {"https://dmpnews.org/later-story/"}


async def test_reading_the_same_ref_twice_still_works() -> None:
    """
    `read` pops from the cache, so a retry would find it gone. It must fall back to
    fetching rather than returning None — a document that vanishes on the second
    attempt is the kind of bug that only shows up under a retry.
    """
    source = DmpNewsSource()
    url = "https://dmpnews.org/uttara-mugging/"
    page = "<html><body><p>উত্তরা থানা পুলিশের অভিযান।</p></body></html>"
    fetcher = feed_fetcher(**{url: page})
    refs = await source.list_recent(fetcher, NOW)

    first = await source.read(fetcher, refs[0], NOW)
    second = await source.read(fetcher, refs[0], NOW)

    assert first is not None and second is not None
    assert fetcher.requested[-1] == url, "the retry must fetch, having consumed the cache"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_dmp_is_registered_last_in_sources() -> None:
    """
    `live_risk` ingests in `SOURCES` order. The newest and least proven source goes
    last so that a slow or broken government feed costs the eight established
    publishers nothing.
    """
    from app.ingestion.sources import SOURCES

    assert SOURCES[-1].source_id == "dmp_news"


def test_dmp_reads_the_crime_feed_not_the_traffic_one() -> None:
    """
    Both category feeds exist. Traffic looked like the obvious choice and is not:
    nine of ten items are the daily enforcement counter (`ট্রাফিক আইন লঙ্ঘনে ডিএমপির
    ২৭৯৯ মামলা`), which is a statistic rather than a road closure and would spend a
    slot of `MAX_EXTRACTIONS_PER_RUN` to be rejected.
    """
    from app.ingestion.sources.dmp_news import CRIME_FEED, DmpNewsSource

    # অপরাধ (crime), percent-encoded as WordPress serves it.
    assert DmpNewsSource().feed_url == CRIME_FEED
    assert "%e0%a6%85%e0%a6%aa%e0%a6%b0%e0%a6%be%e0%a6%a7" in CRIME_FEED


# ---------------------------------------------------------------------------
# What may be published from a police release
# ---------------------------------------------------------------------------


def test_the_prompt_refuses_a_round_up_as_a_located_crime() -> None:
    """
    The owner's decision on 15 Oct: only items naming a located incident.

    `never the police station` was already in the prompt and is not sufficient
    here, because **a Dhaka thana is also a neighbourhood.** যাত্রাবাড়ী is a police
    station and a place the gazetteer resolves at 1.2 km, so
    `যাত্রাবাড়ী থানার বিশেষ অভিযানে গ্রেফতার ১৭` would be pinned as if a crime had
    happened at a spot -- unlike `ডিএমপির অভিযানে গ্রেফতার ৫৩০`, where "DMP"
    resolves to nothing and the discard invariant removes it for free.

    A prompt cannot be unit-tested for behaviour, so this asserts the clause is
    present and says why. The behavioural check is the eval harness.
    """
    from app.agents.live_risk import SYSTEM_PROMPT

    assert "A police unit is not a place" in SYSTEM_PROMPT
    assert "round-up" in SYSTEM_PROMPT
    assert "never the police station" in SYSTEM_PROMPT, (
        "the original rule must stay; the B11a clause narrows it, it does not replace it"
    )


def test_a_thana_name_really_does_resolve_which_is_why_the_clause_is_needed() -> None:
    """
    The premise of the clause above. If this ever fails, the clause may be
    unnecessary — but far more likely the gazetteer has regressed.
    """
    from app.geo.gazetteer import gazetteer

    assert gazetteer().resolve("যাত্রাবাড়ী") is not None, (
        "Jatrabari no longer resolves, so either the gazetteer regressed or the "
        "reasoning behind the police-unit prompt clause needs revisiting"
    )
