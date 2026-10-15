"""
DMP News — the Dhaka Metropolitan Police's own outlet. B11a, 2026-10-15.

The first source here that is not a newspaper, and the only one of four
institutional bodies that publishes anything a machine can read. What the
feasibility survey found:

| body | what its notice board actually holds |
|---|---|
| **DMP News** (dmpnews.org) | WordPress: RSS with full body text, a 37-page sitemap, per-category feeds. **Usable.** |
| Fire Service (fireservice.gov.bd) | Firefighter joining notices and tenders; `/pages/news` is the DG's newspaper op-ed. No incident feed. |
| DNCC (dncc.gov.bd) | Durga Puja cheque distribution, an e-trolley tender, meeting notices, officer postings. No road closures. |
| DSCC (dscc.gov.bd) | Meeting notices, municipal tax deadlines, WASA bill verification. No road closures. |

The three government sites run the same national-portal CMS, which has no RSS or
API and whose notice boards are administrative by design. **The institutional
tier is largely not machine-readable in Bangladesh**, which is the honest answer
to why this file has one entry rather than four.

## Why the crime category and not traffic

Both exist as per-category feeds. The traffic one looked like the obvious choice
and is not: nine of ten items are the daily enforcement counter
(`ট্রাফিক আইন লঙ্ঘনে ডিএমপির ২৭৯৯ মামলা` — 2,799 cases in 24 hours). That is a
statistic, not a road closure, and each one would spend a slot of
`MAX_EXTRACTIONS_PER_RUN` to be rejected. The crime feed names Dhaka thanas and
areas directly — যাত্রাবাড়ী, তুরাগ, উত্তরা, শাহবাগ, রমনা — which is exactly what
the gazetteer resolves after B7.

## The feed carries the body, so `read` does not fetch

`content:encoded` holds the full article. `list_recent` keeps those bodies on the
instance and `read` consumes them, which halves the request count against a
government host and removes a round trip per article. The fallback still fetches
the page, because a feed that stops carrying bodies must degrade rather than
return nothing — and `SOURCES` holds one long-lived instance per publisher, so
the cache is replaced on every `list_recent` rather than accumulating.

## What is NOT decided here

**Whether an arrest belongs on a risk map.** `17 arrested in a Jatrabari thana
drive` names no incident location; `two muggers arrested in Uttara, the
auto-rickshaw used in the mugging recovered` does. That judgement is the
extraction stage's, not this module's -- this file fetches and parses, and
`app/policy/attribution.py` plus the crime extraction prompt decide what may be
published. A source module that filtered on meaning would hide the decision in
the wrong layer.
"""

from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Final
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from app.contracts.risk import RawDocument
from app.ingestion.fetcher import Fetcher
from app.ingestion.sources.base import ArticleRef, Source, article_body
from app.ingestion.store import canonical_url, doc_id_for

SOURCE_ID: Final = "dmp_news"
"""Referenced by `app/policy/independence.py`, so it is a constant, not a literal."""

# The crime category, percent-encoded as WordPress serves it (অপরাধ).
CRIME_FEED: Final = (
    "https://dmpnews.org/category/"
    "%e0%a6%85%e0%a6%aa%e0%a6%b0%e0%a6%be%e0%a6%a7/feed/"
)

_CONTENT_NS: Final = "{http://purl.org/rss/1.0/modules/content/}encoded"

_MAX_BODIES: Final = 60
"""
Ceiling on the body cache, which exists only to bound a long-lived instance.

A category feed serves ten items, so this is never reached in practice; it is
here because `SOURCES` holds one instance for the life of the worker process and
an unbounded dict fed by a remote server is a slow leak, not a cache.
"""


def _published(raw: str | None) -> datetime | None:
    """
    An RSS `pubDate` — RFC 822, not ISO 8601, so `base.parse_time` cannot read it.

    `Wed, 14 Oct 2026 09:17:34 +0000`. Returns None rather than raising: an
    undated item is filtered out by `is_relevant`'s lookback, which treats None as
    "unknown, let it through", and that is the right outcome for a feed whose
    items are all recent by construction.
    """
    if not raw or not raw.strip():
        return None
    try:
        parsed = parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else None


class DmpNewsSource(Source):
    """DMP's crime press releases, from the WordPress category feed."""

    def __init__(
        self,
        *,
        source_id: str = SOURCE_ID,
        name: str = "Dhaka Metropolitan Police",
        feed_url: str = CRIME_FEED,
        language: str = "bn",
    ) -> None:
        self.source_id = source_id
        self.name = name
        self.feed_url = feed_url
        self.language = language
        self._bodies: dict[str, str] = {}

    async def list_recent(self, fetcher: Fetcher, now: datetime) -> list[ArticleRef]:
        refs: list[ArticleRef] = []
        bodies: dict[str, str] = {}

        # A malformed feed must not take the whole run down with it: `live_risk`
        # catches per-source exceptions, but returning [] here keeps the other
        # eight publishers' error logs readable.
        try:
            root = ElementTree.fromstring(await fetcher.text(self.feed_url))
        except ElementTree.ParseError:
            return []

        for item in root.iterfind("./channel/item"):
            link = (item.findtext("link") or "").strip()
            title = (item.findtext("title") or "").strip()
            if not link:
                continue
            url = canonical_url(link)
            refs.append(
                ArticleRef(
                    url=url,
                    title=title,
                    published_at=_published(item.findtext("pubDate")),
                )
            )
            encoded = item.findtext(_CONTENT_NS)
            if encoded and len(bodies) < _MAX_BODIES:
                bodies[url] = encoded

        # Replaced wholesale, not updated: last run's bodies are of no use and
        # keeping them is how a singleton grows without limit.
        self._bodies = bodies
        return refs

    async def read(self, fetcher: Fetcher, ref: ArticleRef, now: datetime) -> RawDocument | None:
        html = self._bodies.pop(ref.url, None)
        if html is None:
            # The feed did not carry it, or `read` was called without a listing.
            # Degrade to fetching rather than returning nothing.
            html = await fetcher.text(ref.url)

        soup = BeautifulSoup(html, "lxml")
        paragraphs = [p.get_text(" ") for p in soup.select("p")]
        if not paragraphs:
            # `content:encoded` is sometimes a bare run of text with no markup.
            text = soup.get_text("\n")
            paragraphs = [line for line in (part.strip() for part in text.split("\n")) if line]

        body = article_body(paragraphs, language=self.language)
        if not body:
            return None

        return RawDocument(
            doc_id=doc_id_for(ref.url),
            source_id=self.source_id,
            url=ref.url,
            fetched_at=now,
            published_at=ref.published_at,
            language=self.language,
            title=ref.title or _title_from(soup),
            body=body,
        )


def _title_from(soup: BeautifulSoup) -> str:
    """A heading out of the encoded body, for the rare item whose `<title>` is empty."""
    heading = soup.find(re.compile("^h[1-3]$"))
    return heading.get_text(strip=True) if heading else ""
