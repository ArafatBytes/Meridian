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

---

## The 2026-10-14 expansion: three newspapers

The three sources above are all **television channels**, and that was a quiet
weakness rather than a neutral fact. `status = 'confirmed'` requires two or more
*independent* publishers (`policy/independence.py`), and TV newsrooms in Dhaka
follow each other and run the same agency copy — so a surface built on three of
them corroborates less often, and less honestly, than its source count suggests.
Newspapers are a genuinely different newsroom, and two of these three publish in
English, which is a second kind of independence: a different desk writing the same
event in different words is exactly the signal Rumour Guard's embedding gate reads.

Sixteen candidates were checked the same way as the originals — robots.txt, a
machine-readable listing of *recent* articles, and whether the body is in the HTML.
Six were added:

    Prothom Alo      news_sitemap.xml, ~590 articles with news:title and
                     news:publication_date; body in div.story-element-text   (bn)
    Jugantor         news_sitemap.xml, ~500 articles; body in
                     div.desktopDetailBody — NOT `main p`, which also picks up
                     the print header, three ad slots and the share buttons  (bn)
    Bangla Tribune   news-sitemap.xml, ~440 articles; div.jw_article_body    (bn)
    Ittefaq          news-sitemap.xml, ~374 articles; div.jw_article_body    (bn)
    Samakal          news_sitemap.xml, ~239 articles, has a `capital` desk;
                     body in div.dNewsDesc                                   (bn)
    Dhaka Tribune    news-sitemap.xml (hyphen, not underscore), ~158 articles;
                     body in article p                                       (en)

Ittefaq and Bangla Tribune turned out to run the same CMS as Ekattor and
Independent — `div.jw_article_body` — so they are instances, not modules, which is
what that parser was built for.

Ten were rejected, and the reasons are kept because the next person to go looking
will otherwise spend the afternoon rediscovering them:

    The Daily Star   Its RSS looks alive and is not. `lastBuildDate` is today's
                     date on every feed while every <item> in /city/rss.xml and
                     /bangladesh/rss.xml is from 2022, and the main /rss.xml is
                     four months stale. The titles are also markup — <title> wraps
                     an <a>, so a naive text read returns ''. The only current
                     listing is sitemaps/2026/sitemap-2026-1.xml: 44,288 URLs and
                     7.9 MB, with no headlines, refreshed in place. Polling that
                     every run is ~760 MB a day of someone else's bandwidth for
                     ~50 new articles, which `fetcher.py`'s politeness rules exist
                     to prevent. Reachable only with a slug-title parser like
                     Channel 24's; left out rather than built on a 7.9 MB poll.
    bdnews24         sitemap/sitemap-news.xml, news-sitemap.xml and
                     sitemap/sitemap-google-news.xml all answer 200 with the
                     client-side app shell and zero <loc> elements — soft 404s.
                     sitemap-section.xml lists sections, not articles.
    TBS News         news-sitemap.xml 502; rss.xml alive but newest item 2021.
    New Age          522 from Cloudflare on every path tried.
    Bangladesh       4xx on robots.txt itself, which `fetcher.py` reads as
    Pratidin         "disallow everything" — the same answer Jamuna TV gives.
    risingbd         4xx on robots.txt itself.
    Daily Sun        403 on the sitemap.
    Observer BD      404 on the sitemap.
    Kaler Kantho,    robots allow, but no news sitemap at any of the four
    banglanews24,    conventional paths. Candidates for a listing-discovery pass,
    jagonews24,      not for guesswork.
    Dhaka Post

Why the English paper was worth having, and not an assumption: of the 1022 entries
in `data/gazetteer/dhaka_central.json`, **1010 (98.8%) carry a `name_en`** and 816
(79.8%) carry a `name_bn`. Romanised place names resolve *better* than Bangla ones,
because `name:en` is the field OSM contributors filled in most completely for
Dhaka. Checked end to end on 2026-10-14: `the capital's Shahbagh intersection area`
resolves to `Shahbagh intersection` at confidence 1.00, and `Nowhere-at-all 99` is
still refused.

Why gazetteer coverage made the English papers worth having, and is not an
assumption: of the 1022 entries in `data/gazetteer/dhaka_central.json`, **1010
(98.8%) carry a `name_en`** and 816 (79.8%) carry a `name_bn`. Romanised place
names resolve *better* than Bangla ones, because `name:en` is the field OSM
contributors filled in most completely for Dhaka. Measured 2026-10-14.
"""

from __future__ import annotations

from typing import Final

from app.ingestion.sources.base import ArticleRef, Source
from app.ingestion.sources.channel24 import Channel24Source
from app.ingestion.sources.dmp_news import DmpNewsSource
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
    NewsSitemapSource(
        source_id="prothom_alo",
        name="Prothom Alo",
        sitemap_url="https://www.prothomalo.com/news_sitemap.xml",
        body_selector="div.story-element-text p",
        language="bn",
    ),
    NewsSitemapSource(
        source_id="jugantor",
        name="Jugantor",
        sitemap_url="https://www.jugantor.com/news_sitemap.xml",
        body_selector="div.desktopDetailBody p",
        language="bn",
    ),
    NewsSitemapSource(
        source_id="samakal",
        name="Samakal",
        sitemap_url="https://samakal.com/news_sitemap.xml",
        body_selector="div.dNewsDesc p",
        language="bn",
    ),
    NewsSitemapSource(
        source_id="ittefaq",
        name="Ittefaq",
        sitemap_url="https://www.ittefaq.com.bd/news-sitemap.xml",
        language="bn",
    ),
    NewsSitemapSource(
        source_id="bangla_tribune",
        name="Bangla Tribune",
        sitemap_url="https://www.banglatribune.com/news-sitemap.xml",
        language="bn",
    ),
    NewsSitemapSource(
        source_id="dhaka_tribune",
        name="Dhaka Tribune",
        sitemap_url="https://www.dhakatribune.com/news-sitemap.xml",
        body_selector="article p",
        language="en",
    ),
    # B11a, 2026-10-15. Last on purpose, for the same reason the harvest layers
    # are ordered: this is the newest and least proven source, and `live_risk`
    # ingests in this order, so a slow or broken institutional feed costs the
    # eight established publishers nothing.
    #
    # **Not a newspaper, and `app/policy/independence.py` knows it.** DMP is
    # registered as authoritative, so one of its reports can reach `confirmed`
    # alone. See that module for who decided that and what it costs.
    DmpNewsSource(),
)

def publisher_name(source_id: str) -> str:
    """
    The masthead as a reader knows it, for anything that cites a publisher.

    Lives here rather than in the agent that first needed it, because the route
    service cites publishers too and importing `agents/live_risk.py` to get a
    string would drag the LLM client, the fetcher and both corroboration guards
    into a request path that needs none of them.

    Falls back to the id with its separators tidied. That fallback matters: a
    statement with no publisher in it is refused by
    `app/policy/attribution.py::assert_attribution_safe`, and an outlet missing
    from `SOURCES` — one removed after rows citing it were written — must never be
    the reason a real report cannot be published.

    >>> publisher_name("prothom_alo")
    'Prothom Alo'
    >>> publisher_name("some_old_outlet")
    'Some Old Outlet'
    """
    for source in SOURCES:
        if source.source_id == source_id:
            return source.name
    return source_id.replace("_", " ").title()


__all__ = ["SOURCES", "ArticleRef", "Source", "publisher_name"]
