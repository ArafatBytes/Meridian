"""
The source-agnostic interface. IMPLEMENTATION_PLAN.md S09.

The concept document's own mitigation for social-media access restrictions is that
no part of the pipeline knows where a document came from: the agent sees `Source`,
and a `Source` is two calls.

    list_recent()   cheap: one listing request (a sitemap), headlines and times only
    read()          expensive: the article itself, as a `RawDocument`

Split because the agent decides *between* the two which articles are worth reading —
already stored, too old, or a headline that cannot be about movement in Dhaka — so
the expensive call only happens for the few that survive.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final

from app.contracts.risk import RawDocument
from app.ingestion.fetcher import Fetcher

DHAKA_TZ: Final = timezone(timedelta(hours=6), "Asia/Dhaka")

MIN_LATIN_PARAGRAPH_CHARS: Final = 40
"""
Shorter than this, an English paragraph is not body text.

The Bangla rule below filters on *script*, because a Bangla article's captions and
credits are the paragraphs with no Bangla in them. An English article has no such
tell — everything is Latin — so length stands in for it. Forty characters was read
off the real pages on 2026-10-14: Dhaka Tribune's shortest genuine sentence in the
sample was 67 characters, while the non-body nodes (empty `<p>` used as spacers,
"Topics:", photo credits) came out at 0 to about 20.

A page that is not an article therefore yields no body at all and `read()` returns
None for it. That is the correct outcome rather than a bug — nothing should be
extracted from a photo gallery or a pull-quote card.
"""


@dataclass(frozen=True, slots=True)
class ArticleRef:
    """One article as a listing describes it, before it has been fetched."""

    url: str  # canonical, see store.canonical_url
    title: str
    published_at: datetime | None

    @property
    def section(self) -> str:
        """The first path segment — `capital`, `country`, `sports` — or ''."""
        path = self.url.split("://", 1)[-1].split("/")
        return path[1] if len(path) > 1 else ""


class Source(ABC):
    """A publisher. Instances, not classes, so two sites on one CMS share a parser."""

    source_id: str  # stable publisher id, stored on every RawDocument and SourceRef
    name: str  # what the app shows in the source strip

    @abstractmethod
    async def list_recent(self, fetcher: Fetcher, now: datetime) -> list[ArticleRef]: ...

    @abstractmethod
    async def read(self, fetcher: Fetcher, ref: ArticleRef, now: datetime) -> RawDocument | None:
        """The article, or None if it has no usable body."""


def parse_time(raw: str | None) -> datetime | None:
    """An ISO 8601 instant from a sitemap. A date with no time is read as Dhaka midnight."""
    if not raw or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=DHAKA_TZ)


def sitemap_entries(xml: str) -> list[dict[str, str]]:
    """
    Every `<url>` in a sitemap as {tag: text}, namespaces stripped.

    The plain sitemap schema and Google News' `news:` extension are flattened by
    local name: `news:news/news:title` becomes `title`. The image and video
    extensions are skipped entirely, because they reuse the same local names —
    Independent TV lists `image:title` ("রামপাল বিদ্যুৎকেন্দ্র। ফাইল ছবি", a photo
    caption) before `news:title`, and taking the first `title` read captions as
    headlines. Found on the first live dry run, 2026-10-08.
    """
    entries: list[dict[str, str]] = []
    for url in ET.fromstring(xml.strip()).iterfind("{*}url"):
        entry: dict[str, str] = {}
        for element in url.iter():
            namespace, _, name = element.tag.rpartition("}")
            if "sitemap-image" in namespace or "sitemap-video" in namespace:
                continue
            if element.text and element.text.strip() and name not in entry:
                entry[name] = element.text.strip()
        if "loc" in entry:
            entries.append(entry)
    return entries


def bangla_paragraphs(paragraphs: list[str]) -> str:
    """Join article paragraphs, dropping empty ones and captions with no Bangla in them."""
    kept = [re.sub(r"\s+", " ", p).strip() for p in paragraphs if any("ঀ" <= c <= "৿" for c in p)]
    return "\n\n".join(p for p in kept if p)


def latin_paragraphs(paragraphs: list[str]) -> str:
    """Join article paragraphs, dropping anything too short to be body text."""
    kept = [re.sub(r"\s+", " ", p).strip() for p in paragraphs]
    return "\n\n".join(p for p in kept if len(p) >= MIN_LATIN_PARAGRAPH_CHARS)


def article_body(paragraphs: list[str], *, language: str) -> str:
    """
    An article's body, joined by whichever rule suits its script.

    One call site per source, so a publisher's language is declared once in
    `sources/__init__.py` and nothing downstream has to guess. `mixed` takes the
    Bangla rule: a mixed document is a Bangla document with English in it, and the
    script filter is the stronger of the two signals.
    """
    return latin_paragraphs(paragraphs) if language == "en" else bangla_paragraphs(paragraphs)


