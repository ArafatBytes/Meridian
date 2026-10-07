"""
Channel 24 — a JavaScript-rendered site, read with Playwright. DEMO_PLAN.md D04.

Two things differ from the news-sitemap publishers, both checked on 2026-10-08:

* **The listing is a daily sitemap** (`/sitemap/sitemap-daily-YYYY-MM-DD.xml`, by
  Dhaka date) with no headline field. The headline is in the URL instead — the last
  path segment is the Bangla title, hyphenated — which is enough for the relevance
  filter. The page `<title>` replaces it once fetched.
* **The article body is rendered client-side.** The static HTML is an 11 KB shell
  with the headline in `<title>` and the lead paragraph in
  `<meta name="description">`. The full body appears in
  `div.details-content-items p` only after the page's JavaScript runs.

So `read()` renders with Playwright, and if that fails — browser not installed,
timeout — it falls back to the static shell's headline plus lead paragraph. The lead
is a news lead: it usually names the event and the place, which is most of what
extraction needs. A thinner document beats a missing one.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from urllib.parse import unquote

from bs4 import BeautifulSoup

from app.contracts.risk import RawDocument
from app.ingestion.fetcher import Fetcher
from app.ingestion.sources.base import (
    DHAKA_TZ,
    ArticleRef,
    Source,
    bangla_paragraphs,
    parse_time,
    sitemap_entries,
)
from app.ingestion.store import canonical_url, doc_id_for

logger = logging.getLogger(__name__)

BODY_SELECTOR = "div.details-content-items p"


def title_from_url(url: str) -> str:
    """`.../article/351544/রাজধানীর-কড়াইল-বস্তিতে-...` → `রাজধানীর কড়াইল বস্তিতে ...`."""
    return unquote(url.rstrip("/").rsplit("/", 1)[-1]).replace("-", " ").strip()


class Channel24Source(Source):
    source_id = "channel24"
    name = "Channel 24"
    base_url = "https://www.channel24bd.tv"

    async def list_recent(self, fetcher: Fetcher, now: datetime) -> list[ArticleRef]:
        # Today's sitemap, and yesterday's: just after midnight in Dhaka today's is
        # nearly empty and the evening's news is all in yesterday's.
        today = now.astimezone(DHAKA_TZ).date()
        refs: list[ArticleRef] = []
        for day in (today, today - timedelta(days=1)):
            xml = await fetcher.text(f"{self.base_url}/sitemap/sitemap-daily-{day.isoformat()}.xml")
            refs += [
                ArticleRef(
                    url=canonical_url(entry["loc"]),
                    title=title_from_url(entry["loc"]),
                    published_at=parse_time(entry.get("lastmod")),
                )
                for entry in sitemap_entries(xml)
            ]
        return refs

    async def read(self, fetcher: Fetcher, ref: ArticleRef, now: datetime) -> RawDocument | None:
        try:
            soup = BeautifulSoup(await fetcher.rendered(ref.url, wait_for=BODY_SELECTOR), "lxml")
            body = bangla_paragraphs([p.get_text(" ") for p in soup.select(BODY_SELECTOR)])
        except Exception as problem:  # noqa: BLE001 - any render failure takes the fallback
            logger.warning(
                "channel24 render failed for %s (%s); using the static lead", ref.url, problem
            )
            soup = BeautifulSoup(await fetcher.text(ref.url), "lxml")
            lead = soup.find("meta", attrs={"name": "description"})
            body = bangla_paragraphs([str(lead.get("content", ""))]) if lead else ""
        if not body:
            return None
        page_title = soup.title.get_text(strip=True) if soup.title else ""
        return RawDocument(
            doc_id=doc_id_for(ref.url),
            source_id=self.source_id,
            url=ref.url,
            fetched_at=now,
            published_at=ref.published_at,
            language="bn",
            title=page_title or ref.title,
            body=body,
        )
