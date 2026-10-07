"""
The publishers the Live Risk Agent reads. DEMO_PLAN.md D04.

Chosen on 2026-10-08 from the ten channels in `top_10_bangladesh_news_channels.md`,
by checking each one's robots.txt, whether it publishes a machine-readable list of
today's articles, and whether the article text is in the HTML:

    Ekattor TV, Independent TV   robots allow; Google News sitemap with headline and
                                 time; body server-rendered          → news_sitemap.py
    Channel 24                   robots allow; daily sitemap, 180+ articles a day,
                                 a Dhaka (`capital`) section; body rendered by
                                 JavaScript                          → channel24.py
    ATN News, News24             listing available, body JavaScript-only. Candidates
                                 for a fourth source on the Playwright path.
    NTV                          RSS stale since January 2025
    Somoy TV, DBC News           no sitemap or RSS found
    Jamuna TV                    403 on robots.txt itself — it does not want crawlers
    RTV                          did not respond

Adding a publisher is one module in this package (or one instance below, if it runs
on a CMS already here) and one line in `SOURCES`.
"""

from __future__ import annotations

from typing import Final

from app.ingestion.sources.base import ArticleRef, Source
from app.ingestion.sources.channel24 import Channel24Source
from app.ingestion.sources.news_sitemap import NewsSitemapSource

SOURCES: Final[tuple[Source, ...]] = (
    NewsSitemapSource(
        source_id="ekattor_tv",
        name="Ekattor TV",
        sitemap_url="https://ekattor.tv/news-sitemap.xml",
    ),
    NewsSitemapSource(
        source_id="independent_tv",
        name="Independent TV",
        sitemap_url="https://www.itvbd.com/news-sitemap.xml",
    ),
    Channel24Source(),
)

__all__ = ["SOURCES", "ArticleRef", "Source"]
