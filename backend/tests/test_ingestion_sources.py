"""
Source parsing against the real formats, checked against the live sites on 2026-10-08.
Inline samples, so the tests need no network and break loudly if a parser regresses.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.ingestion.sources.base import ArticleRef, bangla_paragraphs, parse_time, sitemap_entries
from app.ingestion.sources.channel24 import title_from_url
from app.ingestion.store import canonical_url, content_hash, doc_id_for

GOOGLE_NEWS_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
<url><loc>https://ekattor.tv/capital/95968/%E0%A6%AC%E0%A6%BF</loc>
<news:news><news:publication><news:name>একাত্তর</news:name><news:language>bn</news:language></news:publication>
<news:publication_date>2026-10-07T23:51:56+06:00</news:publication_date>
<news:title>বিমানবন্দরে একাধিক প্রতিষ্ঠানকে জরিমানা</news:title></news:news></url>
</urlset>"""

DAILY_SITEMAP = """<urlset xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"
        xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url>
    <loc>https://www.channel24bd.tv/capital/article/351544/রাজধানীর-কড়াইল-বস্তিতে-অভিযান </loc>
    <image:image><image:loc>https://backoffice.channel24bd.tv/x.jpg</image:loc></image:image>
    <changefreq>hourly</changefreq>
    <lastmod>2026-10-07T18:11:39.000Z</lastmod>
</url>
</urlset>"""


def test_a_google_news_sitemap_yields_url_title_and_time() -> None:
    [entry] = sitemap_entries(GOOGLE_NEWS_SITEMAP)
    assert entry["loc"].startswith("https://ekattor.tv/capital/")
    assert entry["title"] == "বিমানবন্দরে একাধিক প্রতিষ্ঠানকে জরিমানা"
    assert parse_time(entry["publication_date"]) == datetime(2026, 10, 7, 17, 51, 56, tzinfo=UTC)


def test_an_image_caption_is_not_read_as_the_headline() -> None:
    """Independent TV lists image:title before news:title. The caption must lose."""
    xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
    <url><loc>https://www.itvbd.com/national/1/x</loc>
      <image:image><image:loc>https://x/y.jpg</image:loc><image:title>হাইকোর্ট। ফাইল ছবি</image:title></image:image>
      <news:news><news:title>মিরপুরে বাসে আগুন</news:title></news:news></url>
    </urlset>"""
    [entry] = sitemap_entries(xml)
    assert entry["title"] == "মিরপুরে বাসে আগুন"
    assert entry["loc"] == "https://www.itvbd.com/national/1/x"


def test_a_daily_sitemap_yields_the_article_url_not_the_image_url() -> None:
    [entry] = sitemap_entries(DAILY_SITEMAP)
    assert "/article/351544/" in entry["loc"]
    assert parse_time(entry["lastmod"]) == datetime(2026, 10, 7, 18, 11, 39, tzinfo=UTC)


def test_channel24_headline_comes_from_the_url() -> None:
    [entry] = sitemap_entries(DAILY_SITEMAP)
    assert title_from_url(entry["loc"]) == "রাজধানীর কড়াইল বস্তিতে অভিযান"


def test_raw_and_encoded_forms_of_one_url_are_one_document() -> None:
    raw = "https://www.channel24bd.tv/capital/article/351544/রাজধানীর-কড়াইল "
    encoded = canonical_url(raw)
    assert encoded == canonical_url(encoded)
    assert doc_id_for(raw) == doc_id_for(encoded)
    assert " " not in encoded and "রা" not in encoded


def test_query_strings_do_not_make_a_new_document() -> None:
    assert doc_id_for("https://ekattor.tv/capital/1/x?utm=a") == doc_id_for(
        "https://ekattor.tv/capital/1/x"
    )


def test_layout_whitespace_does_not_change_the_content_hash() -> None:
    assert content_hash("এক  দুই\n\nতিন") == content_hash("এক দুই তিন")


def test_body_keeps_bangla_paragraphs_and_drops_empty_and_latin_only_ones() -> None:
    body = bangla_paragraphs(["  মিরপুরে   বাসে আগুন।  ", "", "Photo: Channel 24", "সড়ক বন্ধ।"])
    assert body == "মিরপুরে বাসে আগুন।\n\nসড়ক বন্ধ।"


def test_the_section_is_the_first_path_segment() -> None:
    assert (
        ArticleRef(
            url="https://www.itvbd.com/country/chittagong/1/x", title="", published_at=None
        ).section
        == "country"
    )
    assert (
        ArticleRef(url="https://ekattor.tv/capital/1/x", title="", published_at=None).section
        == "capital"
    )
