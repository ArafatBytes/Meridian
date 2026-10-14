"""
Publishers with a Google News sitemap and server-rendered article bodies.

Ekattor TV and Independent TV run on the same CMS — identical robots.txt, the same
`news-sitemap.xml`, and the body in `div.jw_article_body` on both (checked
2026-10-08). So this is one parser and two instances in `sources/__init__.py`; a
third site on the same CMS is one more line there.

The sitemap gives headline and publication time for free, which is what the agent's
relevance filter runs on before a single article page is fetched.

Two parameters make this the general case rather than a one-CMS parser, and both
were added on 2026-10-14 when Prothom Alo and Dhaka Tribune joined:

* `body_selector`, because the article body is in a different div on every CMS —
  `div.story-element-text p` on Prothom Alo, `article p` on Dhaka Tribune.
* `language`, because it decides which paragraph rule applies **and** what goes in
  `raw_documents.language`. Dhaka Tribune publishes in English, and the Bangla rule
  would have filtered its entire body away on the grounds that it contains no
  Bangla — a source that fetched correctly, parsed correctly, and stored nothing.
"""

from __future__ import annotations

from datetime import datetime

from bs4 import BeautifulSoup

from app.contracts.risk import RawDocument
from app.ingestion.fetcher import Fetcher
from app.ingestion.sources.base import (
    ArticleRef,
    Source,
    article_body,
    parse_time,
    sitemap_entries,
)
from app.ingestion.store import canonical_url, doc_id_for


class NewsSitemapSource(Source):
    def __init__(
        self,
        *,
        source_id: str,
        name: str,
        sitemap_url: str,
        body_selector: str = "div.jw_article_body p",
        language: str = "bn",
    ) -> None:
        self.source_id = source_id
        self.name = name
        self.sitemap_url = sitemap_url
        self.body_selector = body_selector
        self.language = language

    async def list_recent(self, fetcher: Fetcher, now: datetime) -> list[ArticleRef]:
        return [
            ArticleRef(
                url=canonical_url(entry["loc"]),
                title=entry.get("title", ""),
                published_at=parse_time(entry.get("publication_date")),
            )
            for entry in sitemap_entries(await fetcher.text(self.sitemap_url))
        ]

    async def read(self, fetcher: Fetcher, ref: ArticleRef, now: datetime) -> RawDocument | None:
        soup = BeautifulSoup(await fetcher.text(ref.url), "lxml")
        paragraphs = [p.get_text(" ") for p in soup.select(self.body_selector)]
        body = article_body(paragraphs, language=self.language)
        if not body:
            return None
        heading = soup.find("h1")
        return RawDocument(
            doc_id=doc_id_for(ref.url),
            source_id=self.source_id,
            url=ref.url,
            fetched_at=now,
            published_at=ref.published_at,
            language=self.language,
            title=ref.title or (heading.get_text(strip=True) if heading else ""),
            body=body,
        )
